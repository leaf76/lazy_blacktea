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

import threading
from typing import List, Callable, Optional
from PyQt6.QtCore import QObject, pyqtSignal, QTimer

from utils import adb_models, adb_tools


class CommandExecutionManager(QObject):
    """命令執行管理器類"""

    # 信號定義
    console_output_signal = pyqtSignal(str)
    command_results_ready = pyqtSignal(str, object, object)

    def __init__(self, parent_window):
        super().__init__()
        self.parent_window = parent_window
        self.active_processes = []
        self.process_lock = threading.Lock()
        self._console_connected = False
        # 連接信號到父視窗的處理方法
        if hasattr(parent_window, '_write_to_console_safe'):
            self.console_output_signal.connect(parent_window._write_to_console_safe)
            self._console_connected = True
        self.command_results_ready.connect(self._process_command_results)

    def cancel_all_commands(self):
        """Cancel all currently running commands."""
        with self.process_lock:
            if not self.active_processes:
                self.write_to_console("No active commands to cancel.")
                return

            self.write_to_console(f"Attempting to cancel {len(self.active_processes)} running command(s)...")
            for process in self.active_processes:
                try:
                    process.terminate()  # Send SIGTERM
                    self.write_to_console(f"Sent cancel signal to process {process.pid}.")
                except Exception as e:
                    self.write_to_console(f"Error cancelling process {process.pid}: {e}")
            self.active_processes.clear()

    def _monitor_processes(self, processes: list, command: str, serials: list):
        """Monitor running processes, collect output, and log results."""
        try:
            for i, process in enumerate(processes):
                serial = serials[i]
                # The communicate() method will block until the process finishes.
                stdout, stderr = process.communicate()

                # After communicate(), the process is done. Check if it was cancelled.
                with self.process_lock:
                    # Check if the process is still in the list. If not, it was cancelled.
                    if process in self.active_processes:
                        self.active_processes.remove(process)
                    else:
                        # If it's not in the list, it means cancel_all_commands was called.
                        self.write_to_console(f"Process {process.pid} for device {serial} was cancelled. Output might be incomplete.")
                        # Continue to the next process
                        continue
                
                # Combine stdout and stderr for logging
                full_output = []
                if stdout:
                    full_output.extend(stdout.splitlines())
                if stderr:
                    full_output.extend(stderr.splitlines())

                self.command_results_ready.emit(command, [serial], [full_output])

            QTimer.singleShot(0, lambda: self._log_completion(f'All monitored processes for command "{command}" have completed.'))
        except Exception as e:
            QTimer.singleShot(0, lambda: self._log_error(f"Error in process monitor thread: {e}"))


    def run_shell_command(self, command: str, devices: List[adb_models.DeviceInfo]):
        """執行shell命令"""
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

        self.parent_window.show_info(
            'Shell Command',
            f'Running command on {device_count} device(s):\n"{command}"\n\nCheck console output for results.'
        )

        # This function remains non-cancellable for now to maintain original behavior
        def shell_wrapper():
            """Shell命令執行包裝器"""
            try:
                def _handle_results(results):
                    self.command_results_ready.emit(command, serials, results)

                adb_tools.run_adb_shell_command(serials, command, callback=_handle_results)
                QTimer.singleShot(0, lambda: self._log_completion(f'Shell command "{command}" completed on all devices'))
            except Exception as e:
                self._log_error(f"Error executing shell command: {e}")

        self._run_in_thread(shell_wrapper)

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

        def cancellable_shell_wrapper():
            processes = adb_tools.run_cancellable_adb_shell_command(serials, command)
            if not processes:
                self._log_error(f"Failed to start command '{command}'.")
                return

            with self.process_lock:
                self.active_processes.extend(processes)

            monitor_thread = threading.Thread(target=self._monitor_processes, args=(processes, command, serials))
            monitor_thread.daemon = True
            monitor_thread.start()

        self._run_in_thread(cancellable_shell_wrapper)


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

        for command in commands:
            if hasattr(self.parent_window, 'command_history_manager'):
                self.parent_window.command_history_manager.add_to_history(command)

            def cancellable_batch_wrapper(cmd=command):
                processes = adb_tools.run_cancellable_adb_shell_command(serials, cmd)
                if not processes:
                    self._log_error(f"Failed to start batch command '{cmd}'.")
                    return

                with self.process_lock:
                    self.active_processes.extend(processes)

                monitor_thread = threading.Thread(target=self._monitor_processes, args=(processes, cmd, serials))
                monitor_thread.daemon = True
                monitor_thread.start()

            self._run_in_thread(cancellable_batch_wrapper)

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
        """將消息寫入控制台"""
        try:
            if self._console_connected:
                self.console_output_signal.emit(message)
            elif hasattr(self.parent_window, 'write_to_console'):
                self.parent_window.write_to_console(message)
            else:
                print(message)
        except Exception as e:
            print(f'Error emitting console signal: {e}')

    def get_valid_commands_from_text(self, text: str) -> List[str]:
        """從文本中提取有效命令"""
        if not text.strip():
            return []

        lines = text.split('\n')
        commands = []

        for line in lines:
            line = line.strip()
            if line and not line.startswith('#'):
                commands.append(line)

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

    def _run_in_thread(self, func: Callable):
        """在線程中運行函數"""
        if hasattr(self.parent_window, 'run_in_thread'):
            self.parent_window.run_in_thread(func)
        else:
            threading.Thread(target=func, daemon=True).start()

    def _log_completion(self, message: str):
        """記錄完成消息"""
        if hasattr(self.parent_window, 'logger'):
            self.parent_window.logger.info(message)

    def _log_warning(self, message: str):
        """記錄警告消息"""
        if hasattr(self.parent_window, 'logger'):
            self.parent_window.logger.warning(message)

    def _log_error(self, message: str):
        """記錄錯誤消息"""
        if hasattr(self.parent_window, 'logger'):
            self.parent_window.logger.error(message)

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
