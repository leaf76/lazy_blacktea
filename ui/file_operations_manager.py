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
from typing import List, Callable, Optional
from PyQt6.QtCore import QObject, pyqtSignal, QTimer
from PyQt6.QtWidgets import QFileDialog

from utils import adb_models, common, json_utils
from utils.file_generation_utils import (
    generate_bug_report_batch,
    generate_device_discovery_file,
    validate_file_output_path
)


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

    def get_validated_output_path(self, path_text: str) -> Optional[str]:
        """驗證並獲取輸出路徑"""
        validated_path = validate_file_output_path(path_text.strip())
        if not validated_path:
            self.parent_window.show_error(
                'Error',
                'Please select a valid file generation output directory first.'
            )
        return validated_path

    def generate_android_bug_report(self, devices: List[adb_models.DeviceInfo], output_path: str):
        """生成Android Bug Report"""
        validated_path = self.get_validated_output_path(output_path)
        if not validated_path:
            return

        device_count = len(devices)
        self.last_generation_output_path = validated_path
        self.last_generation_summary = ''

        # 顯示進度通知（避免阻塞，改用狀態列與信號）
        initial_message = (
            f'🐛 Preparing bug report generation for {device_count} device(s)... '
            f'(Saving to: {validated_path})'
        )
        QTimer.singleShot(0, lambda: self.file_generation_progress_signal.emit(0, device_count, initial_message))

        def bug_report_callback(operation_name, payload, success_count, icon):
            """Bug report生成完成的回調"""
            summary_text = ''
            output_directory = validated_path

            if isinstance(payload, dict):
                summary_text = payload.get('summary', '')
                output_directory = payload.get('output_path', validated_path)
            else:
                summary_text = str(payload)

            self.last_generation_summary = summary_text
            self.last_generation_output_path = output_directory
            self.file_generation_completed_signal.emit(operation_name, summary_text, success_count, icon)

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

            QTimer.singleShot(0, lambda: self.file_generation_progress_signal.emit(current, total, base_message))

        def generation_wrapper():
            """錯誤處理包裝器"""
            try:
                generate_bug_report_batch(
                    devices,
                    validated_path,
                    bug_report_callback,
                    progress_callback=progress_callback
                )
            except Exception as e:
                QTimer.singleShot(0, lambda: self.parent_window.show_error(
                    '🐛 Bug Report Generation Failed',
                    f'Failed to generate bug reports for some devices.\n\n'
                    f'Error: {str(e)}\n\n'
                    f'📱 Manufacturer-specific solutions:\n'
                    f'• Samsung: Enable Developer Options → USB Debugging (Security)\n'
                    f'• Huawei: Install HiSuite and grant permissions\n'
                    f'• Xiaomi: Enable MIUI Developer Options\n'
                    f'• OPPO/OnePlus: Enable ColorOS/OxygenOS Developer Settings\n'
                    f'• Vivo: Enable FunTouch OS Developer Permissions\n\n'
                    f'🔧 General troubleshooting:\n'
                    f'1. Verify "USB Debugging" is enabled\n'
                    f'2. Authorize this computer on device\n'
                    f'3. Check device has sufficient storage (>100MB)\n'
                    f'4. Ensure stable USB connection\n'
                    f'5. Try generating reports one device at a time\n\n'
                    f'💡 Note: Modern bug reports are saved as .zip files'
                ))
            finally:
                QTimer.singleShot(0, lambda: self.file_generation_progress_signal.emit(
                    device_count, device_count,
                    '🐛 Bug report generation finished'
                ))

        threading.Thread(target=generation_wrapper, daemon=True).start()

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

        def discovery_callback(operation_name, output_path, device_count, icon):
            """設備發現文件生成完成的回調"""
            self.last_generation_summary = f'{operation_name} completed for {device_count} device(s)'
            self.last_generation_output_path = output_path
            self.file_generation_completed_signal.emit(operation_name, output_path, device_count, icon)

        generate_device_discovery_file(devices, validated_path, discovery_callback)

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

        def dcim_wrapper():
            """DCIM拉取包裝器"""
            from utils import adb_tools
            adb_tools.pull_device_dcim_folders_with_device_folder(serials, output_path)

            def emit_completion():
                self.last_generation_summary = 'DCIM folders pulled successfully'
                self.last_generation_output_path = output_path
                self.file_generation_completed_signal.emit(
                    'DCIM Folder Pull', output_path, device_count, '📷'
                )

            QTimer.singleShot(0, emit_completion)

        threading.Thread(target=dcim_wrapper, daemon=True).start()


class CommandHistoryManager:
    """命令歷史管理器"""

    def __init__(self, parent_window):
        self.parent_window = parent_window
        self.command_history = []
        self.load_command_history_from_config()

    def add_to_history(self, command: str):
        """添加命令到歷史記錄"""
        if command and command not in self.command_history:
            self.command_history.append(command)
            # 保持最近50條命令
            if len(self.command_history) > 50:
                self.command_history.pop(0)
            self.save_command_history_to_config()

    def clear_history(self):
        """清空命令歷史"""
        self.command_history.clear()
        if hasattr(self.parent_window, 'update_history_display'):
            self.parent_window.update_history_display()
        self.save_command_history_to_config()

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
            try:
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write('# ADB Command History\n')
                    f.write(f'# Generated: {common.timestamp_time()}\n\n')
                    for command in self.command_history:
                        f.write(f'{command}\n')

                self.parent_window.show_info('Export History', f'Command history exported to:\n{filename}')
            except Exception as e:
                self.parent_window.show_error('Export Error', f'Failed to export history:\n{e}')

    def import_command_history(self):
        """從文件導入命令歷史"""
        filename, _ = QFileDialog.getOpenFileName(
            self.parent_window, 'Import Command History', '',
            'Text Files (*.txt);;All Files (*)'
        )

        if filename:
            try:
                with open(filename, 'r', encoding='utf-8') as f:
                    lines = f.readlines()

                loaded_commands = []
                for line in lines:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        loaded_commands.append(line)

                if loaded_commands:
                    self.command_history.extend(loaded_commands)
                    # 去重並保持順序
                    seen = set()
                    self.command_history = [x for x in self.command_history if not (x in seen or seen.add(x))]
                    # 保持最近50條命令
                    if len(self.command_history) > 50:
                        self.command_history = self.command_history[-50:]

                    if hasattr(self.parent_window, 'update_history_display'):
                        self.parent_window.update_history_display()
                    self.save_command_history_to_config()
                    self.parent_window.show_info('Import History', f'Imported {len(loaded_commands)} commands from:\n{filename}')
                else:
                    self.parent_window.show_info('Import History', 'No valid commands found in file.')

            except Exception as e:
                self.parent_window.show_error('Import Error', f'Failed to import history:\n{e}')

    def load_command_history_from_config(self):
        """從配置文件加載命令歷史"""
        try:
            config_data = json_utils.read_config_json()
            if 'command_history' in config_data:
                self.command_history = config_data['command_history'][-50:]  # 保持最近50條
                if hasattr(self.parent_window, 'update_history_display'):
                    self.parent_window.update_history_display()
        except Exception:
            self.command_history = []

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

            for device in devices:
                try:
                    dump_device_ui.generate_process(device.device_serial_num, output_path)
                    self.parent_window.show_info(
                        'UI Export',
                        f'UI hierarchy exported for device: {device.device_serial_num}'
                    )
                except Exception as e:
                    self.parent_window.show_error(
                        'UI Export Error',
                        f'Failed to export UI for {device.device_serial_num}:\n{e}'
                    )
        else:
            self.parent_window.show_error('Error', 'Please select a valid output directory first.')
