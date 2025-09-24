#!/usr/bin/env python3
"""
重構測試框架 - 確保重構過程中代碼質量和功能完整性

這個框架提供：
1. 重構前後對比測試
2. 接口兼容性驗證
3. 性能回歸檢測
4. 代碼結構分析
"""

import sys
import os
import time
import unittest
import inspect
import importlib
from typing import Dict, List, Any, Callable, Tuple
from unittest.mock import Mock, patch
import tempfile
import json
import hashlib

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class RefactoringTestFramework:
    """重構測試框架主類"""

    def __init__(self, module_name: str = "lazy_blacktea_pyqt"):
        self.module_name = module_name
        self.baseline_data = {}
        self.performance_baseline = {}
        self.interface_snapshots = {}

    def create_baseline(self) -> Dict[str, Any]:
        """創建重構前的基線數據"""
        print("🔍 創建重構基線數據...")

        try:
            # 動態導入模組
            module = importlib.import_module(self.module_name)

            baseline = {
                'timestamp': time.time(),
                'module_info': self._analyze_module_structure(module),
                'class_interfaces': self._extract_class_interfaces(module),
                'function_signatures': self._extract_function_signatures(module),
                'performance_metrics': self._measure_basic_performance(module),
                'code_metrics': self._calculate_code_metrics()
            }

            self.baseline_data = baseline
            self._save_baseline(baseline)

            print("✅ 基線數據創建完成")
            return baseline

        except Exception as e:
            print(f"❌ 創建基線數據失敗: {e}")
            return {}

    def _analyze_module_structure(self, module) -> Dict[str, Any]:
        """分析模組結構"""
        structure = {
            'classes': [],
            'functions': [],
            'constants': [],
            'imports': []
        }

        for name in dir(module):
            obj = getattr(module, name)
            if inspect.isclass(obj) and obj.__module__ == module.__name__:
                class_info = {
                    'name': name,
                    'methods': [m for m in dir(obj) if not m.startswith('_')],
                    'method_count': len([m for m in dir(obj) if callable(getattr(obj, m)) and not m.startswith('_')])
                }
                structure['classes'].append(class_info)
            elif inspect.isfunction(obj):
                structure['functions'].append({
                    'name': name,
                    'signature': str(inspect.signature(obj))
                })
            elif isinstance(obj, (str, int, float, bool, list, dict)) and name.isupper():
                structure['constants'].append(name)

        return structure

    def _extract_class_interfaces(self, module) -> Dict[str, List[str]]:
        """提取類的公共接口"""
        interfaces = {}

        for name in dir(module):
            obj = getattr(module, name)
            if inspect.isclass(obj) and obj.__module__ == module.__name__:
                public_methods = []
                for method_name in dir(obj):
                    if not method_name.startswith('_'):
                        method = getattr(obj, method_name)
                        if callable(method):
                            try:
                                sig = str(inspect.signature(method))
                                public_methods.append(f"{method_name}{sig}")
                            except:
                                public_methods.append(method_name)
                interfaces[name] = public_methods

        return interfaces

    def _extract_function_signatures(self, module) -> Dict[str, str]:
        """提取函數簽名"""
        signatures = {}

        for name in dir(module):
            obj = getattr(module, name)
            if inspect.isfunction(obj) and not name.startswith('_'):
                try:
                    signatures[name] = str(inspect.signature(obj))
                except:
                    signatures[name] = "signature_unavailable"

        return signatures

    def _measure_basic_performance(self, module) -> Dict[str, float]:
        """測量基本性能指標"""
        metrics = {}

        try:
            # 測量模組導入時間
            start_time = time.time()
            importlib.reload(module)
            import_time = time.time() - start_time
            metrics['import_time'] = import_time

            # 對於GUI應用，跳過實例化測試以避免QApplication問題
            # 改為測量類定義的基本屬性
            for name in dir(module):
                obj = getattr(module, name)
                if inspect.isclass(obj) and obj.__module__ == module.__name__:
                    try:
                        # 測量類分析時間而不是實例化
                        start_time = time.time()
                        method_count = len([m for m in dir(obj) if callable(getattr(obj, m)) and not m.startswith('_')])
                        analysis_time = time.time() - start_time
                        metrics[f'{name}_analysis_time'] = analysis_time
                        metrics[f'{name}_method_count'] = method_count
                        break  # 只測試主要類
                    except:
                        pass
        except Exception as e:
            metrics['error'] = str(e)

        return metrics

    def _calculate_code_metrics(self) -> Dict[str, int]:
        """計算代碼指標"""
        metrics = {}

        try:
            file_path = f"{self.module_name}.py"
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

    def _save_baseline(self, baseline: Dict[str, Any]):
        """保存基線數據到文件"""
        baseline_file = "tests/refactoring_baseline.json"
        try:
            with open(baseline_file, 'w', encoding='utf-8') as f:
                json.dump(baseline, f, indent=2, default=str)
            print(f"📁 基線數據已保存到 {baseline_file}")
        except Exception as e:
            print(f"⚠️  保存基線數據失敗: {e}")

    def load_baseline(self) -> Dict[str, Any]:
        """從文件加載基線數據"""
        baseline_file = "tests/refactoring_baseline.json"
        try:
            with open(baseline_file, 'r', encoding='utf-8') as f:
                self.baseline_data = json.load(f)
            print("✅ 基線數據加載完成")
            return self.baseline_data
        except Exception as e:
            print(f"❌ 加載基線數據失敗: {e}")
            return {}

    def verify_interface_compatibility(self) -> bool:
        """驗證接口兼容性"""
        print("🔍 驗證接口兼容性...")

        if not self.baseline_data:
            print("❌ 沒有基線數據，請先創建基線")
            return False

        try:
            # 重新導入模組獲取當前狀態
            module = importlib.import_module(self.module_name)
            current_interfaces = self._extract_class_interfaces(module)
            baseline_interfaces = self.baseline_data.get('class_interfaces', {})

            compatibility_issues = []

            # 檢查每個類的接口
            for class_name, baseline_methods in baseline_interfaces.items():
                if class_name not in current_interfaces:
                    compatibility_issues.append(f"類 {class_name} 已被移除")
                    continue

                current_methods = current_interfaces[class_name]

                # 檢查是否有方法被移除
                for method in baseline_methods:
                    if method not in current_methods:
                        compatibility_issues.append(f"方法 {class_name}.{method} 已被移除或簽名改變")

            if compatibility_issues:
                print("❌ 發現接口兼容性問題:")
                for issue in compatibility_issues:
                    print(f"  - {issue}")
                return False
            else:
                print("✅ 接口兼容性驗證通過")
                return True

        except Exception as e:
            print(f"❌ 接口兼容性驗證失敗: {e}")
            return False

    def measure_performance_regression(self) -> Dict[str, float]:
        """測量性能回歸"""
        print("⚡ 測量性能回歸...")

        if not self.baseline_data:
            print("❌ 沒有基線數據，請先創建基線")
            return {}

        try:
            module = importlib.import_module(self.module_name)
            current_metrics = self._measure_basic_performance(module)
            baseline_metrics = self.baseline_data.get('performance_metrics', {})

            regression_report = {}

            for metric_name, baseline_value in baseline_metrics.items():
                if metric_name in current_metrics and isinstance(baseline_value, (int, float)):
                    current_value = current_metrics[metric_name]
                    if isinstance(current_value, (int, float)):
                        change_percent = ((current_value - baseline_value) / baseline_value) * 100
                        regression_report[metric_name] = {
                            'baseline': baseline_value,
                            'current': current_value,
                            'change_percent': change_percent,
                            'status': 'regression' if change_percent > 20 else 'acceptable'
                        }

            # 打印報告
            for metric, data in regression_report.items():
                status_icon = "❌" if data['status'] == 'regression' else "✅"
                print(f"  {status_icon} {metric}: {data['baseline']:.4f} -> {data['current']:.4f} ({data['change_percent']:+.1f}%)")

            return regression_report

        except Exception as e:
            print(f"❌ 性能回歸測量失敗: {e}")
            return {}

    def generate_refactoring_report(self) -> Dict[str, Any]:
        """生成重構報告"""
        print("📊 生成重構報告...")

        report = {
            'timestamp': time.time(),
            'interface_compatibility': self.verify_interface_compatibility(),
            'performance_regression': self.measure_performance_regression(),
            'recommendations': []
        }

        # 添加建議
        if not report['interface_compatibility']:
            report['recommendations'].append("修復接口兼容性問題")

        perf_issues = [k for k, v in report['performance_regression'].items()
                      if isinstance(v, dict) and v.get('status') == 'regression']
        if perf_issues:
            report['recommendations'].append(f"優化性能回歸問題: {', '.join(perf_issues)}")

        if not report['recommendations']:
            report['recommendations'].append("重構成功！沒有發現問題")

        return report


class RefactoringTestCase(unittest.TestCase):
    """重構專用測試基類"""

    @classmethod
    def setUpClass(cls):
        """設置重構測試環境"""
        cls.framework = RefactoringTestFramework()
        cls.baseline = cls.framework.load_baseline()

    def test_interface_compatibility(self):
        """測試接口兼容性"""
        self.assertTrue(
            self.framework.verify_interface_compatibility(),
            "接口兼容性測試失敗"
        )

    def test_no_major_performance_regression(self):
        """測試沒有嚴重的性能回歸"""
        regression_report = self.framework.measure_performance_regression()

        major_regressions = [
            metric for metric, data in regression_report.items()
            if isinstance(data, dict) and data.get('status') == 'regression'
        ]

        self.assertEqual(
            len(major_regressions), 0,
            f"發現嚴重性能回歸: {major_regressions}"
        )


def create_baseline():
    """創建重構基線的便利函數"""
    framework = RefactoringTestFramework()
    return framework.create_baseline()


def run_refactoring_tests():
    """運行重構測試的便利函數"""
    print("🧪 運行重構測試...")

    # 創建測試套件
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    # 添加重構測試
    suite.addTests(loader.loadTestsFromTestCase(RefactoringTestCase))

    # 運行測試
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    # 生成詳細報告
    framework = RefactoringTestFramework()
    report = framework.generate_refactoring_report()

    print("\n" + "="*60)
    print("📊 重構測試報告")
    print("="*60)
    print(f"接口兼容性: {'✅ 通過' if report['interface_compatibility'] else '❌ 失敗'}")
    print(f"性能回歸檢查: {len([k for k, v in report['performance_regression'].items() if isinstance(v, dict) and v.get('status') == 'acceptable'])} 項通過")
    print("\n建議:")
    for rec in report['recommendations']:
        print(f"  - {rec}")

    return result.wasSuccessful()


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='重構測試框架')
    parser.add_argument('--create-baseline', action='store_true',
                       help='創建重構基線數據')
    parser.add_argument('--run-tests', action='store_true',
                       help='運行重構測試')

    args = parser.parse_args()

    if args.create_baseline:
        create_baseline()
    elif args.run_tests:
        run_refactoring_tests()
    else:
        print("使用方法:")
        print("  python refactoring_framework.py --create-baseline  # 創建基線")
        print("  python refactoring_framework.py --run-tests       # 運行測試")