"""Status bar utilities for the Lazy Blacktea main window."""

from __future__ import annotations

from typing import Callable, Optional, TYPE_CHECKING

from PyQt6.QtWidgets import QLabel, QProgressBar, QStatusBar

from utils import common
from config.constants import ApplicationConstants

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
    ) -> None:
        self.window = window
        self._status_bar_factory = status_bar_factory or QStatusBar
        self._progress_bar_factory = progress_bar_factory or QProgressBar
        self._version_label_factory = version_label_factory or QLabel

    def create_status_bar(self) -> None:
        status_bar = self._status_bar_factory()
        version_label = self._create_version_label()
        progress_bar = self._progress_bar_factory()
        progress_bar.setVisible(False)

        self.window.setStatusBar(status_bar)
        status_bar.addPermanentWidget(version_label)
        status_bar.addPermanentWidget(progress_bar)

        self.window.status_bar = status_bar
        self.window.progress_bar = progress_bar
        self.window.version_label = version_label

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

    def show_message(self, message: str, timeout: int = 0) -> None:
        status_bar = getattr(self.window, "status_bar", None)
        if status_bar is not None:
            status_bar.showMessage(message, timeout)

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

    def reset_progress(self) -> None:
        progress_bar = getattr(self.window, "progress_bar", None)
        if progress_bar is not None:
            progress_bar.setValue(0)
            progress_bar.setVisible(False)
        self.show_message("Ready")


__all__ = ["StatusBarManager"]
