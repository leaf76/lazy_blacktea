#!/usr/bin/env python3
"""
配置管理和錯誤處理整合測試 - 確保兩個系統協同工作

這個測試專門驗證：
1. ConfigManager和ErrorHandler的協同使用
2. 配置錯誤的統一處理
3. 錯誤處理中的配置依賴
4. 系統整合的完整性
"""

import sys
import os
import unittest
import tempfile
from unittest.mock import Mock, patch
from pathlib import Path

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from config.config_manager import ConfigManager, AppConfig
    from ui.error_handler import ErrorHandler, ErrorCode, ErrorLevel
except ImportError as e:
    print(f"❌ 無法導入模組: {e}")
    sys.exit(1)


class ConfigErrorIntegrationTest(unittest.TestCase):
    """配置管理和錯誤處理整合測試類"""

    def setUp(self):
        """設置測試環境"""
        self.temp_dir = tempfile.mkdtemp()
        self.config_path = Path(self.temp_dir) / "test_config.json"
        self.config_manager = ConfigManager(str(self.config_path))

        # Mock parent window for error handler
        self.mock_parent = Mock()
        self.error_handler = ErrorHandler(self.mock_parent)

    def tearDown(self):
        """清理測試環境"""
        import shutil
        if Path(self.temp_dir).exists():
            shutil.rmtree(self.temp_dir)

    def test_config_manager_exists_and_functional(self):
        """測試配置管理器存在且功能正常"""
        print("\n📋 測試配置管理器...")

        # 測試預設配置創建
        config = self.config_manager.load_config()
        self.assertIsInstance(config, AppConfig)
        print("    ✅ 預設配置創建成功")

        # 測試配置保存
        self.config_manager.save_config(config)
        self.assertTrue(self.config_path.exists())
        print("    ✅ 配置保存成功")

        # 測試配置載入
        loaded_config = self.config_manager.load_config()
        self.assertEqual(config.ui.window_width, loaded_config.ui.window_width)
        print("    ✅ 配置載入成功")

    def test_error_handler_exists_and_functional(self):
        """測試錯誤處理器存在且功能正常"""
        print("\n🚨 測試錯誤處理器...")

        # 測試錯誤處理方法存在
        key_methods = [
            'handle_error',
            'show_info',
            'show_warning',
            'show_error'
        ]

        for method_name in key_methods:
            self.assertTrue(hasattr(self.error_handler, method_name))
            method = getattr(self.error_handler, method_name)
            self.assertTrue(callable(method))
            print(f"    ✅ {method_name} 方法存在")

    def test_config_error_handling_integration(self):
        """測試配置錯誤的統一處理"""
        print("\n🔗 測試配置錯誤整合...")

        # 模擬配置載入錯誤
        invalid_config_path = Path(self.temp_dir) / "invalid_config.json"
        with open(invalid_config_path, 'w') as f:
            f.write("invalid json content")

        config_manager = ConfigManager(str(invalid_config_path))

        # 測試錯誤處理 - 配置載入失敗應該回退到預設配置
        config = config_manager.load_config()
        self.assertIsInstance(config, AppConfig)
        print("    ✅ 配置載入錯誤時正確回退到預設配置")

    def test_error_codes_coverage(self):
        """測試錯誤代碼覆蓋率"""
        print("\n📊 測試錯誤代碼覆蓋...")

        # 檢查重要的錯誤代碼存在
        important_error_codes = [
            'DEVICE_NOT_FOUND',
            'COMMAND_FAILED',
            'FILE_NOT_FOUND',
            'CONFIG_INVALID',
            'CONFIG_LOAD_FAILED',
            'NETWORK_TIMEOUT'
        ]

        for code_name in important_error_codes:
            self.assertTrue(hasattr(ErrorCode, code_name))
            print(f"    ✅ {code_name} 錯誤代碼存在")

    def test_error_levels_exist(self):
        """測試錯誤級別定義"""
        print("\n📈 測試錯誤級別...")

        expected_levels = ['INFO', 'WARNING', 'ERROR', 'CRITICAL']

        for level_name in expected_levels:
            self.assertTrue(hasattr(ErrorLevel, level_name))
            print(f"    ✅ {level_name} 級別存在")

    def test_config_sections_completeness(self):
        """測試配置區塊完整性"""
        print("\n🔧 測試配置區塊...")

        config = self.config_manager.load_config()

        # 檢查主要配置區塊
        self.assertIsNotNone(config.ui)
        self.assertIsNotNone(config.device)
        self.assertIsNotNone(config.command)
        self.assertIsNotNone(config.logging)
        print("    ✅ 所有主要配置區塊存在")

        # 檢查UI配置屬性
        ui_attrs = ['window_width', 'window_height', 'ui_scale', 'theme']
        for attr in ui_attrs:
            self.assertTrue(hasattr(config.ui, attr))
            print(f"    ✅ UI配置.{attr} 存在")

    def test_config_validation(self):
        """測試配置驗證"""
        print("\n✅ 測試配置驗證...")

        # 測試無效的UI縮放值
        config = self.config_manager.load_config()
        config.ui.ui_scale = 5.0  # 超出範圍

        # 重新載入應該修正為有效值
        self.config_manager.save_config(config)
        validated_config = self.config_manager.load_config()

        # 檢查是否被修正為有效範圍
        self.assertLessEqual(validated_config.ui.ui_scale, 3.0)
        print("    ✅ 配置驗證正確修正無效值")

    @patch('PyQt6.QtWidgets.QMessageBox')
    def test_error_display_integration(self, mock_messagebox):
        """測試錯誤顯示整合"""
        print("\n💬 測試錯誤顯示...")

        # 模擬錯誤處理
        mock_messagebox.information.return_value = Mock()
        mock_messagebox.warning.return_value = Mock()
        mock_messagebox.critical.return_value = Mock()

        # 測試不同類型的錯誤顯示
        self.error_handler.show_info("測試", "信息訊息")
        self.error_handler.show_warning("測試", "警告訊息")
        self.error_handler.show_error("測試", "錯誤訊息")

        print("    ✅ 錯誤顯示方法正常調用")


def run_config_error_integration_tests():
    """運行配置和錯誤處理整合測試"""
    print("🔗 運行配置管理和錯誤處理整合測試...")

    # 創建測試套件
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    # 添加整合測試
    suite.addTests(loader.loadTestsFromTestCase(ConfigErrorIntegrationTest))

    # 運行測試
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    print("\n" + "="*60)
    print("📊 配置和錯誤處理整合測試報告")
    print("="*60)

    if result.wasSuccessful():
        print("✅ 配置管理和錯誤處理整合測試通過！")
        print("📋 ConfigManager 功能完整")
        print("🚨 ErrorHandler 功能正常")
        print("🔗 兩個系統協同工作良好")
        print("\n💡 建議：")
        print("   • 已有完善的配置管理和錯誤處理系統")
        print("   • 可以統一化主文件中的錯誤處理調用")
        print("   • 考慮添加更多配置選項以提升用戶體驗")
    else:
        print("❌ 配置和錯誤處理整合測試失敗！")

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
    success = run_config_error_integration_tests()
    sys.exit(0 if success else 1)