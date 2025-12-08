"""設備操作管理器 - 負責管理所有設備相關操作

這個模組將所有設備操作邏輯從主窗口中分離出來，提供：
1. 設備控制操作（重啟、藍牙控制等）
2. 媒體操作（截圖、錄屏等）
3. 應用程序操作（安裝APK、啟動工具等）
4. 設備狀態管理
5. 錯誤處理和日誌記錄

重構目標：
- 減少主窗口類的複雜度
- 提高設備操作邏輯的可重用性
- 統一設備操作的錯誤處理
- 改善代碼組織結構
"""

import os
import subprocess
import time
from typing import Dict, List, Any, Optional, Callable

from PyQt6.QtCore import (
    QTimer,
    pyqtSignal,
    QObject,
    QMetaObject,
    Qt,
    Q_ARG,
    Q_RETURN_ARG,
    pyqtSlot,
)
from PyQt6.QtWidgets import QFileDialog, QMessageBox

from utils import adb_models, adb_tools, common, adb_commands
from utils.recording_utils import RecordingManager
from utils.screenshot_utils import take_screenshots_batch
from ui.ui_inspector_dialog import UIInspectorDialog
from utils.ui_inspector_utils import check_ui_inspector_prerequisites
from utils.task_dispatcher import TaskContext, TaskHandle, get_task_dispatcher


class DeviceOperationsManager(QObject):
    """設備操作管理器類 - 負責所有設備相關操作"""

    # 信號定義
    recording_stopped_signal = pyqtSignal(str, str, float, str, str)  # device_name, device_serial, duration, filename, output_path
    recording_state_cleared_signal = pyqtSignal(str)  # device_serial
    screenshot_completed_signal = pyqtSignal(str, int, list)  # output_path, device_count, device_models
    operation_completed_signal = pyqtSignal(str, str, bool, str)  # operation, device_serial, success, message

    def __init__(self, parent_window=None):
        super().__init__()
        self.parent_window = parent_window
        self.logger = common.get_logger('device_operations_manager')
        self._dispatcher = get_task_dispatcher()
        self._active_task_handles: List[TaskHandle] = []

        # 設備狀態管理
        self.device_recordings: Dict[str, Dict] = {}
        self.device_operations: Dict[str, str] = {}

        # 錄製管理器
        self.recording_manager = RecordingManager()

        # 錄製狀態更新定時器
        self.recording_timer = QTimer()
        self.recording_timer.timeout.connect(self.update_recording_status)
        self.recording_timer.start(500)

    # ===== 設備控制操作 =====

    def reboot_device(self, device_serials: List[str] = None, reboot_mode: str = "system") -> bool:
        """重啟設備

        Args:
            device_serials: 設備序列號列表，如果為None則使用選中的設備
            reboot_mode: 重啟模式 ("system", "recovery", "bootloader")
        """
        if device_serials is None:
            device_serials = self._get_selected_device_serials()

        if not device_serials:
            self._show_warning("No Device Selected", "Please select at least one device to reboot.")
            return False

        return self._run_device_tasks(
            'reboot',
            device_serials,
            lambda serial, **kwargs: self._reboot_device_task(serial, reboot_mode=reboot_mode, **kwargs),
            summary_title='Reboot',
            success_message_builder=lambda success, total: f'Reboot command sent to {success}/{total} device(s).',
            failure_message='Failed to send reboot command to any device.',
            partial_message_builder=lambda failures: f'Failed to reboot: {", ".join(failures)}',
        )

    def reboot_single_device(self, device_serial: str, reboot_mode: str = "system") -> bool:
        """重啟單個設備"""
        return self.reboot_device([device_serial], reboot_mode)

    def enable_bluetooth(self, device_serials: List[str] = None) -> bool:
        """啟用設備藍牙"""
        return self._toggle_bluetooth(device_serials, True)

    def disable_bluetooth(self, device_serials: List[str] = None) -> bool:
        """禁用設備藍牙"""
        return self._toggle_bluetooth(device_serials, False)

    def _toggle_bluetooth(self, device_serials: List[str] = None, enable: bool = True) -> bool:
        """切換設備藍牙狀態"""
        if device_serials is None:
            device_serials = self._get_selected_device_serials()

        if not device_serials:
            action = "enable" if enable else "disable"
            self._show_warning("No Device Selected", f"Please select at least one device to {action} Bluetooth.")
            return False

        action_text = "enable" if enable else "disable"
        status_text = "enabled" if enable else "disabled"

        return self._run_device_tasks(
            'bluetooth',
            device_serials,
            lambda serial, **kwargs: self._toggle_bluetooth_task(serial, enable=enable, **kwargs),
            summary_title='Bluetooth Operation',
            success_message_builder=lambda success, total: f'Bluetooth {status_text} on {success}/{total} device(s).',
            failure_message=f'Failed to {action_text} Bluetooth on any device.',
            partial_message_builder=lambda failures: f'Failed to {action_text} Bluetooth on: {", ".join(failures)}',
        )

    # ===== 媒體操作 =====

    def take_screenshot(self, device_serials: List[str] = None, output_path: str = None,
                       callback: Callable = None) -> bool:
        """批量截圖"""
        if device_serials is None:
            device_serials = self._get_selected_device_serials()

        if not device_serials:
            self._show_warning("No Device Selected", "Please select at least one device to take screenshots.")
            return False

        # 獲取輸出路徑
        if output_path is None:
            output_path = self._get_output_path()
            if not output_path:
                return False

        context = TaskContext(name='screenshot', category='screenshot')
        handle = self._dispatcher.submit(
            self._screenshot_task,
            device_serials,
            output_path=output_path,
            context=context,
        )

        def _on_completed(payload: Any) -> None:
            success, _ = self._coerce_task_result(payload)
            device_models = payload.get('device_models', []) if isinstance(payload, dict) else []
            if success:
                self.screenshot_completed_signal.emit(output_path, len(device_serials), device_models)
                if callback:
                    callback(output_path, len(device_serials), device_models)
            else:
                self._log_console('❌ Screenshot operation failed')

        def _on_failed(exc: Exception) -> None:
            self._log_console(f"❌ Screenshot task failed: {exc}")

        handle.completed.connect(_on_completed)
        handle.failed.connect(_on_failed)
        self._track_task_handle(handle)
        return True

    def take_screenshot_single_device(self, device_serial: str, output_path: str = None) -> bool:
        """單設備截圖"""
        return self.take_screenshot([device_serial], output_path)

    def start_screen_record(self, device_serials: List[str] = None, output_path: str = None,
                          duration: int = 30, callback: Callable = None) -> bool:
        """開始屏幕錄製"""
        if device_serials is None:
            device_serials = self._get_selected_device_serials()

        if not device_serials:
            self._show_warning("No Device Selected", "Please select at least one device to start recording.")
            return False

        # 獲取輸出路徑
        if output_path is None:
            output_path = self._get_output_path()
            if not output_path:
                return False

        duplicates = [serial for serial in device_serials if serial in self.device_recordings]
        if duplicates:
            self._show_warning(
                "Already Recording",
                "\n".join([f"Device {serial} is already recording." for serial in duplicates])
            )

        serials_to_start = [serial for serial in device_serials if serial not in self.device_recordings]
        if not serials_to_start:
            return False

        def _result_handler(serial: str, payload: Any) -> None:
            success, _ = self._coerce_task_result(payload)
            device_info = self._get_device_info(serial)
            device_name = device_info.device_model if device_info else serial
            if success and isinstance(payload, dict):
                recording_info = {
                    'start_time': payload.get('start_time', time.time()),
                    'duration': payload.get('duration', duration),
                    'filename': payload.get('filename'),
                    'output_path': payload.get('output_path', output_path),
                }
                self.device_recordings[serial] = recording_info
                self._log_console(f"🎬 Started recording on {device_name} ({serial})")
                self.operation_completed_signal.emit("recording_start", serial, True, "Recording started")
                if callback:
                    callback(
                        device_name,
                        serial,
                        recording_info['duration'],
                        recording_info['filename'],
                        recording_info['output_path'],
                    )
            else:
                message = ''
                if isinstance(payload, dict):
                    message = payload.get('message', '')
                self._log_console(f"❌ Failed to start recording on device {serial}: {message}")
                self.operation_completed_signal.emit("recording_start", serial, False, message or 'Failed to start recording')

        return self._run_device_tasks(
            'recording_start',
            serials_to_start,
            lambda serial, **kwargs: self._start_recording_task(serial, output_path=output_path, duration=duration, **kwargs),
            summary_title='Recording Started',
            success_message_builder=lambda success, total: f'Started recording on {success}/{total} device(s).',
            failure_message='Failed to start recording on any device.',
            partial_message_builder=lambda failures: f'Failed to start recording on: {", ".join(failures)}',
            result_handler=_result_handler,
        )

    def stop_screen_record(self, device_serials: List[str] = None) -> bool:
        """停止屏幕錄製"""
        if device_serials is None:
            # 如果沒有指定設備，停止所有正在錄製的設備
            device_serials = list(self.device_recordings.keys())

        if not device_serials:
            self._show_warning("No Active Recordings", "No active recordings to stop.")
            return False

        active_serials = [serial for serial in device_serials if serial in self.device_recordings]
        if not active_serials:
            self._show_warning("No Active Recordings", "No active recordings to stop.")
            return False

        def _result_handler(serial: str, payload: Any) -> None:
            success, _ = self._coerce_task_result(payload)
            device_info = self._get_device_info(serial)
            device_name = device_info.device_model if device_info else serial
            recording_info = self.device_recordings.get(serial)

            if success and isinstance(payload, dict):
                info = payload.get('recording_info', recording_info) or {}
                start_time = info.get('start_time', time.time())
                duration = time.time() - start_time
                filename = info.get('filename', '')
                output_path = info.get('output_path', '')

                self.recording_stopped_signal.emit(
                    device_name,
                    serial,
                    duration,
                    filename,
                    output_path,
                )
                self.device_recordings.pop(serial, None)
                self._log_console(f"⏹️ Stopped recording on {device_name} ({serial})")
                self.operation_completed_signal.emit("recording_stop", serial, True, "Recording stopped")
            else:
                message = ''
                if isinstance(payload, dict):
                    message = payload.get('message', '')
                self._log_console(f"❌ Failed to stop recording on device {serial}: {message}")
                self.operation_completed_signal.emit("recording_stop", serial, False, message or 'Failed to stop recording')

        return self._run_device_tasks(
            'recording_stop',
            active_serials,
            lambda serial, **kwargs: self._stop_recording_task(
                serial,
                recording_info=self.device_recordings.get(serial, {}).copy(),
                **kwargs,
            ),
            summary_title='Recording Stopped',
            success_message_builder=lambda success, total: f'Stopped recording on {success}/{total} device(s).',
            failure_message='Failed to stop recording on any device.',
            partial_message_builder=lambda failures: f'Failed to stop recording on: {", ".join(failures)}',
            result_handler=_result_handler,
        )

    def update_recording_status(self):
        """更新錄製狀態（定時調用）"""
        current_time = time.time()
        completed_recordings = []

        for serial, recording_info in self.device_recordings.items():
            elapsed_time = current_time - recording_info['start_time']

            # 檢查是否超過預定時間
            if elapsed_time >= recording_info['duration']:
                completed_recordings.append(serial)

        # 處理完成的錄製
        for serial in completed_recordings:
            self._handle_recording_completion(serial)

    def _handle_recording_completion(self, serial: str):
        """處理錄製完成"""
        if serial in self.device_recordings:
            recording_info = self.device_recordings[serial]
            duration = time.time() - recording_info['start_time']

            device_info = self._get_device_info(serial)
            device_name = device_info.device_model if device_info else serial

            # 發送錄製停止信號
            self.recording_stopped_signal.emit(
                device_name,
                serial,
                duration,
                recording_info['filename'],
                recording_info['output_path']
            )

            self._log_console(f"✅ Recording completed on {device_name} ({serial})")

    def clear_device_recording(self, serial: str):
        """清除設備錄製狀態"""
        if serial in self.device_recordings:
            del self.device_recordings[serial]
            self.recording_state_cleared_signal.emit(serial)
            self._log_console(f"🗑️ Cleared recording state for device {serial}")

    # ===== 應用程序操作 =====

    def install_apk(self, device_serials: List[str] = None, apk_file: str = None) -> bool:
        """安裝APK到設備"""
        if device_serials is None:
            device_serials = self._get_selected_device_serials()

        if not device_serials:
            self._show_warning("No Device Selected", "Please select at least one device to install APK.")
            return False

        # 選擇APK文件
        if apk_file is None:
            apk_file, _ = QFileDialog.getOpenFileName(
                self.parent_window,
                "Select APK file",
                "",
                "APK files (*.apk);;All files (*)"
            )

        if not apk_file:
            return False

        apk_name = os.path.basename(apk_file)
        self._log_console(f"📱 Installing {apk_name} on {len(device_serials)} device(s)...")

        return self._run_device_tasks(
            'apk_install',
            device_serials,
            lambda serial, **kwargs: self._install_apk_task(serial, apk_file=apk_file, apk_name=apk_name, **kwargs),
            summary_title='APK Installation',
            success_message_builder=lambda success, total: f'Successfully installed {apk_name} on {success}/{total} device(s).',
            failure_message=f'Failed to install {apk_name} on any device.',
            partial_message_builder=lambda failures: f'Failed to install {apk_name} on: {", ".join(failures)}',
            extra_kwargs_factory=lambda serial, index, total: {
                'position': index,
                'total': total,
            },
        )

    def launch_scrcpy(self, device_serials: List[str] = None) -> bool:
        """啟動scrcpy工具"""
        if device_serials is None:
            device_serials = self._get_selected_device_serials()

        if not device_serials:
            self._show_warning("No Device Selected", "Please select at least one device to launch scrcpy.")
            return False

        if not self._check_scrcpy_available():
            return False

        return self._run_device_tasks(
            'scrcpy',
            device_serials,
            lambda serial, **kwargs: self._scrcpy_task(serial, **kwargs),
            summary_title='scrcpy Launch',
            success_message_builder=lambda success, total: f'scrcpy launched for {success}/{total} device(s).',
            failure_message='Failed to launch scrcpy for any device.',
            partial_message_builder=lambda failures: f'Failed to launch scrcpy for: {", ".join(failures)}',
        )

    def launch_scrcpy_single_device(self, device_serial: str) -> bool:
        """為單個設備啟動scrcpy"""
        return self.launch_scrcpy([device_serial])

    def launch_ui_inspector(self, device_serials: List[str] = None) -> bool:
        """啟動UI檢查器"""
        if not self._ensure_ui_inspector_ready():
            return False

        if device_serials is None:
            device_serials = self._get_selected_device_serials()

        if not device_serials:
            self._show_warning("No Device Selected", "Please select at least one device to launch UI Inspector.")
            return False

        return self._run_device_tasks(
            'ui_inspector',
            device_serials,
            self._ui_inspector_task,
            summary_title='UI Inspector',
            success_message_builder=lambda success, total: f'UI Inspector launched for {success}/{total} device(s).',
            failure_message='Failed to launch UI Inspector for any device.',
            partial_message_builder=lambda failures: f'Failed to launch UI Inspector for: {", ".join(failures)}',
        )

    def launch_ui_inspector_for_device(self, device_serial: str) -> bool:
        if not self._ensure_ui_inspector_ready():
            return False
        return self._launch_ui_inspector_for_device_impl(device_serial)

    @pyqtSlot(str, result=bool)
    def _launch_ui_inspector_for_device_slot(self, device_serial: str) -> bool:
        return self._launch_ui_inspector_for_device_impl(device_serial)

    def _launch_ui_inspector_for_device_impl(self, device_serial: str) -> bool:
        """為單個設備啟動UI檢查器"""
        if not self._ensure_ui_inspector_ready():
            return False
        try:
            device_info = self._get_device_info(device_serial)
            device_name = device_info.device_model if device_info else device_serial

            self._log_console(f"🔍 Launching UI Inspector for {device_name} ({device_serial})...")

            dialog = UIInspectorDialog(self.parent_window, device_serial, device_name)
            dialog.show()

            self._log_console(f"✅ UI Inspector launched for {device_name}")
            self.operation_completed_signal.emit("ui_inspector", device_serial, True, "UI Inspector launched")
            return True

        except Exception as e:
            self._log_console(f"❌ Error launching UI Inspector for device {device_serial}: {str(e)}")
            self.operation_completed_signal.emit("ui_inspector", device_serial, False, str(e))
            return False

    def _ensure_ui_inspector_ready(self) -> bool:
        """Check host prerequisites before launching UI Inspector."""
        ready, issue_message = check_ui_inspector_prerequisites()
        if ready:
            return True

        message = issue_message or 'UI Inspector prerequisites not satisfied.'
        sanitized = message.replace('\n', ' | ')
        self._log_console(f"❌ UI Inspector prerequisites failed: {sanitized}")
        self._show_error("UI Inspector Unavailable", message)
        return False

    # ===== 狀態管理和輔助方法 =====

    def get_device_operation_status(self, device_serial: str) -> str:
        """獲取設備操作狀態"""
        if device_serial in self.device_recordings:
            return "recording"
        elif device_serial in self.device_operations:
            return self.device_operations[device_serial]
        else:
            return "idle"

    def get_device_recording_status(self, device_serial: str) -> str:
        """獲取設備錄製狀態"""
        if device_serial in self.device_recordings:
            recording_info = self.device_recordings[device_serial]
            elapsed = time.time() - recording_info['start_time']
            remaining = max(0, recording_info['duration'] - elapsed)
            return f"Recording ({remaining:.0f}s remaining)"
        return ""

    def show_recording_warning(self, device_serial: str):
        """顯示錄製警告"""
        device_info = self._get_device_info(device_serial)
        device_name = device_info.device_model if device_info else device_serial

        self._show_warning(
            "Device Recording",
            f"Device {device_name} ({device_serial}) is currently recording.\n"
            "Some operations may be unavailable during recording."
        )

    # ===== 任務調度輔助方法 =====

    def _track_task_handle(self, handle: TaskHandle) -> None:
        """Keep task handles alive until completion."""

        self._active_task_handles.append(handle)

        def _cleanup(h=handle) -> None:
            try:
                self._active_task_handles.remove(h)
            except ValueError:
                pass

        handle.finished.connect(_cleanup)

    @staticmethod
    def _coerce_task_result(result: Any) -> tuple[bool, str]:
        """Normalize worker results into (success, message)."""

        if isinstance(result, dict):
            return bool(result.get('success', False)), str(result.get('message', ''))
        if isinstance(result, tuple) and len(result) >= 2:
            success, message = result[0], result[1]
            return bool(success), str(message)
        return bool(result), str(result)

    def _run_device_tasks(
        self,
        operation: str,
        device_serials: List[str],
        worker: Callable[..., Any],
        *,
        summary_title: Optional[str] = None,
        success_message_builder: Optional[Callable[[int, int], str]] = None,
        failure_message: Optional[str] = None,
        partial_message_builder: Optional[Callable[[List[str]], str]] = None,
        extra_kwargs_factory: Optional[Callable[[str, int, int], Dict[str, Any]]] = None,
        result_handler: Optional[Callable[[str, Any], None]] = None,
        failure_handler: Optional[Callable[[str, Exception], None]] = None,
    ) -> bool:
        """Dispatch per-device tasks and present aggregated results."""

        if not device_serials:
            self._show_warning("No Device Selected", "Please select at least one device to execute this operation.")
            return False

        total = len(device_serials)
        pending = total
        results: Dict[str, tuple[bool, str]] = {}
        handles: List[TaskHandle] = []

        success_serials: List[str] = []
        failure_serials: List[str] = []

        def finalize() -> None:
            successes = len(success_serials)
            failures = len(failure_serials)
            title = summary_title or operation.replace('_', ' ').title()

            if successes and success_message_builder:
                self._show_info(title, success_message_builder(successes, total))
            elif successes and successes == total:
                self._show_info(title, f'Operation succeeded on {successes}/{total} device(s).')

            if failures:
                if successes == 0:
                    message = failure_message or f'Operation failed on all {total} device(s).'
                    self._show_error(title, message)
                else:
                    if partial_message_builder:
                        message = partial_message_builder(failure_serials)
                    else:
                        message = f'Failed for: {", ".join(failure_serials)}'
                    self._show_warning(title, message)

        def on_completed(serial: str, payload: Any) -> None:
            success, message = self._coerce_task_result(payload)
            results[serial] = (success, message)
            if success:
                success_serials.append(serial)
            else:
                failure_serials.append(serial)
            if result_handler:
                result_handler(serial, payload)

        def on_failed(serial: str, exc: Exception) -> None:
            results[serial] = (False, str(exc))
            failure_serials.append(serial)
            if failure_handler:
                failure_handler(serial, exc)
            else:
                self._log_console(f"❌ {operation} failed for {serial}: {exc}")

        def on_finished(serial: str) -> None:
            nonlocal pending
            if serial not in results:
                results[serial] = (False, 'Cancelled')
                if serial not in failure_serials:
                    failure_serials.append(serial)
            pending -= 1
            if pending == 0:
                finalize()

        for index, serial in enumerate(device_serials, start=1):
            context = TaskContext(name=operation, device_serial=serial, category='device_operation')
            extra_kwargs = extra_kwargs_factory(serial, index, total) if extra_kwargs_factory else {}
            handle = self._dispatcher.submit(
                worker,
                serial,
                position=index,
                total=total,
                context=context,
                **extra_kwargs,
            )
            handle.completed.connect(lambda payload, s=serial: on_completed(s, payload))
            handle.failed.connect(lambda exc, s=serial: on_failed(s, exc))
            handle.finished.connect(lambda s=serial: on_finished(s))
            self._track_task_handle(handle)
            handles.append(handle)

        return True

    # ===== 私有輔助方法 =====

    def _get_selected_device_serials(self) -> List[str]:
        """獲取選中的設備序列號列表"""
        if self.parent_window and hasattr(self.parent_window, 'get_checked_devices'):
            devices = self.parent_window.get_checked_devices()
            return [device.device_serial_num for device in devices]
        return []

    # ===== 任務執行函數 =====

    def _reboot_device_task(self, serial: str, *, reboot_mode: str, task_handle: Optional[TaskHandle] = None, **_: Any) -> Dict[str, Any]:
        command = {
            'recovery': f'-s {serial} reboot recovery',
            'bootloader': f'-s {serial} reboot bootloader',
        }.get(reboot_mode, f'-s {serial} reboot')

        try:
            self._log_console(f"Rebooting device {serial} to {reboot_mode}...")
            result = adb_tools.run_adb_command(command)
            if result.returncode == 0:
                message = f"Reboot command sent to {reboot_mode}"
                self.operation_completed_signal.emit("reboot", serial, True, message)
                return {'success': True, 'message': message}

            error_msg = getattr(result, 'stderr', '') or 'Reboot command failed'
            self._log_console(f"❌ Failed to reboot device {serial}: {error_msg}")
            self.operation_completed_signal.emit("reboot", serial, False, error_msg)
            return {'success': False, 'message': error_msg}

        except Exception as exc:  # pragma: no cover - defensive
            self._log_console(f"❌ Error rebooting device {serial}: {exc}")
            self.operation_completed_signal.emit("reboot", serial, False, str(exc))
            return {'success': False, 'message': str(exc)}

    def _toggle_bluetooth_task(
        self,
        serial: str,
        *,
        enable: bool,
        task_handle: Optional[TaskHandle] = None,
        **_: Any,
    ) -> Dict[str, Any]:
        command = 'shell service call bluetooth_manager 8' if enable else 'shell service call bluetooth_manager 9'
        action_text = 'enable' if enable else 'disable'

        try:
            result = adb_tools.run_adb_command(f'-s {serial} {command}')
            if result.returncode == 0:
                message = f'Bluetooth {"enabled" if enable else "disabled"}'
                self._log_console(f"✅ Bluetooth {action_text}d on device {serial}")
                self.operation_completed_signal.emit("bluetooth", serial, True, message)
                return {'success': True, 'message': message}

            error_msg = getattr(result, 'stderr', '') or 'Bluetooth command failed'
            self._log_console(f"❌ Failed to {action_text} Bluetooth on device {serial}: {error_msg}")
            self.operation_completed_signal.emit("bluetooth", serial, False, error_msg)
            return {'success': False, 'message': error_msg}

        except Exception as exc:  # pragma: no cover
            self._log_console(f"❌ Error {action_text} Bluetooth on device {serial}: {exc}")
            self.operation_completed_signal.emit("bluetooth", serial, False, str(exc))
            return {'success': False, 'message': str(exc)}

    def _install_apk_task(
        self,
        serial: str,
        *,
        apk_file: str,
        apk_name: str,
        position: int,
        total: int,
        task_handle: Optional[TaskHandle] = None,
        **_: Any,
    ) -> Dict[str, Any]:
        device_info = self._get_device_info(serial)
        device_name = device_info.device_model if device_info else serial
        self._log_console(f"📱 [{position}/{total}] Installing on {device_name} ({serial})...")

        try:
            # Show command preview on console
            try:
                preview_cmd = adb_commands.cmd_adb_install(serial, apk_file)
                self._log_console(f"🚀 Executing: {preview_cmd}")
            except Exception:
                pass

            # Use new structured install API with better error handling
            device_info_map = {serial: device_info} if device_info else None
            batch_result = adb_tools.install_apk(
                [serial],
                apk_file,
                validate=False,  # Skip validation for faster installs
                device_info_map=device_info_map,
            )

            install_result = batch_result.results.get(serial)
            if install_result and install_result.success:
                message = f'APK installed: {apk_name}'
                self._log_console(f"✅ [{position}/{total}] Successfully installed on {device_name}")
                self.operation_completed_signal.emit("apk_install", serial, True, message)
                return {
                    'success': True,
                    'message': message,
                    'device_name': device_name,
                }

            # Use structured error message from the result
            if install_result:
                error_msg = install_result.error_message or install_result.raw_output or 'Installation failed'
            else:
                error_msg = 'Installation failed - no result'

            self._log_console(f"❌ [{position}/{total}] Failed to install on {device_name}: {error_msg}")
            self.operation_completed_signal.emit("apk_install", serial, False, error_msg)
            return {'success': False, 'message': error_msg}

        except Exception as exc:  # pragma: no cover
            error_msg = str(exc)
            self._log_console(f"❌ [{position}/{total}] Error installing on device {serial}: {error_msg}")
            self.operation_completed_signal.emit("apk_install", serial, False, error_msg)
            return {'success': False, 'message': error_msg}

    def _scrcpy_task(self, serial: str, *, task_handle: Optional[TaskHandle] = None, **_: Any) -> Dict[str, Any]:
        device_info = self._get_device_info(serial)
        device_name = device_info.device_model if device_info else serial
        cmd = ['scrcpy', '-s', serial]

        try:
            self._log_console(f"🖥️ Launching scrcpy for {device_name} ({serial})...")
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            self._log_console(f"✅ scrcpy launched for {device_name}")
            self.operation_completed_signal.emit("scrcpy", serial, True, "scrcpy launched")
            return {'success': True, 'message': 'scrcpy launched', 'process': process}
        except Exception as exc:
            self._log_console(f"❌ Failed to launch scrcpy for {device_name}: {exc}")
            self.operation_completed_signal.emit("scrcpy", serial, False, str(exc))
            return {'success': False, 'message': str(exc)}

    def _ui_inspector_task(self, serial: str, *, task_handle: Optional[TaskHandle] = None, **_: Any) -> Dict[str, Any]:
        success, result = QMetaObject.invokeMethod(
            self,
            "_launch_ui_inspector_for_device_slot",
            Qt.ConnectionType.BlockingQueuedConnection,
            Q_RETURN_ARG(bool),
            Q_ARG(str, serial)
        )
        if not success:
            return {'success': False, 'message': f'Failed to invoke UI Inspector for {serial}'}
        return {'success': bool(result), 'message': ''}

    def _screenshot_task(
        self,
        serials: List[str],
        *,
        output_path: str,
        task_handle: Optional[TaskHandle] = None,
        **_: Any,
    ) -> Dict[str, Any]:
        devices = self._get_devices_by_serials(serials)
        device_models = [device.device_model for device in devices]

        try:
            success = take_screenshots_batch(serials, output_path)
            return {
                'success': success,
                'message': 'Screenshots captured' if success else 'Screenshot operation failed',
                'device_models': device_models,
            }
        except Exception as exc:  # pragma: no cover
            return {'success': False, 'message': str(exc), 'device_models': device_models}

    def _start_recording_task(
        self,
        serial: str,
        *,
        output_path: str,
        duration: int,
        task_handle: Optional[TaskHandle] = None,
        **_: Any,
    ) -> Dict[str, Any]:
        filename = f'recording_{serial}_{time.strftime("%Y%m%d_%H%M%S")}.mp4'
        start_time = time.time()
        try:
            success = self.recording_manager.start_recording(serial, output_path, filename, duration)
            return {
                'success': success,
                'message': 'Recording started' if success else 'Failed to start recording',
                'filename': filename,
                'output_path': output_path,
                'start_time': start_time,
                'duration': duration,
            }
        except Exception as exc:  # pragma: no cover
            return {'success': False, 'message': str(exc)}

    def _stop_recording_task(
        self,
        serial: str,
        *,
        recording_info: Optional[Dict[str, Any]] = None,
        task_handle: Optional[TaskHandle] = None,
        **_: Any,
    ) -> Dict[str, Any]:
        if recording_info is None:
            return {'success': False, 'message': 'No active recording'}
        try:
            success = self.recording_manager.stop_recording(serial)
            return {
                'success': success,
                'message': 'Recording stopped' if success else 'Failed to stop recording',
                'recording_info': recording_info,
            }
        except Exception as exc:  # pragma: no cover
            return {'success': False, 'message': str(exc), 'recording_info': recording_info}

    def _get_devices_by_serials(self, serials: List[str]) -> List[adb_models.DeviceInfo]:
        """根據序列號獲取設備信息列表"""
        if self.parent_window and hasattr(self.parent_window, 'device_dict'):
            devices = []
            for serial in serials:
                if serial in self.parent_window.device_dict:
                    devices.append(self.parent_window.device_dict[serial])
            return devices
        return []

    def _get_device_info(self, device_serial: str) -> Optional[adb_models.DeviceInfo]:
        """獲取設備信息"""
        if self.parent_window and hasattr(self.parent_window, 'device_dict'):
            return self.parent_window.device_dict.get(device_serial)
        return None

    def _get_output_path(self) -> str:
        """獲取輸出路徑"""
        if self.parent_window and hasattr(self.parent_window, 'get_primary_output_path'):
            path = self.parent_window.get_primary_output_path()
            if path:
                return path

        # 如果上述都未提供路徑，最後回退到檔案對話框
        directory = QFileDialog.getExistingDirectory(
            self.parent_window,
            "Select Output Directory"
        )
        if directory:
            normalized = common.make_gen_dir_path(directory)
            if self.parent_window and hasattr(self.parent_window, 'output_path_manager'):
                self.parent_window.output_path_manager.set_primary_output_path(
                    normalized,
                    sync_generation_if_following=False,
                    update_previous=True,
                )
            elif self.parent_window and hasattr(self.parent_window, 'output_path_edit'):
                self.parent_window.output_path_edit.setText(normalized)
            return normalized
        return ''

    def _check_scrcpy_available(self) -> bool:
        """檢查scrcpy是否可用"""
        try:
            result = subprocess.run(['scrcpy', '--version'],
                                  capture_output=True,
                                  text=True,
                                  timeout=5)
            return result.returncode == 0
        except (subprocess.SubprocessError, subprocess.TimeoutExpired, FileNotFoundError) as e:
            if hasattr(self.parent_window, 'logging_manager'):
                self.parent_window.logging_manager.debug(f'Scrcpy not available: {e}')
            if self.parent_window and hasattr(self.parent_window, 'show_scrcpy_installation_guide'):
                self.parent_window.show_scrcpy_installation_guide()
            else:
                self._show_error("scrcpy Not Found",
                               "scrcpy is not installed or not in PATH.\n"
                               "Please install scrcpy to use this feature.")
            return False

    def _log_console(self, message: str):
        """記錄消息到控制台"""
        self.logger.info(message)
        if self.parent_window and hasattr(self.parent_window, 'write_to_console'):
            self.parent_window.write_to_console(message)

    def _show_info(self, title: str, message: str):
        """顯示信息對話框"""
        if self.parent_window and hasattr(self.parent_window, 'show_info'):
            self.parent_window.show_info(title, message)
        else:
            QMessageBox.information(self.parent_window, title, message)

    def _show_warning(self, title: str, message: str):
        """顯示警告對話框"""
        if self.parent_window and hasattr(self.parent_window, 'show_warning'):
            self.parent_window.show_warning(title, message)
        else:
            QMessageBox.warning(self.parent_window, title, message)

    def _show_error(self, title: str, message: str):
        """顯示錯誤對話框"""
        if self.parent_window and hasattr(self.parent_window, 'show_error'):
            self.parent_window.show_error(title, message)
        else:
            QMessageBox.critical(self.parent_window, title, message)


# 工廠函數
def create_device_operations_manager(parent_window=None) -> DeviceOperationsManager:
    """創建設備操作管理器實例"""
    return DeviceOperationsManager(parent_window)
