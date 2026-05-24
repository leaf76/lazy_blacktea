"""Status bar utilities for the Lazy Blacktea main window."""

from __future__ import annotations

from typing import Callable, Optional, TYPE_CHECKING

from PyQt6.QtWidgets import QLabel, QProgressBar, QStatusBar

from utils import common
from config.constants import ApplicationConstants
from ui.shell import StatusChipIntent

if TYPE_CHECKING:  # pragma: no cover
    from lazy_blacktea_pyqt import WindowMain


logger = common.get_logger("status_bar_manager")

StatusBarFactory = Callable[[], QStatusBar]
ProgressBarFactory = Callable[[], QProgressBar]


class StatusBarManager:
    """Create and manipulate the main window status bar and progress bar."""

    def __init__(
        self,
        window: "WindowMain",
        status_bar_factory: Optional[StatusBarFactory] = None,
        progress_bar_factory: Optional[ProgressBarFactory] = None,
        version_label_factory: Optional[Callable[[], QLabel]] = None,
        selection_mode_label_factory: Optional[Callable[[], QLabel]] = None,
    ) -> None:
        self.window = window
        self._status_bar_factory = status_bar_factory or QStatusBar
        self._progress_bar_factory = progress_bar_factory or QProgressBar
        self._version_label_factory = version_label_factory or QLabel
        self._selection_mode_label_factory = selection_mode_label_factory or QLabel

    def create_status_bar(self) -> None:
        status_bar = self._status_bar_factory()
        version_label = self._create_version_label()
        selection_label = self._create_selection_mode_label()
        progress_bar = self._progress_bar_factory()
        progress_bar.setVisible(False)

        self.window.setStatusBar(status_bar)
        status_bar.addPermanentWidget(selection_label)
        status_bar.addPermanentWidget(version_label)
        status_bar.addPermanentWidget(progress_bar)

        self.window.status_bar = status_bar
        self.window.progress_bar = progress_bar
        self.window.version_label = version_label
        self.window.selection_mode_status_label = selection_label

        shell_bar = self._shell_status_bar()
        if shell_bar is not None:
            if hasattr(status_bar, "hide"):
                status_bar.hide()
            self._upsert_shell_chip(
                "selection_mode", "Mode: Multi", intent=StatusChipIntent.NEUTRAL
            )
            self._upsert_shell_chip(
                "version",
                f"v{ApplicationConstants.APP_VERSION}",
                intent=StatusChipIntent.NEUTRAL,
                align="right",
            )
            self._upsert_shell_chip("status", "Ready", intent=StatusChipIntent.INFO)

        self.show_message("Ready")
        logger.debug("Status bar and progress bar initialised")

    def _create_version_label(self) -> QLabel:
        label = self._version_label_factory()
        version_text = f"{ApplicationConstants.APP_NAME} v{ApplicationConstants.APP_VERSION}"
        if hasattr(label, "setText"):
            label.setText(version_text)
        if hasattr(label, "setObjectName"):
            label.setObjectName("appVersionLabel")
        if hasattr(label, "setStyleSheet"):
            label.setStyleSheet("color: #6c6c6c; padding-right: 12px;")
        return label

    def _create_selection_mode_label(self) -> QLabel:
        label = self._selection_mode_label_factory()
        if hasattr(label, "setObjectName"):
            label.setObjectName("selectionModeLabel")
        if hasattr(label, "setStyleSheet"):
            label.setStyleSheet("color: #6c6c6c; padding-left: 8px; padding-right: 8px;")
        # Initial text will be set by update_selection_mode
        return label

    def update_selection_mode(self, single: bool) -> None:
        """Update the status bar label indicating selection mode."""
        label = getattr(self.window, "selection_mode_status_label", None)
        if label is None:
            return
        mode_text = "Single" if single else "Multi"
        if hasattr(label, "setText"):
            label.setText(f"Mode: {mode_text}")
        if hasattr(label, "setToolTip"):
            tip = (
                "Single-select: selecting a device replaces any previous selection"
                if single
                else "Multi-select: use checkboxes to select multiple devices"
            )
            label.setToolTip(tip)
        self._upsert_shell_chip(
            "selection_mode", f"Mode: {mode_text}", intent=StatusChipIntent.NEUTRAL
        )

    def show_message(self, message: str, timeout: int = 0) -> None:
        status_bar = getattr(self.window, "status_bar", None)
        if status_bar is not None:
            status_bar.showMessage(message, timeout)
        self._upsert_shell_chip("status", message or "Ready", intent=StatusChipIntent.INFO)

    def update_progress(self, current: int, total: int, message: str) -> None:
        progress_bar = getattr(self.window, "progress_bar", None)
        if progress_bar is None:
            return

        has_set_range = hasattr(progress_bar, "setRange")
        has_set_maximum = hasattr(progress_bar, "setMaximum")

        if total and total > 0:
            maximum = total
            if has_set_range:
                progress_bar.setRange(0, maximum)
            elif has_set_maximum:
                progress_bar.setMaximum(maximum)
            progress_bar.setValue(max(0, min(current, maximum)))
        else:
            # Unknown total - switch to busy indicator mode for visual feedback
            if has_set_range:
                progress_bar.setRange(0, 0)
            elif has_set_maximum:
                progress_bar.setMaximum(0)
            if hasattr(progress_bar, "setValue"):
                progress_bar.setValue(0)

        progress_bar.setVisible(True)

        self.show_message(message)
        label = f"{message} {current}/{total}" if total and total > 0 else message
        self._upsert_shell_chip("progress", label, intent=StatusChipIntent.INFO)

    def reset_progress(self) -> None:
        progress_bar = getattr(self.window, "progress_bar", None)
        if progress_bar is not None:
            progress_bar.setValue(0)
            progress_bar.setVisible(False)
        shell_bar = self._shell_status_bar()
        if shell_bar is not None:
            shell_bar.remove_chip("progress")
        self.show_message("Ready")

    def _shell_status_bar(self):
        shell = getattr(self.window, "app_shell", None)
        if shell is None:
            return None
        return shell.status_bar()

    def _upsert_shell_chip(
        self,
        name: str,
        label: str,
        *,
        intent: StatusChipIntent,
        align: str = "left",
    ) -> None:
        shell_bar = self._shell_status_bar()
        if shell_bar is None:
            return
        if shell_bar.has_chip(name):
            shell_bar.update_chip(name, label, intent=intent)
            return
        shell_bar.add_chip(name, label, intent=intent, align=align)


__all__ = ["StatusBarManager"]
