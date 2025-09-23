"""Debounced refresh utility for preventing excessive UI updates."""

from PyQt6.QtCore import QTimer, QObject, pyqtSignal
from typing import Callable, Optional
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

    def cancel_pending(self) -> None:
        """Cancel any pending refresh requests."""
        if self.timer.isActive():
            self.timer.stop()
            self.logger.debug(f'Cancelled pending refresh (had {self.pending_count} requests)')
            self.pending_count = 0

    def is_pending(self) -> bool:
        """Check if a refresh is currently pending."""
        return self.timer.isActive()

    def set_delay(self, delay_ms: int) -> None:
        """Update the debounce delay."""
        self.delay_ms = delay_ms
        self.logger.debug(f'Updated debounce delay to {delay_ms}ms')

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


class DeviceListDebouncedRefresh(DebouncedRefresh):
    """Specialized debounced refresh for device list updates."""

    def __init__(self, main_window, delay_ms: int = 100):
        """Initialize device list debounced refresh.

        Args:
            main_window: Reference to main window
            delay_ms: Delay in milliseconds before executing refresh
        """
        super().__init__(
            callback=lambda: main_window.refresh_device_list(),
            delay_ms=delay_ms,
            parent=main_window
        )
        self.main_window = main_window
        self.logger = common.get_logger('device_refresh')

    def request_refresh_with_reason(self, reason: str) -> None:
        """Request refresh with a specific reason for logging."""
        self.logger.debug(f'Device refresh requested: {reason}')
        self.request_refresh()


class RecordingStatusDebouncedRefresh(DebouncedRefresh):
    """Specialized debounced refresh for recording status updates."""

    def __init__(self, main_window, delay_ms: int = 500):
        """Initialize recording status debounced refresh.

        Args:
            main_window: Reference to main window
            delay_ms: Delay in milliseconds before executing refresh
        """
        super().__init__(
            callback=lambda: main_window.update_recording_status(),
            delay_ms=delay_ms,
            parent=main_window
        )
        self.main_window = main_window
        self.logger = common.get_logger('recording_status_refresh')


def create_debounced_timer(callback: Callable, delay_ms: int = 100,
                          parent: Optional[QObject] = None) -> QTimer:
    """Create a simple debounced timer for one-off use.

    Args:
        callback: Function to call when timer expires
        delay_ms: Delay in milliseconds
        parent: Parent QObject

    Returns:
        Configured QTimer instance
    """
    timer = QTimer(parent)
    timer.setSingleShot(True)
    timer.timeout.connect(callback)
    return timer


class BatchedUIUpdater(QObject):
    """Utility for batching UI updates to improve performance."""

    def __init__(self, widget, parent=None):
        """Initialize batched UI updater.

        Args:
            widget: Widget to batch updates for
            parent: Parent QObject
        """
        super().__init__(parent)
        self.widget = widget
        self.logger = common.get_logger('batched_ui_updater')
        self._updates_enabled = True

    def __enter__(self):
        """Enter context manager - disable updates."""
        if self._updates_enabled and hasattr(self.widget, 'setUpdatesEnabled'):
            self.widget.setUpdatesEnabled(False)
            self._updates_enabled = False
            self.logger.debug(f'Disabled updates for {self.widget.__class__.__name__}')
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit context manager - re-enable updates."""
        if not self._updates_enabled and hasattr(self.widget, 'setUpdatesEnabled'):
            self.widget.setUpdatesEnabled(True)
            self._updates_enabled = True
            self.logger.debug(f'Re-enabled updates for {self.widget.__class__.__name__}')


class PerformanceOptimizedRefresh(QObject):
    """Advanced refresh utility with performance monitoring."""

    def __init__(self, name: str, callback: Callable, parent=None):
        """Initialize performance optimized refresh.

        Args:
            name: Name for logging/debugging
            callback: Function to call
            parent: Parent QObject
        """
        super().__init__(parent)
        self.name = name
        self.callback = callback
        self.logger = common.get_logger('perf_refresh')

        # Performance tracking
        self.call_count = 0
        self.total_time = 0.0
        self.max_time = 0.0
        self.min_time = float('inf')

    def execute_with_timing(self) -> float:
        """Execute callback with performance timing.

        Returns:
            Execution time in milliseconds
        """
        import time

        start_time = time.perf_counter()
        try:
            self.callback()
        except Exception as e:
            self.logger.error(f'Error in {self.name}: {e}', exc_info=True)
            raise
        finally:
            end_time = time.perf_counter()

        execution_time = (end_time - start_time) * 1000  # Convert to milliseconds

        # Update statistics
        self.call_count += 1
        self.total_time += execution_time
        self.max_time = max(self.max_time, execution_time)
        self.min_time = min(self.min_time, execution_time)

        # Log performance data
        avg_time = self.total_time / self.call_count
        self.logger.debug(
            f'{self.name} executed in {execution_time:.2f}ms '
            f'(avg: {avg_time:.2f}ms, min: {self.min_time:.2f}ms, max: {self.max_time:.2f}ms, '
            f'calls: {self.call_count})'
        )

        return execution_time

    def get_performance_stats(self) -> dict:
        """Get performance statistics.

        Returns:
            Dictionary with performance metrics
        """
        if self.call_count == 0:
            return {'calls': 0, 'avg_time': 0, 'min_time': 0, 'max_time': 0, 'total_time': 0}

        return {
            'calls': self.call_count,
            'avg_time': self.total_time / self.call_count,
            'min_time': self.min_time,
            'max_time': self.max_time,
            'total_time': self.total_time
        }

    def reset_stats(self) -> None:
        """Reset performance statistics."""
        self.call_count = 0
        self.total_time = 0.0
        self.max_time = 0.0
        self.min_time = float('inf')
        self.logger.debug(f'Reset performance stats for {self.name}')