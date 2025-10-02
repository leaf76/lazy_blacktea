"""Manager responsible for browsing device file systems and triggering downloads."""

from __future__ import annotations

import os
import shutil
import threading
import time
from typing import Iterable

from PyQt6.QtCore import QObject, pyqtSignal

from utils import adb_models, adb_tools, common

logger = common.get_logger('device_file_browser_manager')


class DeviceFileBrowserManager(QObject):
    """Coordinates listing, downloading, and previewing files from Android devices."""

    directory_listing_ready = pyqtSignal(str, str, adb_models.DeviceDirectoryListing)
    download_completed = pyqtSignal(str, str, list, list)
    preview_ready = pyqtSignal(str, str, str)
    operation_failed = pyqtSignal(str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._lock = threading.Lock()
        self._preview_dirs: set[str] = set()
        self._preview_meta: dict[str, dict[str, float]] = {}

    # ------------------------------------------------------------------
    # Directory listing
    # ------------------------------------------------------------------
    def fetch_directory(self, serial: str, remote_path: str, *, use_thread: bool = True) -> None:
        """Fetch directory contents for the given device path."""
        if use_thread:
            threading.Thread(
                target=self._fetch_directory,
                args=(serial, remote_path),
                daemon=True,
                name=f'DeviceFileList-{serial}'
            ).start()
        else:
            self._fetch_directory(serial, remote_path)

    def _fetch_directory(self, serial: str, remote_path: str) -> None:
        try:
            listing = adb_tools.list_device_directory(serial, remote_path)
        except Exception as exc:  # pragma: no cover - guarded by tests
            logger.error('Failed to list %s:%s - %s', serial, remote_path, exc)
            self.operation_failed.emit(f'Failed to list {remote_path}: {exc}')
            return

        self.directory_listing_ready.emit(serial, listing.path, listing)

    # ------------------------------------------------------------------
    # Downloads
    # ------------------------------------------------------------------
    def download_paths(
        self,
        serial: str,
        remote_paths: Iterable[str],
        output_path: str,
        *,
        use_thread: bool = True,
    ) -> None:
        """Download the specified paths from the device to the given output directory."""
        remote_list = list(remote_paths)
        if not remote_list:
            logger.info('No paths requested for download for %s', serial)
            return

        if use_thread:
            threading.Thread(
                target=self._download_paths,
                args=(serial, remote_list, output_path),
                daemon=True,
                name=f'DeviceFilePull-{serial}'
            ).start()
        else:
            self._download_paths(serial, remote_list, output_path)

    def _download_paths(self, serial: str, remote_paths: list[str], output_path: str) -> None:
        try:
            results = adb_tools.pull_device_paths(serial, remote_paths, output_path)
        except Exception as exc:  # pragma: no cover - guarded by tests
            logger.error('Failed to download %s from %s - %s', remote_paths, serial, exc)
            self.operation_failed.emit(f'Failed to download files: {exc}')
            return

        self.download_completed.emit(serial, output_path, remote_paths, results)

    # ------------------------------------------------------------------
    # Preview
    # ------------------------------------------------------------------
    def preview_file(
        self,
        serial: str,
        remote_path: str,
        *,
        use_thread: bool = True,
    ) -> None:
        """Pull a remote file into a temporary directory for preview."""
        if use_thread:
            threading.Thread(
                target=self._preview_file,
                args=(serial, remote_path),
                daemon=True,
                name=f'DeviceFilePreview-{serial}'
            ).start()
        else:
            self._preview_file(serial, remote_path)

    def _preview_file(self, serial: str, remote_path: str) -> None:
        try:
            local_path = adb_tools.pull_device_file_preview(serial, remote_path)
        except Exception as exc:  # pragma: no cover - guarded by tests
            logger.error('Failed to prepare preview for %s:%s - %s', serial, remote_path, exc)
            self.operation_failed.emit(f'Failed to preview {remote_path}: {exc}')
            return

        preview_dir = os.path.dirname(local_path)
        if preview_dir:
            with self._lock:
                self._preview_dirs.add(preview_dir)
            self._register_preview_directory(preview_dir)
            logger.debug('Cached preview %s (%s)', local_path, preview_dir)
            self._enforce_cache_limits()

        self.preview_ready.emit(serial, remote_path, local_path)

    def cleanup_preview_cache(self) -> None:
        """Remove any temporary directories created for previews."""
        with self._lock:
            preview_dirs = list(self._preview_dirs)
            self._preview_dirs.clear()
            self._preview_meta = {}

        for directory in preview_dirs:
            self._remove_preview_directory(directory)

    def cleanup_preview_path(self, local_path: str) -> bool:
        """Remove a single preview directory associated with the provided file."""
        if not local_path:
            return False

        directory = os.path.dirname(local_path)
        if not directory:
            return False

        return self._remove_preview_directory(directory)

    def _register_preview_directory(self, directory: str) -> None:
        size = self._compute_directory_size(directory)
        with self._lock:
            self._preview_meta[directory] = {
                'size': float(size),
                'timestamp': time.time(),
            }

    def _enforce_cache_limits(self, *, max_total_bytes: float = 500 * 1024 * 1024, max_age_seconds: float = 3600.0) -> None:
        with self._lock:
            directories = list(self._preview_meta.items())

        now = time.time()
        for directory, meta in directories:
            if now - meta['timestamp'] > max_age_seconds:
                logger.debug('Removing stale preview cache %s', directory)
                self._remove_preview_directory(directory)

        with self._lock:
            directories = list(self._preview_meta.items())
            total_size = sum(meta['size'] for _, meta in directories)

        while total_size > max_total_bytes and directories:
            directories.sort(key=lambda item: item[1]['timestamp'])
            directory, meta = directories.pop(0)
            logger.debug(
                'Removing preview cache %s to enforce size limit (total %.2f MB)',
                directory,
                total_size / (1024 * 1024),
            )
            self._remove_preview_directory(directory)
            with self._lock:
                directories = list(self._preview_meta.items())
                total_size = sum(meta['size'] for _, meta in directories)

    def _compute_directory_size(self, directory: str) -> int:
        total = 0
        for root, _, files in os.walk(directory):
            for filename in files:
                path = os.path.join(root, filename)
                try:
                    total += os.path.getsize(path)
                except OSError:
                    pass
        return total

    def _remove_preview_directory(self, directory: str) -> bool:
        if not directory:
            return False

        with self._lock:
            self._preview_dirs.discard(directory)
            self._preview_meta.pop(directory, None)

        try:
            shutil.rmtree(directory, ignore_errors=True)
            logger.debug('Cleaned preview cache directory %s', directory)
            return True
        except Exception as exc:  # pragma: no cover - best-effort cleanup
            logger.error('Failed to remove preview directory %s: %s', directory, exc)
            return False


__all__ = ['DeviceFileBrowserManager']
