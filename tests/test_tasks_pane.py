import os
import sys
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt6.QtWidgets import QApplication  # noqa: E402


_APP = QApplication.instance() or QApplication([])


class TasksPaneTests(unittest.TestCase):
    def setUp(self):
        from ui.device_operation_status_manager import DeviceOperationStatusManager
        from ui.shell import TasksPane

        self.manager = DeviceOperationStatusManager()
        self.pane = TasksPane(self.manager)
        self.addCleanup(self.pane.deleteLater)

    def _event(self, serial="device1", op_type=None, can_cancel=False):
        from ui.signal_payloads import DeviceOperationEvent, OperationType

        return DeviceOperationEvent.create(
            device_serial=serial,
            operation_type=op_type or OperationType.SCREENSHOT,
            device_name="Pixel",
            can_cancel=can_cancel,
        )

    def test_active_and_recent_groups_follow_manager_state(self):
        from ui.signal_payloads import OperationStatus

        active = self._event()
        terminal = self._event(serial="device2")

        self.manager.add_operation(active)
        terminal_id = self.manager.add_operation(terminal)
        self.manager.update_operation(terminal_id, status=OperationStatus.COMPLETED)

        self.assertEqual(self.pane.active_count(), 1)
        self.assertEqual(self.pane.recent_count(), 1)
        self.assertEqual(self.pane.badge_text(), "1")

    def test_cancel_requested_uses_manager_cancel_operation(self):
        calls = []
        event = self._event(can_cancel=True)
        operation_id = self.manager.add_operation(event, cancel_callback=lambda: calls.append("cancel") or True)

        self.assertTrue(self.pane.cancel_operation(operation_id))

        self.assertEqual(calls, ["cancel"])

    def test_terminal_operations_are_retained_for_recent_tasks(self):
        from ui.signal_payloads import OperationStatus

        event = self._event()
        operation_id = self.manager.add_operation(event)
        self.manager.update_operation(operation_id, status=OperationStatus.COMPLETED)

        self.assertIsNotNone(self.manager.get_operation(operation_id))
        self.assertEqual(self.pane.recent_count(), 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
