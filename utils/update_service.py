"""Application update checking and verified download helpers."""

from __future__ import annotations

import hashlib
import json
import platform
import re
import shutil
import subprocess
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, Iterable, Optional

from utils import common


logger = common.get_logger("update_service")

GITHUB_LATEST_RELEASE_URL = (
    "https://api.github.com/repos/leaf76/lazy_blacktea/releases/latest"
)
CHECKSUM_ASSET_NAMES = ("SHA256SUMS.txt", "checksums.txt", "sha256sums.txt")
STABLE_CHANNEL = "stable"
DOWNLOAD_CHUNK_SIZE = 1024 * 128
ALLOWED_UPDATE_HOSTS = {"api.github.com", "github.com"}


class UpdateError(Exception):
    """Base exception for updater failures."""


class UpdateNetworkError(UpdateError):
    """Raised when update metadata or assets cannot be fetched."""


class UpdateVerificationError(UpdateError):
    """Raised when release assets cannot be verified safely."""


class UnsupportedPlatformError(UpdateError):
    """Raised when no release asset supports the current platform."""


@dataclass
class UpdateAsset:
    """Release asset selected for this platform."""

    name: str
    download_url: str
    size: int = 0
    sha256: str = ""


@dataclass
class UpdateInfo:
    """Result of an update check."""

    current_version: str
    latest_version: str
    release_url: str
    published_at: str
    release_notes: str
    asset: Optional[UpdateAsset]
    is_update_available: bool


ProgressCallback = Callable[[int, str], None]


_VERSION_RE = re.compile(r"^\s*v?(\d+)\.(\d+)\.(\d+)")
_SHA256_RE = re.compile(r"^[a-fA-F0-9]{64}$")


def normalize_version(raw: object) -> Optional[str]:
    """Return ``major.minor.patch`` from a version string, or ``None``."""

    if raw is None:
        return None
    match = _VERSION_RE.match(str(raw).strip())
    if not match:
        return None
    return ".".join(match.groups())


def _version_tuple(raw: object) -> Optional[tuple[int, int, int]]:
    normalized = normalize_version(raw)
    if normalized is None:
        return None
    return tuple(int(part) for part in normalized.split("."))  # type: ignore[return-value]


def is_newer_version(latest: object, current: object) -> bool:
    """Return True when ``latest`` is newer than ``current``."""

    latest_tuple = _version_tuple(latest)
    current_tuple = _version_tuple(current)
    if latest_tuple is None or current_tuple is None:
        return False
    return latest_tuple > current_tuple


def parse_sha256_manifest(text: str) -> Dict[str, str]:
    """Parse common ``SHA256SUMS`` formats into ``filename -> sha256``."""

    checksums: Dict[str, str] = {}
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split(None, 1)
        if len(parts) != 2:
            continue
        digest, filename = parts
        filename = filename.strip()
        if filename.startswith("*"):
            filename = filename[1:]
        filename = Path(filename).name
        if _SHA256_RE.match(digest) and filename:
            checksums[filename] = digest.lower()
    return checksums


def _require_https_url(url: str) -> str:
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != "https" or not parsed.netloc:
        raise UpdateVerificationError("Update URLs must use HTTPS.")
    if parsed.hostname not in ALLOWED_UPDATE_HOSTS:
        raise UpdateVerificationError("Update URLs must point to GitHub Releases.")
    return url


def _asset_from_payload(payload: dict, sha256: str = "") -> UpdateAsset:
    name = str(payload.get("name") or "").strip()
    url = _require_https_url(str(payload.get("browser_download_url") or "").strip())
    try:
        size = int(payload.get("size") or 0)
    except (TypeError, ValueError):
        size = 0
    if not name:
        raise UpdateVerificationError("Release asset is missing a name.")
    return UpdateAsset(name=name, download_url=url, size=max(size, 0), sha256=sha256)


def _checksum_asset(assets: Iterable[dict]) -> Optional[dict]:
    for asset in assets:
        name = str(asset.get("name") or "")
        if name in CHECKSUM_ASSET_NAMES:
            return asset
    return None


def _normalise_machine(machine: str) -> str:
    value = machine.lower()
    if value in {"arm64", "aarch64"}:
        return "arm64"
    if value in {"x86_64", "amd64"}:
        return "x86_64"
    return value


def _asset_score(name: str, system: str, machine: str) -> int:
    lower = name.lower()
    arch = _normalise_machine(machine)
    if system == "Darwin":
        if name == f"LazyBlacktea-macos-{arch}.dmg":
            return 100
        if lower.endswith(".dmg") and "macos" in lower and arch in lower:
            return 90
        if lower.endswith(".dmg") and ("macos" in lower or "darwin" in lower):
            return 70
        return 0
    if system == "Linux":
        if name == "LazyBlacktea-x86_64.AppImage":
            return 100
        if lower.endswith(".appimage") and arch in lower:
            return 95
        if lower.endswith(".appimage"):
            return 85
        if name == "lazyblacktea-linux.tar.gz":
            return 80
        if lower.endswith(".tar.gz") and "linux" in lower:
            return 70
        return 0
    return 0


def select_platform_asset(
    assets: Iterable[dict],
    *,
    platform_system: Optional[str] = None,
    platform_machine: Optional[str] = None,
) -> UpdateAsset:
    """Select the best release asset for the current platform."""

    system = platform_system or platform.system()
    machine = platform_machine or platform.machine()
    scored: list[tuple[int, dict]] = []
    for asset in assets:
        name = str(asset.get("name") or "")
        if name in CHECKSUM_ASSET_NAMES:
            continue
        score = _asset_score(name, system, machine)
        if score:
            scored.append((score, asset))

    if not scored:
        raise UnsupportedPlatformError(f"No update asset supports {system} {machine}.")

    scored.sort(key=lambda item: item[0], reverse=True)
    return _asset_from_payload(scored[0][1])


class ReleaseClient:
    """Small GitHub Releases client using the standard library."""

    def __init__(self, latest_release_url: str = GITHUB_LATEST_RELEASE_URL, timeout: int = 20):
        self.latest_release_url = _require_https_url(latest_release_url)
        self.timeout = timeout

    def _open(self, url: str):
        request = urllib.request.Request(
            _require_https_url(url),
            headers={
                "Accept": "application/vnd.github+json",
                "User-Agent": "LazyBlacktea-Updater",
            },
        )
        return urllib.request.urlopen(request, timeout=self.timeout)

    def fetch_latest_release(self) -> dict:
        """Fetch the latest GitHub release JSON payload."""

        try:
            with self._open(self.latest_release_url) as response:
                payload = response.read().decode("utf-8")
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise UpdateNetworkError(f"Failed to fetch update metadata: {exc}") from exc
        try:
            data = json.loads(payload)
        except json.JSONDecodeError as exc:
            raise UpdateNetworkError("Update metadata response was not valid JSON.") from exc
        if not isinstance(data, dict):
            raise UpdateNetworkError("Update metadata response was not an object.")
        return data

    def fetch_text(self, url: str) -> str:
        """Fetch a small text asset such as ``SHA256SUMS.txt``."""

        try:
            with self._open(url) as response:
                return response.read().decode("utf-8")
        except (UnicodeDecodeError, urllib.error.URLError, TimeoutError, OSError) as exc:
            raise UpdateNetworkError(f"Failed to fetch update checksum manifest: {exc}") from exc

    def download_file(
        self,
        url: str,
        destination: Path,
        progress_callback: Optional[ProgressCallback] = None,
    ) -> Path:
        """Download an asset to ``destination``."""

        destination.parent.mkdir(parents=True, exist_ok=True)
        try:
            with self._open(url) as response:
                total = int(response.headers.get("Content-Length") or 0)
                written = 0
                with open(destination, "wb") as output:
                    while True:
                        chunk = response.read(DOWNLOAD_CHUNK_SIZE)
                        if not chunk:
                            break
                        output.write(chunk)
                        written += len(chunk)
                        if progress_callback is not None and total > 0:
                            percent = max(0, min(100, int(written * 100 / total)))
                            progress_callback(percent, "Downloading")
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise UpdateNetworkError(f"Failed to download update asset: {exc}") from exc

        if progress_callback is not None:
            progress_callback(100, "Downloaded")
        return destination


class UpdateService:
    """Coordinate update metadata checks, asset selection, and verification."""

    def __init__(
        self,
        *,
        current_version: str,
        release_client: Optional[ReleaseClient] = None,
        platform_system: Optional[str] = None,
        platform_machine: Optional[str] = None,
    ):
        self.current_version = normalize_version(current_version) or str(current_version)
        self.release_client = release_client or ReleaseClient()
        self.platform_system = platform_system
        self.platform_machine = platform_machine

    def check_for_updates(self) -> UpdateInfo:
        """Fetch latest release metadata and return a verified update result."""

        release = self.release_client.fetch_latest_release()
        latest_version = normalize_version(release.get("tag_name")) or self.current_version
        release_url = _require_https_url(str(release.get("html_url") or "https://github.com/leaf76/lazy_blacktea/releases"))
        release_notes = str(release.get("body") or "")
        published_at = str(release.get("published_at") or "")

        if bool(release.get("prerelease")):
            return UpdateInfo(
                current_version=self.current_version,
                latest_version=latest_version,
                release_url=release_url,
                published_at=published_at,
                release_notes=release_notes,
                asset=None,
                is_update_available=False,
            )

        if not is_newer_version(latest_version, self.current_version):
            return UpdateInfo(
                current_version=self.current_version,
                latest_version=latest_version,
                release_url=release_url,
                published_at=published_at,
                release_notes=release_notes,
                asset=None,
                is_update_available=False,
            )

        assets = release.get("assets") or []
        if not isinstance(assets, list):
            raise UpdateVerificationError("Release metadata assets are invalid.")

        asset = select_platform_asset(
            assets,
            platform_system=self.platform_system,
            platform_machine=self.platform_machine,
        )
        checksum_payload = _checksum_asset(assets)
        if checksum_payload is None:
            raise UpdateVerificationError("Release is missing SHA256SUMS.txt.")
        checksum_asset = _asset_from_payload(checksum_payload)
        checksums = parse_sha256_manifest(
            self.release_client.fetch_text(checksum_asset.download_url)
        )
        checksum = checksums.get(asset.name)
        if not checksum:
            raise UpdateVerificationError(f"Checksum is missing for {asset.name}.")
        asset.sha256 = checksum

        return UpdateInfo(
            current_version=self.current_version,
            latest_version=latest_version,
            release_url=release_url,
            published_at=published_at,
            release_notes=release_notes,
            asset=asset,
            is_update_available=True,
        )

    def download_update(
        self,
        update_info: UpdateInfo,
        destination_dir: Optional[Path | str] = None,
        progress_callback: Optional[ProgressCallback] = None,
    ) -> Path:
        """Download the selected update asset and verify its SHA256 digest."""

        if update_info.asset is None:
            raise UpdateError("No update asset is available for download.")
        if not update_info.asset.sha256:
            raise UpdateVerificationError("Update asset has no checksum.")

        destination_root = Path(destination_dir) if destination_dir else self.default_download_dir()
        destination_root.mkdir(parents=True, exist_ok=True)
        destination = destination_root / Path(update_info.asset.name).name
        partial = destination.with_name(f"{destination.name}.part")

        for stale_path in (partial, destination):
            if stale_path.exists():
                stale_path.unlink()

        self.release_client.download_file(
            update_info.asset.download_url,
            partial,
            progress_callback=progress_callback,
        )

        actual_sha = self._file_sha256(partial)
        if actual_sha.lower() != update_info.asset.sha256.lower():
            if partial.exists():
                partial.unlink()
            if destination.exists():
                destination.unlink()
            raise UpdateVerificationError("Downloaded update checksum did not match.")

        partial.replace(destination)
        if progress_callback is not None:
            progress_callback(100, "Verified")
        return destination

    @staticmethod
    def default_download_dir() -> Path:
        """Return a user-visible download directory with a temp fallback."""

        downloads = Path.home() / "Downloads"
        if downloads.exists():
            return downloads / "LazyBlackteaUpdates"
        return Path(tempfile.gettempdir()) / "LazyBlackteaUpdates"

    @staticmethod
    def _file_sha256(path: Path) -> str:
        digest = hashlib.sha256()
        with open(path, "rb") as input_file:
            for chunk in iter(lambda: input_file.read(DOWNLOAD_CHUNK_SIZE), b""):
                digest.update(chunk)
        return digest.hexdigest()

    @staticmethod
    def open_downloaded_asset(path: Path | str) -> None:
        """Open a verified downloaded asset or reveal it in the file manager."""

        target = Path(path)
        if not target.exists():
            raise UpdateError("Downloaded update file no longer exists.")

        system = platform.system()
        if system == "Darwin":
            command = ["open", str(target)]
        else:
            opener = shutil.which("xdg-open")
            if opener is None:
                raise UpdateError("No file opener is available on this platform.")
            command = [opener, str(target)]

        try:
            subprocess.Popen(command)
        except OSError as exc:
            raise UpdateError(f"Failed to open downloaded update: {exc}") from exc


__all__ = [
    "CHECKSUM_ASSET_NAMES",
    "GITHUB_LATEST_RELEASE_URL",
    "ALLOWED_UPDATE_HOSTS",
    "ReleaseClient",
    "UnsupportedPlatformError",
    "UpdateAsset",
    "UpdateError",
    "UpdateInfo",
    "UpdateNetworkError",
    "UpdateService",
    "UpdateVerificationError",
    "is_newer_version",
    "normalize_version",
    "parse_sha256_manifest",
    "select_platform_asset",
]
