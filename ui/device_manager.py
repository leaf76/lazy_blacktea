"""Device management module for handling ADB device operations - Simplified using AsyncDeviceManager."""

import logging
from typing import Dict, List
from PyQt6.QtWidgets import QCheckBox, QLabel
from PyQt6.QtCore import QObject, pyqtSignal

from utils import adb_models, common
from ui.async_device_manager import AsyncDeviceManager

logger = common.get_logger('device_manager')


class DeviceManager(QObject):
    """Manages device list, selection and operations using AsyncDeviceManager."""

    # 信號定義
    device_found = pyqtSignal(str, object)  # serial, device_info
    device_lost = pyqtSignal(str)  # serial
    status_updated = pyqtSignal(str)  # status messages

    def __init__(self, parent_widget):
        super().__init__()
        self.parent = parent_widget
        self.device_dict: Dict[str, adb_models.DeviceInfo] = {}
        self.check_devices: Dict[str, QCheckBox] = {}
        self.device_labels: Dict[str, QLabel] = {}
        self.device_operations: Dict[str, str] = {}
        self.device_recording_status: Dict[str, Dict] = {}

        # 使用新的 AsyncDeviceManager
        self.async_device_manager = AsyncDeviceManager(self)
        self._setup_async_signals()

        # 設備狀態追踪
        self.known_device_serials = set()

    def _setup_async_signals(self):
        """設置 AsyncDeviceManager 的信號連接"""
        self.async_device_manager.device_basic_loaded.connect(self._on_device_basic_loaded)
        self.async_device_manager.device_detailed_loaded.connect(self._on_device_detailed_loaded)
        self.async_device_manager.basic_devices_ready.connect(self._on_basic_devices_ready)
        self.async_device_manager.all_devices_ready.connect(self._on_all_devices_ready)

    def start_device_refresh(self):
        """Start device refresh using AsyncDeviceManager."""
        logger.info('Starting device refresh with AsyncDeviceManager')
        # 確保刷新間隔已設置（如果主應用還沒設置的話，使用默認值）
        if hasattr(self.parent, 'refresh_interval') and self.parent.refresh_interval:
            self.async_device_manager.set_refresh_interval(self.parent.refresh_interval)
            logger.info(f'Applied refresh interval from main app: {self.parent.refresh_interval}s')
        self.async_device_manager.start_periodic_refresh()
        # 立即執行一次發現
        self.async_device_manager.start_device_discovery(force_reload=False, load_detailed=True)

    def stop_device_refresh(self):
        """Stop device refresh."""
        logger.info('Stopping device refresh')
        self.async_device_manager.stop_periodic_refresh()

    def set_refresh_interval(self, interval: int):
        """Set refresh interval."""
        self.async_device_manager.set_refresh_interval(interval)

    def get_checked_devices(self) -> List[adb_models.DeviceInfo]:
        """Get list of checked devices."""
        checked_devices = []
        for serial, checkbox in self.check_devices.items():
            if checkbox.isChecked() and serial in self.device_dict:
                checked_devices.append(self.device_dict[serial])
        return checked_devices

    def _on_device_basic_loaded(self, serial: str, device_info: adb_models.DeviceInfo):
        """處理設備基本信息加載完成"""
        if serial not in self.known_device_serials:
            # 新設備
            self.known_device_serials.add(serial)
            self.device_found.emit(serial, device_info)
            logger.info(f'New device found: {serial} - {device_info.device_model}')

        # 更新設備字典
        self.device_dict[serial] = device_info

    def _on_device_detailed_loaded(self, serial: str, device_info: adb_models.DeviceInfo):
        """處理設備詳細信息加載完成"""
        self.device_dict[serial] = device_info
        logger.debug(f'Device detailed info loaded: {serial}')

        # 觸發UI更新以顯示詳細信息
        self.update_device_list(self.device_dict)

    def _on_basic_devices_ready(self, device_dict: Dict[str, adb_models.DeviceInfo]):
        """處理基本設備信息全部就緒"""
        current_serials = set(device_dict.keys())
        lost_serials = self.known_device_serials - current_serials

        # 處理失去的設備
        for serial in lost_serials:
            self.device_lost.emit(serial)
            self.known_device_serials.discard(serial)
            logger.info(f'Device lost: {serial}')

        self.device_dict.update(device_dict)
        device_count = len(device_dict)
        self.status_updated.emit(f'Found {device_count} device(s)')

        # 觸發主程式UI更新
        self.update_device_list(device_dict)

    def _on_all_devices_ready(self, device_dict: Dict[str, adb_models.DeviceInfo]):
        """處理所有設備信息全部就緒"""
        self.device_dict.update(device_dict)
        device_count = len(device_dict)
        self.status_updated.emit(f'All device information loaded - {device_count} device(s)')

        # 觸發主程式UI更新
        self.update_device_list(device_dict)

    def update_device_list(self, device_dict: Dict[str, adb_models.DeviceInfo]):
        """Update the device list display without rebuilding UI."""
        self.device_dict = device_dict

        if hasattr(self.parent, 'update_device_list'):
            self.parent.update_device_list(device_dict)

    def set_device_operation_status(self, serial: str, operation: str):
        """Set operation status for a device."""
        self.device_operations[serial] = operation
        logger.debug(f'Device operation status set: {serial} -> {operation}')

    def get_device_operation_status(self, serial: str) -> str:
        """Get operation status for a device."""
        return self.device_operations.get(serial, '')

    def clear_device_operations(self, serials: List[str]):
        """Clear operation status for multiple devices."""
        for serial in serials:
            self.device_operations.pop(serial, None)

    def clear_device_operation_status(self, serial: str):
        """Clear operation status for a device."""
        self.device_operations.pop(serial, None)

    def set_device_recording_status(self, serial: str, status: Dict):
        """Set recording status for a device."""
        self.device_recording_status[serial] = status

    def get_device_recording_status(self, serial: str) -> Dict:
        """Get recording status for a device."""
        return self.device_recording_status.get(serial, {})

    def _cleanup_device_data(self, serial: str):
        """Clean up device-related data."""
        self.device_dict.pop(serial, None)
        self.device_operations.pop(serial, None)
        self.device_recording_status.pop(serial, None)
        self.known_device_serials.discard(serial)

    def _cleanup_device_ui(self, serial: str):
        """Clean up device-related UI elements."""
        if serial in self.check_devices:
            checkbox = self.check_devices.pop(serial)
            if checkbox.parent():
                checkbox.setParent(None)
                checkbox.deleteLater()

        if serial in self.device_labels:
            label = self.device_labels.pop(serial)
            if label.parent():
                label.setParent(None)
                label.deleteLater()

    def force_refresh(self):
        """Force immediate device refresh."""
        logger.info('Force refresh requested')
        self.async_device_manager.start_device_discovery(force_reload=True, load_detailed=True)

    def cleanup(self):
        """Clean up resources."""
        self.stop_device_refresh()
        if hasattr(self.async_device_manager, 'cleanup'):
            self.async_device_manager.cleanup()
        logger.info('DeviceManager cleanup completed')