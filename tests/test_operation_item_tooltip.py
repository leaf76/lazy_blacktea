"""Regression test: failed operations expose their full error via tooltip (#16)."""

import os
import sys
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt6.QtWidgets import QApplication

from ui.components.device_operation_status_panel import OperationItemWidget
from ui.signal_payloads import DeviceOperationEvent, OperationStatus, OperationType


def _event(status, error_message="", progress=None):
    return DeviceOperationEvent(
        device_serial="dev1",
        operation_type=OperationType.INSTALL_APK,
        status=status,
        error_message=error_message,
        progress=progress,
    )


class OperationItemTooltipTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_failed_sets_full_error_tooltip(self):
        long_error = "INSTALL_FAILED_INSUFFICIENT_STORAGE: not enough space on device"
        widget = OperationItemWidget(_event(OperationStatus.FAILED, long_error))
        self.assertEqual(widget._status_label.toolTip(), long_error)

    def test_running_clears_tooltip_after_reuse(self):
        long_error = "some long failure message that was previously shown"
        widget = OperationItemWidget(_event(OperationStatus.FAILED, long_error))
        self.assertTrue(widget._status_label.toolTip())
        # Reuse the same widget for a new RUNNING event; stale tooltip must clear.
        widget.update_event(_event(OperationStatus.RUNNING))
        self.assertEqual(widget._status_label.toolTip(), "")


if __name__ == '__main__':
    unittest.main()
