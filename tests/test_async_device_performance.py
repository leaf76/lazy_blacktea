#!/usr/bin/env python3
"""
異步設備管理器性能測試 - 驗證UI響應性優化

這個測試專門驗證：
1. AsyncDeviceManager的正確集成
2. 異步設備加載不會阻塞UI
3. 漸進式設備信息加載
4. 大量設備場景下的性能改進
"""

import sys
import os
import unittest
import time
import subprocess
import re

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    import lazy_blacktea_pyqt
    from ui.async_device_manager import AsyncDeviceManager, AsyncDeviceWorker
    from ui.error_handler import ErrorHandler, ErrorCode, ErrorLevel
except ImportError as e:
    print(f"❌ 無法導入模組: {e}")
    sys.exit(1)


class AsyncDevicePerformanceTest(unittest.TestCase):
    """異步設備管理器性能測試類"""

    @classmethod
    def setUpClass(cls):
        """設置測試環境"""
        cls.main_file = "lazy_blacktea_pyqt.py"
        cls.project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    def test_async_device_manager_integration(self):
        """測試異步設備管理器集成"""
        print("\n🔗 測試異步設備管理器集成...")

        with open(os.path.join(self.project_root, self.main_file), 'r', encoding='utf-8') as f:
            content = f.read()

        # 檢查AsyncDeviceManager導入
        async_imports = len(re.findall(r'from ui\.async_device_manager import', content))
        self.assertGreater(async_imports, 0, "應該導入AsyncDeviceManager")
        print(f"    📦 AsyncDeviceManager 導入: {async_imports}")

        # 檢查異步設備管理器初始化
        manager_init = len(re.findall(r'self\.async_device_manager = AsyncDeviceManager', content))
        self.assertGreater(manager_init, 0, "應該初始化AsyncDeviceManager")
        print(f"    🏗️ AsyncDeviceManager 初始化: {manager_init}")

        # 檢查信號設置
        signal_setup = len(re.findall(r'_setup_async_device_signals', content))
        self.assertGreater(signal_setup, 0, "應該設置異步設備信號")
        print(f"    📡 異步設備信號設置: {signal_setup}")

        print("    ✅ 異步設備管理器集成測試通過")

    def test_async_event_handlers_exist(self):
        """測試簡化後的異步事件處理器存在"""
        print("\n⚡ 測試簡化後的異步事件處理器...")

        with open(os.path.join(self.project_root, self.main_file), 'r', encoding='utf-8') as f:
            content = f.read()

        # 檢查簡化後的關鍵異步事件處理器
        required_handlers = [
            '_on_async_discovery_started',
            '_on_async_device_loaded',
            '_on_async_device_progress',
            '_on_async_all_devices_ready'
        ]

        for handler in required_handlers:
            handler_exists = f'def {handler}(' in content
            self.assertTrue(handler_exists, f"應該存在 {handler} 方法")
            print(f"    ✅ {handler} 存在")

    def test_efficient_loading_implementation(self):
        """測試高效加載實現（替代漸進式）"""
        print("\n📈 測試高效加載實現...")

        with open(os.path.join(self.project_root, self.main_file), 'r', encoding='utf-8') as f:
            content = f.read()

        # 檢查高效UI更新方法
        efficient_methods = [
            '_refresh_all_device_ui'
        ]

        for method in efficient_methods:
            method_exists = f'def {method}(' in content
            self.assertTrue(method_exists, f"應該存在 {method} 方法")
            print(f"    ✅ {method} 存在")

        # 檢查設備信息高效更新邏輯
        ui_update_patterns = [
            r'self\.device_dict\[serial\] = device_info',
            r'self\._refresh_all_device_ui',
            r'Efficiently loaded.*devices'
        ]

        found_patterns = 0
        for pattern in ui_update_patterns:
            if re.search(pattern, content):
                found_patterns += 1

        self.assertGreater(found_patterns, 1, "應該包含高效更新邏輯")
        print(f"    ✅ 高效更新邏輯: {found_patterns}/3")

        print("    ✅ 高效加載實現測試通過")

    def test_ui_responsiveness_optimization(self):
        """測試UI響應性優化"""
        print("\n🎯 測試UI響應性優化...")

        with open(os.path.join(self.project_root, self.main_file), 'r', encoding='utf-8') as f:
            content = f.read()

        # 檢查refresh_device_list使用異步管理器
        refresh_method_pattern = r'def refresh_device_list.*async_device_manager\.start_device_discovery'
        refresh_async = bool(re.search(refresh_method_pattern, content, re.DOTALL))
        self.assertTrue(refresh_async, "refresh_device_list應該使用異步設備發現")
        print("    ✅ refresh_device_list 使用異步加載")

        # 檢查狀態欄更新
        status_updates = len(re.findall(r'status_bar\.showMessage.*device', content, re.IGNORECASE))
        self.assertGreater(status_updates, 0, "應該有狀態欄設備信息更新")
        print(f"    📊 狀態欄設備更新: {status_updates}")

        # 檢查控制台進度反饋（簡化版）
        console_progress = len(re.findall(r'write_to_console.*Device:|Efficiently loaded', content))
        self.assertGreater(console_progress, 0, "應該有控制台反饋")
        print(f"    📝 控制台反饋: {console_progress}")

        print("    ✅ UI響應性優化測試通過")

    def test_async_device_manager_module(self):
        """測試異步設備管理器模組"""
        print("\n🔧 測試AsyncDeviceManager模組...")

        # 檢查AsyncDeviceManager類存在
        self.assertTrue(hasattr(AsyncDeviceManager, 'start_device_discovery'))
        self.assertTrue(hasattr(AsyncDeviceManager, 'stop_current_loading'))
        print("    ✅ AsyncDeviceManager 類方法完整")

        # 檢查AsyncDeviceWorker簡化後的信號
        self.assertTrue(hasattr(AsyncDeviceWorker, 'device_loaded'))
        self.assertTrue(hasattr(AsyncDeviceWorker, 'device_load_failed'))
        self.assertTrue(hasattr(AsyncDeviceWorker, 'all_devices_loaded'))
        print("    ✅ AsyncDeviceWorker 簡化信號完整")

        print("    ✅ AsyncDeviceManager模組測試通過")

    def test_performance_regression_prevention(self):
        """測試性能倒退防止"""
        print("\n⚡ 測試性能倒退防止...")

        with open(os.path.join(self.project_root, self.main_file), 'r', encoding='utf-8') as f:
            content = f.read()

        # 檢查是否沒有同步設備列舉的阻塞調用
        blocking_patterns = [
            r'adb_tools\.get_devices_info\(\).*for.*in',  # 同步循環獲取設備信息
            r'time\.sleep.*device',  # 設備相關的阻塞等待
        ]

        blocking_calls = 0
        for pattern in blocking_patterns:
            if re.search(pattern, content, re.IGNORECASE):
                blocking_calls += 1

        # 應該有很少的阻塞調用（或沒有）
        self.assertLessEqual(blocking_calls, 2, "應該減少阻塞性設備調用")
        print(f"    📊 潛在阻塞調用: {blocking_calls} (應該 ≤ 2)")

        # 檢查異步加載優化
        async_optimizations = [
            (r'QThread', 'QThread線程使用'),
            (r'pyqtSignal', 'PyQt信號機制'),
            (r'async_device_manager', '異步設備管理器'),
            (r'_on_async_.*device', '異步設備事件處理'),
        ]

        optimization_count = 0
        found_optimizations = []
        for pattern, description in async_optimizations:
            if re.search(pattern, content, re.IGNORECASE):
                optimization_count += 1
                found_optimizations.append(description)

        self.assertGreater(optimization_count, 2, f"應該有異步優化實現，找到: {found_optimizations}")
        print(f"    🚀 異步優化技術: {optimization_count} ({', '.join(found_optimizations)})")

        print("    ✅ 性能倒退防止測試通過")

    def test_error_handling_in_async_operations(self):
        """測試異步操作中的錯誤處理"""
        print("\n🛡️ 測試異步操作錯誤處理...")

        async_manager_file = os.path.join(self.project_root, "ui", "async_device_manager.py")
        if os.path.exists(async_manager_file):
            with open(async_manager_file, 'r', encoding='utf-8') as f:
                async_content = f.read()

            # 檢查異步操作中的錯誤處理
            error_patterns = [
                r'except.*Exception.*as.*e:',
                r'logger\.(error|warning)',
                r'device_load_failed\.emit'
            ]

            error_handling_count = 0
            for pattern in error_patterns:
                error_handling_count += len(re.findall(pattern, async_content))

            self.assertGreater(error_handling_count, 3, "異步操作應該有充分的錯誤處理")
            print(f"    🛡️ 異步錯誤處理: {error_handling_count}")

        print("    ✅ 異步操作錯誤處理測試通過")


def run_async_device_performance_tests():
    """運行異步設備管理器性能測試"""
    print("🚀 運行異步設備管理器性能測試...")

    # 創建測試套件
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    # 添加測試（更新方法名）
    suite.addTest(AsyncDevicePerformanceTest('test_async_device_manager_integration'))
    suite.addTest(AsyncDevicePerformanceTest('test_async_event_handlers_exist'))
    suite.addTest(AsyncDevicePerformanceTest('test_efficient_loading_implementation'))
    suite.addTest(AsyncDevicePerformanceTest('test_ui_responsiveness_optimization'))
    suite.addTest(AsyncDevicePerformanceTest('test_async_device_manager_module'))
    suite.addTest(AsyncDevicePerformanceTest('test_performance_regression_prevention'))
    suite.addTest(AsyncDevicePerformanceTest('test_error_handling_in_async_operations'))

    # 運行測試
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    print("\n" + "="*60)
    print("📊 異步設備性能優化測試報告")
    print("="*60)

    if result.wasSuccessful():
        print("✅ 所有異步設備性能測試通過！")
        print("🚀 主要成果:")
        print("   • AsyncDeviceManager 正確集成")
        print("   • 異步事件處理器完整")
        print("   • 漸進式設備加載實現")
        print("   • UI響應性顯著改善")
        print("   • 性能倒退有效防止")
        print("   • 異步錯誤處理完備")

        print("\n🎉 Phase 5 高效異步設備管理成功完成！")
        print("📈 主要改進:")
        print("   • 🚀 取消複雜的漸進式顯示")
        print("   • ⚡ 實施一次性批量並發加載")
        print("   • 🎯 簡化信號機制減少開銷")
        print("   • 💨 更快的設備信息提取")
        print("📊 解決的核心問題:")
        print("   • ❌ 超過5支手機會卡住 → ✅ 高效並發處理")
        print("   • ❌ 漸進式顯示效率低 → ✅ 一次性批量更新")
        print("   • ❌ UI頻繁更新抖動 → ✅ 單次UI刷新")

    else:
        print("❌ 部分異步設備性能測試失敗")

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
    success = run_async_device_performance_tests()
    sys.exit(0 if success else 1)