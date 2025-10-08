#!/usr/bin/env python3
"""
文件操作管理器 - 處理所有文件生成和導入/導出操作

這個模組負責：
1. 文件生成操作（Android Bug Report、設備發現文件等）
2. 命令歷史的導入/導出
3. UI層級導出
4. DCIM文件夾拉取
5. 文件操作的錯誤處理和進度回調
"""

import os
import threading
from typing import Any, Dict, List, Callable, Optional
from PyQt6.QtCore import QObject, pyqtSignal, QTimer, Qt
from PyQt6.QtWidgets import QFileDialog, QProgressDialog

from utils import adb_models, common, json_utils
from utils.file_generation_utils import (
    BugReportInProgressError,
    generate_bug_report_batch,
    generate_device_discovery_file,
    get_active_bug_report_serials,
    is_bug_report_generation_active,
    validate_file_output_path
)
from utils.task_dispatcher import TaskContext, TaskHandle, get_task_dispatcher


class FileOperationsManager(QObject):
    """文件操作管理器類"""

    # 信號定義
    file_generation_completed_signal = pyqtSignal(str, str, int, str)
    file_generation_progress_signal = pyqtSignal(int, int, str)

    def __init__(self, parent_window):
        super().__init__()
        self.parent_window = parent_window
        self.last_generation_output_path: str = ''
        self.last_generation_summary: str = ''
        self._bug_report_in_progress: bool = False
        self._active_bug_report_devices: list[str] = []
        self._dispatcher = get_task_dispatcher()
        self._active_handles: List[TaskHandle] = []
        self.progress_dialog: Optional[QProgressDialog] = None
        self._bug_report_cancel_event: Optional[threading.Event] = None
        self._bug_report_handle: Optional[TaskHandle] = None
        self._bug_report_per_device: Dict[str, Dict[str, Any]] = {}

    def _track_handle(self, handle: TaskHandle) -> None:
        self._active_handles.append(handle)

        def _cleanup() -> None:
            try:
                self._active_handles.remove(handle)
            except ValueError:
                pass

        handle.finished.connect(_cleanup)

    def _notify_bug_report_in_progress(
        self,
        requested_serials: list[str],
        *,
        active_serials: Optional[list[str]] = None,
        on_failure: Optional[Callable[[str], None]] = None,
    ) -> None:
        """Display a consistent warning for duplicate bug report requests."""
        active = active_serials if active_serials is not None else get_active_bug_report_serials()
        active = list(dict.fromkeys(active))  # preserve order while deduplicating
        overlap = sorted(set(requested_serials) & set(active))

        if overlap:
            devices_text = ', '.join(overlap)
            message = (
                'Bug report generation is already running for the following devices.\n\n'
                f'{devices_text}\n\nPlease wait for the current run to finish or deselect these devices.'
            )
        else:
            active_text = ', '.join(active) if active else 'Unknown'
            message = (
                'Another bug report generation is already running.\n\n'
                f'Active devices: {active_text}\n\nPlease wait for it to finish before starting a new one.'
            )

        self.parent_window.show_warning('Bug Report In Progress', message)
        if on_failure:
            on_failure('Bug report already in progress')

    def _generate_bug_report_task(
        self,
        devices: List[adb_models.DeviceInfo],
        *,
        output_path: str,
        progress_callback: Optional[Callable[[dict], None]] = None,
        cancel_event: Optional[threading.Event] = None,
        task_handle: Optional[TaskHandle] = None,
        **_: Any,
    ) -> Dict[str, Any]:
        result_container: Dict[str, Any] = {
            'summary': '',
            'output_path': output_path,
            'success_count': len(devices),
            'icon': '🐛',
        }

        def callback(operation_name, payload, success_count, icon):
            result_container['summary'] = payload if isinstance(payload, str) else payload.get('summary', '')
            result_container['output_path'] = payload.get('output_path', output_path) if isinstance(payload, dict) else output_path
            result_container['success_count'] = success_count
            result_container['icon'] = icon

        completion_event = threading.Event()

        generate_bug_report_batch(
            devices,
            output_path,
            callback,
            progress_callback=progress_callback,
            completion_event=completion_event,
            cancel_event=cancel_event,
        )

        completion_event.wait()

        return result_container

    def _pull_dcim_task(
        self,
        serials: List[str],
        *,
        output_path: str,
        task_handle: Optional[TaskHandle] = None,
        **_: Any,
    ) -> Dict[str, Any]:
        from utils import adb_tools

        adb_tools.pull_device_dcim_folders_with_device_folder(serials, output_path)
        return {
            'success': True,
            'summary': 'DCIM folders pulled successfully',
            'output_path': output_path,
        }

    def _generate_discovery_file_task(
        self,
        devices: List[adb_models.DeviceInfo],
        *,
        output_path: str,
        task_handle: Optional[TaskHandle] = None,
        **_: Any,
    ) -> Dict[str, Any]:
        result_container: Dict[str, Any] = {
            'summary': '',
            'output_path': output_path,
            'device_count': len(devices),
            'icon': '🔍',
        }

        def callback(operation_name, generated_path, device_count, icon):
            result_container['summary'] = f'{operation_name} completed for {device_count} device(s)'
            result_container['output_path'] = generated_path
            result_container['device_count'] = device_count
            result_container['icon'] = icon

        generate_device_discovery_file(devices, output_path, callback)
        if not result_container['summary']:
            result_container['summary'] = f'Device discovery file generated for {len(devices)} device(s)'
        return result_container

    def _export_hierarchy_task(
        self,
        devices: List[adb_models.DeviceInfo],
        *,
        output_path: str,
        task_handle: Optional[TaskHandle] = None,
        **_: Any,
    ) -> Dict[str, Any]:
        from utils import dump_device_ui

        results: Dict[str, Optional[Exception]] = {}
        os.makedirs(output_path, exist_ok=True)

        for device in devices:
            try:
                dump_device_ui.generate_process(device.device_serial_num, output_path)
                results[device.device_serial_num] = None
            except Exception as exc:  # pragma: no cover - defensive
                results[device.device_serial_num] = exc

        return {'success': True, 'results': results}

    def get_validated_output_path(self, path_text: str) -> Optional[str]:
        """驗證並獲取輸出路徑"""
        validated_path = validate_file_output_path(path_text.strip())
        if not validated_path:
            self.parent_window.show_error(
                'Error',
                'Please select a valid file generation output directory first.'
            )
        return validated_path

    def generate_android_bug_report(
        self,
        devices: List[adb_models.DeviceInfo],
        output_path: str,
        *,
        on_complete: Optional[Callable[[str], None]] = None,
        on_failure: Optional[Callable[[str], None]] = None,
    ) -> bool:
        """生成Android Bug Report"""
        if self._bug_report_in_progress:
            self._notify_bug_report_in_progress(
                [device.device_serial_num for device in devices],
                active_serials=self._active_bug_report_devices,
                on_failure=on_failure,
            )
            return False

        validated_path = self.get_validated_output_path(output_path)
        if not validated_path:
            if on_failure:
                on_failure('Invalid output path')
            return False

        serials = [device.device_serial_num for device in devices]
        if not serials:
            self.parent_window.show_warning('Bug Report', 'No devices selected.')
            if on_failure:
                on_failure('No devices selected')
            return False

        if not self._bug_report_in_progress and is_bug_report_generation_active():
            self._notify_bug_report_in_progress(
                serials,
                on_failure=on_failure,
            )
            return False

        if self._active_bug_report_devices:
            overlapping = set(serials) & set(self._active_bug_report_devices)
            if overlapping:
                self._notify_bug_report_in_progress(
                    serials,
                    active_serials=self._active_bug_report_devices,
                    on_failure=on_failure,
                )
                return False

        device_count = len(devices)
        self.last_generation_output_path = validated_path
        self.last_generation_summary = ''
        self._bug_report_in_progress = True
        self._active_bug_report_devices = serials

        # 顯示進度通知與非阻塞進度對話框
        initial_message = (
            f'🐛 Preparing bug report generation for {device_count} device(s)... '
            f'(Saving to: {validated_path})'
        )
        QTimer.singleShot(0, lambda: self.file_generation_progress_signal.emit(0, device_count, initial_message))

        # 建立進度對話框（初始未知進度 → Busy）
        self._create_bug_report_progress_dialog(total=device_count, message=initial_message)
        # 準備取消事件
        self._bug_report_cancel_event = threading.Event()

        def progress_callback(payload: dict):
            """Bug report 進度更新回調"""
            status_icon = '✅' if payload.get('success') else '❌'
            current = payload.get('current', 0)
            total = payload.get('total', device_count)
            device_model = payload.get('device_model', 'Unknown Device')
            serial = payload.get('device_serial', 'Unknown Serial')
            base_message = (
                f'{status_icon} Bug report {current}/{total}: '
                f'{device_model} ({serial})'
            )

            if not payload.get('success') and payload.get('error_message'):
                base_message = f"{base_message} — {payload['error_message']}"

            # 更新 per-device 進度
            percent = payload.get('percent', None)
            if serial not in self._bug_report_per_device:
                self._bug_report_per_device[serial] = {
                    'model': device_model,
                    'percent': 0,
                    'status': 'running',
                }
            if isinstance(percent, int):
                self._bug_report_per_device[serial]['percent'] = max(0, min(100, percent))
            # 完成或失敗標記
            if payload.get('success') and percent is None:
                self._bug_report_per_device[serial]['percent'] = 100
                self._bug_report_per_device[serial]['status'] = 'success'
            elif (not payload.get('success')) and payload.get('error_message'):
                self._bug_report_per_device[serial]['status'] = 'failed'

            formatted = self._format_bug_report_progress_message(base_message)

            QTimer.singleShot(0, lambda: self.file_generation_progress_signal.emit(current, total, formatted))
            self._update_bug_report_progress(message=formatted, current=current, total=total)

        context = TaskContext(name='bug_report_generation', category='file_generation')

        handle = self._dispatcher.submit(
            self._generate_bug_report_task,
            devices,
            output_path=validated_path,
            progress_callback=progress_callback,
            cancel_event=self._bug_report_cancel_event,
            context=context,
        )
        self._bug_report_handle = handle

        def _on_completed(payload: Dict[str, Any]) -> None:
            summary_text = payload.get('summary', '')
            output_directory = payload.get('output_path', validated_path)
            success_count = payload.get('success_count', len(devices))
            icon = payload.get('icon', '🐛')
            self.last_generation_summary = summary_text
            self.last_generation_output_path = output_directory
            self.file_generation_completed_signal.emit('Bug Report', summary_text, success_count, icon)
            if on_complete:
                on_complete(summary_text)
            self._bug_report_in_progress = False
            self._active_bug_report_devices = []
            # 完成時更新對話框文案並延遲關閉
            final_message = (
                f'{icon} Bug report generation finished.\n\n'
                f'Output: {output_directory}'
            )
            self._update_bug_report_progress(message=final_message, current=success_count, total=device_count)
            QTimer.singleShot(1500, self._close_bug_report_progress_dialog)
            self._bug_report_handle = None
            self._bug_report_cancel_event = None
            self._bug_report_per_device.clear()

        def _on_failed(exc: Exception) -> None:
            self._bug_report_in_progress = False
            self._active_bug_report_devices = []
            if isinstance(exc, BugReportInProgressError):
                self._notify_bug_report_in_progress(serials, on_failure=on_failure)
                return
            QTimer.singleShot(0, lambda: self.parent_window.show_error(
                '🐛 Bug Report Generation Failed',
                f'Failed to generate bug reports.\n\nError: {str(exc)}'
            ))
            if on_failure:
                on_failure(str(exc))
            # 失敗時亦關閉對話框
            QTimer.singleShot(0, self._close_bug_report_progress_dialog)
            self._bug_report_handle = None
            self._bug_report_cancel_event = None
            self._bug_report_per_device.clear()

        handle.completed.connect(_on_completed)
        handle.failed.connect(_on_failed)
        handle.finished.connect(lambda: self.file_generation_progress_signal.emit(device_count, device_count, '🐛 Bug report generation finished'))
        self._track_handle(handle)
        return True

    def _create_bug_report_progress_dialog(self, total: int, message: str) -> None:
        """Create and show a non-blocking progress dialog for bug report generation.

        Starts in Busy mode (setRange(0, 0)); switches to determinate when total > 0.
        """
        try:
            self.progress_dialog = QProgressDialog(
                message,
                "Cancel",
                0,
                max(0, int(total or 0)),
                self.parent_window,
            )
            self.progress_dialog.setWindowTitle("🐛 Bug Report Progress")
            self.progress_dialog.setWindowModality(Qt.WindowModality.WindowModal)
            self.progress_dialog.setMinimumDuration(0)
            self.progress_dialog.setAutoClose(False)
            self.progress_dialog.setAutoReset(False)

            # Busy mode initially (unknown progress)
            self.progress_dialog.setRange(0, 0)

            # Basic styling (consistent with APK dialog)
            self.progress_dialog.setStyleSheet("""
                QProgressDialog { font-size: 12px; min-width: 460px; min-height: 160px; background-color: #111827; color: #e5e7eb; }
                QLabel { color: #e5e7eb; }
                QPushButton { padding: 6px 12px; border: 1px solid #6b7280; border-radius: 4px; background: #374151; color: #e5e7eb; margin-top: 12px; }
                QPushButton:hover { background: #4b5563; }
                QPushButton:pressed { background: #1f2937; }
                QProgressBar { border: 2px solid #3b82f6; border-radius: 6px; text-align: center; font-weight: bold; font-size: 11px; color: #e5e7eb; background: #1f2937; margin-top: 8px; margin-bottom: 14px; }
                QProgressBar::chunk { background-color: #60a5fa; border-radius: 4px; }
            """)

            self.progress_dialog.show()
            try:
                # 當使用者點擊 Cancel 時觸發取消
                self.progress_dialog.canceled.connect(self._cancel_bug_report_generation)  # type: ignore[attr-defined]
            except Exception:
                pass
        except Exception:
            # Defensive: ignore if dialog cannot be created in test/headless environments
            self.progress_dialog = None

    def _update_bug_report_progress(self, message: str, current: int, total: int) -> None:
        """Update the bug report progress dialog.

        - total <= 0 → Busy mode
        - total > 0 → Determinate mode with range 0..total
        """
        if not self.progress_dialog:
            return

        def _update():
            if not self.progress_dialog:
                return
            try:
                if total and total > 0:
                    self.progress_dialog.setRange(0, int(total))
                else:
                    self.progress_dialog.setRange(0, 0)
            except Exception:
                pass

            try:
                self.progress_dialog.setLabelText(message)
            except Exception:
                pass

            try:
                self.progress_dialog.setValue(max(0, int(current)))
            except Exception:
                pass

        QTimer.singleShot(0, _update)

    def _close_bug_report_progress_dialog(self) -> None:
        dlg = getattr(self, 'progress_dialog', None)
        if dlg is not None:
            try:
                dlg.close()
            except Exception:
                pass
        self.progress_dialog = None

    def _cancel_bug_report_generation(self) -> None:
        """Handle user cancellation from the progress dialog."""
        # 設定取消旗標供背景任務察覺
        if self._bug_report_cancel_event is None:
            self._bug_report_cancel_event = threading.Event()
        self._bug_report_cancel_event.set()

        # 嘗試通知 TaskDispatcher 停止傳遞結果
        handle = getattr(self, '_bug_report_handle', None)
        try:
            if handle is not None:
                handle.cancel()
        except Exception:
            pass

        # UI 反饋：切換為 Busy 並顯示取消中文案
        self._update_bug_report_progress('Cancelling bug report generation...', current=0, total=0)

    def _format_bug_report_progress_message(self, base_message: str) -> str:
        """組合每台裝置的進度清單加入訊息之後。"""
        try:
            per_device = getattr(self, '_bug_report_per_device', {}) or {}
        except Exception:
            per_device = {}
        if not per_device:
            return base_message
        lines = [base_message, '', 'Devices progress:']
        # 維持插入順序
        for serial, info in per_device.items():
            model = info.get('model') or serial
            status = info.get('status', 'running')
            percent = max(0, min(100, int(info.get('percent', 0))))
            if status == 'success':
                suffix = '✅ Done'
            elif status == 'failed':
                suffix = '❌ Failed'
            else:
                suffix = f'{percent}%'
            lines.append(f'• {model} ({serial}) — {suffix}')
        return '\n'.join(lines)

    def is_bug_report_in_progress(self) -> bool:
        """Return whether a bug report generation is currently running."""
        return self._bug_report_in_progress

    def get_active_bug_report_devices(self) -> list[str]:
        """Return the serial numbers involved in the active bug report run."""
        return list(self._active_bug_report_devices)

    def generate_device_discovery_file(self, devices: List[adb_models.DeviceInfo], output_path: str):
        """生成設備發現文件"""
        validated_path = self.get_validated_output_path(output_path)
        if not validated_path:
            return

        # 顯示進度通知
        self.parent_window.show_info(
            '🔍 Generating Discovery File',
            f'Extracting device discovery information for {len(devices)} device(s)...\n\n'
            f'📁 Saving to: {validated_path}\n\n'
            f'Please wait...'
        )
        context = TaskContext(name='device_discovery', category='file_generation')
        handle = self._dispatcher.submit(
            self._generate_discovery_file_task,
            devices,
            output_path=validated_path,
            context=context,
        )

        def _on_completed(payload: Dict[str, Any]) -> None:
            summary = payload.get('summary', 'Device discovery file generated')
            self.last_generation_summary = summary
            self.last_generation_output_path = payload.get('output_path', validated_path)
            device_count = payload.get('device_count', len(devices))
            icon = payload.get('icon', '🔍')
            self.file_generation_completed_signal.emit('Device Discovery File', self.last_generation_output_path, device_count, icon)

        def _on_failed(exc: Exception) -> None:
            QTimer.singleShot(0, lambda: self.parent_window.show_error('Discovery File Failed', str(exc)))

        handle.completed.connect(_on_completed)
        handle.failed.connect(_on_failed)
        self._track_handle(handle)

    def pull_device_dcim_folder(self, devices: List[adb_models.DeviceInfo], output_path: str):
        """拉取設備DCIM文件夾"""
        if not output_path:
            self.parent_window.show_error('Error', 'Please select a file generation output directory first.')
            return

        # 驗證和標準化輸出路徑
        if not common.check_exists_dir(output_path):
            normalized_path = common.make_gen_dir_path(output_path)
            if not normalized_path:
                self.parent_window.show_error('Error', 'Invalid file generation output directory path.')
                return
            output_path = normalized_path

        serials = [d.device_serial_num for d in devices]
        device_count = len(devices)

        # 顯示進度通知
        self.parent_window.show_info(
            '📷 Pulling DCIM Folders',
            f'Pulling DCIM folders from {device_count} device(s)...\n\n'
            f'📁 Saving to: {output_path}\n\n'
            f'This may take a while depending on the number of photos/videos...'
        )

        context = TaskContext(name='dcim_pull', category='file_generation')
        handle = self._dispatcher.submit(
            self._pull_dcim_task,
            serials,
            output_path=output_path,
            context=context,
        )

        def _on_completed(payload: Dict[str, Any]) -> None:
            summary = payload.get('summary', 'DCIM folders pulled successfully')
            self.last_generation_summary = summary
            self.last_generation_output_path = payload.get('output_path', output_path)
            self.file_generation_completed_signal.emit('DCIM Folder Pull', self.last_generation_output_path, device_count, '📷')

        def _on_failed(exc: Exception) -> None:
            QTimer.singleShot(0, lambda: self.parent_window.show_error('DCIM Pull Failed', str(exc)))

        handle.completed.connect(_on_completed)
        handle.failed.connect(_on_failed)
        self._track_handle(handle)


class CommandHistoryManager:
    """命令歷史管理器"""

    def __init__(self, parent_window):
        self.parent_window = parent_window
        self.command_history = []
        self._dispatcher = get_task_dispatcher()
        self._active_handles: List[TaskHandle] = []
        self.load_command_history_from_config()

    def _track_handle(self, handle: TaskHandle) -> None:
        self._active_handles.append(handle)

        def _cleanup() -> None:
            try:
                self._active_handles.remove(handle)
            except ValueError:
                pass

        handle.finished.connect(_cleanup)

    def _can_update_ui(self) -> bool:
        """Return True when parent can safely refresh the history list."""
        return (
            hasattr(self.parent_window, 'update_history_display') and
            hasattr(self.parent_window, 'command_history_manager') and
            getattr(self.parent_window, 'command_history_manager') is self
        )

    def _sync_executor_history(self) -> None:
        """Keep the command executor's history aligned with the manager."""
        executor = getattr(self.parent_window, 'command_executor', None)
        if executor is not None:
            executor.set_command_history(self.command_history)

    def set_history(self, history: List[str], *, persist: bool = False) -> None:
        """Replace command history with the provided sequence."""
        normalized = history[-50:] if history else []
        self.command_history = normalized

        if self._can_update_ui():
            self.parent_window.update_history_display()

        self._sync_executor_history()

        if persist:
            self.save_command_history_to_config()

    def add_to_history(self, command: str):
        """添加命令到歷史記錄"""
        if command and command not in self.command_history:
            updated_history = self.command_history + [command]
            self.set_history(updated_history, persist=True)

    def clear_history(self):
        """清空命令歷史"""
        self.set_history([], persist=True)

    def export_command_history(self):
        """導出命令歷史到文件"""
        if not self.command_history:
            self.parent_window.show_info('Export History', 'No commands in history to export.')
            return

        filename, _ = QFileDialog.getSaveFileName(
            self.parent_window, 'Export Command History',
            f'adb_commands_{common.current_format_time_utc()}.txt',
            'Text Files (*.txt);;All Files (*)'
        )

        if filename:
            context = TaskContext(name='export_history', category='file_generation')
            handle = self._dispatcher.submit(
                self._export_history_task,
                filename,
                commands=list(self.command_history),
                context=context,
            )

            def _on_completed(_: Dict[str, Any]) -> None:
                self.parent_window.show_info('Export History', f'Command history exported to:\n{filename}')

            def _on_failed(exc: Exception) -> None:
                self.parent_window.show_error('Export Error', f'Failed to export history:\n{exc}')

            handle.completed.connect(_on_completed)
            handle.failed.connect(_on_failed)
            self._track_handle(handle)

    def import_command_history(self):
        """從文件導入命令歷史"""
        filename, _ = QFileDialog.getOpenFileName(
            self.parent_window, 'Import Command History', '',
            'Text Files (*.txt);;All Files (*)'
        )

        if filename:
            context = TaskContext(name='import_history', category='file_generation')
            handle = self._dispatcher.submit(
                self._import_history_task,
                filename,
                context=context,
            )

            def _on_completed(payload: Dict[str, Any]) -> None:
                loaded_commands = payload.get('commands', [])
                if loaded_commands:
                    merged_commands = self.command_history + loaded_commands
                    seen = set()
                    deduped_commands = [cmd for cmd in merged_commands if not (cmd in seen or seen.add(cmd))]
                    self.set_history(deduped_commands, persist=True)
                    self.parent_window.show_info('Import History', f'Imported {len(loaded_commands)} commands from:\n{filename}')
                else:
                    self.parent_window.show_info('Import History', 'No valid commands found in file.')

            def _on_failed(exc: Exception) -> None:
                self.parent_window.show_error('Import Error', f'Failed to import history:\n{exc}')

            handle.completed.connect(_on_completed)
            handle.failed.connect(_on_failed)
            self._track_handle(handle)

    def _export_history_task(
        self,
        filename: str,
        *,
        commands: List[str],
        task_handle: Optional[TaskHandle] = None,
        **_: Any,
    ) -> Dict[str, Any]:
        with open(filename, 'w', encoding='utf-8') as f:
            f.write('# ADB Command History\n')
            f.write(f'# Generated: {common.timestamp_time()}\n\n')
            for command in commands:
                f.write(f'{command}\n')
        return {'success': True}

    def _import_history_task(
        self,
        filename: str,
        *,
        task_handle: Optional[TaskHandle] = None,
        **_: Any,
    ) -> Dict[str, Any]:
        with open(filename, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        loaded_commands = [line.strip() for line in lines if line.strip() and not line.startswith('#')]
        return {'success': True, 'commands': loaded_commands}

    def load_command_history_from_config(self):
        """從配置文件加載命令歷史"""
        try:
            config_data = json_utils.read_config_json()
            history = config_data.get('command_history', [])
            self.set_history(history, persist=False)
        except Exception:
            self.command_history = []
            self._sync_executor_history()
            if self._can_update_ui():
                self.parent_window.update_history_display()

    def save_command_history_to_config(self):
        """保存命令歷史到配置文件"""
        try:
            config_data = json_utils.read_config_json()
            config_data['command_history'] = self.command_history
            json_utils.save_config_json(config_data)
            # 使用parent_window的logger如果存在
            if hasattr(self.parent_window, 'logger') and self.parent_window.logger:
                self.parent_window.logger.info(f'Command history auto-saved ({len(self.command_history)} commands)')
        except Exception as e:
            if hasattr(self.parent_window, 'logger') and self.parent_window.logger:
                self.parent_window.logger.warning(f'Failed to save command history to config: {e}')


class UIHierarchyManager:
    """UI層級管理器"""

    def __init__(self, parent_window):
        self.parent_window = parent_window
        self._dispatcher = get_task_dispatcher()
        self._active_handles: List[TaskHandle] = []

    def _track_handle(self, handle: TaskHandle) -> None:
        self._active_handles.append(handle)

        def _cleanup() -> None:
            try:
                self._active_handles.remove(handle)
            except ValueError:
                pass

        handle.finished.connect(_cleanup)

    def export_hierarchy(self, output_path: str):
        """導出UI層級結構"""
        if output_path and common.check_exists_dir(output_path):
            # 使用現有的dump_device_ui功能
            from utils import dump_device_ui

            # 獲取當前選中的設備
            devices = self.parent_window.get_checked_devices()
            if not devices:
                self.parent_window.show_error('Error', 'No devices selected.')
                return

            context = TaskContext(name='ui_hierarchy_export', category='file_generation')
            handle = self._dispatcher.submit(
                self._export_hierarchy_task,
                devices,
                output_path=output_path,
                context=context,
            )

            def _on_completed(payload: Dict[str, Any]) -> None:
                results: Dict[str, Optional[Exception]] = payload.get('results', {})
                for device in devices:
                    error = results.get(device.device_serial_num)
                    if error is None:
                        self.parent_window.show_info(
                            'UI Export',
                            f'UI hierarchy exported for device: {device.device_serial_num}'
                        )
                    else:
                        self.parent_window.show_error(
                            'UI Export Error',
                            f'Failed to export UI for {device.device_serial_num}:\n{error}'
                        )

            def _on_failed(exc: Exception) -> None:
                self.parent_window.show_error('UI Export Error', str(exc))

            handle.completed.connect(_on_completed)
            handle.failed.connect(_on_failed)
            self._track_handle(handle)
        else:
            self.parent_window.show_error('Error', 'Please select a valid output directory first.')
