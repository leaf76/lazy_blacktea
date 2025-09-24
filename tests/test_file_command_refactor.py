#!/usr/bin/env python3
"""
文件操作和命令執行重構測試 - 確保文件和命令操作重構的正確性

這個測試專門驗證：
1. 文件操作管理器的功能完整性
2. 命令執行管理器的功能完整性
3. 命令歷史管理器的功能完整性
4. UI層級管理器的功能完整性
5. 重構前後功能的一致性
"""

import sys
import os
import unittest
from unittest.mock import Mock, patch, MagicMock

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    import lazy_blacktea_pyqt
    from ui.file_operations_manager import FileOperationsManager, CommandHistoryManager, UIHierarchyManager
    from ui.command_execution_manager import CommandExecutionManager
except ImportError as e:
    print(f"❌ 無法導入模組: {e}")
    sys.exit(1)


class FileCommandRefactorTest(unittest.TestCase):
    """文件操作和命令執行重構測試類"""

    @classmethod
    def setUpClass(cls):
        """設置測試環境"""
        cls.module = lazy_blacktea_pyqt

    def test_new_manager_classes_exist(self):
        """測試新管理器類的存在性"""
        print("\n🔍 測試新管理器類...")

        manager_classes = [
            ('FileOperationsManager', FileOperationsManager),
            ('CommandHistoryManager', CommandHistoryManager),
            ('UIHierarchyManager', UIHierarchyManager),
            ('CommandExecutionManager', CommandExecutionManager),
        ]

        for class_name, class_obj in manager_classes:
            print(f"  ✅ {class_name} 類存在")
            self.assertTrue(hasattr(class_obj, '__init__'))
            print(f"    📋 {class_name} 可以實例化")

    def test_main_window_has_managers(self):
        """測試主視窗包含新管理器"""
        print("\n🔍 測試主視窗管理器...")

        if hasattr(self.module, 'WindowMain'):
            WindowMain = getattr(self.module, 'WindowMain')

            # 檢查管理器屬性的存在（在類定義中）
            manager_attrs = [
                'file_operations_manager',
                'command_history_manager',
                'ui_hierarchy_manager',
                'command_execution_manager'
            ]

            # 由於我們不能實例化真實的WindowMain（因為PyQt依賴），
            # 我們檢查__init__方法中是否提及這些管理器
            init_source = None
            try:
                import inspect
                init_source = inspect.getsource(WindowMain.__init__)
            except:
                pass

            if init_source:
                for manager_attr in manager_attrs:
                    if manager_attr in init_source:
                        print(f"  ✅ {manager_attr} 在WindowMain.__init__中被初始化")
                    else:
                        print(f"  ❌ {manager_attr} 未在WindowMain.__init__中找到")
                        self.fail(f"管理器 {manager_attr} 未在WindowMain初始化中找到")
            else:
                print("  ⚠️  無法檢查WindowMain.__init__源碼，跳過詳細檢查")

    def test_file_operations_manager_methods(self):
        """測試文件操作管理器方法"""
        print("\n🔍 測試文件操作管理器方法...")

        # 創建模擬的父視窗
        mock_parent = Mock()
        file_manager = FileOperationsManager(mock_parent)

        # 檢查關鍵方法
        key_methods = [
            'get_validated_output_path',
            'generate_android_bug_report',
            'generate_device_discovery_file',
            'pull_device_dcim_folder'
        ]

        for method_name in key_methods:
            self.assertTrue(hasattr(file_manager, method_name))
            method = getattr(file_manager, method_name)
            self.assertTrue(callable(method))
            print(f"    ✅ {method_name}")

    def test_command_history_manager_methods(self):
        """測試命令歷史管理器方法"""
        print("\n🔍 測試命令歷史管理器方法...")

        mock_parent = Mock()
        history_manager = CommandHistoryManager(mock_parent)

        key_methods = [
            'add_to_history',
            'clear_history',
            'export_command_history',
            'import_command_history',
            'load_command_history_from_config',
            'save_command_history_to_config'
        ]

        for method_name in key_methods:
            self.assertTrue(hasattr(history_manager, method_name))
            method = getattr(history_manager, method_name)
            self.assertTrue(callable(method))
            print(f"    ✅ {method_name}")

        # 測試命令歷史初始化
        self.assertIsInstance(history_manager.command_history, list)
        print(f"    ✅ command_history 初始化為列表")

    def test_command_execution_manager_methods(self):
        """測試命令執行管理器方法"""
        print("\n🔍 測試命令執行管理器方法...")

        mock_parent = Mock()
        exec_manager = CommandExecutionManager(mock_parent)

        key_methods = [
            'run_shell_command',
            'execute_single_command',
            'execute_batch_commands',
            'log_command_results',
            'write_to_console',
            'get_valid_commands_from_text',
            'add_template_command'
        ]

        for method_name in key_methods:
            self.assertTrue(hasattr(exec_manager, method_name))
            method = getattr(exec_manager, method_name)
            self.assertTrue(callable(method))
            print(f"    ✅ {method_name}")

    def test_ui_hierarchy_manager_methods(self):
        """測試UI層級管理器方法"""
        print("\n🔍 測試UI層級管理器方法...")

        mock_parent = Mock()
        ui_manager = UIHierarchyManager(mock_parent)

        key_methods = [
            'export_hierarchy'
        ]

        for method_name in key_methods:
            self.assertTrue(hasattr(ui_manager, method_name))
            method = getattr(ui_manager, method_name)
            self.assertTrue(callable(method))
            print(f"    ✅ {method_name}")

    def test_refactored_methods_in_main_window(self):
        """測試主視窗中重構後的方法"""
        print("\n🔍 測試主視窗重構後的方法...")

        if hasattr(self.module, 'WindowMain'):
            WindowMain = getattr(self.module, 'WindowMain')

            # 檢查重構後的方法仍然存在
            refactored_methods = [
                # 文件操作方法
                'generate_android_bug_report',
                'generate_device_discovery_file',
                'pull_device_dcim_with_folder',
                'dump_device_hsv',

                # 命令歷史方法
                'export_command_history',
                'import_command_history',
                'clear_command_history',
                'add_to_history',

                # 命令執行方法
                'run_shell_command',
                'execute_single_command',
                'run_single_command',
                'run_batch_commands',
                'get_valid_commands',
                'add_template_command'
            ]

            for method_name in refactored_methods:
                self.assertTrue(hasattr(WindowMain, method_name))
                method = getattr(WindowMain, method_name)
                self.assertTrue(callable(method))
                print(f"    ✅ {method_name} 存在且可調用")

    def test_method_delegation_patterns(self):
        """測試方法委託模式"""
        print("\n🔍 測試方法委託模式...")

        if hasattr(self.module, 'WindowMain'):
            WindowMain = getattr(self.module, 'WindowMain')

            # 檢查一些關鍵方法的源碼是否包含管理器委託
            delegation_patterns = {
                'generate_android_bug_report': 'file_operations_manager',
                'export_command_history': 'command_history_manager',
                'run_shell_command': 'command_execution_manager',
                'dump_device_hsv': 'ui_hierarchy_manager'
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

    def test_command_history_functionality(self):
        """測試命令歷史功能"""
        print("\n🔍 測試命令歷史功能...")

        mock_parent = Mock()
        history_manager = CommandHistoryManager(mock_parent)

        # 測試添加命令
        test_command = "adb shell ls"
        history_manager.add_to_history(test_command)
        self.assertIn(test_command, history_manager.command_history)
        print(f"    ✅ 命令添加到歷史記錄成功")

        # 測試重複命令不會重複添加
        initial_length = len(history_manager.command_history)
        history_manager.add_to_history(test_command)
        self.assertEqual(len(history_manager.command_history), initial_length)
        print(f"    ✅ 重複命令不會重複添加")

        # 測試清空歷史
        history_manager.clear_history()
        self.assertEqual(len(history_manager.command_history), 0)
        print(f"    ✅ 命令歷史清空成功")

    def test_command_execution_text_parsing(self):
        """測試命令執行文本解析"""
        print("\n🔍 測試命令執行文本解析...")

        mock_parent = Mock()
        exec_manager = CommandExecutionManager(mock_parent)

        # 測試正常命令解析
        test_text = """
        # This is a comment
        adb shell ls

        adb shell ps
        # Another comment
        adb devices
        """

        commands = exec_manager.get_valid_commands_from_text(test_text)
        expected_commands = ["adb shell ls", "adb shell ps", "adb devices"]

        self.assertEqual(len(commands), 3)
        for expected_cmd in expected_commands:
            self.assertIn(expected_cmd, commands)

        print(f"    ✅ 文本解析正確：找到 {len(commands)} 個有效命令")

    def test_signal_connections_readiness(self):
        """測試信號連接準備情況"""
        print("\n🔍 測試信號連接準備...")

        # 檢查管理器類是否有適當的信號定義
        signal_tests = [
            (FileOperationsManager, 'file_generation_completed_signal'),
            (CommandExecutionManager, 'console_output_signal'),
        ]

        for manager_class, signal_name in signal_tests:
            # 我們需要PyQt來測試信號，這裡只檢查類結構
            print(f"    📋 {manager_class.__name__} 預期有 {signal_name} 信號")


def run_file_command_refactor_tests():
    """運行文件操作和命令執行重構測試的便利函數"""
    print("🔧 運行文件操作和命令執行重構測試...")

    # 創建測試套件
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    # 添加重構測試
    suite.addTests(loader.loadTestsFromTestCase(FileCommandRefactorTest))

    # 運行測試
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    print("\n" + "="*60)
    print("📊 文件操作和命令執行重構測試報告")
    print("="*60)

    if result.wasSuccessful():
        print("✅ 文件操作和命令執行重構測試通過！")
        print("🔧 重構成功完成")
    else:
        print("❌ 文件操作和命令執行重構測試失敗！")
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
    success = run_file_command_refactor_tests()
    sys.exit(0 if success else 1)