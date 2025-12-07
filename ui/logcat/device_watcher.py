"""Device state watcher for logcat viewer.

Monitors device connectivity and emits signals when the watched device
connects or disconnects, enabling graceful handling of device changes.
"""

from typing import Optional, TYPE_CHECKING
import logging

from PyQt6.QtCore import QObject, pyqtSignal

if TYPE_CHECKING:
    from ui.device_manager import DeviceManager
    from utils.adb_models import DeviceInfo

logger = logging.getLogger(__name__)


class DeviceWatcher(QObject):
    """Monitors device connectivity for a specific serial number.

    Emits device_disconnected when the watched device goes offline,
    and device_reconnected when it comes back online.

    Usage:
        watcher = DeviceWatcher(device_serial, device_manager, parent=self)
        watcher.device_disconnected.connect(self._on_device_disconnected)
    """

    device_disconnected = pyqtSignal(str)  # serial
    device_reconnected = pyqtSignal(str, object)  # serial, DeviceInfo

    def __init__(
        self,
        device_serial: str,
        device_manager: "DeviceManager",
        parent: Optional[QObject] = None,
    ) -> None:
        super().__init__(parent)
        self._serial = device_serial
        self._device_manager = device_manager
        self._is_connected = True
        self._connect_signals()

    def _connect_signals(self) -> None:
        """Connect to device manager signals."""
        try:
            self._device_manager.device_lost.connect(self._on_device_lost)
            self._device_manager.device_found.connect(self._on_device_found)
        except (AttributeError, RuntimeError) as exc:
            logger.warning("Failed to connect device manager signals: %s", exc)

    def _on_device_lost(self, serial: str) -> None:
        """Handle device disconnection."""
        if serial == self._serial and self._is_connected:
            self._is_connected = False
            logger.info("Watched device disconnected: %s", serial)
            self.device_disconnected.emit(serial)

    def _on_device_found(self, serial: str, device_info: "DeviceInfo") -> None:
        """Handle device reconnection."""
        if serial == self._serial and not self._is_connected:
            self._is_connected = True
            logger.info("Watched device reconnected: %s", serial)
            self.device_reconnected.emit(serial, device_info)

    def is_device_connected(self) -> bool:
        """Check current connection state from device manager."""
        return self._serial in getattr(self._device_manager, "device_dict", {})

    def cleanup(self) -> None:
        """Disconnect signals to prevent memory leaks."""
        if self._device_manager is None:
            return

        try:
            self._device_manager.device_lost.disconnect(self._on_device_lost)
        except (RuntimeError, TypeError, AttributeError) as exc:
            logger.debug("Signal disconnect skipped (device_lost): %s", exc)

        try:
            self._device_manager.device_found.disconnect(self._on_device_found)
        except (RuntimeError, TypeError, AttributeError) as exc:
            logger.debug("Signal disconnect skipped (device_found): %s", exc)

    @property
    def serial(self) -> str:
        """Get the watched device serial."""
        return self._serial

    @property
    def is_connected(self) -> bool:
        """Get cached connection state."""
        return self._is_connected
