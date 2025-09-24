#!/usr/bin/env python3
"""
性能回歸測試 - 確保重構過程中性能不會顯著惡化

這個測試模組專門測量和比較：
1. 模組導入時間
2. 類初始化性能
3. 關鍵方法執行時間
4. 內存使用情況
5. 代碼複雜度指標
"""

import sys
import os
import time
import unittest
import importlib
import psutil
import gc
from typing import Dict, List, Any, Callable
import json
from functools import wraps

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    import lazy_blacktea_pyqt
except ImportError as e:
    print(f"❌ 無法導入主模組: {e}")
    sys.exit(1)


def measure_time(func: Callable) -> Callable:
    """時間測量裝飾器"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.perf_counter()
        result = func(*args, **kwargs)
        end_time = time.perf_counter()
        execution_time = end_time - start_time
        return result, execution_time
    return wrapper


def measure_memory(func: Callable) -> Callable:
    """內存測量裝飾器"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        gc.collect()  # 強制垃圾回收
        process = psutil.Process()
        memory_before = process.memory_info().rss / 1024 / 1024  # MB

        result = func(*args, **kwargs)

        gc.collect()  # 再次強制垃圾回收
        memory_after = process.memory_info().rss / 1024 / 1024  # MB
        memory_diff = memory_after - memory_before

        return result, memory_diff
    return wrapper


class PerformanceRegressionTest(unittest.TestCase):
    """性能回歸測試類"""

    @classmethod
    def setUpClass(cls):
        """設置測試環境"""
        cls.module = lazy_blacktea_pyqt
        cls.baseline_file = "tests/refactoring_baseline.json"
        cls.performance_threshold = {
            'time_regression': 50.0,  # 50%的時間回歸算嚴重
            'memory_regression': 100.0,  # 100%的內存回歸算嚴重
        }

        # 加載基線數據
        try:
            with open(cls.baseline_file, 'r', encoding='utf-8') as f:
                cls.baseline_data = json.load(f)
            print("✅ 基線數據加載成功")
        except FileNotFoundError:
            print("⚠️  未找到基線數據，將創建新的基線")
            cls.baseline_data = {}
        except Exception as e:
            print(f"❌ 加載基線數據失敗: {e}")
            cls.baseline_data = {}

    def test_module_import_performance(self):
        """測試模組導入性能"""
        print("\n⚡ 測試模組導入性能...")

        @measure_time
        def import_module():
            return importlib.reload(lazy_blacktea_pyqt)

        # 測量多次取平均值
        times = []
        for i in range(5):
            _, import_time = import_module()
            times.append(import_time)

        avg_import_time = sum(times) / len(times)
        print(f"  📊 平均導入時間: {avg_import_time:.4f}秒")

        # 與基線比較
        baseline_import_time = self.baseline_data.get('performance_metrics', {}).get('import_time', 0)
        if baseline_import_time > 0:
            regression_percent = ((avg_import_time - baseline_import_time) / baseline_import_time) * 100
            print(f"  📈 與基線比較: {regression_percent:+.1f}%")

            self.assertLess(
                regression_percent, self.performance_threshold['time_regression'],
                f"導入時間回歸過大: {regression_percent:.1f}%"
            )
        else:
            print("  ⚠️  無基線數據可比較")

    def test_class_analysis_performance(self):
        """測試類分析性能"""
        print("\n⚡ 測試類分析性能...")

        @measure_time
        def analyze_main_class():
            if hasattr(self.module, 'WindowMain'):
                WindowMain = getattr(self.module, 'WindowMain')
                # 分析類的方法和屬性
                methods = [m for m in dir(WindowMain) if callable(getattr(WindowMain, m)) and not m.startswith('_')]
                return len(methods)
            return 0

        _, analysis_time = analyze_main_class()
        print(f"  📊 類分析時間: {analysis_time:.4f}秒")

        # 與基線比較
        baseline_analysis_time = self.baseline_data.get('performance_metrics', {}).get('WindowMain_analysis_time', 0)
        if baseline_analysis_time > 0:
            regression_percent = ((analysis_time - baseline_analysis_time) / baseline_analysis_time) * 100
            print(f"  📈 與基線比較: {regression_percent:+.1f}%")

            self.assertLess(
                regression_percent, self.performance_threshold['time_regression'],
                f"類分析時間回歸過大: {regression_percent:.1f}%"
            )
        else:
            print("  ⚠️  無基線數據可比較")

    def test_memory_usage_stability(self):
        """測試內存使用穩定性"""
        print("\n💾 測試內存使用穩定性...")

        @measure_memory
        def load_and_analyze_module():
            # 重新載入模組並分析
            module = importlib.reload(lazy_blacktea_pyqt)
            if hasattr(module, 'WindowMain'):
                WindowMain = getattr(module, 'WindowMain')
                # 執行一些基本分析
                methods = dir(WindowMain)
                return len(methods)
            return 0

        method_count, memory_diff = load_and_analyze_module()
        print(f"  📊 內存變化: {memory_diff:+.2f} MB")
        print(f"  🔢 分析方法數: {method_count}")

        # 內存使用不應該過度增長
        self.assertLess(
            abs(memory_diff), 50.0,  # 內存變化不應超過50MB
            f"內存使用變化過大: {memory_diff:+.2f} MB"
        )

    def test_code_complexity_metrics(self):
        """測試代碼複雜度指標"""
        print("\n📏 測試代碼複雜度指標...")

        # 計算當前的代碼指標
        current_metrics = self._calculate_current_metrics()

        # 與基線比較
        baseline_metrics = self.baseline_data.get('code_metrics', {})

        if baseline_metrics:
            print("  📊 代碼指標比較:")

            metrics_to_check = ['total_lines', 'function_count', 'class_count']
            for metric in metrics_to_check:
                current_value = current_metrics.get(metric, 0)
                baseline_value = baseline_metrics.get(metric, 0)

                if baseline_value > 0:
                    change_percent = ((current_value - baseline_value) / baseline_value) * 100
                    status = "✅" if abs(change_percent) < 20 else "⚠️"
                    print(f"    {status} {metric}: {baseline_value} -> {current_value} ({change_percent:+.1f}%)")

                    # 代碼行數不應該在重構中顯著增加
                    if metric == 'total_lines':
                        self.assertLess(
                            change_percent, 20.0,
                            f"代碼行數增長過多: {change_percent:.1f}%"
                        )
        else:
            print("  ⚠️  無基線指標可比較")

    def test_method_count_stability(self):
        """測試方法數量穩定性"""
        print("\n🔢 測試方法數量穩定性...")

        if hasattr(self.module, 'WindowMain'):
            WindowMain = getattr(self.module, 'WindowMain')
            current_method_count = len([m for m in dir(WindowMain)
                                      if callable(getattr(WindowMain, m))
                                      and not m.startswith('_')])

            print(f"  📊 當前公共方法數: {current_method_count}")

            # 與基線比較
            baseline_method_count = self.baseline_data.get('performance_metrics', {}).get('WindowMain_method_count', 0)
            if baseline_method_count > 0:
                change_percent = ((current_method_count - baseline_method_count) / baseline_method_count) * 100
                print(f"  📈 與基線比較: {change_percent:+.1f}%")

                # 在重構過程中，方法數量可能會有所變化，但不應該過度增加
                self.assertLess(
                    change_percent, 50.0,
                    f"方法數量增長過多，可能表示重構不當: {change_percent:.1f}%"
                )

                # 方法數量也不應該大幅減少（除非是有意的重構）
                self.assertGreater(
                    change_percent, -30.0,
                    f"方法數量減少過多，可能破壞了功能: {change_percent:.1f}%"
                )
            else:
                print("  ⚠️  無基線數據可比較")

    def test_overall_performance_benchmark(self):
        """綜合性能基準測試"""
        print("\n🏆 綜合性能基準測試...")

        benchmark_results = {}

        # 測試1: 模組重載性能
        @measure_time
        def reload_module():
            return importlib.reload(lazy_blacktea_pyqt)

        _, reload_time = reload_module()
        benchmark_results['reload_time'] = reload_time

        # 測試2: 類檢查性能
        @measure_time
        def inspect_classes():
            classes = []
            for name in dir(self.module):
                obj = getattr(self.module, name)
                if hasattr(obj, '__module__') and obj.__module__ == self.module.__name__:
                    if hasattr(obj, '__dict__'):
                        classes.append(name)
            return len(classes)

        class_count, inspect_time = inspect_classes()
        benchmark_results['inspect_time'] = inspect_time
        benchmark_results['class_count'] = class_count

        print(f"  📊 綜合基準結果:")
        print(f"    🔄 重載時間: {reload_time:.4f}秒")
        print(f"    🔍 檢查時間: {inspect_time:.4f}秒")
        print(f"    📝 類數量: {class_count}")

        # 總體性能不應該太差
        total_time = reload_time + inspect_time
        self.assertLess(total_time, 1.0, f"總體操作時間過長: {total_time:.4f}秒")

    def _calculate_current_metrics(self) -> Dict[str, int]:
        """計算當前的代碼指標"""
        metrics = {}

        try:
            file_path = "lazy_blacktea_pyqt.py"
            if os.path.exists(file_path):
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()

                metrics.update({
                    'total_lines': len(content.splitlines()),
                    'non_empty_lines': len([line for line in content.splitlines() if line.strip()]),
                    'comment_lines': len([line for line in content.splitlines() if line.strip().startswith('#')]),
                    'class_count': content.count('class '),
                    'function_count': content.count('def '),
                    'file_size': len(content)
                })
        except Exception as e:
            metrics['error'] = str(e)

        return metrics

    def test_no_major_memory_leaks(self):
        """測試沒有明顯的內存洩漏"""
        print("\n🔍 測試內存洩漏...")

        initial_memory = psutil.Process().memory_info().rss / 1024 / 1024

        # 執行多次操作
        for i in range(10):
            importlib.reload(lazy_blacktea_pyqt)
            if hasattr(lazy_blacktea_pyqt, 'WindowMain'):
                WindowMain = getattr(lazy_blacktea_pyqt, 'WindowMain')
                # 執行一些基本操作
                methods = dir(WindowMain)
            gc.collect()

        final_memory = psutil.Process().memory_info().rss / 1024 / 1024
        memory_growth = final_memory - initial_memory

        print(f"  📊 內存增長: {memory_growth:+.2f} MB")

        # 內存增長不應該過多
        self.assertLess(
            memory_growth, 20.0,
            f"可能存在內存洩漏: {memory_growth:+.2f} MB"
        )


def run_performance_tests():
    """運行性能回歸測試的便利函數"""
    print("⚡ 運行性能回歸測試...")

    # 創建測試套件
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    # 添加性能測試
    suite.addTests(loader.loadTestsFromTestCase(PerformanceRegressionTest))

    # 運行測試
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    print("\n" + "="*60)
    print("📊 性能回歸測試報告")
    print("="*60)

    if result.wasSuccessful():
        print("✅ 所有性能測試通過！")
        print("🚀 性能表現良好，可以安全繼續重構")
    else:
        print("❌ 發現性能回歸問題！")
        print("⚠️  請在繼續重構前優化性能")

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
    success = run_performance_tests()
    sys.exit(0 if success else 1)