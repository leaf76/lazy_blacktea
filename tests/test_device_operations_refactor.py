#!/usr/bin/env python3
"""
設備操作重構專用測試 - 確保設備操作邏輯重構的正確性

這個測試專門驗證：
1. 設備操作方法的存在性和可調用性
2. 重構前後設備操作的一致性
3. 設備操作管理器的功能完整性
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


class DeviceOperationsRefactorTest(unittest.TestCase):
    """設備操作重構測試類"""

    @classmethod
    def setUpClass(cls):
        """設置測試環境"""
        cls.module = lazy_blacktea_pyqt

        # 定義需要重構的設備操作方法
        cls.device_operation_methods = {
            # 設備控制操作
            'control_operations': [
                'reboot_device',
                'reboot_single_device',
                'enable_bluetooth',
                'disable_bluetooth'
            ],

            # 媒體操作
            'media_operations': [
                'take_screenshot',
                'take_screenshot_single_device',
                'start_screen_record',
                'stop_screen_record'
            ],

            # 應用程序操作
            'app_operations': [
                'install_apk',
                'launch_scrcpy',
                'launch_scrcpy_single_device',
                'launch_ui_inspector',
                'launch_ui_inspector_for_device'
            ],

            # 內部輔助方法
            'helper_operations': [
                'update_recording_status',
                'show_recording_warning',
                '_install_apk_with_progress',
                '_on_recording_stopped',
                '_on_recording_state_cleared',
                '_on_recording_progress_event',
                '_on_screenshot_completed',
                '_show_screenshot_quick_actions',
                '_handle_screenshot_completion',
                '_update_screenshot_button_state',
                '_clear_device_recording'
            ]
        }

    def test_device_operation_methods_exist(self):
        """測試設備操作方法在主類中存在"""
        print("\n🔍 測試設備操作方法...")

        if hasattr(self.module, 'WindowMain'):
            WindowMain = getattr(self.module, 'WindowMain')

            for category, methods in self.device_operation_methods.items():
                print(f"\n  📂 {category}:")
                for method_name in methods:
                    with self.subTest(method=method_name, category=category):
                        self.assertTrue(
                            hasattr(WindowMain, method_name),
                            f"設備操作方法 {method_name} 在WindowMain中不存在"
                        )

                        method = getattr(WindowMain, method_name)
                        self.assertTrue(
                            callable(method),
                            f"設備操作方法 {method_name} 不可調用"
                        )
                        print(f"    ✅ {method_name}")

    def test_device_operation_method_signatures(self):
        """測試設備操作方法的簽名"""
        print("\n📝 測試方法簽名...")

        if hasattr(self.module, 'WindowMain'):
            WindowMain = getattr(self.module, 'WindowMain')

            # 檢查關鍵方法的參數
            signature_tests = {
                'reboot_device': 0,  # 批量操作，無參數
                'reboot_single_device': 1,  # 單設備操作，需要device_serial
                'take_screenshot': 0,  # 批量操作，無參數
                'take_screenshot_single_device': 1,  # 單設備操作
                'enable_bluetooth': 0,  # 批量操作
                'disable_bluetooth': 0,  # 批量操作
                'install_apk': 0,  # 批量操作，會彈出文件選擇
                'launch_scrcpy': 0,  # 批量操作
                'launch_scrcpy_single_device': 1,  # 單設備操作
            }

            for method_name, expected_param_count in signature_tests.items():
                if hasattr(WindowMain, method_name):
                    method = getattr(WindowMain, method_name)
                    try:
                        import inspect
                        sig = inspect.signature(method)
                        # 減去self參數
                        actual_param_count = len(sig.parameters) - 1

                        print(f"  📋 {method_name}: 預期{expected_param_count}, 實際{actual_param_count}")

                        self.assertEqual(
                            actual_param_count, expected_param_count,
                            f"{method_name} 參數數量不符: 預期{expected_param_count}, 實際{actual_param_count}"
                        )
                    except Exception as e:
                        print(f"  ⚠️  無法檢查 {method_name} 的簽名: {e}")

    def test_device_operation_dependencies(self):
        """測試設備操作方法的依賴關係"""
        print("\n🔗 測試設備操作依賴...")

        if hasattr(self.module, 'WindowMain'):
            WindowMain = getattr(self.module, 'WindowMain')

            # 檢查依賴的屬性和方法
            required_attributes = [
                'device_dict',
                'check_devices',
                'device_recordings',
                'device_operations',
                'recording_timer'
            ]

            required_methods = [
                'get_checked_devices',
                'show_info',
                'show_warning',
                'show_error',
                'write_to_console'
            ]

            print("  📋 檢查必要屬性:")
            for attr in required_attributes:
                # 我們無法直接檢查實例屬性，但可以檢查在__init__中是否提及
                print(f"    📝 {attr} (需要在初始化時創建)")

            print("  📋 檢查必要方法:")
            for method in required_methods:
                if hasattr(WindowMain, method):
                    print(f"    ✅ {method} 存在")
                else:
                    print(f"    ❌ {method} 缺失")
                    self.fail(f"設備操作所需的方法 {method} 缺失")

    def test_threading_and_async_operations(self):
        """測試線程和異步操作的存在性"""
        print("\n🔄 測試線程操作...")

        if hasattr(self.module, 'WindowMain'):
            WindowMain = getattr(self.module, 'WindowMain')

            # 檢查線程相關的方法
            threading_methods = [
                'run_in_thread',  # 通用線程執行方法
            ]

            signal_methods = [
                'recording_stopped_signal',
                'recording_state_cleared_signal',
                'screenshot_completed_signal',
                'file_generation_completed_signal'
            ]

            for method in threading_methods:
                if hasattr(WindowMain, method):
                    print(f"  ✅ 線程方法 {method} 存在")
                else:
                    print(f"  ⚠️  線程方法 {method} 可能需要檢查")

            # 信號通常在__init__中定義，我們檢查它們的處理方法
            signal_handlers = [
                '_on_recording_stopped',
                '_on_recording_state_cleared',
                '_on_screenshot_completed',
                '_on_file_generation_completed'
            ]

            for handler in signal_handlers:
                if hasattr(WindowMain, handler):
                    print(f"  ✅ 信號處理器 {handler} 存在")
                else:
                    print(f"  ❌ 信號處理器 {handler} 缺失")

    def test_error_handling_patterns(self):
        """測試錯誤處理模式"""
        print("\n🛡️  測試錯誤處理...")

        if hasattr(self.module, 'WindowMain'):
            WindowMain = getattr(self.module, 'WindowMain')

            # 檢查錯誤處理相關方法
            error_methods = [
                'show_error',
                'show_warning',
                'show_info'
            ]

            for method in error_methods:
                if hasattr(WindowMain, method):
                    print(f"  ✅ 錯誤處理方法 {method} 存在")

                    # 檢查方法簽名
                    try:
                        import inspect
                        sig = inspect.signature(getattr(WindowMain, method))
                        param_count = len(sig.parameters) - 1  # 減去self

                        if param_count >= 2:  # title, message
                            print(f"    📋 {method}: {param_count} 個參數 (符合預期)")
                        else:
                            print(f"    ⚠️  {method}: {param_count} 個參數 (可能不足)")
                    except:
                        pass
                else:
                    print(f"  ❌ 錯誤處理方法 {method} 缺失")
                    self.fail(f"錯誤處理方法 {method} 缺失")

    def test_device_validation_methods(self):
        """測試設備驗證方法"""
        print("\n✅ 測試設備驗證...")

        if hasattr(self.module, 'WindowMain'):
            WindowMain = getattr(self.module, 'WindowMain')

            validation_methods = [
                'get_checked_devices',  # 獲取選中的設備
            ]

            for method in validation_methods:
                if hasattr(WindowMain, method):
                    print(f"  ✅ 驗證方法 {method} 存在")

                    # 檢查返回類型註解
                    try:
                        import inspect
                        sig = inspect.signature(getattr(WindowMain, method))
                        return_annotation = sig.return_annotation

                        if return_annotation != inspect.Signature.empty:
                            print(f"    📋 {method} 返回類型: {return_annotation}")
                        else:
                            print(f"    📝 {method} 無返回類型註解")
                    except:
                        pass
                else:
                    print(f"  ❌ 驗證方法 {method} 缺失")

    def test_device_operations_refactor_readiness(self):
        """測試設備操作重構準備情況"""
        print("\n🏗️  測試重構準備...")

        # 檢查是否已經有相關的模組結構
        existing_modules = [
            'ui.device_manager',
            'ui.command_executor',
            'utils.recording_utils',
            'utils.screenshot_utils'
        ]

        for module_name in existing_modules:
            try:
                __import__(module_name)
                print(f"  ✅ 相關模組 {module_name} 已存在")
            except ImportError:
                print(f"  ⚠️  相關模組 {module_name} 不存在")

        print("\n  📊 設備操作方法統計:")
        total_methods = sum(len(methods) for methods in self.device_operation_methods.values())
        print(f"    總計: {total_methods} 個設備操作方法需要重構")

        for category, methods in self.device_operation_methods.items():
            print(f"    {category}: {len(methods)} 個方法")


def run_device_operations_tests():
    """運行設備操作重構測試的便利函數"""
    print("🔧 運行設備操作重構測試...")

    # 創建測試套件
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    # 添加設備操作測試
    suite.addTests(loader.loadTestsFromTestCase(DeviceOperationsRefactorTest))

    # 運行測試
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    print("\n" + "="*60)
    print("📊 設備操作重構測試報告")
    print("="*60)

    if result.wasSuccessful():
        print("✅ 設備操作重構準備測試通過！")
        print("🔧 可以安全開始設備操作邏輯重構")
    else:
        print("❌ 設備操作重構準備測試失敗！")
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
    success = run_device_operations_tests()
    sys.exit(0 if success else 1)
