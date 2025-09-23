"""Device management module for handling ADB device operations."""

import logging
import time
import hashlib
from typing import Dict, List, Optional
from PyQt6.QtWidgets import QCheckBox, QLabel, QHBoxLayout, QWidget
from PyQt6.QtCore import QThread, pyqtSignal, QMutex, QMutexLocker

from utils import adb_models, adb_tools, common

logger = common.get_logger('device_manager')

# Global cache for device information
_device_cache = {
    'devices': {},
    'last_update': 0,
    'cache_ttl': 3.0,  # Cache for 3 seconds
    'last_hash': ''
}


def get_devices_cached() -> List[adb_models.DeviceInfo]:
    """Get devices with caching to reduce ADB calls."""
    current_time = time.time()

    # Check if cache is still valid
    if (current_time - _device_cache['last_update']) < _device_cache['cache_ttl']:
        logger.debug('Using cached device list')
        return list(_device_cache['devices'].values())

    # Get fresh device list
    try:
        devices = adb_tools.get_devices_list()

        # Create hash of device serials to detect changes
        device_serials = sorted([d.device_serial_num for d in devices])
        current_hash = hashlib.md5('|'.join(device_serials).encode()).hexdigest()

        # Only update cache if devices actually changed or cache expired
        if current_hash != _device_cache['last_hash'] or devices:
            _device_cache['devices'] = {d.device_serial_num: d for d in devices}
            _device_cache['last_update'] = current_time
            _device_cache['last_hash'] = current_hash
            logger.debug(f'Updated device cache with {len(devices)} devices')

        return devices

    except Exception as e:
        logger.error(f'Error getting device list: {e}')
        # Return cached devices if available
        return list(_device_cache['devices'].values())


class DeviceRefreshThread(QThread):
    """Thread for refreshing device list without blocking UI."""

    devices_updated = pyqtSignal(dict)

    def __init__(self, parent=None, refresh_interval=10):  # Increased default interval
        super().__init__(parent)
        self.refresh_interval = refresh_interval
        self.running = True
        self.mutex = QMutex()
        self.last_device_count = 0

    def run(self):
        """Main thread loop for device refresh."""
        while self.running:
            try:
                with QMutexLocker(self.mutex):
                    if not self.running:
                        break

                # Use cached device detection
                devices = get_devices_cached()
                device_dict = {device.device_serial_num: device for device in devices}

                # Only emit signal if device count changed or this is the first run
                current_count = len(devices)
                if current_count != self.last_device_count or self.last_device_count == 0:
                    self.devices_updated.emit(device_dict)
                    self.last_device_count = current_count
                    logger.debug(f'Emitted device update: {current_count} devices')

                self.msleep(self.refresh_interval * 1000)
            except Exception as e:
                logger.error(f'Error in device refresh thread: {e}')
                self.msleep(10000)  # Wait 10 seconds before retry

    def stop(self):
        """Stop the refresh thread."""
        with QMutexLocker(self.mutex):
            self.running = False

    def set_refresh_interval(self, interval):
        """Update refresh interval."""
        with QMutexLocker(self.mutex):
            self.refresh_interval = interval


class DeviceManager:
    """Manages device list, selection and operations."""

    def __init__(self, parent_widget):
        self.parent = parent_widget
        self.device_dict: Dict[str, adb_models.DeviceInfo] = {}
        self.check_devices: Dict[str, QCheckBox] = {}
        self.device_labels: Dict[str, QLabel] = {}
        self.device_operations: Dict[str, str] = {}
        self.device_recording_status: Dict[str, Dict] = {}

        # Initialize refresh thread
        self.refresh_thread = DeviceRefreshThread(parent_widget, refresh_interval=5)
        self.refresh_thread.devices_updated.connect(self.update_device_list)

    def start_device_refresh(self):
        """Start the device refresh thread."""
        if not self.refresh_thread.isRunning():
            self.refresh_thread.start()
            logger.info('Device refresh thread started')

    def stop_device_refresh(self):
        """Stop the device refresh thread with timeout to prevent hanging."""
        if self.refresh_thread.isRunning():
            self.refresh_thread.stop()
            # Use very short timeout for immediate shutdown
            if not self.refresh_thread.wait(300):  # 300ms timeout for immediate feel
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
            if serial in self.device_operations:
                del self.device_operations[serial]

    def set_device_recording_status(self, serial: str, status: Dict):
        """Set recording status for a device."""
        self.device_recording_status[serial] = status

    def get_device_recording_status(self, serial: str) -> Dict:
        """Get recording status for a device."""
        return self.device_recording_status.get(serial, {})

    def cleanup(self):
        """Clean up resources."""
        self.stop_device_refresh()
        logger.info('DeviceManager cleanup completed')