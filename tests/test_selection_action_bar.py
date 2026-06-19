"""Tests for the Devices-pane sticky batch-action bar (audit finding #15)."""

import os
import sys
import unittest
from unittest.mock import MagicMock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt6.QtWidgets import QApplication

from ui.components.selection_action_bar import SelectionActionBar


class SelectionActionBarTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_hidden_when_no_selection(self):
        bar = SelectionActionBar()
        bar.set_selection_count(0)
        self.assertFalse(bar.isVisibleTo(None) if bar.parent() else bar.isVisible())

    def test_visible_and_labelled_when_selected(self):
        bar = SelectionActionBar()
        bar.set_selection_count(3)
        self.assertTrue(bar.isVisible())
        self.assertIn('3 selected', bar._count_label.text())

    def test_buttons_invoke_callbacks(self):
        screenshot, record, shell, clear = (MagicMock() for _ in range(4))
        bar = SelectionActionBar(
            on_screenshot=screenshot,
            on_record=record,
            on_shell=shell,
            on_clear=clear,
        )
        bar._screenshot_btn.click()
        bar._record_btn.click()
        bar._shell_btn.click()
        bar._clear_btn.click()
        screenshot.assert_called_once()
        record.assert_called_once()
        shell.assert_called_once()
        clear.assert_called_once()


if __name__ == '__main__':
    unittest.main()
