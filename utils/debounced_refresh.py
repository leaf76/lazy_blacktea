"""Debounced refresh utility for preventing excessive UI updates."""

from PyQt6.QtCore import QTimer, QObject, pyqtSignal
from typing import Callable
from utils import common


class DebouncedRefresh(QObject):
    """A utility class that debounces refresh requests to prevent excessive UI updates."""

    # Signal emitted when refresh is actually executed
    refresh_executed = pyqtSignal()

    def __init__(self, callback: Callable, delay_ms: int = 100, parent=None):
        """Initialize the debounced refresh utility.

        Args:
            callback: Function to call when refresh is triggered
            delay_ms: Delay in milliseconds before executing refresh
            parent: Parent QObject
        """
        super().__init__(parent)
        self.callback = callback
        self.delay_ms = delay_ms
        self.logger = common.get_logger('debounced_refresh')

        # Setup timer
        self.timer = QTimer()
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self._execute_refresh)

        # Track pending requests
        self.pending_count = 0

    def request_refresh(self) -> None:
        """Request a refresh. If already pending, restart the timer."""
        self.pending_count += 1

        # Stop existing timer if running
        if self.timer.isActive():
            self.timer.stop()
            self.logger.debug(f'Debounced refresh request #{self.pending_count} (restarting timer)')
        else:
            self.logger.debug(f'Debounced refresh request #{self.pending_count} (starting timer)')

        # Start/restart timer
        self.timer.start(self.delay_ms)

    def force_refresh(self) -> None:
        """Force immediate refresh, bypassing debounce timer."""
        self.timer.stop()
        self.pending_count += 1
        self.logger.debug(f'Force refresh request #{self.pending_count}')
        self._execute_refresh()

    def _execute_refresh(self) -> None:
        """Internal method to execute the actual refresh."""
        try:
            requests_processed = self.pending_count
            self.pending_count = 0

            self.logger.debug(f'Executing refresh (processed {requests_processed} requests)')

            # Execute the callback
            self.callback()

            # Emit signal
            self.refresh_executed.emit()

        except Exception as e:
            self.logger.error(f'Error during debounced refresh: {e}', exc_info=True)
