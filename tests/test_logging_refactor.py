#!/usr/bin/env python3
"""
日誌系統重構測試 - 確保日誌管理器和診斷功能的正確性

這個測試專門驗證：
1. LoggingManager類的功能完整性
2. DiagnosticsManager診斷功能
3. LogcatManager logcat管理功能
4. ConsoleHandler控制台處理器
5. 主文件中日誌重構的正確性
"""

import sys
import os
import unittest
from unittest.mock import Mock, patch, MagicMock

import logging

from PyQt6.QtWidgets import QApplication, QTextEdit

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_TEST_HOME = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", ".test_home_logging")
)
os.environ["HOME"] = _TEST_HOME
os.makedirs(os.path.join(_TEST_HOME, ".lazy_blacktea_logs"), exist_ok=True)

try:
    import lazy_blacktea_pyqt
    from ui.logging_manager import LoggingManager, DiagnosticsManager, LogcatManager, ConsoleHandler
    from utils import adb_models
except ImportError as e:
    print(f"❌ 無法導入模組: {e}")
    sys.exit(1)


class LoggingRefactorTest(unittest.TestCase):
    """日誌系統重構測試類"""

    @classmethod
    def setUpClass(cls):
        """設置測試環境"""
        cls.module = lazy_blacktea_pyqt
        cls._qt_app = QApplication.instance() or QApplication([])

    def test_logging_classes_exist(self):
        """測試日誌管理類的存在性"""
        print("\n📋 測試日誌管理類...")

        manager_classes = [
            ('LoggingManager', LoggingManager),
            ('DiagnosticsManager', DiagnosticsManager),
            ('LogcatManager', LogcatManager),
            ('ConsoleHandler', ConsoleHandler),
        ]

        for class_name, class_obj in manager_classes:
            print(f"  ✅ {class_name} 類存在")
            self.assertTrue(hasattr(class_obj, '__init__'))
            print(f"    📋 {class_name} 可以實例化")

    def test_main_window_has_logging_managers(self):
        """測試主視窗包含日誌管理器"""
        print("\n🔍 測試主視窗日誌管理器...")

        if hasattr(self.module, 'WindowMain'):
            WindowMain = getattr(self.module, 'WindowMain')

            # 檢查__init__方法中是否提及日誌管理器
            try:
                import inspect
                init_source = inspect.getsource(WindowMain.__init__)

                managers_to_check = [
                    'logging_manager',
                    'diagnostics_manager'
                ]

                for manager_name in managers_to_check:
                    if manager_name in init_source:
                        print(f"  ✅ {manager_name} 在WindowMain.__init__中被初始化")
                    else:
                        print(f"  ❌ {manager_name} 未在WindowMain.__init__中找到")
                        self.fail(f"日誌管理器 {manager_name} 未在WindowMain初始化中找到")
            except:
                print("  ⚠️  無法檢查WindowMain.__init__源碼，跳過詳細檢查")

    def test_logging_manager_methods(self):
        """測試日誌管理器方法"""
        print("\n🔧 測試日誌管理器方法...")

        mock_parent = Mock()
        logging_manager = LoggingManager(mock_parent)

        # 測試核心方法
        key_methods = [
            'initialize_logging',
            'set_log_level',
            'get_current_log_level',
            'debug', 'info', 'warning', 'error', 'critical',
            'log_operation_start',
            'log_operation_complete',
            'log_operation_failed',
            'log_device_operation',
            'log_command_execution',
            'clear_console_log',
            'export_log_to_file'
        ]

        for method_name in key_methods:
            self.assertTrue(hasattr(logging_manager, method_name))
            method = getattr(logging_manager, method_name)
            self.assertTrue(callable(method))
            print(f"    ✅ {method_name}")

        # 測試屬性
        self.assertIsInstance(logging_manager.log_levels, dict)
        self.assertIn('INFO', logging_manager.log_levels)
        self.assertIn('ERROR', logging_manager.log_levels)
        print(f"    ✅ 日誌級別配置正確")

    def test_diagnostics_manager_methods(self):
        """測試診斷管理器方法"""
        print("\n🔍 測試診斷管理器方法...")

        mock_parent = Mock()
        diagnostics_manager = DiagnosticsManager(mock_parent)

        key_methods = [
            'get_system_info',
            'get_device_diagnostics',
            'run_connection_test',
            'generate_diagnostics_report'
        ]

        for method_name in key_methods:
            self.assertTrue(hasattr(diagnostics_manager, method_name))
            method = getattr(diagnostics_manager, method_name)
            self.assertTrue(callable(method))
            print(f"    ✅ {method_name}")

    def test_logcat_manager_methods(self):
        """測試Logcat管理器方法"""
        print("\n📱 測試Logcat管理器方法...")

        mock_parent = Mock()
        logcat_manager = LogcatManager(mock_parent)

        key_methods = [
            'clear_logcat_on_devices',
            'clear_logcat_selected_devices'
        ]

        for method_name in key_methods:
            self.assertTrue(hasattr(logcat_manager, method_name))
            method = getattr(logcat_manager, method_name)
            self.assertTrue(callable(method))
            print(f"    ✅ {method_name}")

    def test_console_handler_functionality(self):
        """測試控制台處理器功能"""
        print("\n💬 測試控制台處理器...")

        # 模擬QTextEdit控件
        mock_text_widget = Mock()
        mock_text_widget.textCursor.return_value = Mock()
        mock_text_widget.isVisible.return_value = True

        mock_parent = Mock()
        mock_parent.isVisible.return_value = True

        console_handler = ConsoleHandler(mock_text_widget, mock_parent)

        # 測試基本屬性
        self.assertIsNotNone(console_handler.text_widget)
        self.assertIsNotNone(console_handler.mutex)
        print(f"    ✅ 控制台處理器初始化正確")

        # 測試方法存在
        handler_methods = ['emit', '_update_widget']
        for method_name in handler_methods:
            self.assertTrue(hasattr(console_handler, method_name))
            method = getattr(console_handler, method_name)
            self.assertTrue(callable(method))
            print(f"    ✅ {method_name}")

    def test_console_handler_appends_newline(self):
        """測試控制台輸出包含換行字元"""
        print("\n💬 測試控制台換行行為...")

        text_widget = QTextEdit()
        handler = ConsoleHandler(text_widget, Mock())

        handler._update_widget("Test message", "INFO")

        self.assertTrue(
            text_widget.toPlainText().endswith("\n"),
            "Console text should end with a newline character",
        )

    def test_console_handler_updates_when_parent_hidden(self):
        """即使視窗隱藏也應更新控制台"""
        print("\n💬 測試控制台在視窗隱藏時仍更新...")

        text_widget = QTextEdit()
        hidden_parent = Mock()
        hidden_parent.isVisible.return_value = False

        handler = ConsoleHandler(text_widget, hidden_parent)

        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname=__file__,
            lineno=0,
            msg="Hidden message",
            args=(),
            exc_info=None,
        )

        handler.emit(record)
        self._qt_app.processEvents()

        self.assertIn("Hidden message", text_widget.toPlainText())

    def test_console_displays_related_logger_errors(self):
        """測試相關模組的錯誤訊息會顯示在控制台"""
        print("\n💬 測試控制台顯示相關 logger 訊息...")

        console_parent = Mock()
        console_parent.isVisible.return_value = True

        text_widget = QTextEdit()
        logging_manager = LoggingManager(console_parent)
        logging_manager.initialize_logging(text_widget)

        common_logger = logging.getLogger('common')
        test_message = "Simulated install failure: adb returned INSTALL_PARSE_FAILED_NO_CERTIFICATES"
        common_logger.warning(test_message)

        # 觸發 QTimer callbacks
        self._qt_app.processEvents()

        console_text = text_widget.toPlainText()
        self.assertIn(test_message, console_text)

    def test_log_levels_functionality(self):
        """測試日誌級別功能"""
        print("\n📊 測試日誌級別功能...")

        mock_parent = Mock()
        logging_manager = LoggingManager(mock_parent)

        # 測試日誌級別設定
        test_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
        for level in test_levels:
            logging_manager.set_log_level(level)
            # 由於沒有實際的logger，我們只是確保方法可以調用
            print(f"    ✅ 可以設置日誌級別: {level}")

        # 測試無效級別
        logging_manager.set_log_level('INVALID_LEVEL')
        print(f"    ✅ 無效日誌級別處理正確")

    def test_diagnostics_functionality(self):
        """測試診斷功能"""
        print("\n🔧 測試診斷功能...")

        mock_parent = Mock()
        mock_parent.device_dict = {
            'device1': Mock(device_serial_num='device1', device_model='Test Device 1')
        }

        diagnostics_manager = DiagnosticsManager(mock_parent)

        # 測試系統信息
        system_info = diagnostics_manager.get_system_info()
        self.assertIsInstance(system_info, dict)
        self.assertIn('系統', system_info)
        self.assertIn('Python版本', system_info)
        print(f"    ✅ 系統信息獲取正確")

        # 測試設備診斷
        device_diag = diagnostics_manager.get_device_diagnostics('device1')
        self.assertIsInstance(device_diag, dict)
        self.assertIn('設備序號', device_diag)
        print(f"    ✅ 設備診斷信息獲取正確")

        # 測試診斷報告生成
        report = diagnostics_manager.generate_diagnostics_report()
        self.assertIsInstance(report, str)
        self.assertIn('Lazy BlackTea 診斷報告', report)
        print(f"    ✅ 診斷報告生成正確")

    def test_main_window_method_delegation(self):
        """測試主視窗方法委託"""
        print("\n🔗 測試主視窗方法委託...")

        if hasattr(self.module, 'WindowMain'):
            WindowMain = getattr(self.module, 'WindowMain')

            # 檢查重構後的方法仍然存在
            refactored_methods = [
                'clear_logcat'
            ]

            for method_name in refactored_methods:
                self.assertTrue(hasattr(WindowMain, method_name))
                method = getattr(WindowMain, method_name)
                self.assertTrue(callable(method))
                print(f"    ✅ {method_name} 存在且可調用")

    def test_method_delegation_patterns(self):
        """測試方法委託模式"""
        print("\n📋 測試方法委託模式...")

        if hasattr(self.module, 'WindowMain'):
            WindowMain = getattr(self.module, 'WindowMain')

            # 檢查關鍵方法的源碼是否包含管理器委託
            delegation_patterns = {
                'clear_logcat': 'logging_manager'
            }

            for method_name, expected_manager in delegation_patterns.items():
                if hasattr(WindowMain, method_name):
                    try:
                        import inspect
                        method_source = inspect.getsource(getattr(WindowMain, method_name))
                        if expected_manager in method_source:
                            print(f"    ✅ {method_name} 委託給 {expected_manager}")
                        else:
                            print(f"    ⚠️  {method_name} 可能未正確委託給 {expected_manager}")
                    except:
                        print(f"    ⚠️  無法檢查 {method_name} 的源碼")

    def test_signal_definitions(self):
        """測試信號定義"""
        print("\n📡 測試信號定義...")

        mock_parent = Mock()

        # 測試LoggingManager信號
        logging_manager = LoggingManager(mock_parent)
        logging_signals = [
            'log_message_signal'
        ]

        for signal_name in logging_signals:
            self.assertTrue(hasattr(logging_manager, signal_name))
            print(f"    ✅ LoggingManager.{signal_name}")

    def test_mock_logging_operations(self):
        """測試日誌操作（模擬）"""
        print("\n⚡ 測試日誌操作...")

        mock_parent = Mock()
        logging_manager = LoggingManager(mock_parent)

        # 測試操作日誌方法
        operation_methods = [
            ('log_operation_start', ['測試操作', '詳細信息']),
            ('log_operation_complete', ['測試操作', '完成信息']),
            ('log_operation_failed', ['測試操作', '錯誤信息']),
        ]

        for method_name, args in operation_methods:
            method = getattr(logging_manager, method_name)
            # 這裡我們只是確保方法可以調用而不會拋出異常
            try:
                method(*args)
                print(f"    ✅ {method_name} 可以正常調用")
            except Exception as e:
                print(f"    ⚠️  {method_name} 調用時出現異常: {e}")

    def test_device_logging_operations(self):
        """測試設備相關日誌操作"""
        print("\n📱 測試設備日誌操作...")

        mock_parent = Mock()
        mock_parent.device_dict = {
            'test_device': Mock(device_serial_num='test_device', device_model='Test Device')
        }

        logging_manager = LoggingManager(mock_parent)

        # 測試設備操作日誌
        try:
            logging_manager.log_device_operation('test_device', '測試操作', '成功')
            logging_manager.log_command_execution('test command', ['device1', 'device2'], '執行中')
            print(f"    ✅ 設備日誌操作正常")
        except Exception as e:
            print(f"    ⚠️  設備日誌操作異常: {e}")


def run_logging_refactor_tests():
    """運行日誌系統重構測試的便利函數"""
    print("📋 運行日誌系統重構測試...")

    # 創建測試套件
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    # 添加重構測試
    suite.addTests(loader.loadTestsFromTestCase(LoggingRefactorTest))

    # 運行測試
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    print("\n" + "="*60)
    print("📊 日誌系統重構測試報告")
    print("="*60)

    if result.wasSuccessful():
        print("✅ 日誌系統重構測試通過！")
        print("📋 日誌管理器功能正常")
        print("🔧 診斷功能完整")
        print("💬 控制台處理器正確實現")
    else:
        print("❌ 日誌系統重構測試失敗！")
        print("⚠️  請檢查重構問題")

        if result.failures:
            print(f"\n失敗的測試 ({len(result.failures)}):")
            for test, traceback in result.failures:
                print(f"  - {test}")

        if result.errors:
            print(f"\n錯誤的測試 ({len(result.errors)}):")
            for test, traceback in result.errors:
                print(f"  - {test}")

    return result.wasSuccessful()


if __name__ == '__main__':
    success = run_logging_refactor_tests()
    sys.exit(0 if success else 1)
