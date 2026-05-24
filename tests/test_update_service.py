import hashlib
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _asset(name: str, url: str, size: int = 1234) -> dict:
    return {
        "name": name,
        "browser_download_url": url,
        "size": size,
    }


def _release(tag_name: str, assets: list[dict], prerelease: bool = False) -> dict:
    return {
        "tag_name": tag_name,
        "html_url": f"https://github.com/leaf76/lazy_blacktea/releases/tag/{tag_name}",
        "published_at": "2026-05-24T00:00:00Z",
        "body": "Release notes",
        "prerelease": prerelease,
        "assets": assets,
    }


class _FakeClient:
    def __init__(self, release_payload: dict, texts: dict[str, str] | None = None, data: bytes = b""):
        self.release_payload = release_payload
        self.texts = texts or {}
        self.data = data

    def fetch_latest_release(self) -> dict:
        return self.release_payload

    def fetch_text(self, url: str) -> str:
        return self.texts[url]

    def download_file(self, url: str, destination: Path, progress_callback=None) -> Path:
        destination.write_bytes(self.data)
        if progress_callback is not None:
            progress_callback(100, "Downloaded")
        return destination


class UpdateServiceTests(unittest.TestCase):
    def test_version_normalization_and_comparison(self):
        from utils.update_service import is_newer_version, normalize_version

        self.assertEqual(normalize_version(" v0.0.52 "), "0.0.52")
        self.assertEqual(normalize_version("0.0.52-beta.1"), "0.0.52")
        self.assertTrue(is_newer_version("v0.0.52", "0.0.51"))
        self.assertFalse(is_newer_version("v0.0.51", "0.0.51"))
        self.assertFalse(is_newer_version("v0.0.50", "0.0.51"))

    def test_sha256_manifest_parsing_accepts_common_formats(self):
        from utils.update_service import parse_sha256_manifest

        sha = "a" * 64
        parsed = parse_sha256_manifest(
            f"# generated\n{sha}  LazyBlacktea-macos-arm64.dmg\n{sha} *LazyBlacktea-x86_64.AppImage\n"
        )

        self.assertEqual(parsed["LazyBlacktea-macos-arm64.dmg"], sha)
        self.assertEqual(parsed["LazyBlacktea-x86_64.AppImage"], sha)

    def test_release_client_rejects_non_github_update_source(self):
        from utils.update_service import ReleaseClient, UpdateVerificationError

        with self.assertRaises(UpdateVerificationError):
            ReleaseClient("https://example.com/releases/latest")

    def test_check_for_updates_selects_macos_arm64_asset_and_checksum(self):
        from utils.update_service import UpdateService

        checksum_url = "https://github.com/leaf76/lazy_blacktea/releases/download/v0.0.52/SHA256SUMS.txt"
        asset_url = "https://github.com/leaf76/lazy_blacktea/releases/download/v0.0.52/LazyBlacktea-macos-arm64.dmg"
        sha = "b" * 64
        client = _FakeClient(
            _release(
                "v0.0.52",
                [
                    _asset("LazyBlacktea-macos-arm64.dmg", asset_url),
                    _asset("SHA256SUMS.txt", checksum_url),
                ],
            ),
            texts={checksum_url: f"{sha}  LazyBlacktea-macos-arm64.dmg\n"},
        )
        service = UpdateService(
            current_version="0.0.51",
            release_client=client,
            platform_system="Darwin",
            platform_machine="arm64",
        )

        info = service.check_for_updates()

        self.assertTrue(info.is_update_available)
        self.assertEqual(info.latest_version, "0.0.52")
        self.assertEqual(info.asset.name, "LazyBlacktea-macos-arm64.dmg")
        self.assertEqual(info.asset.sha256, sha)

    def test_check_for_updates_requires_checksum_manifest_for_new_release(self):
        from utils.update_service import UpdateService, UpdateVerificationError

        asset_url = "https://github.com/leaf76/lazy_blacktea/releases/download/v0.0.52/LazyBlacktea-macos-arm64.dmg"
        service = UpdateService(
            current_version="0.0.51",
            release_client=_FakeClient(
                _release("v0.0.52", [_asset("LazyBlacktea-macos-arm64.dmg", asset_url)])
            ),
            platform_system="Darwin",
            platform_machine="arm64",
        )

        with self.assertRaises(UpdateVerificationError):
            service.check_for_updates()

    def test_same_or_prerelease_release_is_not_reported_as_available(self):
        from utils.update_service import UpdateService

        client = _FakeClient(_release("v0.0.52-beta.1", [], prerelease=True))
        service = UpdateService(
            current_version="0.0.51",
            release_client=client,
            platform_system="Darwin",
            platform_machine="arm64",
        )

        info = service.check_for_updates()

        self.assertFalse(info.is_update_available)
        self.assertEqual(info.latest_version, "0.0.52")

    def test_download_update_verifies_checksum_and_removes_mismatch(self):
        from utils.update_service import UpdateAsset, UpdateInfo, UpdateService, UpdateVerificationError

        data = b"verified payload"
        good_sha = hashlib.sha256(data).hexdigest()
        bad_sha = "c" * 64
        asset = UpdateAsset(
            name="LazyBlacktea-macos-arm64.dmg",
            download_url="https://github.com/leaf76/lazy_blacktea/releases/download/v0.0.52/LazyBlacktea-macos-arm64.dmg",
            size=10,
            sha256=good_sha,
        )
        info = UpdateInfo(
            current_version="0.0.51",
            latest_version="0.0.52",
            release_url="https://github.com/leaf76/lazy_blacktea/releases/tag/v0.0.52",
            published_at="2026-05-24T00:00:00Z",
            release_notes="Release notes",
            asset=asset,
            is_update_available=True,
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            service = UpdateService(
                current_version="0.0.51",
                release_client=_FakeClient({}, data=data),
            )
            downloaded = service.download_update(info, Path(temp_dir))
            self.assertEqual(downloaded.read_bytes(), data)

            info.asset.sha256 = bad_sha
            with self.assertRaises(UpdateVerificationError):
                service.download_update(info, Path(temp_dir))
            self.assertFalse((Path(temp_dir) / info.asset.name).exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
