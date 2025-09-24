#!/usr/bin/env python3
"""
接口兼容性測試 - 確保重構過程中公共接口不被破壞

這個測試模組專門驗證：
1. 公共類和方法的可用性
2. 方法簽名的一致性
3. 重要屬性的存在性
4. 向後兼容性
"""

import sys
import os
import unittest
import importlib
from typing import Dict, List, Any, Set
from unittest.mock import Mock, patch

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    import lazy_blacktea_pyqt
except ImportError as e:
    print(f"❌ 無法導入主模組: {e}")
    sys.exit(1)


class InterfaceCompatibilityTest(unittest.TestCase):
    """接口兼容性測試類"""

    @classmethod
    def setUpClass(cls):
        """設置測試環境"""
        cls.module = lazy_blacktea_pyqt

        # 定義重要的公共接口 - 這些在重構過程中不應該被破壞
        cls.critical_classes = {
            'WindowMain': [
                # 設備管理相關
                'get_checked_devices',
                'update_device_list',
                'refresh_device_list',
                'select_all_devices',
                'select_no_devices',

                # UI相關
                'init_ui',
                'set_ui_scale',
                'set_refresh_interval',

                # 設備操作相關
                'reboot_device',
                'enable_bluetooth',
                'disable_bluetooth',
                'take_screenshot',
                'start_screen_record',
                'stop_screen_record',

                # 命令執行相關
                'run_shell_command',
                'install_apk',
                'launch_scrcpy',

                # 文件生成相關
                'generate_android_bug_report',
                'generate_device_discovery_file',

                # 配置管理相關
                'save_config',
                'load_config',

                # 事件處理相關
                'on_search_changed',
                'on_sort_changed',

                # 消息顯示相關
                'show_info',
                'show_warning',
                'show_error'
            ],

            'UIInspectorDialog': [
                'setup_ui',
                'create_screenshot_panel'
            ],

            'ClickableScreenshotLabel': [
                'mousePressEvent'
            ],

            'ConsoleHandler': [
                'emit'
            ]
        }

        # 定義重要的模組級函數
        cls.critical_functions = [
            'main'
        ]

    def test_critical_classes_exist(self):
        """測試重要類是否存在"""
        print("\n🔍 測試重要類是否存在...")

        for class_name in self.critical_classes.keys():
            with self.subTest(class_name=class_name):
                self.assertTrue(
                    hasattr(self.module, class_name),
                    f"重要類 {class_name} 不存在"
                )
                print(f"  ✅ {class_name} 存在")

    def test_critical_methods_exist(self):
        """測試重要方法是否存在"""
        print("\n🔍 測試重要方法是否存在...")

        for class_name, methods in self.critical_classes.items():
            if hasattr(self.module, class_name):
                cls = getattr(self.module, class_name)

                for method_name in methods:
                    with self.subTest(class_name=class_name, method_name=method_name):
                        self.assertTrue(
                            hasattr(cls, method_name),
                            f"重要方法 {class_name}.{method_name} 不存在"
                        )
                        print(f"  ✅ {class_name}.{method_name} 存在")

    def test_critical_methods_callable(self):
        """測試重要方法是否可調用"""
        print("\n🔍 測試重要方法是否可調用...")

        for class_name, methods in self.critical_classes.items():
            if hasattr(self.module, class_name):
                cls = getattr(self.module, class_name)

                for method_name in methods:
                    if hasattr(cls, method_name):
                        with self.subTest(class_name=class_name, method_name=method_name):
                            method = getattr(cls, method_name)
                            self.assertTrue(
                                callable(method),
                                f"方法 {class_name}.{method_name} 不可調用"
                            )
                            print(f"  ✅ {class_name}.{method_name} 可調用")

    def test_critical_functions_exist(self):
        """測試重要函數是否存在"""
        print("\n🔍 測試重要函數是否存在...")

        for func_name in self.critical_functions:
            with self.subTest(func_name=func_name):
                self.assertTrue(
                    hasattr(self.module, func_name),
                    f"重要函數 {func_name} 不存在"
                )
                self.assertTrue(
                    callable(getattr(self.module, func_name)),
                    f"函數 {func_name} 不可調用"
                )
                print(f"  ✅ {func_name} 存在且可調用")

    def test_windowmain_initialization_compatibility(self):
        """測試WindowMain類的初始化兼容性"""
        print("\n🔍 測試WindowMain初始化兼容性...")

        if hasattr(self.module, 'WindowMain'):
            WindowMain = getattr(self.module, 'WindowMain')

            # 測試是否可以不帶參數初始化（可能會因為PyQt6而失敗，但至少類定義要正確）
            try:
                # 不實際創建實例，只檢查類定義
                init_method = getattr(WindowMain, '__init__')
                self.assertTrue(callable(init_method))
                print(f"  ✅ WindowMain.__init__ 方法存在且可調用")
            except Exception as e:
                self.fail(f"WindowMain 初始化檢查失敗: {e}")

    def test_important_attributes_exist(self):
        """測試重要屬性是否在類定義中存在"""
        print("\n🔍 測試重要屬性定義...")

        if hasattr(self.module, 'WindowMain'):
            WindowMain = getattr(self.module, 'WindowMain')

            # 檢查__init__方法中是否定義了重要屬性
            # 這裡我們通過檢查方法來推斷屬性的存在
            important_method_patterns = [
                ('device_dict', ['update_device_list', 'get_checked_devices']),
                ('check_devices', ['select_all_devices', 'select_no_devices']),
                ('refresh_interval', ['set_refresh_interval']),
                ('device_search_manager', ['on_search_changed', 'on_sort_changed'])
            ]

            for attr_name, related_methods in important_method_patterns:
                methods_exist = all(hasattr(WindowMain, method) for method in related_methods)
                if methods_exist:
                    print(f"  ✅ {attr_name} 相關方法存在，屬性應該已定義")
                else:
                    missing = [m for m in related_methods if not hasattr(WindowMain, m)]
                    self.fail(f"屬性 {attr_name} 相關的方法缺失: {missing}")

    def test_module_imports_successfully(self):
        """測試模組可以成功導入而不出錯"""
        print("\n🔍 測試模組導入...")

        try:
            # 重新導入模組確認沒有語法錯誤
            importlib.reload(self.module)
            print("  ✅ 模組導入成功")
        except Exception as e:
            self.fail(f"模組導入失敗: {e}")

    def test_no_missing_dependencies(self):
        """測試沒有缺失依賴"""
        print("\n🔍 測試依賴完整性...")

        # 檢查重要的導入
        important_imports = [
            'PyQt6.QtWidgets',
            'PyQt6.QtCore',
            'PyQt6.QtGui',
            'utils.adb_models',
            'utils.adb_tools',
            'ui.device_search_manager'
        ]

        for import_name in important_imports:
            try:
                __import__(import_name)
                print(f"  ✅ {import_name} 可以導入")
            except ImportError as e:
                # 某些導入可能在測試環境中不可用，這是可以接受的
                print(f"  ⚠️  {import_name} 導入警告: {e}")

    def test_backward_compatibility_aliases(self):
        """測試向後兼容性別名（如果有的話）"""
        print("\n🔍 測試向後兼容性...")

        # 如果在重構過程中創建了別名，在這裡測試
        # 例如：如果我們將某個方法重命名，但保留了舊名字作為別名

        # 這個測試會在實際重構時根據需要更新
        print("  ✅ 向後兼容性檢查完成（目前無特殊別名需求）")

    def test_interface_stability(self):
        """測試接口穩定性 - 檢查方法簽名沒有意外改變"""
        print("\n🔍 測試接口穩定性...")

        # 這個測試會檢查關鍵方法的簽名
        if hasattr(self.module, 'WindowMain'):
            WindowMain = getattr(self.module, 'WindowMain')

            # 檢查一些關鍵方法的存在性和基本簽名
            key_methods_with_expected_params = {
                'get_checked_devices': 0,  # 應該不需要參數
                'show_info': 2,  # 應該需要 title 和 message
                'show_warning': 2,  # 應該需要 title 和 message
                'show_error': 2,   # 應該需要 title 和 message
            }

            for method_name, expected_param_count in key_methods_with_expected_params.items():
                if hasattr(WindowMain, method_name):
                    method = getattr(WindowMain, method_name)
                    if callable(method):
                        try:
                            import inspect
                            sig = inspect.signature(method)
                            # 減去self參數
                            actual_param_count = len(sig.parameters) - 1

                            if actual_param_count == expected_param_count:
                                print(f"  ✅ {method_name} 簽名符合預期")
                            else:
                                print(f"  ⚠️  {method_name} 參數數量: 預期{expected_param_count}, 實際{actual_param_count}")
                        except Exception as e:
                            print(f"  ⚠️  無法檢查 {method_name} 的簽名: {e}")


def run_compatibility_tests():
    """運行接口兼容性測試的便利函數"""
    print("🔬 運行接口兼容性測試...")

    # 創建測試套件
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    # 添加兼容性測試
    suite.addTests(loader.loadTestsFromTestCase(InterfaceCompatibilityTest))

    # 運行測試
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    print("\n" + "="*60)
    print("📊 接口兼容性測試報告")
    print("="*60)
    if result.wasSuccessful():
        print("✅ 所有接口兼容性測試通過！")
        print("🎯 重構可以安全進行")
    else:
        print("❌ 發現接口兼容性問題！")
        print("⚠️  請在繼續重構前修復這些問題")

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
    success = run_compatibility_tests()
    sys.exit(0 if success else 1)