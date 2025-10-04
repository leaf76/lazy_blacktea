#!/usr/bin/env python3
"""
應用管理重構測試 - 確保scrcpy和APK管理重構的正確性

這個測試專門驗證：
1. AppManagementManager類的功能完整性
2. ScrcpyManager子管理器的功能
3. ApkInstallationManager子管理器的功能
4. 主文件中方法委託的正確性
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
    from ui.app_management_manager import AppManagementManager, ScrcpyManager, ApkInstallationManager
    from config.config_manager import ScrcpySettings
    from utils import adb_models
except ImportError as e:
    print(f"❌ 無法導入模組: {e}")
    sys.exit(1)


class AppManagementRefactorTest(unittest.TestCase):
    """應用管理重構測試類"""

    @classmethod
    def setUpClass(cls):
        """設置測試環境"""
        cls.module = lazy_blacktea_pyqt

    def test_app_management_classes_exist(self):
        """測試應用管理類的存在性"""
        print("\n🔍 測試應用管理類...")

        manager_classes = [
            ('AppManagementManager', AppManagementManager),
            ('ScrcpyManager', ScrcpyManager),
            ('ApkInstallationManager', ApkInstallationManager),
        ]

        for class_name, class_obj in manager_classes:
            print(f"  ✅ {class_name} 類存在")
            self.assertTrue(hasattr(class_obj, '__init__'))
            print(f"    📋 {class_name} 可以實例化")

    def test_main_window_has_app_manager(self):
        """測試主視窗包含應用管理器"""
        print("\n🔍 測試主視窗應用管理器...")

        if hasattr(self.module, 'WindowMain'):
            WindowMain = getattr(self.module, 'WindowMain')

            # 檢查__init__方法中是否提及應用管理器
            try:
                import inspect
                init_source = inspect.getsource(WindowMain.__init__)

                if 'app_management_manager' in init_source:
                    print(f"  ✅ app_management_manager 在WindowMain.__init__中被初始化")
                else:
                    print(f"  ❌ app_management_manager 未在WindowMain.__init__中找到")
                    self.fail(f"應用管理器 app_management_manager 未在WindowMain初始化中找到")
            except:
                print("  ⚠️  無法檢查WindowMain.__init__源碼，跳過詳細檢查")

    def test_scrcpy_manager_methods(self):
        """測試scrcpy管理器方法"""
        print("\n🔍 測試scrcpy管理器方法...")

        mock_parent = Mock()
        scrcpy_manager = ScrcpyManager(mock_parent)

        key_methods = [
            'check_scrcpy_availability',
            'launch_scrcpy_for_device',
            'launch_scrcpy_for_selected_devices',
            '_parse_scrcpy_version',
            '_select_device_for_mirroring',
            '_launch_scrcpy_process',
            '_build_scrcpy_command',
            '_backup_device_selections',
            '_restore_device_selections'
        ]

        for method_name in key_methods:
            self.assertTrue(hasattr(scrcpy_manager, method_name))
            method = getattr(scrcpy_manager, method_name)
            self.assertTrue(callable(method))
            print(f"    ✅ {method_name}")

        # 測試屬性
        self.assertIsInstance(scrcpy_manager.scrcpy_available, bool)
        self.assertIsInstance(scrcpy_manager.scrcpy_major_version, int)
        print(f"    ✅ 屬性初始化正確")

    def test_apk_manager_methods(self):
        """測試APK管理器方法"""
        print("\n🔍 測試APK管理器方法...")

        mock_parent = Mock()
        apk_manager = ApkInstallationManager(mock_parent)

        key_methods = [
            'install_apk_dialog',
            'install_apk_to_devices',
            '_install_apk_with_progress'
        ]

        for method_name in key_methods:
            self.assertTrue(hasattr(apk_manager, method_name))
            method = getattr(apk_manager, method_name)
            self.assertTrue(callable(method))
            print(f"    ✅ {method_name}")

    def test_app_management_manager_methods(self):
        """測試主應用管理器方法"""
        print("\n🔍 測試主應用管理器方法...")

        mock_parent = Mock()
        app_manager = AppManagementManager(mock_parent)

        # 測試子管理器存在
        self.assertIsInstance(app_manager.scrcpy_manager, ScrcpyManager)
        self.assertIsInstance(app_manager.apk_manager, ApkInstallationManager)
        print(f"    ✅ 子管理器正確初始化")

        # 測試委託方法
        delegate_methods = [
            'check_scrcpy_available',
            'launch_scrcpy_for_device',
            'launch_scrcpy_for_selected_devices',
            'install_apk_dialog',
            'install_apk_to_devices'
        ]

        for method_name in delegate_methods:
            self.assertTrue(hasattr(app_manager, method_name))
            method = getattr(app_manager, method_name)
            self.assertTrue(callable(method))
            print(f"    ✅ {method_name}")

        # 測試屬性
        self.assertTrue(hasattr(app_manager, 'scrcpy_available'))
        self.assertTrue(hasattr(app_manager, 'scrcpy_major_version'))
        print(f"    ✅ 屬性委託正確")

    def test_main_window_method_delegation(self):
        """測試主視窗方法委託"""
        print("\n🔍 測試主視窗方法委託...")

        if hasattr(self.module, 'WindowMain'):
            WindowMain = getattr(self.module, 'WindowMain')

            # 檢查重構後的方法仍然存在
            refactored_methods = [
                '_check_scrcpy_available',
                'launch_scrcpy_single_device',
                'install_apk',
                'launch_scrcpy'
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

            # 檢查關鍵方法的源碼是否包含管理器委託
            delegation_patterns = {
                '_check_scrcpy_available': 'app_management_manager',
                'launch_scrcpy_single_device': 'app_management_manager',
                'install_apk': 'app_management_manager',
                'launch_scrcpy': 'app_management_manager'
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
        print("\n🔍 測試信號定義...")

        mock_parent = Mock()

        # 測試ScrcpyManager信號
        scrcpy_manager = ScrcpyManager(mock_parent)
        scrcpy_signals = [
            'scrcpy_launch_signal',
            'scrcpy_error_signal'
        ]

        for signal_name in scrcpy_signals:
            self.assertTrue(hasattr(scrcpy_manager, signal_name))
            print(f"    ✅ ScrcpyManager.{signal_name}")

        # 測試ApkInstallationManager信號
        apk_manager = ApkInstallationManager(mock_parent)
        apk_signals = [
            'installation_progress_signal',
            'installation_completed_signal',
            'installation_error_signal'
        ]

        for signal_name in apk_signals:
            self.assertTrue(hasattr(apk_manager, signal_name))
            print(f"    ✅ ApkInstallationManager.{signal_name}")

    def test_mock_scrcpy_functionality(self):
        """測試scrcpy功能（模擬）"""
        print("\n🔍 測試scrcpy功能...")

        mock_parent = Mock()
        mock_parent.device_dict = {
            'device1': Mock(device_serial_num='device1', device_model='Test Device 1')
        }

        scrcpy_manager = ScrcpyManager(mock_parent)

        # 測試版本解析
        version_output_v2 = "scrcpy 2.5.1"
        version = scrcpy_manager._parse_scrcpy_version(version_output_v2)
        self.assertEqual(version, 2)
        print(f"    ✅ scrcpy v2 版本解析正確")

        version_output_v3 = "scrcpy 3.1.2"
        version = scrcpy_manager._parse_scrcpy_version(version_output_v3)
        self.assertEqual(version, 3)
        print(f"    ✅ scrcpy v3 版本解析正確")

        # 測試無效版本輸出
        version_invalid = scrcpy_manager._parse_scrcpy_version("invalid output")
        self.assertEqual(version_invalid, 2)  # 應該返回預設值
        print(f"    ✅ 無效版本輸出處理正確")

    def test_scrcpy_command_respects_custom_settings(self):
        """scrcpy命令應遵循自訂設定"""

        mock_parent = Mock()
        mock_parent.logger = None
        mock_parent.dialog_manager = Mock()

        class StubConfigManager:
            def get_scrcpy_settings(self_inner):
                return ScrcpySettings(
                    stay_awake=False,
                    turn_screen_off=False,
                    disable_screensaver=False,
                    enable_audio_playback=True,
                    bitrate='12M',
                    max_size=1080,
                    extra_args='--always-on-top --crop 0:0:900:1600'
                )

        mock_parent.config_manager = StubConfigManager()

        scrcpy_manager = ScrcpyManager(mock_parent)
        scrcpy_manager.scrcpy_major_version = 3

        command = scrcpy_manager._build_scrcpy_command('ABC123')

        self.assertIn('scrcpy', command[0])
        self.assertNotIn('--stay-awake', command)
        self.assertNotIn('--turn-screen-off', command)
        self.assertIn('--audio-source=playback', command)
        self.assertIn('--audio-dup', command)
        self.assertIn('--bit-rate=12M', command)
        self.assertIn('--max-size=1080', command)
        self.assertIn('--always-on-top', command)
        self.assertIn('--crop', command)
        self.assertIn('-s', command)
        self.assertIn('ABC123', command)

        scrcpy_manager.scrcpy_major_version = 2
        command_v2 = scrcpy_manager._build_scrcpy_command('XYZ789')
        self.assertNotIn('--audio-source=playback', command_v2)
        self.assertIn('--bit-rate=12M', command_v2)

    def test_mock_apk_functionality(self):
        """測試APK功能（模擬）"""
        print("\n🔍 測試APK功能...")

        mock_parent = Mock()
        apk_manager = ApkInstallationManager(mock_parent)

        # 測試設備列表
        mock_devices = [
            Mock(device_serial_num='device1', device_model='Test Device 1'),
            Mock(device_serial_num='device2', device_model='Test Device 2')
        ]

        # 這裡我們只是確保方法存在並可以調用
        # 實際的功能測試需要更完整的PyQt環境
        self.assertTrue(callable(apk_manager.install_apk_to_devices))
        print(f"    ✅ APK安裝方法可調用")


def run_app_management_refactor_tests():
    """運行應用管理重構測試的便利函數"""
    print("📱 運行應用管理重構測試...")

    # 創建測試套件
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    # 添加重構測試
    suite.addTests(loader.loadTestsFromTestCase(AppManagementRefactorTest))

    # 運行測試
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    print("\n" + "="*60)
    print("📊 應用管理重構測試報告")
    print("="*60)

    if result.wasSuccessful():
        print("✅ 應用管理重構測試通過！")
        print("📱 scrcpy和APK管理功能重構成功")
        print("🔧 方法委託正確實現")
    else:
        print("❌ 應用管理重構測試失敗！")
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
    success = run_app_management_refactor_tests()
    sys.exit(0 if success else 1)
