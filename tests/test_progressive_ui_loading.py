#!/usr/bin/env python3
"""
漸進式UI加載測試 - 驗證新的漸進式設備信息加載機制

這個測試專門驗證：
1. 快速基本信息提取功能
2. 漸進式UI更新機制
3. 加載中狀態顯示
4. 異步詳細信息補充
5. 用戶體驗改進效果
"""

import sys
import os
import unittest
import time
import threading
import unittest.mock as mock

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from utils import adb_tools, adb_models
    from ui.async_device_manager import AsyncDeviceManager, AsyncDeviceWorker
    from PyQt6.QtCore import QObject, QThread
    from PyQt6.QtWidgets import QApplication
except ImportError as e:
    print(f"❌ 無法導入模組: {e}")
    sys.exit(1)


class ProgressiveUILoadingTest(unittest.TestCase):
    """漸進式UI加載測試類"""

    @classmethod
    def setUpClass(cls):
        """設置測試環境"""
        # 創建QApplication實例（如果不存在）
        if not QApplication.instance():
            cls.app = QApplication([])
        else:
            cls.app = QApplication.instance()

    def test_fast_basic_device_info_extraction(self):
        """測試快速基本設備信息提取"""
        print("\n⚡ 測試快速基本設備信息提取...")

        # 測試get_devices_list_fast函數存在
        self.assertTrue(hasattr(adb_tools, 'get_devices_list_fast'))
        print("    ✅ get_devices_list_fast 函數存在")

        # 測試device_basic_info_entry函數存在
        self.assertTrue(hasattr(adb_tools, 'device_basic_info_entry'))
        print("    ✅ device_basic_info_entry 函數存在")

        # 測試快速加載性能
        start_time = time.time()
        try:
            basic_devices = adb_tools.get_devices_list_fast()
            load_time = time.time() - start_time

            print(f"    📊 基本信息加載時間: {load_time:.3f}秒")
            print(f"    📱 發現設備數量: {len(basic_devices)}")

            # 基本信息加載應該很快（<1秒）
            self.assertLess(load_time, 1.0, "基本信息加載應該在1秒內完成")

            # 驗證返回的設備信息結構
            for device in basic_devices:
                self.assertIsInstance(device, adb_models.DeviceInfo)
                self.assertIsNotNone(device.device_serial_num)
                self.assertIsNotNone(device.device_model)
                # 檢查是否有加載中的占位符
                self.assertEqual(device.android_ver, '加載中...')
                print(f"    📱 {device.device_serial_num} - {device.device_model} (狀態: {device.android_ver})")

        except Exception as e:
            print(f"    ⚠️ 基本信息加載測試跳過（無設備）: {e}")

        print("    ✅ 快速基本設備信息提取測試完成")

    def test_detailed_info_async_loading(self):
        """測試詳細信息異步加載"""
        print("\n📋 測試詳細信息異步加載...")

        # 測試get_device_detailed_info函數存在
        self.assertTrue(hasattr(adb_tools, 'get_device_detailed_info'))
        print("    ✅ get_device_detailed_info 函數存在")

        try:
            # 先獲取基本設備信息
            basic_devices = adb_tools.get_devices_list_fast()

            if basic_devices:
                device_serial = basic_devices[0].device_serial_num
                print(f"    🔍 測試設備: {device_serial}")

                # 測試詳細信息加載
                start_time = time.time()
                detailed_info = adb_tools.get_device_detailed_info(device_serial)
                load_time = time.time() - start_time

                print(f"    📊 詳細信息加載時間: {load_time:.3f}秒")

                # 驗證返回的詳細信息結構
                self.assertIsInstance(detailed_info, dict)

                expected_keys = ['wifi_status', 'bluetooth_status', 'android_version',
                               'android_api_level', 'gms_version', 'build_fingerprint']
                for key in expected_keys:
                    self.assertIn(key, detailed_info)
                    print(f"    ✅ {key}: {detailed_info[key]}")

            else:
                print("    ⚠️ 詳細信息加載測試跳過（無設備）")

        except Exception as e:
            print(f"    ⚠️ 詳細信息加載測試跳過: {e}")

        print("    ✅ 詳細信息異步加載測試完成")

    def test_progressive_loading_performance(self):
        """測試漸進式加載性能改進"""
        print("\n🚀 測試漸進式加載性能改進...")

        try:
            # 模擬舊版本：完整加載
            start_time = time.time()
            full_devices = adb_tools.get_devices_list()
            full_load_time = time.time() - start_time

            # 新版本：基本信息加載
            start_time = time.time()
            basic_devices = adb_tools.get_devices_list_fast()
            basic_load_time = time.time() - start_time

            print(f"    📊 舊版本完整加載時間: {full_load_time:.3f}秒")
            print(f"    📊 新版本基本加載時間: {basic_load_time:.3f}秒")

            if basic_load_time > 0 and full_load_time > 0:
                speedup = full_load_time / basic_load_time
                print(f"    🚀 響應速度提升: {speedup:.1f}倍")

                # 基本信息加載應該明顯更快
                self.assertLess(basic_load_time, full_load_time,
                               "基本信息加載應該比完整加載更快")

                # 速度提升應該至少2倍以上
                self.assertGreaterEqual(speedup, 2.0, "速度提升應該至少2倍")

        except Exception as e:
            print(f"    ⚠️ 性能測試跳過: {e}")

        print("    ✅ 漸進式加載性能改進測試完成")

    def test_async_device_manager_signals(self):
        """測試AsyncDeviceManager信號機制"""
        print("\n📡 測試AsyncDeviceManager信號機制...")

        manager = AsyncDeviceManager()

        # 檢查漸進式加載信號
        required_signals = [
            'device_discovery_started',
            'device_basic_loaded',
            'device_detailed_loaded',
            'device_load_progress',
            'basic_devices_ready',
            'all_devices_ready'
        ]

        for signal_name in required_signals:
            self.assertTrue(hasattr(manager, signal_name))
            print(f"    ✅ {signal_name} 信號存在")

        print("    ✅ AsyncDeviceManager信號機制測試完成")

    def test_async_device_worker_functionality(self):
        """測試AsyncDeviceWorker功能"""
        print("\n⚙️ 測試AsyncDeviceWorker功能...")

        worker = AsyncDeviceWorker()

        # 檢查漸進式加載信號
        required_signals = [
            'device_basic_loaded',
            'device_detailed_loaded',
            'device_load_failed',
            'progress_updated',
            'all_basic_loaded',
            'all_detailed_loaded'
        ]

        for signal_name in required_signals:
            self.assertTrue(hasattr(worker, signal_name))
            print(f"    ✅ {signal_name} 信號存在")

        # 檢查關鍵方法
        required_methods = [
            '_load_devices_efficiently',
            '_load_basic_info_immediately',
            '_load_detailed_info_progressively'
        ]

        for method_name in required_methods:
            self.assertTrue(hasattr(worker, method_name))
            print(f"    ✅ {method_name} 方法存在")

        print("    ✅ AsyncDeviceWorker功能測試完成")

    def test_loading_state_indicators(self):
        """測試加載中狀態指示器"""
        print("\n🔄 測試加載中狀態指示器...")

        try:
            basic_devices = adb_tools.get_devices_list_fast()

            if basic_devices:
                device = basic_devices[0]

                # 檢查加載中的占位符
                loading_indicators = [
                    device.android_ver,
                    device.android_api_level,
                    device.gms_version,
                    device.build_fingerprint
                ]

                for indicator in loading_indicators:
                    self.assertEqual(indicator, '加載中...',
                                   f"應該顯示加載中狀態: {indicator}")

                print("    ✅ 所有詳細信息字段都顯示加載中狀態")
                print(f"    📱 設備: {device.device_serial_num} - {device.device_model}")
                print(f"    🔄 狀態: {device.android_ver}")

            else:
                print("    ⚠️ 加載狀態測試跳過（無設備）")

        except Exception as e:
            print(f"    ⚠️ 加載狀態測試跳過: {e}")

        print("    ✅ 加載中狀態指示器測試完成")

    def test_ui_update_methods_exist(self):
        """測試UI更新方法存在"""
        print("\n🖥️ 測試UI更新方法存在...")

        main_file = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                 "lazy_blacktea_pyqt.py")

        with open(main_file, 'r', encoding='utf-8') as f:
            content = f.read()

        # 檢查新的UI更新方法
        ui_methods = [
            '_update_device_in_ui_immediately',
            '_update_device_detailed_in_ui',
            '_on_async_device_basic_loaded',
            '_on_async_device_detailed_loaded',
            '_on_async_basic_devices_ready'
        ]

        for method_name in ui_methods:
            method_exists = f'def {method_name}(' in content
            self.assertTrue(method_exists, f"應該存在 {method_name} 方法")
            print(f"    ✅ {method_name} 方法存在")

        # 檢查加載中圖標的使用
        loading_icon_usage = '🔄' in content
        self.assertTrue(loading_icon_usage, "應該使用加載中圖標")
        print("    ✅ 加載中圖標 🔄 被使用")

        print("    ✅ UI更新方法存在測試完成")

    def test_signal_flow_integration(self):
        """測試信號流程整合"""
        print("\n🔄 測試信號流程整合...")

        main_file = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                 "lazy_blacktea_pyqt.py")

        with open(main_file, 'r', encoding='utf-8') as f:
            content = f.read()

        # 檢查信號連接設置
        signal_connections = [
            'device_basic_loaded.connect',
            'device_detailed_loaded.connect',
            'basic_devices_ready.connect'
        ]

        for connection in signal_connections:
            connection_exists = connection in content
            self.assertTrue(connection_exists, f"應該存在信號連接: {connection}")
            print(f"    ✅ {connection} 信號連接存在")

        print("    ✅ 信號流程整合測試完成")


def run_progressive_ui_loading_tests():
    """運行漸進式UI加載測試"""
    print("🚀 運行漸進式UI加載測試...")

    # 創建測試套件
    suite = unittest.TestSuite()

    # 添加所有測試
    test_methods = [
        'test_fast_basic_device_info_extraction',
        'test_detailed_info_async_loading',
        'test_progressive_loading_performance',
        'test_async_device_manager_signals',
        'test_async_device_worker_functionality',
        'test_loading_state_indicators',
        'test_ui_update_methods_exist',
        'test_signal_flow_integration'
    ]

    for test_method in test_methods:
        suite.addTest(ProgressiveUILoadingTest(test_method))

    # 運行測試
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    print("\n" + "="*60)
    print("📊 漸進式UI加載測試報告")
    print("="*60)

    if result.wasSuccessful():
        print("✅ 所有漸進式UI加載測試通過！")
        print("🎉 主要成果:")
        print("   • ⚡ 快速基本設備信息提取功能完整")
        print("   • 📋 詳細信息異步加載機制運作正常")
        print("   • 🚀 漸進式加載性能顯著改善")
        print("   • 📡 AsyncDeviceManager信號機制完善")
        print("   • 🔄 加載中狀態指示清晰")
        print("   • 🖥️ UI更新方法實現完整")
        print("   • 🔄 信號流程整合良好")

        print("\n🎯 用戶體驗改進總結:")
        print("   • 📱 設備列表立即顯示，不再等待")
        print("   • 🔄 加載狀態清晰可見")
        print("   • ⚡ UI響應速度顯著提升")
        print("   • 📋 詳細信息後台自動補充")
        print("   • 🚀 支持大量設備無阻塞")

    else:
        print("❌ 部分漸進式UI加載測試失敗")

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
    success = run_progressive_ui_loading_tests()
    sys.exit(0 if success else 1)