"""Device management module for handling ADB device operations - Simplified using AsyncDeviceManager."""

import hashlib
import logging
import threading
import time
from typing import Dict, List, Optional

try:
    from PyQt6.QtCore import QObject, pyqtSignal  # type: ignore
    from PyQt6.QtWidgets import QCheckBox, QLabel  # type: ignore
    PYQT6_AVAILABLE = True
except ImportError:  # pragma: no cover - sandbox fallback
    PYQT6_AVAILABLE = False

    class _DummySignal:
        def connect(self, *_args, **_kwargs) -> None:
            return None

        def emit(self, *_args, **_kwargs) -> None:
            return None

        def disconnect(self, *_args, **_kwargs) -> None:
            return None

    def pyqtSignal(*_args, **_kwargs):  # type: ignore
        return _DummySignal()

    class QObject:  # type: ignore
        def __init__(self, *_args, **_kwargs) -> None:
            super().__init__()

    class QCheckBox:  # type: ignore
        def __init__(self) -> None:
            self._checked = False
            self._parent = None
            self.stateChanged = _DummySignal()
            self.customContextMenuRequested = _DummySignal()

        def isChecked(self) -> bool:
            return self._checked

        def setChecked(self, value: bool) -> None:
            self._checked = bool(value)

        def blockSignals(self, *_args, **_kwargs) -> None:
            return None

        def setParent(self, parent) -> None:
            self._parent = parent

        def parent(self):  # noqa: D401
            return self._parent

        def deleteLater(self) -> None:
            return None

        def hide(self) -> None:
            return None

        def setVisible(self, *_args, **_kwargs) -> None:
            return None

        def setText(self, *_args, **_kwargs) -> None:
            return None

        def setContextMenuPolicy(self, *_args, **_kwargs) -> None:
            return None

        def setFont(self, *_args, **_kwargs) -> None:
            return None

        def setToolTip(self, *_args, **_kwargs) -> None:
            return None

        def enterEvent(self, *_args, **_kwargs) -> None:  # pragma: no cover - stub
            return None

        def leaveEvent(self, *_args, **_kwargs) -> None:  # pragma: no cover - stub
            return None

        def __getattr__(self, _name):  # pragma: no cover - defensive
            # Provide no-op for unexpected attribute usage during tests
            return lambda *_a, **_kw: None

    class QLabel:  # type: ignore
        def __init__(self) -> None:
            self._parent = None

        def setParent(self, parent) -> None:
            self._parent = parent

        def parent(self):  # noqa: D401
            return self._parent

        def deleteLater(self) -> None:
            return None

from utils import adb_models, adb_tools, common

try:
    from ui.async_device_manager import AsyncDeviceManager  # type: ignore
except Exception:  # pragma: no cover - PyQt6 unavailable
    AsyncDeviceManager = None  # type: ignore

logger = common.get_logger('device_manager')


class DeviceManagerConfig:
    """Configuration constants retained for backwards compatibility."""

    DEFAULT_CACHE_TTL: float = 5.0
    DEFAULT_REFRESH_INTERVAL: int = 5
    SHUTDOWN_TIMEOUT: int = 5
    ERROR_RETRY_DELAY: int = 3
    PROGRESSIVE_DELAY: int = 1
    FULL_UPDATE_INTERVAL: int = 30


class StatusMessages:
    """Common status message templates used across legacy tests."""

    DEVICES_CONNECTED = "📱 {count} device{s} connected"
    DEVICE_FOUND = "📱 Found device: {serial}"
    DEVICES_LOST = "📱 {count} device{s} disconnected"
    SCAN_ERROR = "❌ Device scan error: {error}"
    REFRESH_STARTED = "🔄 Refreshing device list..."
    REFRESH_COMPLETED = "✅ Device list updated"


class DeviceCache:
    """Lightweight cache wrapper for device discovery, matching legacy expectations."""

    def __init__(self, cache_ttl: float = DeviceManagerConfig.DEFAULT_CACHE_TTL):
        self.cache_ttl = float(cache_ttl)
        self._cache: List[adb_models.DeviceInfo] = []
        self._last_hash = ""
        self.last_update = 0.0
        self._lock = threading.Lock()

    def _calculate_hash(self, devices: List[adb_models.DeviceInfo]) -> str:
        digest = hashlib.md5()
        for device in devices:
            fingerprint = "|".join(
                str(getattr(device, attr, ""))
                for attr in (
                    "device_serial_num",
                    "device_model",
                    "android_ver",
                    "android_api_level",
                    "gms_version",
                )
            )
            digest.update(fingerprint.encode("utf-8"))
        return digest.hexdigest()

    def get_devices(self) -> List[adb_models.DeviceInfo]:
        with self._lock:
            cached = list(self._cache)
            cache_age = time.monotonic() - self.last_update
            if cached and cache_age < self.cache_ttl:
                return cached

        try:
            fresh_devices = list(adb_tools.get_devices_list())
        except Exception as exc:  # pragma: no cover - defensive branch
            if cached := self._cache:
                logger.warning("Falling back to cached devices after error: %s", exc)
                return list(cached)
            raise

        with self._lock:
            self._cache = fresh_devices
            self.last_update = time.monotonic()
            self._last_hash = self._calculate_hash(fresh_devices)
            return list(self._cache)

    def force_refresh(self) -> None:
        with self._lock:
            self._cache = []
            self._last_hash = ""
            self.last_update = 0.0


_GLOBAL_DEVICE_CACHE = DeviceCache()


def get_devices_cached() -> List[adb_models.DeviceInfo]:
    """Return cached device list used by legacy helpers."""

    return _GLOBAL_DEVICE_CACHE.get_devices()


class DeviceRefreshThread:
    """Compatibility shim retained for legacy tests that expect a thread class."""

    def __init__(self, manager: Optional["DeviceManager"], interval: Optional[int] = None):
        self.manager = manager
        self.interval = interval or DeviceManagerConfig.DEFAULT_REFRESH_INTERVAL
        self._running = False

    def run(self) -> None:
        self._running = True
        if self.manager is not None:
            logger.info("DeviceRefreshThread is delegating to DeviceManager.start_device_refresh()")
            self.manager.start_device_refresh()

    def stop(self) -> None:
        if self.manager is not None:
            self.manager.stop_device_refresh()
        self._running = False


class DeviceManager(QObject):
    """Manages device list, selection and operations using AsyncDeviceManager."""

    # 信號定義
    device_found = pyqtSignal(str, object)  # serial, device_info
    device_lost = pyqtSignal(str)  # serial
    status_updated = pyqtSignal(str)  # status messages
    unauthorized_devices_detected = pyqtSignal(list)  # list of unauthorized serial numbers

    def __init__(self, parent_widget):
        if not PYQT6_AVAILABLE or AsyncDeviceManager is None:
            raise RuntimeError('PyQt6 is required to instantiate DeviceManager')
        super().__init__()
        self.parent = parent_widget
        self.device_dict: Dict[str, adb_models.DeviceInfo] = {}
        self.check_devices: Dict[str, object] = {}
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
        self.async_device_manager.unauthorized_devices_detected.connect(
            self._on_unauthorized_devices_detected
        )

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

    def set_auto_refresh_enabled(self, enabled: bool):
        """Enable or disable automatic refresh."""
        self.async_device_manager.set_auto_refresh_enabled(enabled)

    def get_checked_devices(self) -> List[adb_models.DeviceInfo]:
        """Get list of checked devices."""
        selection_manager = getattr(self.parent, 'device_selection_manager', None)
        if selection_manager is None:
            return []
        serials = selection_manager.get_selected_serials()
        return [self.device_dict[serial] for serial in serials if serial in self.device_dict]

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

        for serial in lost_serials:
            self.device_dict.pop(serial, None)

        self.device_dict.update(device_dict)
        device_count = len(device_dict)
        self.status_updated.emit(f'Found {device_count} device(s)')

        # 觸發主程式UI更新
        self.update_device_list(device_dict)

    def _on_all_devices_ready(self, device_dict: Dict[str, adb_models.DeviceInfo]):
        """處理所有設備信息全部就緒"""
        stale_serials = set(self.device_dict.keys()) - set(device_dict.keys())
        for serial in stale_serials:
            self.device_dict.pop(serial, None)
        self.device_dict.update(device_dict)
        device_count = len(device_dict)
        self.status_updated.emit(f'All device information loaded - {device_count} device(s)')

        # 觸發主程式UI更新
        self.update_device_list(device_dict)

    def _on_unauthorized_devices_detected(self, unauthorized_serials: List[str]):
        """Handle unauthorized devices detection and notify user."""
        if not unauthorized_serials:
            return

        logger.warning(
            'Unauthorized devices detected: %s. User should authorize USB debugging.',
            unauthorized_serials
        )
        # Forward the signal so main window can display a warning
        self.unauthorized_devices_detected.emit(unauthorized_serials)

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
        checkbox = self.check_devices.pop(serial, None)
        if checkbox is not None:
            if hasattr(checkbox, 'setParent'):
                checkbox.setParent(None)
            if hasattr(checkbox, 'deleteLater'):
                checkbox.deleteLater()

        selection_manager = getattr(self.parent, 'device_selection_manager', None)
        if selection_manager is not None:
            remaining = [s for s in selection_manager.get_selected_serials() if s != serial]
            selection_manager.set_selected_serials(remaining)
            if hasattr(self.parent, 'device_list_controller'):
                self.parent.device_list_controller.update_selection_count()

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
