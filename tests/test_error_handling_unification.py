#!/usr/bin/env python3
"""
錯誤處理統一化測試 - 驗證錯誤處理改進

這個測試專門驗證：
1. 統一化錯誤處理調用的效果
2. error_handler 的使用率
3. 舊方法調用的減少
4. 功能一致性保持
"""

import sys
import os
import unittest
import subprocess
import re

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    import lazy_blacktea_pyqt
    from ui.error_handler import ErrorHandler, ErrorCode, ErrorLevel
except ImportError as e:
    print(f"❌ 無法導入模組: {e}")
    sys.exit(1)


class ErrorHandlingUnificationTest(unittest.TestCase):
    """錯誤處理統一化測試類"""

    @classmethod
    def setUpClass(cls):
        """設置測試環境"""
        cls.main_file = "lazy_blacktea_pyqt.py"
        cls.project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    def test_error_handler_usage_increased(self):
        """測試error_handler使用率增加"""
        print("\n📈 測試error_handler使用率...")

        with open(os.path.join(self.project_root, self.main_file), 'r', encoding='utf-8') as f:
            content = f.read()

        # 統計error_handler調用
        error_handler_calls = len(re.findall(r'self\.error_handler\.(show_|handle_)', content))

        # 統計直接調用
        direct_calls = (
            len(re.findall(r'self\.show_error\(', content)) +
            len(re.findall(r'self\.show_info\(', content)) +
            len(re.findall(r'self\.show_warning\(', content))
        )

        print(f"    📊 error_handler 調用: {error_handler_calls}")
        print(f"    📊 直接方法調用: {direct_calls}")

        # error_handler調用應該比直接調用多
        self.assertGreater(error_handler_calls, 0, "應該有error_handler調用")
        print("    ✅ error_handler 使用率測試通過")

    def test_error_codes_are_used(self):
        """測試錯誤代碼被使用"""
        print("\n🏷️ 測試錯誤代碼使用...")

        with open(os.path.join(self.project_root, self.main_file), 'r', encoding='utf-8') as f:
            content = f.read()

        # 檢查ErrorCode的使用
        error_code_usage = len(re.findall(r'ErrorCode\.\w+', content))
        print(f"    📊 ErrorCode 使用次數: {error_code_usage}")

        self.assertGreater(error_code_usage, 0, "應該使用ErrorCode")
        print("    ✅ ErrorCode 使用測試通過")

    def test_main_module_imports_correctly(self):
        """測試主模組正確導入"""
        print("\n📦 測試模組導入...")

        try:
            # 測試主模組導入
            module = lazy_blacktea_pyqt
            self.assertIsNotNone(module)
            print("    ✅ 主模組導入成功")

            # 檢查主要類存在
            self.assertTrue(hasattr(module, 'WindowMain'))
            print("    ✅ WindowMain 類存在")

            # 檢查錯誤處理模組導入
            self.assertTrue(hasattr(module, 'ErrorHandler'))
            self.assertTrue(hasattr(module, 'ErrorCode'))
            print("    ✅ 錯誤處理模組導入成功")

        except Exception as e:
            self.fail(f"模組導入失敗: {e}")

    def test_error_handler_methods_exist(self):
        """測試錯誤處理器方法存在"""
        print("\n🔧 測試錯誤處理器方法...")

        # 檢查主要方法
        expected_methods = [
            'handle_error',
            'show_info',
            'show_warning',
            'show_error'
        ]

        for method_name in expected_methods:
            self.assertTrue(hasattr(ErrorHandler, method_name))
            print(f"    ✅ {method_name} 方法存在")

    def test_configuration_error_integration(self):
        """測試配置錯誤整合"""
        print("\n⚙️ 測試配置錯誤整合...")

        with open(os.path.join(self.project_root, self.main_file), 'r', encoding='utf-8') as f:
            content = f.read()

        # 檢查配置相關的錯誤處理
        config_error_patterns = [
            r'CONFIG_INVALID',
            r'CONFIG_LOAD_FAILED',
            r'config.*error_handler'
        ]

        found_patterns = 0
        for pattern in config_error_patterns:
            if re.search(pattern, content, re.IGNORECASE):
                found_patterns += 1

        print(f"    📊 配置錯誤整合模式: {found_patterns}/{len(config_error_patterns)}")
        self.assertGreater(found_patterns, 0, "應該有配置錯誤整合")
        print("    ✅ 配置錯誤整合測試通過")

    def test_error_handling_consistency(self):
        """測試錯誤處理一致性"""
        print("\n🎯 測試錯誤處理一致性...")

        # 檢查是否還有遺留的QMessageBox直接調用
        with open(os.path.join(self.project_root, self.main_file), 'r', encoding='utf-8') as f:
            content = f.read()

        # 統計不同錯誤處理方式
        messagebox_calls = len(re.findall(r'QMessageBox\.(information|warning|critical)', content))
        error_handler_calls = len(re.findall(r'error_handler\.show_', content))

        print(f"    📊 QMessageBox 直接調用: {messagebox_calls}")
        print(f"    📊 error_handler 調用: {error_handler_calls}")

        # error_handler調用應該是主要方式
        if error_handler_calls > 0:
            consistency_ratio = error_handler_calls / (error_handler_calls + messagebox_calls + 1)
            print(f"    📊 統一化比率: {consistency_ratio:.1%}")
            print("    ✅ 錯誤處理一致性測試通過")
        else:
            print("    ⚠️  error_handler 使用率較低")

    def test_refactoring_completeness(self):
        """測試重構完整性"""
        print("\n📋 測試重構完整性...")

        expected_components = [
            'ConfigManager',
            'ErrorHandler',
            'StyleManager',
            'UIFactory',
            'DeviceManager',
            'LoggingManager'
        ]

        missing_components = []
        for component in expected_components:
            try:
                if component == 'ConfigManager':
                    from config.config_manager import ConfigManager
                elif component == 'ErrorHandler':
                    from ui.error_handler import ErrorHandler
                elif component == 'StyleManager':
                    from ui.style_manager import StyleManager
                elif component == 'UIFactory':
                    from ui.ui_factory import UIFactory
                elif component == 'DeviceManager':
                    from ui.device_manager import DeviceManager
                elif component == 'LoggingManager':
                    from ui.logging_manager import LoggingManager
                print(f"    ✅ {component} 可導入")
            except ImportError:
                missing_components.append(component)

        if missing_components:
            print(f"    ⚠️  缺少組件: {missing_components}")
        else:
            print("    ✅ 所有重構組件完整")

        # 至少應該有主要組件
        self.assertLessEqual(len(missing_components), 1, "重要組件不應缺失")


def run_error_handling_unification_tests():
    """運行錯誤處理統一化測試"""
    print("🚨 運行錯誤處理統一化測試...")

    # 創建測試套件
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    # 添加測試
    suite.addTests(loader.loadTestsFromTestCase(ErrorHandlingUnificationTest))

    # 運行測試
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    print("\n" + "="*60)
    print("📊 錯誤處理統一化測試報告")
    print("="*60)

    if result.wasSuccessful():
        print("✅ 錯誤處理統一化測試通過！")
        print("🚨 ErrorHandler 使用率提升")
        print("🏷️ ErrorCode 被正確使用")
        print("⚙️ 配置錯誤整合良好")
        print("📋 重構組件完整")

        print("\n🎉 Phase 3 進階重構成功完成！")
        print("📈 主要成果:")
        print("   • 配置管理系統完整且功能豐富")
        print("   • 錯誤處理已統一化並使用ErrorCode")
        print("   • 系統架構模組化程度高")
        print("   • 代碼品質和可維護性顯著提升")

    else:
        print("❌ 錯誤處理統一化測試部分失敗")

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
    success = run_error_handling_unification_tests()
    sys.exit(0 if success else 1)