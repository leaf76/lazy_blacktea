"""Status bar utilities for the Lazy Blacktea main window."""

from __future__ import annotations

from typing import Callable, Optional, TYPE_CHECKING

from PyQt6.QtWidgets import QProgressBar, QStatusBar

from utils import common

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
    ) -> None:
        self.window = window
        self._status_bar_factory = status_bar_factory or QStatusBar
        self._progress_bar_factory = progress_bar_factory or QProgressBar

    def create_status_bar(self) -> None:
        status_bar = self._status_bar_factory()
        progress_bar = self._progress_bar_factory()
        progress_bar.setVisible(False)

        self.window.setStatusBar(status_bar)
        status_bar.addPermanentWidget(progress_bar)

        self.window.status_bar = status_bar
        self.window.progress_bar = progress_bar

        self.show_message("Ready")
        logger.debug("Status bar and progress bar initialised")

    def show_message(self, message: str, timeout: int = 0) -> None:
        status_bar = getattr(self.window, "status_bar", None)
        if status_bar is not None:
            status_bar.showMessage(message, timeout)

    def update_progress(self, current: int, total: int, message: str) -> None:
        progress_bar = getattr(self.window, "progress_bar", None)
        if progress_bar is None:
            return

        maximum = total or 1
        progress_bar.setMaximum(maximum)
        progress_bar.setValue(max(0, min(current, maximum)))
        progress_bar.setVisible(True)

        self.show_message(message)

    def reset_progress(self) -> None:
        progress_bar = getattr(self.window, "progress_bar", None)
        if progress_bar is not None:
            progress_bar.setValue(0)
            progress_bar.setVisible(False)
        self.show_message("Ready")


__all__ = ["StatusBarManager"]
