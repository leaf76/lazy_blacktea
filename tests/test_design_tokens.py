"""Tests for ui.design_tokens (Phase 1 of the redesign).

Goals:
* Guarantee zero visual regression by asserting the legacy palette returned
  by ``design_tokens.get_legacy_palette`` matches ``style_manager``'s
  forensic ``_LEGACY_THEME_PRESETS`` snapshot byte-for-byte.
* Verify the runtime ``_THEME_PRESETS`` exposes both legacy and spec keys.
* Sanity-check key spec namespace presence.
"""

from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestDesignTokensModule(unittest.TestCase):
    """Pure-data tests for ui.design_tokens."""

    def test_supported_themes_are_light_and_dark(self):
        from ui.design_tokens import SUPPORTED_THEMES

        self.assertEqual(SUPPORTED_THEMES, ("light", "dark"))

    def test_default_theme_alias_resolves_to_light(self):
        from ui.design_tokens import get_palette

        self.assertEqual(get_palette("default"), get_palette("light"))

    def test_invalid_theme_falls_back_to_light(self):
        from ui.design_tokens import get_palette

        self.assertEqual(get_palette("not-a-theme"), get_palette("light"))

    def test_light_dark_palettes_are_distinct(self):
        from ui.design_tokens import get_palette

        light = get_palette("light")
        dark = get_palette("dark")
        # At least the canvas background must differ between themes.
        self.assertNotEqual(light["bg_canvas"], dark["bg_canvas"])
        self.assertNotEqual(light["text_primary"], dark["text_primary"])

    def test_legacy_keys_match_style_manager_snapshot(self):
        """Every legacy key must keep its historic value in Phase 1."""

        from ui.design_tokens import get_legacy_palette
        from ui.style_manager import _LEGACY_THEME_PRESETS

        for theme in ("light", "dark"):
            with self.subTest(theme=theme):
                snapshot = _LEGACY_THEME_PRESETS[theme]
                derived = get_legacy_palette(theme)
                self.assertEqual(
                    snapshot,
                    derived,
                    msg=f"design_tokens drifted from style_manager snapshot for {theme}",
                )

    def test_runtime_theme_presets_contain_both_namespaces(self):
        from ui.design_tokens import get_palette
        from ui.style_manager import _THEME_PRESETS

        for theme in ("light", "dark"):
            with self.subTest(theme=theme):
                runtime = _THEME_PRESETS[theme]
                expected = get_palette(theme)
                self.assertEqual(runtime, expected)

    def test_spec_namespace_keys_present(self):
        """Phase 2/3 widgets rely on these spec keys existing."""

        from ui.design_tokens import get_tokens

        required_spec_keys = {
            "bg_canvas",
            "bg_surface",
            "bg_surface_alt",
            "bg_elevated",
            "bg_hover",
            "bg_active",
            "border_subtle",
            "border_default",
            "border_strong",
            "border_focus",
            "fg_primary",
            "fg_secondary",
            "fg_muted",
            "fg_inverse",
            "fg_link",
            "accent_primary",
            "accent_primary_hover",
            "accent_success",
            "accent_warning",
            "accent_danger",
            "accent_info",
            "tint_primary",
            "tint_success",
            "tint_warning",
            "tint_danger",
            "tint_info",
        }

        for theme in ("light", "dark"):
            with self.subTest(theme=theme):
                tokens = get_tokens(theme)
                missing = required_spec_keys - set(tokens)
                self.assertFalse(
                    missing, msg=f"missing spec tokens in {theme}: {missing}"
                )

    def test_all_token_values_are_strings(self):
        from ui.design_tokens import get_palette

        for theme in ("light", "dark"):
            for key, value in get_palette(theme).items():
                self.assertIsInstance(
                    value, str, msg=f"{theme}.{key} not a string: {value!r}"
                )
                self.assertTrue(
                    value.startswith(("#", "rgb")),
                    msg=f"{theme}.{key}={value!r} not a CSS color literal",
                )

    def test_typography_and_motion_helpers_present(self):
        from ui.design_tokens import (
            FONT_SIZE_PX,
            FONT_WEIGHT,
            MOTION_MS,
            RADIUS,
            SPACING,
            get_typography,
        )

        self.assertIn("text_md", FONT_SIZE_PX)
        self.assertIn("weight_regular", FONT_WEIGHT)
        self.assertIn("motion_normal", MOTION_MS)
        self.assertIn("radius_md", RADIUS)
        self.assertIn("space_3", SPACING)

        typo = get_typography()
        self.assertIn("font_ui", typo)
        self.assertIn("font_mono", typo)


class TestThemeManagerIntegration(unittest.TestCase):
    """Theme switching must keep both namespaces aligned."""

    def test_theme_switch_updates_both_namespaces(self):
        from ui.design_tokens import get_palette
        from ui.style_manager import StyleManager, ThemeManager

        manager = ThemeManager()
        manager.set_theme("light")
        self.assertEqual(StyleManager.COLORS["bg_canvas"], get_palette("light")["bg_canvas"])
        self.assertEqual(StyleManager.COLORS["text_primary"], get_palette("light")["text_primary"])

        manager.set_theme("dark")
        self.assertEqual(StyleManager.COLORS["bg_canvas"], get_palette("dark")["bg_canvas"])
        self.assertEqual(StyleManager.COLORS["text_primary"], get_palette("dark")["text_primary"])

        manager.set_theme("light")  # restore for isolation


if __name__ == "__main__":
    unittest.main(verbosity=2)
