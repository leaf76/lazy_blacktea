"""Application update dialog."""

from __future__ import annotations

import webbrowser
from pathlib import Path
from typing import Optional

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
)

from config.constants import ApplicationConstants
from utils.task_dispatcher import TaskContext, TaskHandle, get_task_dispatcher
from utils.update_service import UpdateError, UpdateInfo, UpdateService


class UpdateDialog(QDialog):
    """Dialog for checking, downloading, and opening verified app updates."""

    version_skipped = pyqtSignal(str)

    def __init__(
        self,
        *,
        update_service: Optional[UpdateService] = None,
        config_manager=None,
        current_version: Optional[str] = None,
        task_dispatcher=None,
        parent=None,
    ):
        super().__init__(parent)
        self.setWindowTitle("Check for Updates")
        self.setModal(False)
        self.setMinimumWidth(560)

        self._update_service = update_service or UpdateService(
            current_version=current_version or ApplicationConstants.APP_VERSION
        )
        self._config_manager = config_manager
        self._task_dispatcher = task_dispatcher or get_task_dispatcher()
        self._handles: list[TaskHandle] = []
        self._update_info: Optional[UpdateInfo] = None
        self._download_path: Optional[Path] = None

        self._build_ui(current_version or self._update_service.current_version)

    def _build_ui(self, current_version: str) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        title = QLabel("Application Updates")
        title.setObjectName("updateDialogTitle")
        title.setStyleSheet("font-size: 16px; font-weight: 600;")
        layout.addWidget(title)

        self.status_label = QLabel("Ready to check for updates.")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

        self.current_version_label = QLabel(f"Current version: {current_version}")
        self.latest_version_label = QLabel("Latest version: Not checked")
        self.asset_label = QLabel("Asset: Not selected")
        for label in (
            self.current_version_label,
            self.latest_version_label,
            self.asset_label,
        ):
            label.setWordWrap(True)
            layout.addWidget(label)

        self.release_notes = QPlainTextEdit()
        self.release_notes.setReadOnly(True)
        self.release_notes.setPlaceholderText("Release notes will appear here.")
        self.release_notes.setMaximumHeight(150)
        layout.addWidget(self.release_notes)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        action_row = QHBoxLayout()
        action_row.setSpacing(8)

        self.check_button = QPushButton("Check Again")
        self.check_button.clicked.connect(self.start_check)
        action_row.addWidget(self.check_button)

        self.download_button = QPushButton("Download")
        self.download_button.setEnabled(False)
        self.download_button.clicked.connect(self.start_download)
        action_row.addWidget(self.download_button)

        self.open_download_button = QPushButton("Open Download")
        self.open_download_button.setEnabled(False)
        self.open_download_button.clicked.connect(self.open_downloaded_update)
        action_row.addWidget(self.open_download_button)

        self.open_release_button = QPushButton("Open Release")
        self.open_release_button.setEnabled(False)
        self.open_release_button.clicked.connect(self.open_release_page)
        action_row.addWidget(self.open_release_button)

        self.skip_button = QPushButton("Skip Version")
        self.skip_button.setEnabled(False)
        self.skip_button.clicked.connect(self.skip_current_version)
        action_row.addWidget(self.skip_button)

        action_row.addStretch(1)
        layout.addLayout(action_row)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def start_check(self) -> None:
        """Start a background update check."""

        self._set_busy("Checking for updates...")
        handle = self._task_dispatcher.submit(
            self._update_service.check_for_updates,
            context=TaskContext(name="check_for_updates", category="updates"),
        )
        self._track_handle(handle)
        handle.completed.connect(self.set_check_result)
        handle.failed.connect(self.set_error)

    def start_download(self) -> None:
        """Start a background verified download."""

        if self._update_info is None or self._update_info.asset is None:
            return
        self._set_busy("Downloading update...")
        self.download_button.setEnabled(False)
        destination = self._configured_download_dir()
        handle = self._task_dispatcher.submit(
            self._update_service.download_update,
            self._update_info,
            destination,
            context=TaskContext(name="download_update", category="updates"),
        )
        self._track_handle(handle)
        handle.progress.connect(self._on_download_progress)
        handle.completed.connect(self.set_download_result)
        handle.failed.connect(self.set_error)

    def set_check_result(self, update_info: UpdateInfo) -> None:
        """Render a completed update check."""

        self._update_info = update_info
        self._download_path = None
        self.progress_bar.setVisible(False)
        self.open_download_button.setEnabled(False)
        self.open_release_button.setEnabled(bool(update_info.release_url))
        self.latest_version_label.setText(f"Latest version: {update_info.latest_version}")
        self.release_notes.setPlainText(update_info.release_notes or "")

        if not update_info.is_update_available:
            self.status_label.setText("You are up to date.")
            self.asset_label.setText("Asset: Not needed")
            self.download_button.setEnabled(False)
            self.skip_button.setEnabled(False)
            return

        asset = update_info.asset
        if asset is None:
            self.status_label.setText("An update is available, but no compatible asset was found.")
            self.asset_label.setText("Asset: Not available")
            self.download_button.setEnabled(False)
            self.skip_button.setEnabled(True)
            return

        size_label = f"{asset.size:,} bytes" if asset.size else "unknown size"
        self.status_label.setText("Update available. Download requires checksum verification.")
        self.asset_label.setText(f"Asset: {asset.name} ({size_label})")
        self.download_button.setEnabled(True)
        self.skip_button.setEnabled(True)

    def set_error(self, exc: Exception) -> None:
        """Render an update check or download error."""

        self.progress_bar.setVisible(False)
        self.status_label.setText(str(exc) or "Update failed.")
        self.download_button.setEnabled(False)
        self.open_download_button.setEnabled(False)

    def set_download_result(self, path: Path | str) -> None:
        """Render a successful verified download."""

        self._download_path = Path(path)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(100)
        self.status_label.setText(f"Downloaded and verified: {self._download_path}")
        self.open_download_button.setEnabled(True)
        self.download_button.setEnabled(False)

    def open_release_page(self) -> None:
        """Open the GitHub Release page."""

        if self._update_info is not None and self._update_info.release_url:
            webbrowser.open(self._update_info.release_url)

    def open_downloaded_update(self) -> None:
        """Open the verified downloaded update asset."""

        if self._download_path is None:
            return
        try:
            self._update_service.open_downloaded_asset(self._download_path)
        except UpdateError as exc:
            self.set_error(exc)

    def skip_current_version(self) -> None:
        """Persist the currently displayed version as skipped."""

        if self._update_info is None or self._config_manager is None:
            return
        updater = getattr(self._config_manager, "update_update_settings", None)
        if callable(updater):
            updater(skipped_version=self._update_info.latest_version)
        self.status_label.setText(f"Skipped version {self._update_info.latest_version}.")
        self.download_button.setEnabled(False)
        self.skip_button.setEnabled(False)
        self.version_skipped.emit(self._update_info.latest_version)

    def _configured_download_dir(self) -> Optional[Path]:
        if self._config_manager is None:
            return None
        getter = getattr(self._config_manager, "get_update_settings", None)
        if not callable(getter):
            return None
        settings = getter()
        download_dir = str(getattr(settings, "download_dir", "") or "").strip()
        return Path(download_dir).expanduser() if download_dir else None

    def _set_busy(self, message: str) -> None:
        self.status_label.setText(message)
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)
        self.check_button.setEnabled(False)
        self.download_button.setEnabled(False)
        self.open_download_button.setEnabled(False)

    def _on_download_progress(self, value: int, label: str) -> None:
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(max(0, min(100, int(value))))
        self.status_label.setText(label)

    def _track_handle(self, handle: TaskHandle) -> None:
        self._handles.append(handle)

        def _cleanup() -> None:
            if handle in self._handles:
                self._handles.remove(handle)
            self.check_button.setEnabled(True)

        handle.finished.connect(_cleanup)

    def closeEvent(self, event) -> None:
        for handle in list(self._handles):
            handle.cancel()
        super().closeEvent(event)


__all__ = ["UpdateDialog"]
