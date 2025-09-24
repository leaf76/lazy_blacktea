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

    def __init__(self, parent_window):
        super().__init__()
        self.parent_window = parent_window
        # 連接信號到父視窗的處理方法
        if hasattr(parent_window, '_write_to_console_safe'):
            self.console_output_signal.connect(parent_window._write_to_console_safe)

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

        self.parent_window.show_info(
            'Shell Command',
            f'Running command on {device_count} device(s):\n"{command}"\n\nCheck console output for results.'
        )

        def shell_wrapper():
            """Shell命令執行包裝器"""
            try:
                adb_tools.run_adb_shell_command(serials, command)
                QTimer.singleShot(0, lambda: self._log_completion(f'Shell command "{command}" completed on all devices'))
            except Exception as e:
                raise e  # 重新拋出異常由run_in_thread處理

        self._run_in_thread(shell_wrapper)

    def execute_single_command(self, command: str, devices: List[adb_models.DeviceInfo]):
        """執行單個命令並添加到歷史記錄"""
        if not devices:
            self.parent_window.show_error('Error', 'No devices selected.')
            return

        serials = [d.device_serial_num for d in devices]
        device_count = len(devices)

        if hasattr(self.parent_window, 'logger'):
            self.parent_window.logger.info(f'🚀 Starting command execution: "{command}" on {device_count} device(s)')

        self.parent_window.show_info(
            'Single Command',
            f'Running command on {device_count} device(s):\n"{command}"\n\nCheck console output for results.'
        )

        # 添加到歷史記錄
        if hasattr(self.parent_window, 'command_history_manager'):
            self.parent_window.command_history_manager.add_to_history(command)

        def shell_wrapper():
            """單個命令執行包裝器"""
            try:
                def log_results(results):
                    """結果記錄回調"""
                    self.write_to_console('📨 Callback received, processing results...')
                    self.log_command_results(command, serials, results)

                if hasattr(self.parent_window, 'logger'):
                    self.parent_window.logger.info(f'📞 Calling adb_tools.run_adb_shell_command with callback')

                adb_tools.run_adb_shell_command(serials, command, callback=log_results)
                QTimer.singleShot(0, lambda: self._log_completion(f'✅ Single command "{command}" execution completed'))
            except Exception as e:
                if hasattr(self.parent_window, 'logger'):
                    self.parent_window.logger.error(f'❌ Command execution failed: {e}')
                raise e

        self._run_in_thread(shell_wrapper)

    def execute_batch_commands(self, commands: List[str], devices: List[adb_models.DeviceInfo]):
        """執行批次命令"""
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

        # 同時執行所有命令
        for command in commands:
            # 添加到歷史記錄
            if hasattr(self.parent_window, 'command_history_manager'):
                self.parent_window.command_history_manager.add_to_history(command)

            def shell_wrapper(cmd=command):
                """批次命令執行包裝器"""
                try:
                    def log_results(results):
                        """批次結果記錄回調"""
                        self.write_to_console(f'🚀 Executing: {cmd}')
                        self.log_command_results(cmd, serials, results)

                    adb_tools.run_adb_shell_command(serials, cmd, callback=log_results)
                except Exception as e:
                    QTimer.singleShot(0, lambda c=cmd: self._log_warning(f'Command failed: {c} - {e}'))

            self._run_in_thread(shell_wrapper)

    def log_command_results(self, command: str, serials: List[str], results):
        """記錄命令結果到控制台"""
        if hasattr(self.parent_window, 'logger'):
            self.parent_window.logger.info(f'🔍 Processing results for command: {command}')

        if not results:
            if hasattr(self.parent_window, 'logger'):
                self.parent_window.logger.warning(f'❌ No results for command: {command}')
            self.write_to_console(f'❌ No results: {command}')
            return

        # 將結果轉換為列表
        results_list = list(results) if not isinstance(results, list) else results
        if hasattr(self.parent_window, 'logger'):
            self.parent_window.logger.info(f'🔍 Found {len(results_list)} result set(s)')

        for serial, result in zip(serials, results_list):
            # 獲取設備名稱以便更好的顯示
            device_name = serial
            if (hasattr(self.parent_window, 'device_dict') and
                serial in self.parent_window.device_dict):
                device_name = f"{self.parent_window.device_dict[serial].device_model} ({serial[:8]}...)"

            if hasattr(self.parent_window, 'logger'):
                self.parent_window.logger.info(f'📱 [{device_name}] Command: {command}')
            self.write_to_console(f'📱 [{device_name}] {command}')

            if result and len(result) > 0:
                # 顯示前幾行輸出
                max_lines = 10  # 減少顯示行數以保持清潔
                output_lines = result[:max_lines] if len(result) > max_lines else result

                if hasattr(self.parent_window, 'logger'):
                    self.parent_window.logger.info(f'📱 [{device_name}] 📋 Output ({len(result)} lines total):')
                self.write_to_console(f'📋 {len(result)} lines output:')

                for line_num, line in enumerate(output_lines):
                    if line and line.strip():  # 跳過空行
                        output_line = f'  {line.strip()}'  # 簡化格式
                        if hasattr(self.parent_window, 'logger'):
                            self.parent_window.logger.info(f'📱 [{device_name}] {line_num+1:2d}▶️ {line.strip()}')
                        self.write_to_console(output_line)

                if len(result) > max_lines:
                    truncated_msg = f'  ... {len(result) - max_lines} more lines'
                    if hasattr(self.parent_window, 'logger'):
                        self.parent_window.logger.info(f'📱 [{device_name}] ... and {len(result) - max_lines} more lines (truncated)')
                    self.write_to_console(truncated_msg)

                success_msg = f'✅ [{device_name}] Completed'
                if hasattr(self.parent_window, 'logger'):
                    self.parent_window.logger.info(f'📱 [{device_name}] ✅ Command completed successfully')
                self.write_to_console(success_msg)
            else:
                error_msg = f'❌ [{device_name}] No output'
                if hasattr(self.parent_window, 'logger'):
                    self.parent_window.logger.warning(f'📱 [{device_name}] ❌ No output or command failed')
                self.write_to_console(error_msg)

        if hasattr(self.parent_window, 'logger'):
            self.parent_window.logger.info(f'🏁 Results display completed for command: {command}')
            self.parent_window.logger.info('─' * 50)  # 分隔線
        self.write_to_console('─' * 30)  # 較短的分隔線

    def write_to_console(self, message: str):
        """將消息寫入控制台"""
        try:
            # 使用信號進行線程安全的控制台輸出
            self.console_output_signal.emit(message)
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
            # 跳過空行和註釋
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
            # 備用線程運行方式
            threading.Thread(target=func, daemon=True).start()

    def _log_completion(self, message: str):
        """記錄完成消息"""
        if hasattr(self.parent_window, 'logger'):
            self.parent_window.logger.info(message)

    def _log_warning(self, message: str):
        """記錄警告消息"""
        if hasattr(self.parent_window, 'logger'):
            self.parent_window.logger.warning(message)