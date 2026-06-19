"""Regression tests for blue accent (#28) and live theme refresh (#9)."""

import os
import sys
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt6.QtWidgets import QApplication

from ui import design_tokens
from ui.style_manager import StyleManager
from ui.collapsible_panel import CollapsiblePanel


class AccentColorTests(unittest.TestCase):
    def test_accent_primary_is_documented_blue(self):
        self.assertEqual(design_tokens.get_tokens('light')['accent_primary'], '#2D6CDF')
        self.assertEqual(design_tokens.get_tokens('dark')['accent_primary'], '#5B9DFF')

    def test_legacy_primary_stays_green(self):
        # Legacy buttons must be unaffected by the spec-token brand change.
        self.assertEqual(design_tokens.get_legacy_palette('light')['primary'], '#4CAF50')


class ThemeRefreshTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_collapsible_panel_refresh_theme_repaints(self):
        original = StyleManager.COLORS
        try:
            StyleManager.COLORS = dict(original)
            StyleManager.COLORS['panel_background'] = '#111111'
            panel = CollapsiblePanel('Section')
            StyleManager.COLORS['panel_background'] = '#FAFAFA'
            panel.refresh_theme()
            self.assertIn('#FAFAFA', panel._content_container.styleSheet())
        finally:
            StyleManager.COLORS = original


if __name__ == '__main__':
    unittest.main()
