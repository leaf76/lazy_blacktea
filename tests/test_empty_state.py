"""Tests for the rich device-list empty state (audit finding #37)."""

import os
import sys
import unittest
from unittest.mock import MagicMock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt6.QtWidgets import QApplication

from ui.components.empty_state import EmptyStateWidget


class EmptyStateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_no_devices_mode_shows_refresh_and_guide_hides_clear(self):
        w = EmptyStateWidget()
        w.show_no_devices()
        self.assertTrue(w._refresh_btn.isVisible() or not w.isVisible())
        self.assertFalse(w._clear_btn.isVisibleTo(w))
        self.assertIn('No devices connected', w._headline.text())

    def test_no_match_mode_shows_clear_hides_refresh(self):
        w = EmptyStateWidget()
        w.show_no_match()
        self.assertTrue(w._clear_btn.isVisibleTo(w))
        self.assertFalse(w._refresh_btn.isVisibleTo(w))
        self.assertIn('No devices match', w._headline.text())

    def test_callbacks_fire(self):
        refresh, clear, guide = MagicMock(), MagicMock(), MagicMock()
        w = EmptyStateWidget(on_refresh=refresh, on_clear=clear, on_open_guide=guide)
        w.show_no_devices()
        w._refresh_btn.click()
        w._guide_btn.click()
        w.show_no_match()
        w._clear_btn.click()
        refresh.assert_called_once()
        guide.assert_called_once()
        clear.assert_called_once()

    def test_settext_fallback_sets_headline(self):
        w = EmptyStateWidget()
        w.setText('Custom headline')
        self.assertEqual(w._headline.text(), 'Custom headline')


if __name__ == '__main__':
    unittest.main()
