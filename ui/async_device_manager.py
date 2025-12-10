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
import shlex
import subprocess
import threading
import time
from typing import Callable, Dict, IO, List, Optional, Set
from collections import OrderedDict
from dataclasses import dataclass, field
from enum import Enum
from PyQt6.QtCore import QObject, pyqtSignal, QThread, QMutex, QMutexLocker, QTimer

from config.constants import ADBConstants
from utils import adb_tools, common, adb_models, adb_commands
from utils.task_dispatcher import TaskHandle, TaskContext, get_task_dispatcher

logger = common.get_logger('async_device_manager')


class ADBCommandError(RuntimeError):
    """Raised when executing an adb command fails."""


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

    def __init__(self, parent=None, status_checker: Optional[Callable[[str], bool]] = None):
        super().__init__(parent)
        self.device_serials: List[str] = []
        self.load_detailed: bool = True
        self.max_concurrent: int = 3  # 限制並發數量
        self.stop_requested: bool = False
        self.is_running: bool = False
        self.mutex = QMutex()
        self.status_checker: Optional[Callable[[str], bool]] = status_checker
        self.refresh_only: bool = False
        self._task_handle: Optional[TaskHandle] = None

    def set_devices(self, device_serials: List[str], load_detailed: bool = True, refresh_only: bool = False):
        """設置要加載的設備列表"""
        with QMutexLocker(self.mutex):
            self.device_serials = device_serials.copy()
            self.load_detailed = load_detailed
            self.stop_requested = False
            self.is_running = False
            self.refresh_only = refresh_only

    def set_status_checker(self, checker: Optional[Callable[[str], bool]]):
        """設定設備狀態檢查器，便於在詳細加載前確認設備仍可用"""
        with QMutexLocker(self.mutex):
            self.status_checker = checker

    def request_stop(self):
        """請求停止加載"""
        with QMutexLocker(self.mutex):
            self.stop_requested = True
            self.is_running = False
            handle = self._task_handle

        if handle:
            handle.cancel()

    def isRunning(self) -> bool:
        """檢查是否正在運行"""
        with QMutexLocker(self.mutex):
            return self.is_running

    def start_loading(self):
        """開始異步加載 - 透過共用 QThreadPool 執行"""
        with QMutexLocker(self.mutex):
            self.is_running = True
            # 任何既有任務需要先取消
            if self._task_handle:
                self._task_handle.cancel()
                self._task_handle = None

        dispatcher = get_task_dispatcher()
        context = TaskContext(
            name='async_device_load',
            category='device_discovery',
        )
        handle = dispatcher.submit(self._load_devices_efficiently, context=context)
        handle.completed.connect(lambda _: self._on_task_completed())
        handle.failed.connect(self._on_task_failed)
        handle.finished.connect(self._on_task_finished)

        with QMutexLocker(self.mutex):
            self._task_handle = handle

    def _load_devices_efficiently(self):
        """漸進式設備加載：先顯示基本信息，再異步補充詳細信息"""
        if not self.device_serials:
            return

        if self.refresh_only:
            logger.info('Starting detail refresh for %s cached device(s)', len(self.device_serials))
        else:
            logger.info(f'Starting progressive async load for {len(self.device_serials)} device(s)')

            # Phase 1: 快速加載並顯示基本信息
            self._load_basic_info_immediately()

            if not self.stop_requested:
                self.all_basic_loaded.emit()

        # 異步加載詳細信息
        if self.load_detailed and not self.stop_requested:
            self._load_detailed_info_progressively()

        if not self.stop_requested:
            self.all_detailed_loaded.emit()
            if self.refresh_only:
                logger.info('Detail refresh completed for %s device(s)', len(self.device_serials))
            else:
                logger.info('Progressive async load completed for %s device(s)', len(self.device_serials))

        # 設置運行狀態為完成
        with QMutexLocker(self.mutex):
            self.is_running = False

    def _on_task_completed(self) -> None:
        logger.debug('Async device load task completed')

    def _on_task_failed(self, exc: Exception) -> None:
        logger.error('Async device load task failed: %s', exc)

    def _on_task_finished(self) -> None:
        with QMutexLocker(self.mutex):
            self._task_handle = None

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

    def _load_single_device_info(self, serial: str) -> Optional[dict]:
        """為單一設備加載詳細資訊，若設備已離線則直接跳過"""
        with QMutexLocker(self.mutex):
            should_stop = self.stop_requested
            checker = self.status_checker

        if should_stop:
            return None

        if checker is not None and not checker(serial):
            logger.debug('Skipping detailed info for %s (device unavailable during load)', serial)
            return None

        if self.stop_requested:
            return None

        return adb_tools.get_device_detailed_info(serial)

    def _load_detailed_info_progressively(self):
        """漸進式加載詳細設備信息"""
        logger.info('Phase 2: Loading detailed device information asynchronously')

        import concurrent.futures

        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_concurrent) as executor:
            # 提交詳細信息加載任務
            future_to_serial = {
                executor.submit(self._load_single_device_info, serial): serial
                for serial in self.device_serials
            }

            loaded_count = 0
            for future in concurrent.futures.as_completed(future_to_serial):
                if self.stop_requested:
                    break

                serial = future_to_serial[future]
                try:
                    detailed_info = future.result()
                    if detailed_info is None:
                        # 已跳過或沒有可用資料，不視為失敗
                        logger.debug('Detailed info skipped for %s', serial)
                        continue

                    # 發送詳細信息更新
                    self.device_detailed_loaded.emit(serial, detailed_info)
                    loaded_count += 1
                except Exception as e:
                    logger.error(f'Failed to load detailed information for device {serial}: {e}')
                    self.device_load_failed.emit(serial, str(e))

                # 更新詳細信息加載進度
                if loaded_count % max(1, len(self.device_serials) // 5) == 0:
                    logger.debug(f'Detailed information load progress: {loaded_count}/{len(self.device_serials)}')

            logger.info(f'Detailed information loaded for {loaded_count} device(s)')





class TrackDevicesWorker(QThread):
    """Background thread that follows `adb track-devices` output."""

    device_list_changed = pyqtSignal(list)  # List[Tuple[str, str]] -> (serial, status)
    error_occurred = pyqtSignal(str)

    def __init__(self, command_factory: Optional[Callable[[], List[str]]] = None, parent=None):
        super().__init__(parent)
        self._command_factory = command_factory or (lambda: ['adb', 'track-devices'])
        self._stop_event = threading.Event()
        self._process: Optional[subprocess.Popen] = None
        self._last_emitted_entries: tuple[tuple[str, str], ...] = ()

    def run(self) -> None:  # type: ignore[override]
        self._stop_event.clear()
        while not self.isInterruptionRequested():
            try:
                command = self._command_factory()
                logger.info('Starting adb track-devices listener: %s', command)
                self._process = subprocess.Popen(
                    command,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    bufsize=0,
                )

                stdout_pipe = self._process.stdout
                if stdout_pipe is None:
                    logger.warning('track-devices stdout unavailable; restarting listener')
                    continue

                for snapshot in self._consume_track_stream(stdout_pipe, self._stop_event):
                    if self._stop_event.is_set() or self.isInterruptionRequested():
                        break
                    self._emit_snapshot(snapshot)

                if self._process:
                    self._process.wait(timeout=1)

            except FileNotFoundError:
                self.error_occurred.emit('ADB executable not found for track-devices')
                self._wait_before_retry(5)
            except Exception as exc:
                self.error_occurred.emit(f'track-devices error: {exc}')
                self._wait_before_retry(2)
            finally:
                self._finalize_process()

    def stop(self):
        self._stop_event.set()
        self.requestInterruption()
        self._finalize_process()
        # Wait briefly for thread to exit to prevent crash on Python shutdown
        if self.isRunning():
            if not self.wait(2000):
                logger.warning('TrackDevicesWorker did not stop within timeout')

    def _finalize_process(self) -> None:
        """Terminate the adb process safely and drain remaining stderr output."""
        process = self._process
        self._process = None

        if process is None:
            return

        stderr_output = None

        try:
            # Close stdout first to unblock any pending read() calls in run()
            if process.stdout is not None:
                try:
                    process.stdout.close()
                except Exception:
                    pass

            if process.poll() is None:
                try:
                    process.terminate()
                except Exception:
                    pass

            try:
                _stdout_unused, stderr_output = process.communicate(timeout=1)
            except subprocess.TimeoutExpired:
                try:
                    process.kill()
                except Exception:
                    pass
                try:
                    _stdout_unused, stderr_output = process.communicate(timeout=1)
                except Exception:
                    stderr_output = None
            except Exception:
                stderr_output = None
        except Exception:
            stderr_output = None

        if stderr_output:
            if isinstance(stderr_output, bytes):
                stderr_text = stderr_output.decode('utf-8', errors='replace').strip()
            else:
                stderr_text = str(stderr_output).strip()
            if stderr_text:
                logger.warning('track-devices stderr: %s', stderr_text)

    @staticmethod
    def _consume_track_stream(stream: IO[bytes], stop_event: Optional[threading.Event] = None):
        """Yield device status snapshots from an adb track-devices byte stream."""
        while True:
            if stop_event is not None and stop_event.is_set():
                break

            header = stream.read(4)
            if not header or len(header) < 4:
                break

            try:
                chunk_len = int(header.decode('ascii'), 16)
            except ValueError:
                logger.debug('Unexpected track-devices chunk header: %r', header)
                continue

            if chunk_len == 0:
                yield OrderedDict()
                continue

            payload = TrackDevicesWorker._read_exact(stream, chunk_len, stop_event)
            if not payload or len(payload) < chunk_len:
                break

            snapshot = TrackDevicesWorker._parse_track_payload(payload.decode('utf-8', errors='replace'))
            yield snapshot

    @staticmethod
    def _read_exact(stream: IO[bytes], size: int, stop_event: Optional[threading.Event] = None) -> Optional[bytes]:
        """Read exactly *size* bytes unless the stream ends or stop is requested."""
        data = bytearray()
        while len(data) < size:
            if stop_event is not None and stop_event.is_set():
                break
            chunk = stream.read(size - len(data))
            if not chunk:
                break
            data.extend(chunk)
        return bytes(data)

    @staticmethod
    def _parse_track_payload(payload_text: str) -> OrderedDict[str, str]:
        """Convert a payload block into an ordered serial->status mapping."""
        snapshot: OrderedDict[str, str] = OrderedDict()
        for raw_line in payload_text.splitlines():
            line = raw_line.strip()
            if not line or line.startswith('List of devices attached'):
                continue

            parts = line.split()
            if not parts:
                continue

            serial = parts[0].strip()
            status = parts[1].strip() if len(parts) > 1 else ''

            if serial in snapshot:
                snapshot.pop(serial)
            snapshot[serial] = status

        return snapshot

    def _emit_from_buffer(self, buffer: List[str]):
        snapshot = OrderedDict[str, str]()
        for entry in buffer:
            parts = entry.split()
            if not parts:
                continue
            serial = parts[0]
            status = parts[1] if len(parts) > 1 else ''
            if serial in snapshot:
                snapshot.pop(serial)
            snapshot[serial] = status

        self._emit_snapshot(snapshot)

    def _emit_snapshot(self, snapshot: OrderedDict[str, str]):
        if not snapshot:
            if self._last_emitted_entries:
                self._emit_entries([])
            return

        entries = list(snapshot.items())
        self._emit_entries(entries)

    def _emit_entries(self, entries: List[tuple[str, str]]):
        normalized = tuple(sorted(entries))
        if normalized == self._last_emitted_entries:
            return
        logger.info('track-devices entries: %s', entries)
        self._last_emitted_entries = normalized
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
    unauthorized_devices_detected = pyqtSignal(list)  # list of unauthorized serial numbers

    def __init__(self, parent=None, tracker_factory: Optional[Callable[[], Optional[TrackDevicesWorker]]] = None):
        super().__init__(parent)
        self.device_cache: Dict[str, adb_models.DeviceInfo] = {}
        self.device_progress: Dict[str, DeviceLoadProgress] = {}
        self.last_discovered_serials: Optional[Set[str]] = None
        self.worker: Optional[AsyncDeviceWorker] = None
        self.device_tracker_thread: Optional[TrackDevicesWorker] = None
        self._tracker_factory = tracker_factory or (lambda: TrackDevicesWorker(parent=self))
        self.tracked_device_statuses: Dict[str, str] = {}
        self._serial_aliases: Dict[str, str] = {}
        self._unauthorized_serials: Set[str] = set()  # Track unauthorized devices
        self._shutting_down = False
        self._pending_discovery: Optional[tuple[bool, bool, Optional[List[str]]]] = None
        self._pending_discovery_timer = QTimer(self)
        self._pending_discovery_timer.setSingleShot(True)
        self._pending_discovery_timer.timeout.connect(self._process_pending_discovery)

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
        tracker_thread: Optional[TrackDevicesWorker] = None

        if self._tracker_factory:
            try:
                tracker_thread = self._tracker_factory()
            except Exception as exc:
                logger.error(f'Failed to create device tracker worker: {exc}')
                tracker_thread = None

        if tracker_thread is None:
            logger.info('Device tracker not started (factory returned None)')
            return

        self.device_tracker_thread = tracker_thread
        self.device_tracker_thread.device_list_changed.connect(self._on_tracked_devices_changed)
        self.device_tracker_thread.error_occurred.connect(
            lambda msg: logger.warning(f'Device tracker warning: {msg}')
        )
        self.device_tracker_thread.start()

    @staticmethod
    def _normalize_status(status: Optional[str]) -> str:
        return (status or '').strip().lower()

    def start_device_discovery(self, force_reload: bool = False, load_detailed: bool = True, serials: Optional[List[str]] = None):
        """開始異步設備發現"""
        if self._shutting_down:
            logger.debug('Discovery request ignored during shutdown')
            return

        logger.info('Starting async device discovery')

        if self.worker and self.worker.isRunning():
            logger.info('Discovery already in progress; queuing another run')
            serials_copy = list(serials) if serials else None
            self._pending_discovery = (force_reload, load_detailed, serials_copy)
            self._pending_discovery_timer.start(200)
            return

        self._pending_discovery = None
        self._start_device_discovery_internal(force_reload, load_detailed, serials)

    def _start_device_discovery_internal(self, force_reload: bool, load_detailed: bool, serials: Optional[List[str]]):
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

            # 創建工作線程並設定狀態檢查器，避免對離線設備發送命令
            self.worker = AsyncDeviceWorker(status_checker=self._is_device_tracked)
            self.worker.set_devices(basic_device_serials, load_detailed, refresh_only=False)

            # 連接信號（漸進式版）
            self.worker.device_basic_loaded.connect(self._on_device_basic_loaded)
            self.worker.device_detailed_loaded.connect(self._on_device_detailed_loaded)
            self.worker.device_load_failed.connect(self._on_device_load_failed)
            self.worker.progress_updated.connect(self._on_progress_updated)
            self.worker.all_basic_loaded.connect(self._on_all_basic_loaded)
            self.worker.all_detailed_loaded.connect(self._on_all_detailed_loaded)
            self.worker.all_detailed_loaded.connect(self._on_worker_completed)

            # 啟動工作線程池任務
            self.worker.start_loading()

        except ADBCommandError as exc:
            self._handle_device_enumeration_failure(exc)
        except Exception as e:
            logger.error(f'Failed to start device discovery: {e}')

    def stop_current_loading(self):
        """停止當前的加載過程"""
        if self.worker:
            logger.info('Stopping current device loading process')
            self.worker.request_stop()

    def _run_adb_devices_command(self) -> subprocess.CompletedProcess[str]:
        """Execute `adb devices -l` and bubble up detailed failures."""
        command_str = adb_commands.cmd_get_adb_devices()
        command_parts = shlex.split(command_str)
        logger.debug('Executing adb devices command: %s', command_parts)

        try:
            completed = subprocess.run(
                command_parts,
                capture_output=True,
                text=True,
                check=False,
            )
        except Exception as exc:
            logger.error('Failed to execute adb devices: %s', exc)
            raise ADBCommandError(str(exc)) from exc

        stderr_output = (completed.stderr or '').strip()
        if completed.returncode != 0:
            message = stderr_output or f'adb devices exited with code {completed.returncode}'
            logger.error('adb devices command failed: %s', message)
            raise ADBCommandError(message)

        if stderr_output:
            logger.debug('adb devices stderr: %s', stderr_output)

        return completed

    def _enumerate_adb_devices(self) -> List[tuple[str, str]]:
        """Run adb devices -l and return (serial, status) tuples."""
        completed = self._run_adb_devices_command()
        entries: List[tuple[str, str]] = []

        for raw_line in completed.stdout.splitlines():
            line = raw_line.strip()
            if not line or line.startswith('*') or line.startswith('List of devices attached'):
                continue
            parts = line.split()
            if not parts:
                continue
            serial = parts[0].strip()
            status = self._normalize_status(parts[1] if len(parts) > 1 else '')
            if serial:
                entries.append((serial, status))

        return entries

    def _get_basic_device_serials(self) -> List[str]:
        """快速獲取設備序號列表"""
        entries = self._enumerate_adb_devices()
        valid_statuses = BASIC_ACCEPTED_STATUSES

        device_serials = [serial for serial, status in entries if not status or status in valid_statuses]
        logger.debug('Enumerated %d device serial(s)', len(device_serials))
        return device_serials

    def _ensure_aliases_via_devices(self, candidate_serials: Set[str]):
        """Ensure aliases from track-devices map to real serials using adb devices -l output."""
        unresolved = {
            serial for serial in candidate_serials
            if serial and serial not in self._serial_aliases
            and serial not in self.device_cache
            and serial not in self.tracked_device_statuses
            and (self.last_discovered_serials is None or serial not in self.last_discovered_serials)
        }

        if not unresolved:
            return

        try:
            entries = self._enumerate_adb_devices()
        except ADBCommandError as exc:
            logger.warning('Failed to refresh aliases via adb devices: %s', exc)
            return

        real_serials = [serial for serial, status in entries]
        if not real_serials:
            return

        logger.debug('Attempting alias resolution for: %s', sorted(unresolved))
        for alias in unresolved:
            for real in real_serials:
                if alias.endswith(real) or real.endswith(alias) or real in alias or alias in real:
                    self._serial_aliases[alias] = real
                    logger.debug('Mapped alias %s -> %s via adb devices -l', alias, real)
                    break

    def _handle_device_enumeration_failure(self, error: Exception):
        """Handle adb enumeration failures without clearing cached devices."""
        logger.warning(
            'Device enumeration failed (%s); preserving %d cached device(s)',
            error,
            len(self.device_cache),
        )

        if self.device_cache:
            self.basic_devices_ready.emit(self.device_cache.copy())

        if self._pending_discovery is None:
            self._pending_discovery = (True, True, None)
        if not self._pending_discovery_timer.isActive():
            # Retry enumeration shortly to recover once adb becomes available again
            self._pending_discovery_timer.start(1000)

    def _normalize_tracker_serial(self, serial: str) -> str:
        sanitized = (serial or '').strip()
        if not sanitized:
            return ''

        if sanitized in self._serial_aliases:
            return self._serial_aliases[sanitized]

        known_serials = set(self.device_cache.keys())
        known_serials.update(self.tracked_device_statuses.keys())
        if self.last_discovered_serials:
            known_serials.update(self.last_discovered_serials)

        if sanitized in known_serials:
            return sanitized

        if len(sanitized) > 4:
            prefix = sanitized[:4]
            if all(char in '0123456789abcdefABCDEF' for char in prefix):
                candidate = sanitized[4:]
                if candidate in known_serials:
                    self._serial_aliases[sanitized] = candidate
                    logger.debug('Normalized tracker alias %s -> %s', sanitized, candidate)
                    return candidate

        return sanitized

    def _purge_aliases_for_serial(self, serial: str):
        if not serial:
            return
        to_remove = [alias for alias, target in self._serial_aliases.items() if target == serial or alias == serial]
        for alias in to_remove:
            self._serial_aliases.pop(alias, None)

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

            audio_state = detailed_info.get('audio_state')
            if audio_state:
                device_info.audio_state = audio_state

            bt_manager_state = detailed_info.get('bluetooth_manager_state')
            if bt_manager_state:
                device_info.bluetooth_manager_state = bt_manager_state

            # 發送更新信號
            self.device_detailed_loaded.emit(serial, device_info)

        # 更新進度
        if serial in self.device_progress:
            self.device_progress[serial].status = DeviceLoadStatus.FULLY_LOADED
            self.device_progress[serial].detailed_info = detailed_info

    def _on_all_basic_loaded(self):
        """所有設備基本信息加載完成"""
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
        self._serial_aliases.clear()
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

    def _refresh_device_details_for_known_devices(self, serials: List[str]):
        """使用 refresh worker 更新已知設備的詳細資訊"""
        unique_serials = [serial for serial in serials if serial]
        if not unique_serials:
            logger.debug('Skipping detail refresh with empty serial list')
            return
        if self.worker and self.worker.isRunning():
            logger.debug('Skipping detail refresh while another worker is running')
            return

        logger.debug('Refreshing detailed information for %s cached device(s)', len(unique_serials))
        self.worker = AsyncDeviceWorker(status_checker=self._is_device_tracked)
        self.worker.set_devices(unique_serials, load_detailed=True, refresh_only=True)
        self.worker.device_detailed_loaded.connect(self._on_device_detailed_loaded)
        self.worker.device_load_failed.connect(self._on_device_load_failed)
        self.worker.progress_updated.connect(self._on_progress_updated)
        self.worker.all_detailed_loaded.connect(self._on_all_detailed_loaded)
        self.worker.all_detailed_loaded.connect(self._on_worker_completed)
        self.worker.start_loading()

    def _periodic_refresh(self):
        """定時刷新回調"""
        # 如果有工作線程正在運行，跳過這次刷新避免衝突
        if self.worker and self.worker.isRunning():
            logger.info('Skipping periodic refresh while devices are loading to avoid interruption')
            return

        known_serials = sorted(self.device_cache.keys())
        self.refresh_cycle_count += 1

        if not known_serials:
            logger.info('Periodic refresh cycle %s found no cached devices; running discovery', self.refresh_cycle_count)
            try:
                self.start_device_discovery(force_reload=True, load_detailed=True)
            except Exception as e:
                logger.error(f'Periodic refresh failed: {e}')
            return

        logger.debug('Periodic refresh cycle %s updating %s cached device(s)', self.refresh_cycle_count, len(known_serials))
        self._refresh_device_details_for_known_devices(known_serials)

    def cleanup(self):
        """清理資源"""
        self._shutting_down = True
        self._pending_discovery = None
        self._pending_discovery_timer.stop()
        self.stop_periodic_refresh()
        self.stop_current_loading()
        self.clear_cache()
        if self.device_tracker_thread:
            self.device_tracker_thread.stop()
            # stop() already waits up to 2 seconds, no need to wait again
        self.device_tracker_thread = None
        self.worker = None

    def _process_pending_discovery(self):
        if self._shutting_down:
            logger.debug('Skipping pending discovery during shutdown')
            self._pending_discovery = None
            return

        if self.worker and self.worker.isRunning():
            logger.debug('Discovery still running; rescheduling pending request')
            self._pending_discovery_timer.start(200)
            return

        if not self._pending_discovery:
            return

        force_reload, load_detailed, serials = self._pending_discovery
        self._pending_discovery = None
        self._start_device_discovery_internal(force_reload, load_detailed, serials)

    def _on_worker_completed(self):
        self.worker = None
        if self._pending_discovery and not self._shutting_down:
            self._pending_discovery_timer.start(0)

    def _on_tracked_devices_changed(self, entries: List[tuple[str, str]]):
        """Handle change events from adb track-devices."""
        if self._shutting_down:
            logger.debug('Ignoring tracker update during shutdown')
            return
        raw_serials: Set[str] = set()
        for serial, _status in entries:
            raw_serial = (serial or '').strip()
            if raw_serial:
                raw_serials.add(raw_serial)

        if raw_serials:
            self._ensure_aliases_via_devices(raw_serials)

        previous_serials = set(self.tracked_device_statuses.keys())
        last_status_map: Dict[str, str] = {}
        status_history: Dict[str, Set[str]] = {}

        for serial, status in entries:
            raw_serial = (serial or '').strip()
            if not raw_serial:
                continue
            normalized_serial = self._normalize_tracker_serial(raw_serial)
            status_normalized = self._normalize_status(status)
            last_status_map[normalized_serial] = status_normalized
            status_history.setdefault(normalized_serial, set()).add(status_normalized)

            if normalized_serial != raw_serial and raw_serial not in self._serial_aliases:
                self._serial_aliases[raw_serial] = normalized_serial

        current_serials = set(last_status_map.keys())

        # Use final status (last_status_map) to determine removal, not historical statuses.
        # This prevents false removal when device quickly reconnects (offline -> device).
        removal_candidates = {
            serial for serial, status in last_status_map.items()
            if status in TRACKER_REMOVAL_STATUSES
        }
        missing_serials = previous_serials - current_serials
        removed_serials = removal_candidates | missing_serials

        # Refresh tracked status cache excluding removed devices and non-ready states
        self.tracked_device_statuses = {
            serial: status
            for serial, status in last_status_map.items()
            if status in TRACKER_READY_STATUSES and serial not in removed_serials
        }

        # Detect unauthorized devices and emit signal if changed
        current_unauthorized = {
            serial for serial, status in last_status_map.items()
            if status == ADBConstants.DEVICE_STATE_UNAUTHORIZED
            and serial not in removed_serials
        }
        if current_unauthorized != self._unauthorized_serials:
            self._unauthorized_serials = current_unauthorized
            if current_unauthorized:
                logger.warning(
                    'Unauthorized devices detected: %s',
                    sorted(current_unauthorized)
                )
                self.unauthorized_devices_detected.emit(sorted(current_unauthorized))

        ready_serials = set(self.tracked_device_statuses.keys())

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
            self._purge_aliases_for_serial(serial)

        if removal_detected:
            logger.info('Device tracker removed devices: %s', sorted(removed_serials))
            self.basic_devices_ready.emit(self.device_cache.copy())

        need_refresh = removal_detected
        new_candidates = {
            serial for serial, statuses in status_history.items()
            if (
                statuses & TRACKER_READY_STATUSES
                and serial not in previous_serials
                and (self.last_discovered_serials is None or serial not in self.last_discovered_serials)
            )
        }
        if new_candidates:
            logger.debug('Device tracker reports potential new devices: %s', sorted(new_candidates))
            need_refresh = True
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

    def _is_device_tracked(self, serial: str) -> bool:
        """檢查設備是否仍被追蹤且視為可用"""
        status = self.tracked_device_statuses.get(serial)
        if status is not None:
            return status in TRACKER_READY_STATUSES

        if self.last_discovered_serials is None:
            return True

        return serial in self.last_discovered_serials

    def get_unauthorized_serials(self) -> List[str]:
        """Return list of currently unauthorized device serials."""
        return sorted(self._unauthorized_serials)

    def is_device_unauthorized(self, serial: str) -> bool:
        """Check if a specific device is in unauthorized state."""
        return serial in self._unauthorized_serials
