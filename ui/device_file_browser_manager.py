"""Manager responsible for browsing device file systems and triggering downloads."""

from __future__ import annotations

import threading
from typing import Iterable

from PyQt6.QtCore import QObject, pyqtSignal

from utils import adb_models, adb_tools, common

logger = common.get_logger('device_file_browser_manager')


class DeviceFileBrowserManager(QObject):
    """Coordinates listing and downloading files from Android devices."""

    directory_listing_ready = pyqtSignal(str, str, adb_models.DeviceDirectoryListing)
    download_completed = pyqtSignal(str, str, list, list)
    operation_failed = pyqtSignal(str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._lock = threading.Lock()

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


__all__ = ['DeviceFileBrowserManager']
