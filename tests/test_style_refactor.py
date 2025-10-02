#!/usr/bin/env python3
"""
樣式重構測試 - 確保樣式管理器功能正確性

這個測試專門驗證：
1. StyleManager類的功能完整性
2. 樣式枚舉類型的完整性
3. 樣式生成方法的正確性
4. 樣式應用方法的功能
5. 主文件中樣式重構的正確性
"""

import sys
import os
import unittest
from unittest.mock import Mock, patch

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from ui.style_manager import StyleManager, ButtonStyle, LabelStyle, PanelStyle, ThemeManager
    import lazy_blacktea_pyqt
except ImportError as e:
    print(f"❌ 無法導入模組: {e}")
    sys.exit(1)


class StyleRefactorTest(unittest.TestCase):
    """樣式重構測試類"""

    def test_style_enums_exist(self):
        """測試樣式枚舉類型的存在性"""
        print("\n🎨 測試樣式枚舉類型...")

        # 檢查ButtonStyle
        button_styles = [
            ButtonStyle.PRIMARY,
            ButtonStyle.SECONDARY,
            ButtonStyle.WARNING,
            ButtonStyle.DANGER,
            ButtonStyle.NEUTRAL,
            ButtonStyle.SYSTEM
        ]

        for style in button_styles:
            self.assertIsInstance(style, ButtonStyle)
            print(f"    ✅ {style.name}")

        # 檢查LabelStyle
        label_styles = [
            LabelStyle.HEADER,
            LabelStyle.SUBHEADER,
            LabelStyle.SUCCESS,
            LabelStyle.ERROR,
            LabelStyle.WARNING,
            LabelStyle.INFO,
            LabelStyle.STATUS
        ]

        for style in label_styles:
            self.assertIsInstance(style, LabelStyle)
            print(f"    ✅ {style.name}")

    def test_style_manager_methods(self):
        """測試StyleManager方法的存在性"""
        print("\n🔧 測試StyleManager方法...")

        key_methods = [
            'get_button_style',
            'get_label_style',
            'get_input_style',
            'get_search_input_style',
            'get_search_label_style',
            'get_tree_style',
            'get_console_style',
            'get_checkbox_style',
            'get_menu_style',
            'get_device_info_style',
            'get_tooltip_style',
            'get_action_button_style',
            'apply_button_style',
            'apply_label_style',
            'get_status_styles'
        ]

        for method_name in key_methods:
            self.assertTrue(hasattr(StyleManager, method_name))
            method = getattr(StyleManager, method_name)
            self.assertTrue(callable(method))
            print(f"    ✅ {method_name}")

    def test_color_constants(self):
        """測試顏色常數的完整性"""
        print("\n🌈 測試顏色常數...")

        required_colors = [
            'primary', 'primary_hover',
            'secondary', 'secondary_hover',
            'warning', 'warning_hover',
            'danger', 'danger_hover',
            'neutral', 'neutral_hover',
            'success', 'error', 'info',
            'text_primary', 'text_secondary', 'text_hint',
            'border', 'background', 'background_hover'
        ]

        for color_name in required_colors:
            self.assertIn(color_name, StyleManager.COLORS)
            color_value = StyleManager.COLORS[color_name]
            self.assertIsInstance(color_value, str)
            print(f"    ✅ {color_name}: {color_value}")

    def test_button_style_generation(self):
        """測試按鈕樣式生成"""
        print("\n🔘 測試按鈕樣式生成...")

        for button_style in ButtonStyle:
            css = StyleManager.get_button_style(button_style, 36)
            self.assertIsInstance(css, str)
            self.assertIn('QPushButton', css)

            if button_style != ButtonStyle.SYSTEM:
                self.assertIn('background-color:', css)
                self.assertIn('color:', css)
                self.assertIn('height: 36px', css)

            print(f"    ✅ {button_style.name} -> {len(css)} 個字符")

    def test_high_contrast_button_styles_on_unix_platforms(self):
        """確保在 Linux 與 macOS 上啟用高對比按鈕樣式。"""
        print("\n🖥️ 測試 Unix-like 平台高對比樣式...")

        for platform_key in ("linux", "darwin"):
            with self.subTest(platform=platform_key), \
                    patch('ui.style_manager.StyleManager._detect_platform', return_value=platform_key):
                secondary_css = StyleManager.get_button_style(ButtonStyle.SECONDARY, 36).lower()
                neutral_css = StyleManager.get_button_style(ButtonStyle.NEUTRAL, 36).lower()
                system_css = StyleManager.get_button_style(ButtonStyle.SYSTEM, 36).lower()

                self.assertIn('border: 2px solid', secondary_css)
                self.assertIn('border: 2px solid', neutral_css)
                self.assertIn('border: 2px solid', system_css)

                self.assertNotIn('background-color: #f9f9f9', secondary_css)
                self.assertNotIn('background-color: #f2f2f2', neutral_css)
                self.assertIn('background-color', system_css)

                print(f"    ✅ {platform_key} secondary border -> {secondary_css.count('border:')}")

    def test_windows_button_styles_remain_lightweight(self):
        """驗證 Windows 上維持原本的輕量樣式。"""
        print("\n🪟 測試 Windows 平台保持原樣式...")

        with patch('ui.style_manager.StyleManager._detect_platform', return_value='windows'):
            secondary_css = StyleManager.get_button_style(ButtonStyle.SECONDARY, 36).lower()
            system_css = StyleManager.get_button_style(ButtonStyle.SYSTEM, 36).lower()

        self.assertIn('border: 1px solid', secondary_css)
        self.assertIn('background-color: #f9f9f9', secondary_css)
        self.assertNotIn('border: 2px solid', system_css)
        self.assertNotIn('background-color', system_css)

        print("    ✅ Windows secondary retains lightweight border")

    def test_label_style_generation(self):
        """測試標籤樣式生成"""
        print("\n🏷️ 測試標籤樣式生成...")

        for label_style in LabelStyle:
            css = StyleManager.get_label_style(label_style)
            self.assertIsInstance(css, str)

            if label_style != LabelStyle.STATUS:  # STATUS是特例
                self.assertIn('QLabel', css)

            print(f"    ✅ {label_style.name} -> {len(css)} 個字符")

    def test_status_styles_dictionary(self):
        """測試狀態樣式字典"""
        print("\n📊 測試狀態樣式...")

        status_styles = StyleManager.get_status_styles()
        self.assertIsInstance(status_styles, dict)

        expected_keys = [
            'recording_active',
            'recording_inactive',
            'screenshot_ready',
            'screenshot_processing'
        ]

        for key in expected_keys:
            self.assertIn(key, status_styles)
            self.assertIsInstance(status_styles[key], str)
            print(f"    ✅ {key}")

    def test_theme_manager_functionality(self):
        """測試主題管理器功能"""
        print("\n🎭 測試主題管理器...")

        theme_manager = ThemeManager()

        # 測試預設主題
        self.assertEqual(theme_manager.get_current_theme(), "default")
        print(f"    ✅ 預設主題: {theme_manager.get_current_theme()}")

        # 測試主題切換
        original_colors = StyleManager.COLORS.copy()
        theme_manager.set_theme("dark")

        self.assertEqual(theme_manager.get_current_theme(), "dark")
        print(f"    ✅ 切換主題: {theme_manager.get_current_theme()}")

        # 測試無效主題
        theme_manager.set_theme("invalid_theme")
        self.assertEqual(theme_manager.get_current_theme(), "dark")  # 應該保持不變
        print(f"    ✅ 無效主題處理")

    def test_main_file_style_integration(self):
        """測試主文件樣式整合"""
        print("\n🔗 測試主文件樣式整合...")

        # 檢查主文件是否正確導入StyleManager
        self.assertTrue(hasattr(lazy_blacktea_pyqt, 'StyleManager'))
        self.assertTrue(hasattr(lazy_blacktea_pyqt, 'ButtonStyle'))
        self.assertTrue(hasattr(lazy_blacktea_pyqt, 'LabelStyle'))
        print(f"    ✅ StyleManager導入到主文件")

        # 檢查WindowMain類是否存在
        if hasattr(lazy_blacktea_pyqt, 'WindowMain'):
            WindowMain = getattr(lazy_blacktea_pyqt, 'WindowMain')
            print(f"    ✅ WindowMain類存在")
        else:
            self.fail("WindowMain類不存在")

    def test_css_output_format(self):
        """測試CSS輸出格式"""
        print("\n📝 測試CSS格式...")

        # 測試基本CSS格式
        primary_css = StyleManager.get_button_style(ButtonStyle.PRIMARY)

        # CSS應該包含基本結構
        self.assertIn('QPushButton {', primary_css)
        self.assertIn('}', primary_css)
        self.assertIn('padding:', primary_css)
        self.assertIn('border-radius:', primary_css)

        print(f"    ✅ CSS格式正確")
        print(f"    📏 PRIMARY按鈕CSS長度: {len(primary_css)} 字符")

    def test_action_button_style_has_explicit_text_color(self):
        """確保動作按鈕樣式包含文字顏色設定避免反白看不見。"""
        style = StyleManager.get_action_button_style()
        self.assertIn('\n    color:', style)
        print("    ✅ Action 按鈕具備文字顏色設定")

    def test_style_consistency(self):
        """測試樣式一致性"""
        print("\n⚖️ 測試樣式一致性...")

        # 檢查所有按鈕樣式是否使用統一的顏色
        for button_style in [ButtonStyle.PRIMARY, ButtonStyle.SECONDARY, ButtonStyle.WARNING]:
            with patch('ui.style_manager.StyleManager._detect_platform', return_value='windows'):
                css = StyleManager.get_button_style(button_style)

            profile = StyleManager.BUTTON_STYLE_PROFILES[button_style]
            self.assertIn(profile['bg'], css)
            self.assertIn(profile['border'], css)
            self.assertIn(profile['hover'], css)

            print(f"    ✅ {button_style.name} 使用正確顏色")


def run_style_refactor_tests():
    """運行樣式重構測試的便利函數"""
    print("🎨 運行樣式重構測試...")

    # 創建測試套件
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    # 添加樣式重構測試
    suite.addTests(loader.loadTestsFromTestCase(StyleRefactorTest))

    # 運行測試
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    print("\n" + "="*60)
    print("📊 樣式重構測試報告")
    print("="*60)

    if result.wasSuccessful():
        print("✅ 樣式重構測試通過！")
        print("🎨 樣式管理器功能正常")
        print("🔧 樣式重構成功完成")
    else:
        print("❌ 樣式重構測試失敗！")
        print("⚠️  請檢查樣式重構問題")

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
    success = run_style_refactor_tests()
    sys.exit(0 if success else 1)
