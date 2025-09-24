"""Device management module for handling ADB device operations."""

import logging
import time
import hashlib
from typing import Dict, List
from PyQt6.QtWidgets import QCheckBox, QLabel
from PyQt6.QtCore import QThread, pyqtSignal, QMutex, QMutexLocker

from utils import adb_models, adb_tools, common

logger = common.get_logger('device_manager')

# Configuration constants
class DeviceManagerConfig:
    DEFAULT_CACHE_TTL = 3.0
    DEFAULT_REFRESH_INTERVAL = 3
    SHUTDOWN_TIMEOUT = 300  # milliseconds
    ERROR_RETRY_DELAY = 5000  # milliseconds
    PROGRESSIVE_DELAY = 100  # milliseconds
    FULL_UPDATE_INTERVAL = 10  # seconds

class DeviceCache:
    """Manages device information caching to reduce ADB calls."""

    def __init__(self, cache_ttl: float = DeviceManagerConfig.DEFAULT_CACHE_TTL):
        self.devices: Dict[str, adb_models.DeviceInfo] = {}
        self.last_update = 0
        self.cache_ttl = cache_ttl
        self.last_hash = ''

    def get_devices(self) -> List[adb_models.DeviceInfo]:
        """Get devices with caching."""
        current_time = time.time()

        # Check if cache is still valid
        if (current_time - self.last_update) < self.cache_ttl:
            logger.debug('Using cached device list')
            return list(self.devices.values())

        return self._refresh_cache()

    def _refresh_cache(self) -> List[adb_models.DeviceInfo]:
        """Refresh the device cache."""
        try:
            devices = adb_tools.get_devices_list()
            current_hash = self._calculate_hash(devices)

            # Only update cache if devices actually changed
            if current_hash != self.last_hash or devices:
                self.devices = {d.device_serial_num: d for d in devices}
                self.last_update = time.time()
                self.last_hash = current_hash
                logger.debug(f'Updated device cache with {len(devices)} devices')

            return devices

        except Exception as e:
            logger.error(f'Error getting device list: {e}')
            return list(self.devices.values())

    def _calculate_hash(self, devices: List[adb_models.DeviceInfo]) -> str:
        """Calculate hash for device list to detect changes."""
        device_serials = sorted([d.device_serial_num for d in devices])
        return hashlib.md5('|'.join(device_serials).encode()).hexdigest()

    def force_refresh(self):
        """Force cache refresh on next access."""
        self.last_update = 0


# Global device cache instance
_device_cache = DeviceCache()


def get_devices_cached() -> List[adb_models.DeviceInfo]:
    """Get devices with caching to reduce ADB calls."""
    return _device_cache.get_devices()


class StatusMessages:
    """Status message constants for device discovery."""
    SCANNING = "🔍 Scanning for devices..."
    NO_DEVICES = "📱 No devices connected"
    DEVICES_CONNECTED = "📱 {count} device{s} connected"
    DEVICES_FOUND = "✅ {count} device{s} connected"
    DEVICE_FOUND = "📱 Found device: {serial}"
    SCAN_ERROR = "❌ Device scan error: {error}"


class DeviceRefreshThread(QThread):
    """Thread for refreshing device list without blocking UI with progressive discovery."""

    devices_updated = pyqtSignal(dict)
    device_found = pyqtSignal(str, adb_models.DeviceInfo)  # individual device found
    device_lost = pyqtSignal(str)  # device disconnected
    status_updated = pyqtSignal(str)  # status messages

    def __init__(self, parent=None, refresh_interval: int = DeviceManagerConfig.DEFAULT_REFRESH_INTERVAL):
        super().__init__(parent)
        self.refresh_interval = refresh_interval
        self.running = True
        self.mutex = QMutex()
        self.known_devices = set()  # Track known device serials
        self.last_full_update = 0

    def run(self):
        """Main thread loop for progressive device refresh."""
        while self.running:
            try:
                if self._should_stop():
                    break

                self._perform_device_scan()
                self.msleep(self.refresh_interval * 1000)

            except Exception as e:
                self._handle_scan_error(e)

    def _should_stop(self) -> bool:
        """Check if thread should stop."""
        with QMutexLocker(self.mutex):
            return not self.running

    def _perform_device_scan(self):
        """Perform a single device scan cycle."""
        self.status_updated.emit(StatusMessages.SCANNING)

        devices = get_devices_cached()
        current_serials = set(device.device_serial_num for device in devices)

        # Handle device changes
        lost_devices = self._process_lost_devices(current_serials)
        new_devices = self._process_new_devices(devices, current_serials)

        # Update status and emit periodic full update
        self._update_status_message(new_devices, lost_devices)
        self._emit_periodic_update(devices)

    def _process_lost_devices(self, current_serials: set) -> set:
        """Process devices that have been disconnected."""
        lost_devices = self.known_devices - current_serials
        for serial in lost_devices:
            self.device_lost.emit(serial)
            self.known_devices.discard(serial)
            logger.info(f'Device disconnected: {serial}')
        return lost_devices

    def _process_new_devices(self, devices: List[adb_models.DeviceInfo], current_serials: set) -> set:
        """Process newly discovered devices."""
        new_devices = current_serials - self.known_devices

        for device in devices:
            serial = device.device_serial_num
            if serial in new_devices:
                self.status_updated.emit(StatusMessages.DEVICE_FOUND.format(serial=serial))
                self.device_found.emit(serial, device)
                self.known_devices.add(serial)
                logger.info(f'New device found: {serial} - {device.device_model}')
                self.msleep(DeviceManagerConfig.PROGRESSIVE_DELAY)

        return new_devices

    def _update_status_message(self, new_devices: set, lost_devices: set):
        """Update status message based on device changes."""
        total_devices = len(self.known_devices)
        plural_s = 's' if total_devices != 1 else ''

        if total_devices == 0:
            self.status_updated.emit(StatusMessages.NO_DEVICES)
        elif new_devices or lost_devices:
            self.status_updated.emit(StatusMessages.DEVICES_FOUND.format(
                count=total_devices, s=plural_s))
        else:
            self.status_updated.emit(StatusMessages.DEVICES_CONNECTED.format(
                count=total_devices, s=plural_s))

    def _emit_periodic_update(self, devices: List[adb_models.DeviceInfo]):
        """Emit full device list periodically for batch operations."""
        current_time = time.time()
        if current_time - self.last_full_update > DeviceManagerConfig.FULL_UPDATE_INTERVAL:
            device_dict = {device.device_serial_num: device for device in devices}
            self.devices_updated.emit(device_dict)
            self.last_full_update = current_time

    def _handle_scan_error(self, error: Exception):
        """Handle errors during device scanning."""
        logger.error(f'Error in device refresh thread: {error}')
        self.status_updated.emit(StatusMessages.SCAN_ERROR.format(error=str(error)))
        self.msleep(DeviceManagerConfig.ERROR_RETRY_DELAY)

    def stop(self):
        """Stop the refresh thread."""
        with QMutexLocker(self.mutex):
            self.running = False

    def set_refresh_interval(self, interval):
        """Update refresh interval."""
        with QMutexLocker(self.mutex):
            self.refresh_interval = interval

    def force_refresh(self):
        """Force immediate device refresh by clearing known devices."""
        with QMutexLocker(self.mutex):
            self.known_devices.clear()  # Force rediscovery of all devices
        logger.info('Force refresh: cleared known devices for immediate rediscovery')


class DeviceManager:
    """Manages device list, selection and operations."""

    def __init__(self, parent_widget):
        self.parent = parent_widget
        self.device_dict: Dict[str, adb_models.DeviceInfo] = {}
        self.check_devices: Dict[str, QCheckBox] = {}
        self.device_labels: Dict[str, QLabel] = {}
        self.device_operations: Dict[str, str] = {}
        self.device_recording_status: Dict[str, Dict] = {}

        # Initialize refresh thread with progressive discovery
        self.refresh_thread = DeviceRefreshThread(parent_widget, refresh_interval=3)
        self.refresh_thread.devices_updated.connect(self.update_device_list)
        self.refresh_thread.device_found.connect(self._on_device_found)
        self.refresh_thread.device_lost.connect(self._on_device_lost)
        self.refresh_thread.status_updated.connect(self._on_status_updated)

    def start_device_refresh(self):
        """Start the device refresh thread."""
        if not self.refresh_thread.isRunning():
            self.refresh_thread.start()
            logger.info('Device refresh thread started')

    def stop_device_refresh(self):
        """Stop the device refresh thread with timeout to prevent hanging."""
        if self.refresh_thread.isRunning():
            self.refresh_thread.stop()
            if not self.refresh_thread.wait(DeviceManagerConfig.SHUTDOWN_TIMEOUT):
                logger.debug('Device refresh thread terminated immediately for fast shutdown')
                self.refresh_thread.terminate()
            else:
                logger.debug('Device refresh thread stopped gracefully')

    def get_checked_devices(self) -> List[adb_models.DeviceInfo]:
        """Get list of checked devices."""
        checked_devices = []
        for serial, checkbox in self.check_devices.items():
            if checkbox.isChecked() and serial in self.device_dict:
                checked_devices.append(self.device_dict[serial])
        return checked_devices

    def update_device_list(self, device_dict: Dict[str, adb_models.DeviceInfo]):
        """Update the device list display without rebuilding UI."""
        self.device_dict = device_dict

        # Get currently checked devices to preserve state
        checked_serials = set()
        for serial, checkbox in self.check_devices.items():
            if checkbox.isChecked():
                checked_serials.add(serial)

        # Find devices to add and remove
        current_serials = set(self.check_devices.keys())
        new_serials = set(device_dict.keys())

        # Remove devices that are no longer connected
        for serial in current_serials - new_serials:
            if serial in self.check_devices:
                checkbox = self.check_devices[serial]
                checkbox.setParent(None)
                del self.check_devices[serial]

                if serial in self.device_labels:
                    label = self.device_labels[serial]
                    label.setParent(None)
                    del self.device_labels[serial]

        # Add new devices (this would need UI layout reference)
        # Implementation depends on parent widget's layout structure

        # Restore checked state
        for serial in checked_serials:
            if serial in self.check_devices:
                self.check_devices[serial].setChecked(True)

    def set_device_operation_status(self, serial: str, operation: str):
        """Set operation status for a device."""
        self.device_operations[serial] = operation
        logger.debug(f'Device {serial} operation: {operation}')

    def get_device_operation_status(self, serial: str) -> str:
        """Get operation status for a device."""
        return self.device_operations.get(serial, 'idle')

    def clear_device_operations(self, serials: List[str]):
        """Clear operation status for multiple devices."""
        for serial in serials:
            self._remove_from_dict(self.device_operations, serial)

    def clear_device_operation_status(self, serial: str):
        """Clear operation status for a single device."""
        self._remove_from_dict(self.device_operations, serial)

    def set_device_recording_status(self, serial: str, status: Dict):
        """Set recording status for a device."""
        self.device_recording_status[serial] = status

    def get_device_recording_status(self, serial: str) -> Dict:
        """Get recording status for a device."""
        return self.device_recording_status.get(serial, {})

    def _safe_execute(self, operation_name: str, operation_func):
        """Safely execute an operation with error handling."""
        try:
            operation_func()
        except Exception as e:
            logger.error(f'Error in {operation_name}: {e}')

    def _remove_from_dict(self, dictionary: Dict, key: str) -> bool:
        """Safely remove key from dictionary."""
        if key in dictionary:
            del dictionary[key]
            return True
        return False

    def _cleanup_device_data(self, serial: str):
        """Clean up all tracking data for a device."""
        self._remove_from_dict(self.device_dict, serial)
        self._remove_from_dict(self.device_operations, serial)
        self._remove_from_dict(self.device_recording_status, serial)

    def _cleanup_device_ui(self, serial: str):
        """Clean up UI elements for a device."""
        if serial in self.check_devices:
            checkbox = self.check_devices[serial]
            checkbox.setParent(None)
            checkbox.deleteLater()
            del self.check_devices[serial]


    def _on_device_found(self, serial: str, device_info: adb_models.DeviceInfo):
        """Handle individual device found - add to UI immediately."""
        def add_device():
            self.device_dict[serial] = device_info
            if hasattr(self.parent, 'add_device_to_ui'):
                self.parent.add_device_to_ui(serial, device_info)
            else:
                self.parent.update_device_list(self.device_dict)
            logger.info(f'Individual device added: {serial} - {device_info.device_model}')

        self._safe_execute('device found handling', add_device)

    def _on_device_lost(self, serial: str):
        """Handle individual device lost - remove from UI immediately."""
        def remove_device():
            self._cleanup_device_data(serial)
            self._cleanup_device_ui(serial)
            if hasattr(self.parent, 'remove_device_from_ui'):
                self.parent.remove_device_from_ui(serial)
            else:
                self.parent.update_device_list(self.device_dict)
            logger.info(f'Individual device removed: {serial}')

        self._safe_execute('device lost handling', remove_device)

    def _on_status_updated(self, status: str):
        """Handle status updates from device discovery."""
        def update_status():
            if hasattr(self.parent, 'update_status_message'):
                self.parent.update_status_message(status)
            elif hasattr(self.parent, 'status_bar'):
                self.parent.status_bar.showMessage(status)
            logger.debug(f'Device status update: {status}')

        self._safe_execute('status update handling', update_status)

    def force_refresh(self):
        """Force immediate device refresh."""
        if hasattr(self.refresh_thread, 'force_refresh'):
            self.refresh_thread.force_refresh()
        logger.info('Forced device refresh requested')

    def cleanup(self):
        """Clean up resources."""
        self.stop_device_refresh()
        logger.info('DeviceManager cleanup completed')