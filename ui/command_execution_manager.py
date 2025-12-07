#!/usr/bin/env python3
"""
命令執行管理器 - 處理所有shell命令和批次命令執行

這個模組負責：
1. 單個shell命令執行
2. 批次命令執行
3. 命令結果處理和格式化
4. 命令執行的線程管理
5. 命令結果的控制台輸出
"""

import subprocess
import threading
from typing import Any, Dict, List, Callable, Optional
from PyQt6.QtCore import QObject, pyqtSignal, QTimer

from utils import adb_models, adb_tools, common
from utils.task_dispatcher import TaskContext, TaskHandle, get_task_dispatcher


_fallback_logger = common.get_logger('ui_console_fallback')


class CommandExecutionManager(QObject):
    """命令執行管理器類"""

    # 信號定義
    console_output_signal = pyqtSignal(str)
    command_results_ready = pyqtSignal(str, object, object)

    def __init__(self, parent_window):
        super().__init__()
        self.parent_window = parent_window
        self._dispatcher = get_task_dispatcher()
        self.process_lock = threading.Lock()
        self._active_handles: List[TaskHandle] = []
        self._handle_processes: dict[TaskHandle, List[subprocess.Popen]] = {}
        self._console_connected = False
        # Track batch executions: batch_id -> {
        #   expected, done, failed, serials, commands,
        #   completed_commands: List[str], failed_commands: List[tuple[str, str]]
        # }
        self._batch_states: Dict[str, Dict[str, Any]] = {}
        # 連接信號到父視窗的處理方法
        if hasattr(parent_window, '_write_to_console_safe'):
            self.console_output_signal.connect(parent_window._write_to_console_safe)
            self._console_connected = True
        self.command_results_ready.connect(self._process_command_results)

    def cancel_all_commands(self):
        """Cancel all currently running commands."""
        with self.process_lock:
            if not self._active_handles:
                self.write_to_console("No active commands to cancel.")
                return

            self.write_to_console(f"Attempting to cancel {len(self._active_handles)} running command(s)...")
            handles = list(self._active_handles)
            for handle in handles:
                handle.cancel()
                processes = self._handle_processes.get(handle, [])
                for process in processes:
                    try:
                        process.terminate()
                        self.write_to_console(f"Sent cancel signal to process {process.pid}.")
                    except Exception as exc:
                        self.write_to_console(f"Error cancelling process {getattr(process, 'pid', '?')}: {exc}")

    def _track_handle(self, handle: TaskHandle) -> None:
        with self.process_lock:
            self._active_handles.append(handle)

        def _cleanup() -> None:
            with self.process_lock:
                if handle in self._active_handles:
                    self._active_handles.remove(handle)
                self._handle_processes.pop(handle, None)

        handle.finished.connect(_cleanup)

    def _register_processes_for_handle(self, handle: Optional[TaskHandle], processes: List[subprocess.Popen]) -> None:
        if handle is None:
            return
        with self.process_lock:
            self._handle_processes[handle] = processes


    def run_shell_command(self, command: str, devices: List[adb_models.DeviceInfo]):
        """Execute shell command using the cancellable task implementation."""
        if not command.strip():
            self.parent_window.show_error('Error', 'Please enter a command.')
            return

        if not devices:
            self.parent_window.show_error('Error', 'No devices selected.')
            return

        serials = [d.device_serial_num for d in devices]
        device_count = len(devices)

        if hasattr(self.parent_window, 'logger'):
            self.parent_window.logger.info(f'Running shell command "{command}" on {device_count} device(s): {serials}')

        self.write_to_console(f'🚀 Running shell command "{command}" on {device_count} device(s)...')

        context = TaskContext(name='shell_command', category='command')
        handle = self._dispatcher.submit(
            self._run_cancellable_command_task,
            serials,
            command=command,
            context=context,
        )

        handle.completed.connect(lambda payload: self._on_shell_command_completed(command, serials, payload))
        handle.failed.connect(lambda exc: self._on_command_failed(command, exc))
        self._track_handle(handle)

    def execute_single_command(self, command: str, devices: List[adb_models.DeviceInfo]):
        """執行單個命令並添加到歷史記錄 (Cancellable)"""
        if not devices:
            self.parent_window.show_error('Error', 'No devices selected.')
            return

        serials = [d.device_serial_num for d in devices]
        device_count = len(devices)

        if hasattr(self.parent_window, 'logger'):
            self.parent_window.logger.info(f'🚀 Starting cancellable command: "{command}" on {device_count} device(s)')

        self.write_to_console(f'🚀 Running single command "{command}" on {device_count} device(s)...')

        self.parent_window.show_info(
            'Single Command',
            f'Running command on {device_count} device(s):\n"{command}"\n\nCheck console output for results.'
        )

        if hasattr(self.parent_window, 'command_history_manager'):
            self.parent_window.command_history_manager.add_to_history(command)

        context = TaskContext(name='single_command', category='command')
        handle = self._dispatcher.submit(
            self._run_cancellable_command_task,
            serials,
            command=command,
            context=context,
        )

        handle.completed.connect(lambda payload: self._on_cancellable_command_completed(command, serials, payload))
        handle.failed.connect(lambda exc: self._log_error(f"Error executing command '{command}': {exc}"))
        self._track_handle(handle)


    def execute_batch_commands(self, commands: List[str], devices: List[adb_models.DeviceInfo]):
        """執行批次命令 (Cancellable)"""
        if not commands:
            self.parent_window.show_error('Error', 'No valid commands found.')
            return

        if not devices:
            self.parent_window.show_error('Error', 'No devices selected.')
            return

        serials = [d.device_serial_num for d in devices]
        device_count = len(devices)

        self.parent_window.show_info(
            'Batch Commands',
            f'Running {len(commands)} commands simultaneously on {device_count} device(s):\n\n' +
            '\n'.join(f'• {cmd}' for cmd in commands[:5]) +
            (f'\n... and {len(commands)-5} more' if len(commands) > 5 else '')
        )

        self.write_to_console(
            f'🚀 Running {len(commands)} batch command(s) on {device_count} device(s)...'
        )

        # Initialize batch tracking
        batch_id = common.generate_trace_id()
        with self.process_lock:
            self._batch_states[batch_id] = {
                'expected': len(commands),
                'done': 0,
                'failed': 0,
                'serials': serials,
                'commands': list(commands),
                'completed_commands': [],
                'failed_commands': [],  # (command, error)
            }

        for cmd in commands:
            if hasattr(self.parent_window, 'command_history_manager'):
                self.parent_window.command_history_manager.add_to_history(cmd)

            context = TaskContext(name='batch_command', category='command')
            handle = self._dispatcher.submit(
                self._run_cancellable_command_task,
                serials,
                command=cmd,
                context=context,
            )
            # Suppress per-command dialog; aggregate by batch_id
            handle.completed.connect(
                lambda payload, c=cmd, bid=batch_id: self._on_cancellable_command_completed(c, serials, payload, is_batch=True, batch_id=bid)
            )
            handle.failed.connect(
                lambda exc, c=cmd, bid=batch_id: self._on_batch_command_failed(c, serials, exc, batch_id=bid)
            )
            self._track_handle(handle)

    def log_command_results(self, command: str, serials: List[str], results):
        """Record command execution results in the console."""
        normalized_results = self._normalize_results(results, len(serials))
        delegate = getattr(self.parent_window, 'log_command_results', None)
        handled = False
        if callable(delegate):
            try:
                delegate(command, serials, normalized_results)
                handled = True
            except Exception as exc:
                self._log_error(f'Error delegating command results: {exc}')

        # Fallback if parent window does not provide its own implementation
        if handled:
            return

        if not normalized_results:
            self.write_to_console(f'❌ No results: {command}')
            return

        for serial, result in zip(serials, normalized_results):
            device_name = serial
            self.write_to_console(f'📱 [{device_name}] {command}')

            output_lines = result if isinstance(result, list) else []
            if output_lines:
                self.write_to_console(f'📋 {len(output_lines)} lines output:')
                for line in output_lines:
                    if line and str(line).strip():
                        self.write_to_console(f'  {str(line).strip()}')
                self.write_to_console(f'✅ [{device_name}] Completed')
            else:
                self.write_to_console(f'❌ [{device_name}] No output')

        self.write_to_console('─' * 30)

    def _process_command_results(self, command, serials, results):
        if isinstance(serials, (list, tuple)):
            serials_list = list(serials)
        else:
            serials_list = [serials]

        if results is None:
            results_payload = []
        elif isinstance(results, (list, tuple)):
            results_payload = list(results)
        else:
            results_payload = [results]

        self._emit_command_results(command, serials_list, results_payload)

    def _emit_command_results(self, command: str, serials: List[str], results):
        """Normalize and forward command results."""
        self.log_command_results(command, serials, results)

    def write_to_console(self, message: str):
        """Write message to console (delegates to parent_window.write_to_console)."""
        try:
            if self._console_connected:
                self.console_output_signal.emit(message)
            elif hasattr(self.parent_window, 'write_to_console'):
                self.parent_window.write_to_console(message)
            else:
                _fallback_logger.error(message)
        except Exception:
            _fallback_logger.exception('Error emitting console signal')

    def get_valid_commands_from_text(self, text: str) -> List[str]:
        """Extract valid commands from text, supporting line continuation with backslash."""
        if not text.strip():
            return []

        lines = text.split('\n')
        commands = []
        current_command = []

        for line in lines:
            stripped = line.strip()
            # Skip empty lines and comments
            if not stripped or stripped.startswith('#'):
                # If we have a pending command, finalize it
                if current_command:
                    commands.append(' '.join(current_command))
                    current_command = []
                continue

            # Check for line continuation (ends with \)
            if stripped.endswith('\\'):
                # Remove the backslash and add to current command
                current_command.append(stripped[:-1].rstrip())
            else:
                # No continuation - finalize the command
                current_command.append(stripped)
                commands.append(' '.join(current_command))
                current_command = []

        # Handle any remaining command
        if current_command:
            commands.append(' '.join(current_command))

        return commands

    def add_template_command(self, command: str):
        """添加模板命令到批次命令區域"""
        if hasattr(self.parent_window, 'batch_commands_edit'):
            current_text = self.parent_window.batch_commands_edit.toPlainText()
            if current_text:
                new_text = current_text + '\n' + command
            else:
                new_text = command
            self.parent_window.batch_commands_edit.setPlainText(new_text)

    def _log_completion(self, message: str):
        """記錄完成消息"""
        if hasattr(self.parent_window, 'logger'):
            self.parent_window.logger.info(message)

    def _log_warning(self, message: str):
        """記錄警告消息"""
        if hasattr(self.parent_window, 'logger'):
            self.parent_window.logger.warning(message)

    def _log_error(self, message: str):
        """Record error message to logger."""
        if hasattr(self.parent_window, 'logger'):
            self.parent_window.logger.error(message)

    def _on_command_failed(self, command: str, exc: Exception) -> None:
        """Handle command execution failure with proper user feedback."""
        error_msg = f'Command "{command}" failed: {exc}'
        self._log_error(error_msg)
        self.write_to_console(f'❌ {error_msg}')
        try:
            self.parent_window.show_error('Command Failed', error_msg)
        except Exception:
            pass

    def _on_shell_command_completed(self, command: str, serials: List[str], payload: Any) -> None:
        results = []
        if isinstance(payload, dict):
            results = payload.get('results', [])
        self.command_results_ready.emit(command, serials, results)
        # Log and notify completion via UI dialog
        QTimer.singleShot(0, lambda: self._log_completion(f'Shell command "{command}" completed on all devices'))
        try:
            device_count = len(serials) if isinstance(serials, (list, tuple)) else 1
            QTimer.singleShot(
                0,
                lambda: getattr(self.parent_window, 'show_info', lambda *_: None)(
                    'Shell Command Completed',
                    f'Command "{command}" completed on {device_count} device(s).'
                ),
            )
        except Exception:
            # Avoid breaking the flow if dialog presentation fails
            pass

    def _on_cancellable_command_completed(self, command: str, serials: List[str], payload: Any, is_batch: bool = False, batch_id: Optional[str] = None) -> None:
        results = []
        if isinstance(payload, dict):
            results = payload.get('results', [])
        self.command_results_ready.emit(command, serials, results)
        QTimer.singleShot(0, lambda: self._log_completion(f'Command "{command}" completed on {len(serials)} device(s)'))

        if is_batch and batch_id:
            # Update batch state and maybe show one summary dialog
            self._increment_batch_done(batch_id, success=True, command=command)
            return

        # Non-batch single command: show completion dialog
        try:
            device_count = len(serials) if isinstance(serials, (list, tuple)) else 1
            QTimer.singleShot(
                0,
                lambda: getattr(self.parent_window, 'show_info', lambda *_: None)(
                    'Command Completed',
                    f'Command "{command}" completed on {device_count} device(s).'
                ),
            )
        except Exception:
            # Defensive: ignore dialog issues
            pass

    def _on_batch_command_failed(self, command: str, serials: List[str], exc: Exception, *, batch_id: Optional[str] = None) -> None:
        self._log_error(f"Error executing batch command '{command}': {exc}")
        if batch_id:
            self._increment_batch_done(batch_id, success=False, command=command, error=str(exc))

    def _increment_batch_done(self, batch_id: str, *, success: bool, command: Optional[str] = None, error: Optional[str] = None) -> None:
        with self.process_lock:
            state = self._batch_states.get(batch_id)
            if not state:
                return
            state['done'] += 1
            if not success:
                state['failed'] += 1
                if command is not None:
                    state['failed_commands'].append((command, error or ''))
            else:
                if command is not None:
                    state['completed_commands'].append(command)

            done = state['done']
            expected = state['expected']
            failed = state['failed']
            serials = state.get('serials', [])

            if done < expected:
                return

            # Batch completed: show one summary and cleanup
            device_count = len(serials) if isinstance(serials, (list, tuple)) else 1
            summary_lines: List[str] = []
            summary_lines.append(f'Executed {expected} command(s) on {device_count} device(s).')
            if failed:
                summary_lines.append(f'Failures: {failed}')

            # Include first few commands for quick glance
            try:
                commands: List[str] = list(state.get('commands') or [])
                if commands:
                    preview_count = min(5, len(commands))
                    summary_lines.append('Commands:')
                    for cmd in commands[:preview_count]:
                        summary_lines.append(f'• {cmd}')
                    if len(commands) > preview_count:
                        summary_lines.append(f'... and {len(commands) - preview_count} more')
            except Exception:
                pass

            # Include failed commands brief list
            try:
                failures: List[tuple[str, str]] = list(state.get('failed_commands') or [])
                if failures:
                    preview_fail = min(5, len(failures))
                    summary_lines.append('Failed Commands:')
                    for cmd, err in failures[:preview_fail]:
                        err_snippet = (err or '').strip().splitlines()[0][:120]
                        if err_snippet:
                            summary_lines.append(f'• {cmd} — {err_snippet}')
                        else:
                            summary_lines.append(f'• {cmd}')
                    if len(failures) > preview_fail:
                        summary_lines.append(f'... and {len(failures) - preview_fail} more failures')
            except Exception:
                pass

            summary = '\n'.join(summary_lines)

            QTimer.singleShot(
                0,
                lambda: getattr(self.parent_window, 'show_info', lambda *_: None)('Batch Commands Completed', summary),
            )

            # Cleanup state
            self._batch_states.pop(batch_id, None)

    def _run_cancellable_command_task(
        self,
        serials: List[str],
        *,
        command: str,
        task_handle: Optional[TaskHandle] = None,
        **_: Any,
    ) -> Dict[str, Any]:
        processes = adb_tools.run_cancellable_adb_shell_command(serials, command)
        if not processes:
            raise RuntimeError(f"Failed to start command '{command}'.")

        self._register_processes_for_handle(task_handle, processes)

        results: List[List[str]] = []
        for serial, process in zip(serials, processes):
            stdout, stderr = self._collect_process_output(process, task_handle)
            lines: List[str] = []
            if stdout:
                if isinstance(stdout, bytes):
                    lines.extend(stdout.decode('utf-8', errors='ignore').splitlines())
                else:
                    lines.extend(str(stdout).splitlines())
            if stderr:
                if isinstance(stderr, bytes):
                    lines.extend(stderr.decode('utf-8', errors='ignore').splitlines())
                else:
                    lines.extend(str(stderr).splitlines())
            results.append(lines)

        return {
            'success': True,
            'results': results,
        }

    def _collect_process_output(
        self,
        process: subprocess.Popen,
        task_handle: Optional[TaskHandle],
        *,
        poll_interval: float = 0.2,
        kill_timeout: float = 0.5,
    ) -> tuple[Any, Any]:
        """Wait for process completion while honouring task cancellation."""

        while True:
            if task_handle and task_handle.is_cancelled():
                self._request_process_termination(process)

            try:
                return process.communicate(timeout=poll_interval)
            except subprocess.TimeoutExpired:
                if task_handle and task_handle.is_cancelled():
                    self._force_kill_process(process, timeout=kill_timeout)
                continue

    @staticmethod
    def _request_process_termination(process: subprocess.Popen) -> None:
        if process.poll() is not None:
            return
        try:
            process.terminate()
        except Exception:
            pass

    @staticmethod
    def _force_kill_process(process: subprocess.Popen, *, timeout: float) -> None:
        if process.poll() is not None:
            return
        try:
            process.terminate()
        except Exception:
            pass
        try:
            process.wait(timeout=timeout)
            return
        except subprocess.TimeoutExpired:
            pass

        try:
            process.kill()
        except Exception:
            pass

    @staticmethod
    def _normalize_results(results, expected_length: int) -> List[List[str]]:
        """Ensure command results are a list of string lists with consistent length."""
        normalized: List[List[str]] = []

        if results is None:
            results = []

        if not isinstance(results, list):
            results = list(results)

        for item in results:
            if isinstance(item, (list, tuple)):
                normalized.append([str(line) for line in item])
            elif item is None:
                normalized.append([])
            else:
                normalized.append([str(item)])

        while len(normalized) < expected_length:
            normalized.append([])

        return normalized
