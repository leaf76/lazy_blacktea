#!/usr/bin/env python3
"""
UI工廠重構專用測試 - 確保UI創建邏輯重構的正確性

這個測試專門驗證：
1. UI創建方法的存在性和可調用性
2. 重構前後UI組件創建的一致性
3. UI工廠模組的功能完整性
"""

import sys
import os
import unittest
from unittest.mock import Mock, patch, MagicMock

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    import lazy_blacktea_pyqt
except ImportError as e:
    print(f"❌ 無法導入主模組: {e}")
    sys.exit(1)


class UIFactoryRefactorTest(unittest.TestCase):
    """UI工廠重構測試類"""

    @classmethod
    def setUpClass(cls):
        """設置測試環境"""
        cls.module = lazy_blacktea_pyqt

        # 定義需要重構的UI創建方法
        cls.ui_creation_methods = [
            'create_tools_panel',
            'create_adb_tools_tab',
            'create_shell_commands_tab',
            'create_file_generation_tab',
            'create_device_groups_tab',
            'create_console_panel',
            'create_status_bar'
        ]

        # UIInspectorDialog中的UI創建方法
        cls.ui_inspector_methods = [
            'create_modern_toolbar',
            'create_system_button',
            'create_screenshot_panel',
            'create_inspector_panel',
            'create_element_details_tab',
            'create_hierarchy_tab'
        ]

    def test_original_ui_methods_exist_in_main_class(self):
        """測試原始UI方法在主類中存在"""
        print("\n🔍 測試原始UI創建方法...")

        if hasattr(self.module, 'WindowMain'):
            WindowMain = getattr(self.module, 'WindowMain')

            for method_name in self.ui_creation_methods:
                with self.subTest(method=method_name):
                    self.assertTrue(
                        hasattr(WindowMain, method_name),
                        f"UI創建方法 {method_name} 在WindowMain中不存在"
                    )

                    method = getattr(WindowMain, method_name)
                    self.assertTrue(
                        callable(method),
                        f"UI創建方法 {method_name} 不可調用"
                    )
                    print(f"  ✅ {method_name} 存在且可調用")

    def test_ui_inspector_methods_exist(self):
        """測試UIInspectorDialog中的UI方法存在"""
        print("\n🔍 測試UIInspectorDialog UI方法...")

        if hasattr(self.module, 'UIInspectorDialog'):
            UIInspectorDialog = getattr(self.module, 'UIInspectorDialog')

            for method_name in self.ui_inspector_methods:
                with self.subTest(method=method_name):
                    self.assertTrue(
                        hasattr(UIInspectorDialog, method_name),
                        f"UI方法 {method_name} 在UIInspectorDialog中不存在"
                    )

                    method = getattr(UIInspectorDialog, method_name)
                    self.assertTrue(
                        callable(method),
                        f"UI方法 {method_name} 不可調用"
                    )
                    print(f"  ✅ {method_name} 存在且可調用")

    @patch('PyQt6.QtWidgets.QWidget')
    @patch('PyQt6.QtWidgets.QVBoxLayout')
    @patch('PyQt6.QtWidgets.QHBoxLayout')
    def test_ui_creation_methods_basic_functionality(self, mock_hlayout, mock_vlayout, mock_widget):
        """測試UI創建方法的基本功能（模擬PyQt6環境）"""
        print("\n🧪 測試UI創建方法基本功能...")

        # 模擬PyQt6組件
        mock_widget_instance = Mock()
        mock_layout_instance = Mock()
        mock_widget.return_value = mock_widget_instance
        mock_vlayout.return_value = mock_layout_instance
        mock_hlayout.return_value = mock_layout_instance

        if hasattr(self.module, 'WindowMain'):
            # 無法直接實例化WindowMain（需要QApplication），所以測試方法存在性
            WindowMain = getattr(self.module, 'WindowMain')

            # 檢查方法簽名
            for method_name in self.ui_creation_methods:
                method = getattr(WindowMain, method_name)

                # 檢查方法是否接受適當的參數
                import inspect
                sig = inspect.signature(method)
                param_count = len(sig.parameters) - 1  # 減去self參數

                print(f"  📋 {method_name}: {param_count} 個參數")

                # 基本的參數數量檢查
                if method_name in ['create_tools_panel', 'create_console_panel']:
                    self.assertGreaterEqual(param_count, 1, f"{method_name} 應該接受parent參數")
                elif method_name in ['create_adb_tools_tab', 'create_shell_commands_tab',
                                   'create_file_generation_tab', 'create_device_groups_tab']:
                    self.assertGreaterEqual(param_count, 1, f"{method_name} 應該接受tab_widget參數")

    def test_ui_method_return_types_documentation(self):
        """測試UI方法的返回類型文檔"""
        print("\n📝 測試UI方法文檔...")

        if hasattr(self.module, 'WindowMain'):
            WindowMain = getattr(self.module, 'WindowMain')

            for method_name in self.ui_creation_methods:
                method = getattr(WindowMain, method_name)

                # 檢查是否有文檔字符串
                docstring = getattr(method, '__doc__', None)

                if docstring:
                    print(f"  📚 {method_name}: 有文檔")
                else:
                    print(f"  ⚠️  {method_name}: 缺少文檔")

    def test_prepare_for_ui_factory_extraction(self):
        """測試準備UI工廠提取的先決條件"""
        print("\n🏭 測試UI工廠提取準備...")

        # 檢查是否已經有現有的UI相關模組
        ui_modules = ['ui.panels_manager', 'ui.device_manager', 'ui.device_search_manager']

        for module_name in ui_modules:
            try:
                __import__(module_name)
                print(f"  ✅ {module_name} 已存在")
            except ImportError:
                print(f"  ❌ {module_name} 不存在")

        # 檢查主模組的導入結構
        if hasattr(self.module, 'WindowMain'):
            WindowMain = getattr(self.module, 'WindowMain')

            # 檢查是否已經有UI相關的屬性
            ui_related_attrs = ['panels_manager', 'device_manager', 'device_search_manager']

            for attr_name in ui_related_attrs:
                if hasattr(WindowMain, '__init__'):
                    # 這裡我們只能檢查屬性名是否在類的某個地方被提及
                    print(f"  📋 檢查 {attr_name} 屬性的準備情況")

    def test_method_dependencies(self):
        """測試方法之間的依賴關係"""
        print("\n🔗 測試方法依賴關係...")

        if hasattr(self.module, 'WindowMain'):
            WindowMain = getattr(self.module, 'WindowMain')

            # 檢查create_方法是否依賴於其他方法
            dependencies = {
                'create_tools_panel': ['create_adb_tools_tab'],
                'create_adb_tools_tab': [],
                'create_shell_commands_tab': [],
                'create_file_generation_tab': [],
                'create_device_groups_tab': [],
                'create_console_panel': [],
                'create_status_bar': []
            }

            for method_name, expected_deps in dependencies.items():
                print(f"  🔍 檢查 {method_name} 的依賴:")
                for dep in expected_deps:
                    if hasattr(WindowMain, dep):
                        print(f"    ✅ 依賴 {dep} 存在")
                    else:
                        print(f"    ❌ 依賴 {dep} 缺失")

    def test_ui_components_import_readiness(self):
        """測試UI組件導入準備情況"""
        print("\n📦 測試UI組件導入準備...")

        # 檢查必要的PyQt6組件是否可導入
        required_imports = [
            'PyQt6.QtWidgets.QWidget',
            'PyQt6.QtWidgets.QVBoxLayout',
            'PyQt6.QtWidgets.QHBoxLayout',
            'PyQt6.QtWidgets.QGridLayout',
            'PyQt6.QtWidgets.QTabWidget',
            'PyQt6.QtWidgets.QPushButton',
            'PyQt6.QtWidgets.QLabel',
            'PyQt6.QtWidgets.QGroupBox'
        ]

        for import_path in required_imports:
            try:
                module_path, class_name = import_path.rsplit('.', 1)
                module = __import__(module_path, fromlist=[class_name])
                getattr(module, class_name)
                print(f"  ✅ {class_name} 可導入")
            except (ImportError, AttributeError) as e:
                print(f"  ❌ {class_name} 導入失敗: {e}")


def run_ui_factory_tests():
    """運行UI工廠重構測試的便利函數"""
    print("🏭 運行UI工廠重構測試...")

    # 創建測試套件
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    # 添加UI工廠測試
    suite.addTests(loader.loadTestsFromTestCase(UIFactoryRefactorTest))

    # 運行測試
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    print("\n" + "="*60)
    print("📊 UI工廠重構測試報告")
    print("="*60)

    if result.wasSuccessful():
        print("✅ UI工廠重構準備測試通過！")
        print("🏭 可以安全開始UI創建邏輯重構")
    else:
        print("❌ UI工廠重構準備測試失敗！")
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
    success = run_ui_factory_tests()
    sys.exit(0 if success else 1)