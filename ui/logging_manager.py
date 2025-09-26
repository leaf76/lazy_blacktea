#!/usr/bin/env python3
"""
日誌管理器 - 統一管理所有日誌功能和診斷工具

這個模組負責：
1. 集中管理日誌配置和處理器
2. 提供統一的日誌記錄介面
3. 管理控制台輸出和日誌級別
4. 提供logcat清理和診斷功能
5. 支援多線程安全的日誌操作
"""

import logging
import threading
from typing import Dict, Optional, List
from PyQt6.QtCore import QObject, pyqtSignal, QMutex, QMutexLocker, QTimer
from PyQt6.QtGui import QTextCursor, QFont
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QTextEdit

from utils import adb_tools, common


class ConsoleHandler(logging.Handler):
    """自定義控制台處理器 - 將日誌輸出到QTextEdit控件"""

    def __init__(self, text_widget: QTextEdit, parent=None):
        super().__init__()
        self.text_widget = text_widget
        self.parent = parent
        self.mutex = QMutex()

    def _update_widget(self, msg: str, levelname: str):
        """在主線程中更新QTextEdit控件"""
        try:
            with QMutexLocker(self.mutex):
                cursor = self.text_widget.textCursor()
                cursor.movePosition(QTextCursor.MoveOperation.End)

                # 根據日誌級別設置顏色
                if levelname == 'WARNING':
                    self.text_widget.setTextColor(Qt.GlobalColor.magenta)
                elif levelname == 'ERROR':
                    self.text_widget.setTextColor(Qt.GlobalColor.red)
                elif levelname == 'CRITICAL':
                    font = QFont()
                    font.setBold(True)
                    self.text_widget.setCurrentFont(font)
                    self.text_widget.setTextColor(Qt.GlobalColor.red)
                else:
                    # INFO消息使用藍色
                    self.text_widget.setTextColor(Qt.GlobalColor.blue)

                self.text_widget.insertPlainText(msg + '\n')

                # 自動滾動到底部
                cursor.movePosition(QTextCursor.MoveOperation.End)
                self.text_widget.setTextCursor(cursor)
                self.text_widget.ensureCursorVisible()

                # 重置格式
                font = QFont()
                font.setBold(False)
                self.text_widget.setCurrentFont(font)
                self.text_widget.setTextColor(Qt.GlobalColor.black)

        except Exception as e:
            print(f'Error updating console widget: {e}')

    def emit(self, record):
        """發送日誌記錄到控制台"""
        try:
            msg = self.format(record)
            levelname = record.levelname

            # 使用QTimer確保在主線程中執行UI更新
            if hasattr(self.parent, 'isVisible') and self.parent.isVisible():
                QTimer.singleShot(0, lambda: self._update_widget(msg, levelname))
        except Exception as e:
            print(f'Error in ConsoleHandler.emit: {e}')


class LoggingManager(QObject):
    """日誌管理器"""

    # 信號定義
    log_message_signal = pyqtSignal(str, str)  # message, level

    def __init__(self, parent_window):
        super().__init__()
        self.parent_window = parent_window
        self.logger = None
        self.console_handler = None
        self.file_handler = None
        self.logcat_manager = LogcatManager(parent_window)

        # 日誌級別映射
        self.log_levels = {
            'DEBUG': logging.DEBUG,
            'INFO': logging.INFO,
            'WARNING': logging.WARNING,
            'ERROR': logging.ERROR,
            'CRITICAL': logging.CRITICAL
        }

    def initialize_logging(self, console_widget: Optional[QTextEdit] = None):
        """初始化日誌系統"""
        # 獲取主日誌器
        self.logger = common.get_logger('lazy_blacktea')

        if console_widget:
            self._setup_console_handler(console_widget)

        self._setup_related_loggers()

        # 設置預設日誌級別
        self.set_log_level('INFO')

        self.info('日誌系統初始化完成')

    def _setup_console_handler(self, console_widget: QTextEdit):
        """設置控制台處理器"""
        # 移除現有的StreamHandler
        for handler in self.logger.handlers[:]:
            if isinstance(handler, logging.StreamHandler) and not isinstance(handler, ConsoleHandler):
                self.logger.removeHandler(handler)

        # 添加自定義控制台處理器
        if not any(isinstance(h, ConsoleHandler) for h in self.logger.handlers):
            self.console_handler = ConsoleHandler(console_widget, self.parent_window)
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            self.console_handler.setFormatter(formatter)
            self.logger.addHandler(self.console_handler)

    def _setup_related_loggers(self):
        """設置相關模組的日誌器"""
        related_loggers = ['adb_tools', 'common', 'ui_inspector_utils', 'dump_device_ui']
        for logger_name in related_loggers:
            module_logger = logging.getLogger(logger_name)
            module_logger.setLevel(logging.INFO)
            module_logger.propagate = True  # 傳播到主日誌器

    def set_log_level(self, level: str):
        """設置日誌級別"""
        if level in self.log_levels and self.logger:
            self.logger.setLevel(self.log_levels[level])
            if self.console_handler:
                self.console_handler.setLevel(self.log_levels[level])

    def get_current_log_level(self) -> str:
        """獲取當前日誌級別"""
        if self.logger:
            level = self.logger.level
            for name, value in self.log_levels.items():
                if value == level:
                    return name
        return 'INFO'

    # 日誌記錄方法
    def debug(self, message: str, **kwargs):
        """記錄DEBUG級別日誌"""
        if self.logger:
            self.logger.debug(message, **kwargs)

    def info(self, message: str, **kwargs):
        """記錄INFO級別日誌"""
        if self.logger:
            self.logger.info(message, **kwargs)

    def warning(self, message: str, **kwargs):
        """記錄WARNING級別日誌"""
        if self.logger:
            self.logger.warning(message, **kwargs)

    def error(self, message: str, **kwargs):
        """記錄ERROR級別日誌"""
        if self.logger:
            self.logger.error(message, **kwargs)

    def critical(self, message: str, **kwargs):
        """記錄CRITICAL級別日誌"""
        if self.logger:
            self.logger.critical(message, **kwargs)

    def log_operation_start(self, operation: str, details: str = ""):
        """記錄操作開始"""
        message = f'🚀 開始操作: {operation}'
        if details:
            message += f' - {details}'
        self.info(message)

    def log_operation_complete(self, operation: str, details: str = ""):
        """記錄操作完成"""
        message = f'✅ 完成操作: {operation}'
        if details:
            message += f' - {details}'
        self.info(message)

    def log_operation_failed(self, operation: str, error: str):
        """記錄操作失敗"""
        message = f'❌ 操作失敗: {operation} - {error}'
        self.error(message)

    def log_device_operation(self, device_serial: str, operation: str, status: str):
        """記錄設備操作"""
        device_name = self._get_device_name(device_serial)
        message = f'📱 [{device_name}] {operation}: {status}'

        if '成功' in status or '完成' in status:
            self.info(message)
        elif '失敗' in status or '錯誤' in status:
            self.error(message)
        else:
            self.info(message)

    def log_command_execution(self, command: str, devices: List[str], status: str):
        """記錄命令執行"""
        device_count = len(devices)
        message = f'⚡ 命令執行: "{command}" (設備數: {device_count}) - {status}'
        self.info(message)

    def _get_device_name(self, device_serial: str) -> str:
        """獲取設備名稱"""
        if (hasattr(self.parent_window, 'device_dict') and
            device_serial in self.parent_window.device_dict):
            device = self.parent_window.device_dict[device_serial]
            return f"{device.device_model} ({device_serial[:8]}...)"
        return device_serial

    def clear_console_log(self):
        """清空控制台日誌"""
        if self.console_handler and self.console_handler.text_widget:
            self.console_handler.text_widget.clear()
            self.info('控制台日誌已清空')

    def export_log_to_file(self, filepath: str):
        """導出日誌到檔案"""
        try:
            if self.console_handler and self.console_handler.text_widget:
                content = self.console_handler.text_widget.toPlainText()
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(f'# Lazy BlackTea 日誌導出\\n')
                    f.write(f'# 導出時間: {common.timestamp_time()}\\n\\n')
                    f.write(content)
                self.info(f'日誌已導出到: {filepath}')
                return True
        except Exception as e:
            self.error(f'日誌導出失敗: {e}')
            return False


class LogcatManager:
    """Logcat管理器"""

    def __init__(self, parent_window):
        self.parent_window = parent_window

    def clear_logcat_on_devices(self, device_serials: List[str]):
        """清除指定設備的logcat"""
        def logcat_wrapper():
            for serial in device_serials:
                try:
                    adb_tools.clear_device_logcat(serial)
                    if hasattr(self.parent_window, 'logging_manager'):
                        self.parent_window.logging_manager.log_device_operation(
                            serial, 'Logcat清除', '成功'
                        )
                except Exception as e:
                    if hasattr(self.parent_window, 'logging_manager'):
                        self.parent_window.logging_manager.log_device_operation(
                            serial, 'Logcat清除', f'失敗: {e}'
                        )

        # 在背景線程執行
        threading.Thread(target=logcat_wrapper, daemon=True).start()

    def clear_logcat_selected_devices(self):
        """清除選中設備的logcat"""
        devices = self.parent_window.get_checked_devices()
        if not devices:
            if hasattr(self.parent_window, 'show_error'):
                self.parent_window.show_error('Error', 'No devices selected.')
            return

        device_serials = [d.device_serial_num for d in devices]
        self.clear_logcat_on_devices(device_serials)

        if hasattr(self.parent_window, 'logging_manager'):
            self.parent_window.logging_manager.info(f'開始清除 {len(devices)} 個設備的logcat')


class DiagnosticsManager:
    """診斷管理器"""

    def __init__(self, parent_window):
        self.parent_window = parent_window

    def get_system_info(self) -> Dict[str, str]:
        """獲取系統診斷信息"""
        import platform
        import sys

        info = {
            '系統': platform.system(),
            '系統版本': platform.version(),
            '處理器': platform.processor(),
            'Python版本': sys.version,
            'PyQt版本': '6.x',  # 簡化版本檢查
        }

        # 添加ADB資訊
        try:
            adb_version = adb_tools.get_adb_version()
            info['ADB版本'] = adb_version if adb_version else '未檢測到'
        except (subprocess.SubprocessError, FileNotFoundError) as e:
            logger.debug(f'ADB version detection failed: {e}')
            info['ADB版本'] = '檢測失敗'
        except Exception as e:
            logger.warning(f'Unexpected error getting ADB version: {e}')
            info['ADB版本'] = '檢測失敗'

        return info

    def get_device_diagnostics(self, device_serial: str) -> Dict[str, str]:
        """獲取設備診斷信息"""
        diagnostics = {
            '設備序號': device_serial,
            '連接狀態': '未知',
            '設備型號': '未知',
            'Android版本': '未知',
            'API級別': '未知'
        }

        try:
            if (hasattr(self.parent_window, 'device_dict') and
                device_serial in self.parent_window.device_dict):
                device = self.parent_window.device_dict[device_serial]
                diagnostics['連接狀態'] = '已連接'
                diagnostics['設備型號'] = device.device_model
                diagnostics['Android版本'] = getattr(device, 'android_version', '未知')
        except Exception as e:
            diagnostics['錯誤'] = str(e)

        return diagnostics

    def run_connection_test(self, device_serial: str) -> bool:
        """運行設備連接測試"""
        try:
            # 簡單的ADB連接測試
            result = adb_tools.run_adb_command(['-s', device_serial, 'shell', 'echo', 'test'])
            return 'test' in str(result)
        except (subprocess.SubprocessError, subprocess.TimeoutExpired) as e:
            logger.debug(f'Connection test failed for {device_serial}: {e}')
            return False
        except Exception as e:
            logger.warning(f'Unexpected error in connection test for {device_serial}: {e}')
            return False

    def generate_diagnostics_report(self) -> str:
        """生成診斷報告"""
        report = []
        report.append('=== Lazy BlackTea 診斷報告 ===')
        report.append(f'生成時間: {common.timestamp_time()}')
        report.append('')

        # 系統信息
        report.append('--- 系統信息 ---')
        system_info = self.get_system_info()
        for key, value in system_info.items():
            report.append(f'{key}: {value}')
        report.append('')

        # 設備信息
        report.append('--- 設備信息 ---')
        if hasattr(self.parent_window, 'device_dict'):
            device_count = len(self.parent_window.device_dict)
            report.append(f'檢測到設備數量: {device_count}')

            for serial, device in self.parent_window.device_dict.items():
                device_diag = self.get_device_diagnostics(serial)
                report.append(f'  設備: {device_diag.get("設備型號", "未知")} ({serial})')
                report.append(f'    狀態: {device_diag.get("連接狀態", "未知")}')
        else:
            report.append('無法獲取設備信息')

        return '\\n'.join(report)
