"""Regression tests for routine-success toast feedback (audit finding #11)."""

import os
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt6.QtWidgets import QApplication

from ui.device_operations_manager import DeviceOperationsManager


class RoutineSuccessToastTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_show_toast_routes_to_window_show_toast(self):
        window = SimpleNamespace(show_toast=MagicMock(), show_info=MagicMock())
        mgr = DeviceOperationsManager(parent_window=window)
        mgr._show_toast("Done", style="success", fallback_title="Reboot")
        window.show_toast.assert_called_once_with("Done", "success")
        window.show_info.assert_not_called()

    def test_show_toast_falls_back_to_dialog_when_unavailable(self):
        window = SimpleNamespace(show_info=MagicMock())  # no show_toast
        mgr = DeviceOperationsManager(parent_window=window)
        mgr._show_toast("Done", fallback_title="Reboot")
        window.show_info.assert_called_once_with("Reboot", "Done")


if __name__ == '__main__':
    unittest.main()
