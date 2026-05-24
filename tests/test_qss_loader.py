"""Tests for ui.qss_loader.

Verifies template discovery, token substitution, theme awareness, and the
defensive fallback wired into ``StyleManager.get_tooltip_style``.
"""

from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestQssLoader(unittest.TestCase):
    def setUp(self):
        from ui import qss_loader

        qss_loader.clear_cache()
        self.qss_loader = qss_loader

    def test_tooltip_template_is_bundled(self):
        self.assertIn("tooltip", self.qss_loader.available())

    def test_render_substitutes_tokens(self):
        rendered = self.qss_loader.render("tooltip", "light")
        # Light theme tooltip background is the legacy ``tooltip_background``.
        self.assertIn("rgba(45, 45, 45, 0.95)", rendered)
        # The literal placeholder must not leak through.
        self.assertNotIn("{tooltip_background}", rendered)

    def test_render_respects_theme_switch(self):
        light = self.qss_loader.render("tooltip", "light")
        dark = self.qss_loader.render("tooltip", "dark")
        self.assertNotEqual(light, dark)
        self.assertIn("rgba(240, 240, 240, 0.95)", dark)

    def test_render_extra_overrides_palette(self):
        out = self.qss_loader.render(
            "tooltip", "light", extra={"tooltip_background": "#FF00AA"}
        )
        self.assertIn("#FF00AA", out)

    def test_render_missing_template_raises(self):
        from ui.qss_loader import QSSTemplateNotFound

        with self.assertRaises(QSSTemplateNotFound):
            self.qss_loader.render("does-not-exist")

    def test_style_manager_tooltip_uses_external_qss(self):
        from ui.style_manager import StyleManager, ThemeManager

        manager = ThemeManager()
        try:
            manager.set_theme("light")
            css = StyleManager.get_tooltip_style()
            self.assertIn("rgba(45, 45, 45, 0.95)", css)
            self.assertIn("QToolTip", css)

            manager.set_theme("dark")
            css_dark = StyleManager.get_tooltip_style()
            self.assertIn("rgba(240, 240, 240, 0.95)", css_dark)
        finally:
            manager.set_theme("light")


if __name__ == "__main__":
    unittest.main(verbosity=2)
