#!/usr/bin/env python3
"""
異步設備管理器 - 解決大量設備時的UI凍結問題

這個模組負責：
1. 漸進式設備發現和信息加載
2. 異步設備信息提取，不阻塞UI
3. 實時進度反饋和狀態更新
4. 優先加載基本信息，詳細信息按需加載
5. 內存使用優化和設備信息緩存
"""

import subprocess
import threading
import time
from typing import Callable, Dict, List, Optional, Set
from dataclasses import dataclass, field
from enum import Enum
from PyQt6.QtCore import QObject, pyqtSignal, QThread, QMutex, QMutexLocker, QTimer, QRunnable, QThreadPool

from config.constants import ADBConstants
from utils import adb_tools, common, adb_models

logger = common.get_logger('async_device_manager')


TRACKER_READY_STATUSES = frozenset({
    ADBConstants.DEVICE_STATE_DEVICE,
    ADBConstants.DEVICE_STATE_UNAUTHORIZED,
    ADBConstants.DEVICE_STATE_RECOVERY,
    ADBConstants.DEVICE_STATE_BOOTLOADER,
    ADBConstants.DEVICE_STATE_SIDELOAD,
})

TRACKER_REMOVAL_STATUSES = frozenset({
    ADBConstants.DEVICE_STATE_OFFLINE,
})

BASIC_ACCEPTED_STATUSES = TRACKER_READY_STATUSES


class DeviceLoadStatus(Enum):
    """設備加載狀態"""
    DISCOVERING = "discovering"      # 發現中
    BASIC_LOADED = "basic_loaded"    # 基本信息已加載
    DETAILED_LOADING = "detailed_loading"  # 詳細信息加載中
    FULLY_LOADED = "fully_loaded"    # 完全加載
    ERROR = "error"                  # 加載錯誤


@dataclass
class DeviceLoadProgress:
    """設備加載進度信息"""
    serial: str
    status: DeviceLoadStatus
    basic_info: Optional[adb_models.DeviceInfo] = None
    detailed_info: Optional[Dict] = None
    error_message: Optional[str] = None
    load_time: float = field(default_factory=time.time)


class AsyncDeviceWorker(QObject):
    """異步設備信息加載工作對象 - 使用安全的worker模式"""

    # 漸進式加載信號定義
    device_basic_loaded = pyqtSignal(str, object)  # device_serial, basic_info
    device_detailed_loaded = pyqtSignal(str, object)  # device_serial, detailed_info
    device_load_failed = pyqtSignal(str, str)  # device_serial, error_message
    progress_updated = pyqtSignal(int, int)  # current_count, total_count
    all_basic_loaded = pyqtSignal()  # 所有基本信息加載完成
    all_detailed_loaded = pyqtSignal()  # 所有詳細信息加載完成

    def __init__(self, parent=None):
        super().__init__(parent)
        self.device_serials: List[str] = []
        self.load_detailed: bool = True
        self.max_concurrent: int = 3  # 限制並發數量
        self.stop_requested: bool = False
        self.is_running: bool = False
        self.mutex = QMutex()

    def set_devices(self, device_serials: List[str], load_detailed: bool = True):
        """設置要加載的設備列表"""
        with QMutexLocker(self.mutex):
            self.device_serials = device_serials.copy()
            self.load_detailed = load_detailed
            self.stop_requested = False
            self.is_running = False

    def request_stop(self):
        """請求停止加載"""
        with QMutexLocker(self.mutex):
            self.stop_requested = True
            self.is_running = False

    def isRunning(self) -> bool:
        """檢查是否正在運行"""
        with QMutexLocker(self.mutex):
            return self.is_running

    def start_loading(self):
        """開始異步加載 - 使用QRunnable"""
        with QMutexLocker(self.mutex):
            self.is_running = True
        runnable = DeviceLoadingRunnable(self)
        QThreadPool.globalInstance().start(runnable)

    def _load_devices_efficiently(self):
        """漸進式設備加載：先顯示基本信息，再異步補充詳細信息"""
        if not self.device_serials:
            return

        logger.info(f'Starting progressive async load for {len(self.device_serials)} device(s)')

        # Phase 1: 快速加載並顯示基本信息
        self._load_basic_info_immediately()

        if not self.stop_requested:
            self.all_basic_loaded.emit()

        # Phase 2: 異步加載詳細信息
        if self.load_detailed and not self.stop_requested:
            self._load_detailed_info_progressively()

        if not self.stop_requested:
            self.all_detailed_loaded.emit()
            logger.info('Progressive async load completed for %s device(s)', len(self.device_serials))

        # 設置運行狀態為完成
        with QMutexLocker(self.mutex):
            self.is_running = False

    def _load_basic_info_immediately(self):
        """立即加載所有設備的基本信息（僅基本信息，不執行耗時檢查）"""
        logger.info('Phase 1: Loading basic device information')

        try:
            # 使用新的快速設備列表函數
            basic_device_infos = adb_tools.get_devices_list_fast()

            loaded_count = 0
            for device_info in basic_device_infos:
                if self.stop_requested:
                    break

                # 立即發送基本信息到UI
                self.device_basic_loaded.emit(device_info.device_serial_num, device_info)
                loaded_count += 1

                # 更新進度
                self.progress_updated.emit(loaded_count, len(self.device_serials))

            logger.info(f'Basic information loaded for {loaded_count} device(s)')

        except Exception as e:
            logger.error(f'Failed to load basic device information: {e}')

    def _load_detailed_info_progressively(self):
        """漸進式加載詳細設備信息"""
        logger.info('Phase 2: Loading detailed device information asynchronously')

        import concurrent.futures

        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_concurrent) as executor:
            # 提交詳細信息加載任務
            future_to_serial = {
                executor.submit(adb_tools.get_device_detailed_info, serial): serial
                for serial in self.device_serials
            }

            loaded_count = 0
            for future in concurrent.futures.as_completed(future_to_serial):
                if self.stop_requested:
                    break

                serial = future_to_serial[future]
                try:
                    detailed_info = future.result()
                    if detailed_info:
                        # 發送詳細信息更新
                        self.device_detailed_loaded.emit(serial, detailed_info)
                        loaded_count += 1
                    else:
                        self.device_load_failed.emit(serial, 'Unable to load detailed device information')
                except Exception as e:
                    logger.error(f'Failed to load detailed information for device {serial}: {e}')
                    self.device_load_failed.emit(serial, str(e))

                # 更新詳細信息加載進度
                if loaded_count % max(1, len(self.device_serials) // 5) == 0:
                    logger.debug(f'Detailed information load progress: {loaded_count}/{len(self.device_serials)}')

            logger.info(f'Detailed information loaded for {loaded_count} device(s)')


class DeviceLoadingRunnable(QRunnable):
    """設備加載任務 - 在線程池中運行"""

    def __init__(self, worker: AsyncDeviceWorker):
        super().__init__()
        self.worker = worker
        self.setAutoDelete(True)

    def run(self):
        """執行異步設備加載"""
        try:
            self.worker._load_devices_efficiently()
        except Exception as e:
            logger.error(f'Async device loading error: {e}')





class TrackDevicesWorker(QObject):
    """Background worker that follows `adb track-devices` output."""

    device_list_changed = pyqtSignal(list)  # List[Tuple[str, str]] -> (serial, status)
    error_occurred = pyqtSignal(str)

    def __init__(self, command_factory: Optional[Callable[[], List[str]]] = None, parent=None):
        super().__init__(parent)
        self._command_factory = command_factory or (lambda: ['adb', 'track-devices'])
        self._stop_event = threading.Event()
        self._process: Optional[subprocess.Popen] = None

    def run(self):
        """Main loop executed within a dedicated QThread."""
        while not self._stop_event.is_set():
            try:
                command = self._command_factory()
                self._process = subprocess.Popen(
                    command,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    bufsize=1,
                    universal_newlines=True,
                )

                buffer: List[str] = []

                while not self._stop_event.is_set():
                    if self._process.stdout is None:
                        break
                    line = self._process.stdout.readline()

                    if line == '' and self._process.poll() is not None:
                        break

                    line = line.strip()
                    if not line:
                        self._emit_from_buffer(buffer)
                        buffer = []
                        continue

                    if line.startswith('List of devices attached'):
                        buffer = []
                        continue

                    buffer.append(line)

                if buffer:
                    self._emit_from_buffer(buffer)

                if self._process:
                    self._process.wait(timeout=1)

            except FileNotFoundError:
                self.error_occurred.emit('ADB executable not found for track-devices')
                self._wait_before_retry(5)
            except Exception as exc:
                self.error_occurred.emit(f'track-devices error: {exc}')
                self._wait_before_retry(2)
            finally:
                if self._process:
                    try:
                        if self._process.poll() is None:
                            self._process.terminate()
                        self._process.wait(timeout=1)
                    except Exception:
                        pass
                self._process = None

    def stop(self):
        self._stop_event.set()
        if self._process and self._process.poll() is None:
            try:
                self._process.terminate()
                self._process.wait(timeout=1)
            except Exception:
                try:
                    self._process.kill()
                except Exception:
                    pass
        self._process = None

    def _emit_from_buffer(self, buffer: List[str]):
        entries: List[tuple[str, str]] = []
        for entry in buffer:
            parts = entry.split()
            if not parts:
                continue
            serial = parts[0].strip()
            status = parts[1].strip() if len(parts) > 1 else ''
            if serial:
                entries.append((serial, status))

        if entries:
            self.device_list_changed.emit(entries)

    def _wait_before_retry(self, seconds: int):
        for _ in range(seconds * 10):
            if self._stop_event.is_set():
                break
            time.sleep(0.1)


class AsyncDeviceManager(QObject):
    """異步設備管理器"""

    # 漸進式加載信號定義
    device_discovery_started = pyqtSignal()
    device_basic_loaded = pyqtSignal(str, object)  # device_serial, basic_info
    device_detailed_loaded = pyqtSignal(str, object)  # device_serial, detailed_info
    device_load_progress = pyqtSignal(int, int, str)  # current, total, message
    basic_devices_ready = pyqtSignal(dict)  # 基本信息加載完成
    all_devices_ready = pyqtSignal(dict)  # 所有信息加載完成

    def __init__(self, parent=None, tracker_factory: Optional[Callable[[], Optional[TrackDevicesWorker]]] = None):
        super().__init__(parent)
        self.device_cache: Dict[str, adb_models.DeviceInfo] = {}
        self.device_progress: Dict[str, DeviceLoadProgress] = {}
        self.last_discovered_serials: Optional[Set[str]] = None
        self.worker: Optional[AsyncDeviceWorker] = None
        self.device_tracker_thread: Optional[QThread] = None
        self.device_tracker_worker: Optional[TrackDevicesWorker] = None
        self._tracker_factory = tracker_factory or (lambda: TrackDevicesWorker())
        self.tracked_device_statuses: Dict[str, str] = {}

        # 設置
        self.max_cache_size = 50  # 最大緩存設備數
        self.detailed_loading_enabled = True

        # 定時刷新設置
        self.refresh_timer = QTimer(self)  # 確保timer有正確的parent
        self.refresh_timer.timeout.connect(self._periodic_refresh)
        self.refresh_interval = 30   # 默認30秒刷新間隔
        self.auto_refresh_enabled = True
        self.refresh_cycle_count = 0  # 用於追踪刷新週期

        self._initialize_device_tracker()

    def _initialize_device_tracker(self):
        """Set up adb track-devices monitoring in background."""
        tracker_instance: Optional[TrackDevicesWorker] = None

        if self._tracker_factory:
            try:
                tracker_instance = self._tracker_factory()
            except Exception as exc:
                logger.error(f'Failed to create device tracker worker: {exc}')
                tracker_instance = None

        if tracker_instance is None:
            logger.info('Device tracker not started (factory returned None)')
            return

        self.device_tracker_worker = tracker_instance
        self.device_tracker_thread = QThread(self)
        self.device_tracker_worker.moveToThread(self.device_tracker_thread)
        self.device_tracker_thread.started.connect(self.device_tracker_worker.run)
        self.device_tracker_worker.device_list_changed.connect(self._on_tracked_devices_changed)
        self.device_tracker_worker.error_occurred.connect(lambda msg: logger.warning(f'Device tracker warning: {msg}'))
        self.device_tracker_thread.start()

    @staticmethod
    def _normalize_status(status: Optional[str]) -> str:
        return (status or '').strip().lower()

    def start_device_discovery(self, force_reload: bool = False, load_detailed: bool = True, serials: Optional[List[str]] = None):
        """開始異步設備發現"""
        # force_reload parameter kept for compatibility but not currently used
        logger.info('Starting async device discovery')

        # 停止現有工作線程
        self.stop_current_loading()

        self.device_discovery_started.emit()

        try:
            if serials is not None:
                basic_device_serials = serials
            else:
                # 快速獲取設備列表（不包含詳細信息）
                basic_device_serials = self._get_basic_device_serials()

            self.last_discovered_serials = set(basic_device_serials)

            if not basic_device_serials:
                logger.warning('No devices detected')
                self.all_devices_ready.emit({})
                return

            logger.info(f'Discovered {len(basic_device_serials)} device(s); starting async load')

            # 創建工作線程
            self.worker = AsyncDeviceWorker()
            self.worker.set_devices(basic_device_serials, load_detailed)

            # 連接信號（漸進式版）
            self.worker.device_basic_loaded.connect(self._on_device_basic_loaded)
            self.worker.device_detailed_loaded.connect(self._on_device_detailed_loaded)
            self.worker.device_load_failed.connect(self._on_device_load_failed)
            self.worker.progress_updated.connect(self._on_progress_updated)
            self.worker.all_basic_loaded.connect(self._on_all_basic_loaded)
            self.worker.all_detailed_loaded.connect(self._on_all_detailed_loaded)

            # 啟動工作線程池任務
            self.worker.start_loading()

        except Exception as e:
            logger.error(f'Failed to start device discovery: {e}')

    def stop_current_loading(self):
        """停止當前的加載過程"""
        if self.worker:
            logger.info('Stopping current device loading process')
            self.worker.request_stop()
            # 對於QRunnable，我們只能請求停止，無法強制終止

    def _get_basic_device_serials(self) -> List[str]:
        """快速獲取設備序號列表"""
        try:
            # 只執行基本的設備列舉，不獲取詳細信息
            result = common.run_command('adb devices')
            device_serials = []

            valid_statuses = BASIC_ACCEPTED_STATUSES

            for line in result:
                if not line or line.startswith('*'):
                    continue
                parts = line.split()
                if not parts:
                    continue
                serial = parts[0].strip()
                status = self._normalize_status(parts[1] if len(parts) > 1 else '')
                if serial and (not status or status in valid_statuses):
                    device_serials.append(serial)

            return device_serials
        except Exception as e:
            logger.error(f'Failed to retrieve basic device list: {e}')
            return []

    def _on_device_basic_loaded(self, serial: str, device_info: adb_models.DeviceInfo):
        """設備基本信息加載完成時的處理"""
        logger.debug(f'Basic information loaded for device {serial} - {device_info.device_model}')

        # 智能更新緩存：保留現有的詳細信息
        if serial in self.device_cache:
            existing_device = self.device_cache[serial]
            # 只更新基本信息，保留詳細信息
            existing_device.device_serial_num = device_info.device_serial_num
            existing_device.device_usb = device_info.device_usb
            existing_device.device_prod = device_info.device_prod
            existing_device.device_model = device_info.device_model
            # 詳細信息字段保持不變（android_ver, android_api_level, gms_version, build_fingerprint, wifi_is_on, bt_is_on）
            device_info = existing_device  # 使用合併後的設備信息
        else:
            # 新設備，直接添加
            self.device_cache[serial] = device_info

        # 更新進度
        if serial in self.device_progress:
            self.device_progress[serial].status = DeviceLoadStatus.BASIC_LOADED
            self.device_progress[serial].basic_info = device_info

        # 發送信號，立即更新UI
        self.device_basic_loaded.emit(serial, device_info)

    def _on_device_detailed_loaded(self, serial: str, detailed_info: dict):
        """設備詳細信息加載完成時的處理"""
        logger.debug(f'Detailed information loaded for device {serial}')

        # 更新設備信息
        if serial in self.device_cache:
            device_info = self.device_cache[serial]

            # 只更新實際獲得的有效值，保持原有值不被覆蓋
            wifi_status = detailed_info.get('wifi_status')
            if wifi_status is not None:
                device_info.wifi_status = wifi_status
                device_info.wifi_is_on = (wifi_status == 1)

            bt_status = detailed_info.get('bluetooth_status')
            if bt_status is not None:
                device_info.bluetooth_status = bt_status
                device_info.bt_is_on = (bt_status == 1)

            # 只在獲得有效非Unknown值時才更新字符串字段
            android_ver = detailed_info.get('android_version')
            if android_ver and android_ver != 'Unknown':
                device_info.android_ver = android_ver
            elif device_info.android_ver is None:  # 初次加載且沒有值
                device_info.android_ver = 'Unknown'

            android_api = detailed_info.get('android_api_level')
            if android_api and android_api != 'Unknown':
                device_info.android_api_level = android_api
            elif device_info.android_api_level is None:  # 初次加載且沒有值
                device_info.android_api_level = 'Unknown'

            gms_ver = detailed_info.get('gms_version')
            if gms_ver and gms_ver != 'Unknown':
                device_info.gms_version = gms_ver
            elif device_info.gms_version is None:  # 初次加載且沒有值
                device_info.gms_version = 'Unknown'

            build_fp = detailed_info.get('build_fingerprint')
            if build_fp and build_fp != 'Unknown':
                device_info.build_fingerprint = build_fp
            elif device_info.build_fingerprint is None:  # 初次加載且沒有值
                device_info.build_fingerprint = 'Unknown'

            # 發送更新信號
            self.device_detailed_loaded.emit(serial, device_info)

        # 更新進度
        if serial in self.device_progress:
            self.device_progress[serial].status = DeviceLoadStatus.FULLY_LOADED
            self.device_progress[serial].detailed_info = detailed_info

    def _on_all_basic_loaded(self):
        """所有設備基本信息加載完成"""
        logger.info('All basic device information loaded')
        self.basic_devices_ready.emit(self.device_cache.copy())

    def _on_all_detailed_loaded(self):
        """所有設備詳細信息加載完成"""
        logger.info('All detailed device information loaded')
        self.all_devices_ready.emit(self.device_cache.copy())

    def _on_device_load_failed(self, serial: str, error_message: str):
        """設備加載失敗時的處理"""
        logger.warning(f'Device load failed: {serial} - {error_message}')

        # 更新進度
        if serial in self.device_progress:
            self.device_progress[serial].status = DeviceLoadStatus.ERROR
            self.device_progress[serial].error_message = error_message

    def _on_progress_updated(self, current: int, total: int):
        """進度更新時的處理"""
        message = f'Loaded {current}/{total} device basic record(s)'
        logger.debug(message)
        self.device_load_progress.emit(current, total, message)

    def _on_all_devices_loaded(self):
        """所有設備加載完成時的處理"""
        logger.info('All device information loaded')
        self.all_devices_ready.emit(self.device_cache.copy())

    def get_device_info(self, serial: str) -> Optional[adb_models.DeviceInfo]:
        """獲取設備信息"""
        return self.device_cache.get(serial)

    def get_all_devices(self) -> Dict[str, adb_models.DeviceInfo]:
        """獲取所有設備信息"""
        return self.device_cache.copy()

    def get_load_progress(self, serial: str) -> Optional[DeviceLoadProgress]:
        """獲取設備加載進度"""
        return self.device_progress.get(serial)

    def clear_cache(self):
        """清空設備緩存"""
        self.device_cache.clear()
        self.device_progress.clear()
        logger.info('Device cache cleared')

    def start_periodic_refresh(self):
        """開始定時刷新"""
        logger.info(
            'Attempting to start periodic refresh - auto_refresh_enabled: %s, timer_active: %s, interval: %s seconds',
            self.auto_refresh_enabled,
            self.refresh_timer.isActive(),
            self.refresh_interval,
        )
        if self.auto_refresh_enabled and not self.refresh_timer.isActive():
            self.refresh_timer.start(self.refresh_interval * 1000)  # 轉換為毫秒
            logger.info('Periodic refresh started; interval: %s seconds', self.refresh_interval)
        elif self.refresh_timer.isActive():
            logger.warning('Periodic refresh is already running')
        elif not self.auto_refresh_enabled:
            logger.warning('Automatic refresh is disabled; cannot start periodic refresh')

    def stop_periodic_refresh(self):
        """停止定時刷新"""
        if self.refresh_timer.isActive():
            self.refresh_timer.stop()
            logger.info('Periodic refresh stopped')

    def set_refresh_interval(self, interval: int):
        """設置刷新間隔"""
        self.refresh_interval = max(5, interval)  # 最小5秒間隔
        if self.refresh_timer.isActive():
            self.refresh_timer.setInterval(self.refresh_interval * 1000)
        logger.info('Refresh interval set to %s seconds', self.refresh_interval)

    def set_auto_refresh_enabled(self, enabled: bool):
        """設置是否啟用自動刷新"""
        self.auto_refresh_enabled = enabled
        if enabled:
            self.start_periodic_refresh()
        else:
            self.stop_periodic_refresh()
        logger.info('Automatic refresh %s', 'enabled' if enabled else 'disabled')

    def _periodic_refresh(self):
        """定時刷新回調"""
        # 如果有工作線程正在運行，跳過這次刷新避免衝突
        if self.worker and self.worker.isRunning():
            logger.info('Skipping periodic refresh while devices are loading to avoid interruption')
            return

        try:
            current_serials = self._get_basic_device_serials()
        except Exception as exc:
            logger.error(f'Periodic refresh failed to enumerate devices: {exc}')
            current_serials = []

        current_set = set(current_serials)

        if self.last_discovered_serials is not None and current_set == self.last_discovered_serials:
            self.refresh_cycle_count += 1
            logger.info('No device changes detected; skipping refresh cycle %s', self.refresh_cycle_count)
            return

        self.refresh_cycle_count += 1
        logger.info('Running periodic device refresh cycle %s (full detail)', self.refresh_cycle_count)
        try:
            self.start_device_discovery(force_reload=True, load_detailed=True)
        except Exception as e:
            logger.error(f'Periodic refresh failed: {e}')

    def cleanup(self):
        """清理資源"""
        self.stop_periodic_refresh()
        self.stop_current_loading()
        self.clear_cache()
        if self.device_tracker_worker:
            self.device_tracker_worker.stop()
        if self.device_tracker_thread:
            self.device_tracker_thread.quit()
            self.device_tracker_thread.wait(1000)
            self.device_tracker_thread = None
        self.device_tracker_worker = None

    def _on_tracked_devices_changed(self, entries: List[tuple[str, str]]):
        """Handle change events from adb track-devices."""
        if not entries:
            return

        previous_serials = set(self.tracked_device_statuses.keys())
        normalized_status: Dict[str, str] = {}

        for serial, status in entries:
            serial = (serial or '').strip()
            if not serial:
                continue
            status_normalized = self._normalize_status(status)
            normalized_status[serial] = status_normalized

        if not normalized_status:
            return

        current_serials = set(normalized_status.keys())
        removed_serials = {
            serial for serial, status in normalized_status.items()
            if status in TRACKER_REMOVAL_STATUSES
        }
        missing_serials = previous_serials - current_serials
        removed_serials.update(missing_serials)

        # Refresh tracked status cache excluding removed devices
        self.tracked_device_statuses = {
            serial: status
            for serial, status in normalized_status.items()
            if status not in TRACKER_REMOVAL_STATUSES
        }

        ready_serials = {
            serial for serial, status in self.tracked_device_statuses.items()
            if status in TRACKER_READY_STATUSES
        }

        removal_detected = bool(removed_serials)
        removed_any = False
        for serial in removed_serials:
            if serial in self.device_cache:
                removed_any = True
                self.device_cache.pop(serial, None)
            if serial in self.device_progress:
                self.device_progress.pop(serial, None)
            if self.last_discovered_serials is not None:
                self.last_discovered_serials.discard(serial)

        if removed_any:
            logger.info('Device tracker removed devices: %s', sorted(removed_serials))
            self.basic_devices_ready.emit(self.device_cache.copy())

        need_refresh = removal_detected
        if not need_refresh:
            if self.last_discovered_serials is None:
                need_refresh = True
            elif ready_serials != self.last_discovered_serials:
                need_refresh = True
            elif any(status not in TRACKER_READY_STATUSES for status in self.tracked_device_statuses.values()):
                logger.info('Device tracker reports status changes; triggering discovery')
                need_refresh = True

        if not need_refresh:
            logger.debug('Tracked device list unchanged; ignoring update')
            return

        logger.info('Device tracker detected change: %s', entries)
        try:
            self.start_device_discovery(force_reload=True, load_detailed=True)
        except Exception as exc:
            logger.error(f'Failed to refresh devices after track update: {exc}')
