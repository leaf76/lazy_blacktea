"""Tests: completed operations auto-dismiss from the panel only (#20).

The operation must leave the visible panel but remain available to the manager
(Tasks pane / Recent-tasks palette provider). Failed rows stay until cleared.
"""

import os
import sys
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt6.QtWidgets import QApplication

from ui.components.device_operation_status_panel import DeviceOperationStatusPanel
from ui.signal_payloads import DeviceOperationEvent, OperationStatus, OperationType


def _event(status):
    return DeviceOperationEvent(
        device_serial='dev1',
        operation_type=OperationType.SCREENSHOT,
        status=status,
        operation_id='op1',
    )


class PanelAutoDismissTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_completed_schedules_dismiss(self):
        panel = DeviceOperationStatusPanel()
        panel.add_operation(_event(OperationStatus.RUNNING))
        panel.update_operation(_event(OperationStatus.COMPLETED))
        self.assertIn('op1', panel._dismiss_timers)

    def test_failed_does_not_schedule_dismiss(self):
        panel = DeviceOperationStatusPanel()
        panel.add_operation(_event(OperationStatus.RUNNING))
        panel.update_operation(_event(OperationStatus.FAILED))
        self.assertNotIn('op1', panel._dismiss_timers)

    def test_auto_dismiss_removes_widget_from_panel(self):
        panel = DeviceOperationStatusPanel()
        panel.add_operation(_event(OperationStatus.RUNNING))
        panel.update_operation(_event(OperationStatus.COMPLETED))
        panel._panel_auto_dismiss('op1')
        self.assertNotIn('op1', panel._items)
        self.assertNotIn('op1', panel._dismiss_timers)


if __name__ == '__main__':
    unittest.main()
