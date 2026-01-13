"""Tests for device operation status tracking components.

Tests cover:
- DeviceOperationEvent dataclass (signal_payloads.py)
- DeviceOperationStatusManager (device_operation_status_manager.py)
"""

import os
import sys
import time
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestOperationStatus(unittest.TestCase):
    """Tests for OperationStatus enum."""

    def test_enum_values(self):
        from ui.signal_payloads import OperationStatus

        self.assertEqual(OperationStatus.PENDING.value, "pending")
        self.assertEqual(OperationStatus.RUNNING.value, "running")
        self.assertEqual(OperationStatus.COMPLETED.value, "completed")
        self.assertEqual(OperationStatus.FAILED.value, "failed")
        self.assertEqual(OperationStatus.CANCELLED.value, "cancelled")

    def test_enum_string_subclass(self):
        from ui.signal_payloads import OperationStatus

        self.assertIsInstance(OperationStatus.RUNNING, str)
        self.assertEqual(OperationStatus.RUNNING.value, "running")


class TestOperationType(unittest.TestCase):
    """Tests for OperationType enum."""

    def test_enum_values(self):
        from ui.signal_payloads import OperationType

        self.assertEqual(OperationType.SCREENSHOT.value, "screenshot")
        self.assertEqual(OperationType.REBOOT.value, "reboot")
        self.assertEqual(OperationType.INSTALL_APK.value, "install_apk")
        self.assertEqual(OperationType.SHELL_COMMAND.value, "shell_command")

    def test_display_name(self):
        from ui.signal_payloads import OperationType

        self.assertEqual(OperationType.SCREENSHOT.display_name, "Screenshot")
        self.assertEqual(OperationType.INSTALL_APK.display_name, "Install APK")
        self.assertEqual(OperationType.BUG_REPORT.display_name, "Bug Report")

    def test_icon(self):
        from ui.signal_payloads import OperationType

        self.assertEqual(OperationType.SCREENSHOT.icon, "📸")
        self.assertEqual(OperationType.REBOOT.icon, "🔄")
        self.assertEqual(OperationType.BUG_REPORT.icon, "🐛")


class TestDeviceOperationEvent(unittest.TestCase):
    """Tests for DeviceOperationEvent dataclass."""

    def test_create_event(self):
        from ui.signal_payloads import (
            DeviceOperationEvent,
            OperationStatus,
            OperationType,
        )

        event = DeviceOperationEvent(
            device_serial="abc123",
            operation_type=OperationType.SCREENSHOT,
            status=OperationStatus.PENDING,
        )

        self.assertEqual(event.device_serial, "abc123")
        self.assertEqual(event.operation_type, OperationType.SCREENSHOT)
        self.assertEqual(event.status, OperationStatus.PENDING)
        self.assertIsNotNone(event.operation_id)
        self.assertIsNotNone(event.started_at)

    def test_create_factory_method(self):
        from ui.signal_payloads import (
            DeviceOperationEvent,
            OperationStatus,
            OperationType,
        )

        event = DeviceOperationEvent.create(
            device_serial="device1",
            operation_type=OperationType.REBOOT,
            device_name="Test Device",
            can_cancel=True,
        )

        self.assertEqual(event.device_serial, "device1")
        self.assertEqual(event.operation_type, OperationType.REBOOT)
        self.assertEqual(event.status, OperationStatus.PENDING)
        self.assertEqual(event.device_name, "Test Device")
        self.assertTrue(event.can_cancel)

    def test_is_active_property(self):
        from ui.signal_payloads import (
            DeviceOperationEvent,
            OperationStatus,
            OperationType,
        )

        pending = DeviceOperationEvent(
            device_serial="d1",
            operation_type=OperationType.SCREENSHOT,
            status=OperationStatus.PENDING,
        )
        running = DeviceOperationEvent(
            device_serial="d1",
            operation_type=OperationType.SCREENSHOT,
            status=OperationStatus.RUNNING,
        )
        completed = DeviceOperationEvent(
            device_serial="d1",
            operation_type=OperationType.SCREENSHOT,
            status=OperationStatus.COMPLETED,
        )

        self.assertTrue(pending.is_active)
        self.assertTrue(running.is_active)
        self.assertFalse(completed.is_active)

    def test_is_terminal_property(self):
        from ui.signal_payloads import (
            DeviceOperationEvent,
            OperationStatus,
            OperationType,
        )

        running = DeviceOperationEvent(
            device_serial="d1",
            operation_type=OperationType.SCREENSHOT,
            status=OperationStatus.RUNNING,
        )
        completed = DeviceOperationEvent(
            device_serial="d1",
            operation_type=OperationType.SCREENSHOT,
            status=OperationStatus.COMPLETED,
        )
        failed = DeviceOperationEvent(
            device_serial="d1",
            operation_type=OperationType.SCREENSHOT,
            status=OperationStatus.FAILED,
        )
        cancelled = DeviceOperationEvent(
            device_serial="d1",
            operation_type=OperationType.SCREENSHOT,
            status=OperationStatus.CANCELLED,
        )

        self.assertFalse(running.is_terminal)
        self.assertTrue(completed.is_terminal)
        self.assertTrue(failed.is_terminal)
        self.assertTrue(cancelled.is_terminal)

    def test_status_icon(self):
        from ui.signal_payloads import (
            DeviceOperationEvent,
            OperationStatus,
            OperationType,
        )

        event = DeviceOperationEvent(
            device_serial="d1",
            operation_type=OperationType.SCREENSHOT,
            status=OperationStatus.RUNNING,
        )
        self.assertEqual(event.status_icon, "⟳")

        event = DeviceOperationEvent(
            device_serial="d1",
            operation_type=OperationType.SCREENSHOT,
            status=OperationStatus.COMPLETED,
        )
        self.assertEqual(event.status_icon, "✓")

        event = DeviceOperationEvent(
            device_serial="d1",
            operation_type=OperationType.SCREENSHOT,
            status=OperationStatus.FAILED,
        )
        self.assertEqual(event.status_icon, "✗")

    def test_display_status(self):
        from ui.signal_payloads import (
            DeviceOperationEvent,
            OperationStatus,
            OperationType,
        )

        # Normal status
        event = DeviceOperationEvent(
            device_serial="d1",
            operation_type=OperationType.SCREENSHOT,
            status=OperationStatus.RUNNING,
        )
        self.assertEqual(event.display_status, "Running")

        # With progress
        event_progress = DeviceOperationEvent(
            device_serial="d1",
            operation_type=OperationType.SCREENSHOT,
            status=OperationStatus.RUNNING,
            progress=0.75,
        )
        self.assertEqual(event_progress.display_status, "75%")

        # Failed with error
        event_failed = DeviceOperationEvent(
            device_serial="d1",
            operation_type=OperationType.SCREENSHOT,
            status=OperationStatus.FAILED,
            error_message="Connection timeout",
        )
        self.assertIn("Failed:", event_failed.display_status)

    def test_with_status_preserves_fields(self):
        from ui.signal_payloads import (
            DeviceOperationEvent,
            OperationStatus,
            OperationType,
        )

        original = DeviceOperationEvent(
            device_serial="device1",
            operation_type=OperationType.INSTALL_APK,
            status=OperationStatus.PENDING,
            device_name="My Device",
            can_cancel=True,
        )

        updated = original.with_status(OperationStatus.RUNNING, progress=0.5)

        # Check preserved fields
        self.assertEqual(updated.device_serial, original.device_serial)
        self.assertEqual(updated.operation_type, original.operation_type)
        self.assertEqual(updated.operation_id, original.operation_id)
        self.assertEqual(updated.started_at, original.started_at)
        self.assertEqual(updated.device_name, original.device_name)
        self.assertEqual(updated.can_cancel, original.can_cancel)

        # Check updated fields
        self.assertEqual(updated.status, OperationStatus.RUNNING)
        self.assertEqual(updated.progress, 0.5)

    def test_with_status_sets_completed_at_for_terminal(self):
        from ui.signal_payloads import (
            DeviceOperationEvent,
            OperationStatus,
            OperationType,
        )

        original = DeviceOperationEvent(
            device_serial="device1",
            operation_type=OperationType.SCREENSHOT,
            status=OperationStatus.RUNNING,
        )
        self.assertIsNone(original.completed_at)

        completed = original.with_status(OperationStatus.COMPLETED)
        self.assertIsNotNone(completed.completed_at)

    def test_elapsed_seconds(self):
        from ui.signal_payloads import (
            DeviceOperationEvent,
            OperationStatus,
            OperationType,
        )

        event = DeviceOperationEvent(
            device_serial="d1",
            operation_type=OperationType.SCREENSHOT,
            status=OperationStatus.RUNNING,
            started_at=time.time() - 5.0,  # Started 5 seconds ago
        )

        elapsed = event.elapsed_seconds
        self.assertGreaterEqual(elapsed, 5.0)
        self.assertLess(elapsed, 6.0)


class DummySignal:
    """Mock signal for DummyQTimer."""

    def __init__(self):
        self._callback = None

    def connect(self, callback):
        self._callback = callback

    def emit(self):
        if self._callback:
            self._callback()


class DummyQTimer:
    """Mock QTimer for testing without Qt event loop."""

    def __init__(self, parent=None):
        self._timeout = DummySignal()
        self._single_shot = False
        self._interval = 0
        self._running = False

    def setSingleShot(self, single_shot):
        self._single_shot = single_shot

    @property
    def timeout(self):
        return self._timeout

    def start(self, interval=None):
        if interval is not None:
            self._interval = interval
        self._running = True

    def stop(self):
        self._running = False

    def deleteLater(self):
        pass

    def trigger(self):
        """Simulate timer firing."""
        self._timeout.emit()


class TestDeviceOperationStatusManager(unittest.TestCase):
    """Tests for DeviceOperationStatusManager."""

    def setUp(self):
        # Patch QTimer before importing the manager
        self.qtimer_patcher = patch(
            "ui.device_operation_status_manager.QTimer", DummyQTimer
        )
        self.mock_qtimer = self.qtimer_patcher.start()

        from ui.device_operation_status_manager import DeviceOperationStatusManager
        from ui.signal_payloads import (
            DeviceOperationEvent,
            OperationStatus,
            OperationType,
        )

        self.manager = DeviceOperationStatusManager()
        self.DeviceOperationEvent = DeviceOperationEvent
        self.OperationStatus = OperationStatus
        self.OperationType = OperationType

    def tearDown(self):
        self.qtimer_patcher.stop()

    def _create_event(self, serial="device1", op_type=None, can_cancel=False):
        if op_type is None:
            op_type = self.OperationType.SCREENSHOT
        return self.DeviceOperationEvent.create(
            device_serial=serial,
            operation_type=op_type,
            can_cancel=can_cancel,
        )

    def test_add_operation(self):
        event = self._create_event()
        op_id = self.manager.add_operation(event)

        self.assertIsNotNone(op_id)
        self.assertEqual(op_id, event.operation_id)
        self.assertEqual(self.manager.get_operation(op_id), event)

    def test_add_operation_emits_signals(self):
        added_signal = MagicMock()
        status_changed_signal = MagicMock()
        self.manager.operation_added.connect(added_signal)
        self.manager.device_status_changed.connect(status_changed_signal)

        event = self._create_event(serial="test_device")
        self.manager.add_operation(event)

        added_signal.assert_called_once_with(event)
        status_changed_signal.assert_called_once_with("test_device")

    def test_update_operation_progress(self):
        event = self._create_event()
        op_id = self.manager.add_operation(event)

        updated = self.manager.update_operation(op_id, progress=0.5)

        self.assertIsNotNone(updated)
        self.assertEqual(updated.progress, 0.5)
        self.assertEqual(updated.status, self.OperationStatus.PENDING)

    def test_update_operation_status(self):
        event = self._create_event()
        op_id = self.manager.add_operation(event)

        updated = self.manager.update_operation(
            op_id, status=self.OperationStatus.RUNNING
        )

        self.assertIsNotNone(updated)
        self.assertEqual(updated.status, self.OperationStatus.RUNNING)

    def test_complete_operation(self):
        event = self._create_event()
        op_id = self.manager.add_operation(event)

        completed = self.manager.complete_operation(op_id, message="Done!")

        self.assertIsNotNone(completed)
        self.assertEqual(completed.status, self.OperationStatus.COMPLETED)
        self.assertEqual(completed.message, "Done!")
        self.assertTrue(completed.is_terminal)

    def test_fail_operation(self):
        event = self._create_event()
        op_id = self.manager.add_operation(event)

        failed = self.manager.fail_operation(op_id, error_message="Connection lost")

        self.assertIsNotNone(failed)
        self.assertEqual(failed.status, self.OperationStatus.FAILED)
        self.assertEqual(failed.error_message, "Connection lost")

    def test_cancel_operation_with_callback(self):
        cancel_callback = MagicMock(return_value=True)
        event = self._create_event(can_cancel=True)
        op_id = self.manager.add_operation(event, cancel_callback=cancel_callback)

        result = self.manager.cancel_operation(op_id)

        self.assertTrue(result)
        cancel_callback.assert_called_once()
        cancelled_event = self.manager.get_operation(op_id)
        self.assertEqual(cancelled_event.status, self.OperationStatus.CANCELLED)

    def test_cancel_operation_without_callback(self):
        event = self._create_event(can_cancel=True)
        op_id = self.manager.add_operation(event)

        result = self.manager.cancel_operation(op_id)

        self.assertTrue(result)
        cancelled_event = self.manager.get_operation(op_id)
        self.assertEqual(cancelled_event.status, self.OperationStatus.CANCELLED)

    def test_cancel_non_cancellable_operation(self):
        event = self._create_event(can_cancel=False)
        op_id = self.manager.add_operation(event)

        result = self.manager.cancel_operation(op_id)

        self.assertFalse(result)
        pending_event = self.manager.get_operation(op_id)
        self.assertEqual(pending_event.status, self.OperationStatus.PENDING)

    def test_cancel_terminal_operation_returns_false(self):
        event = self._create_event(can_cancel=True)
        op_id = self.manager.add_operation(event)
        self.manager.complete_operation(op_id)

        result = self.manager.cancel_operation(op_id)

        self.assertFalse(result)

    def test_get_device_operations(self):
        event1 = self._create_event(serial="device1")
        event2 = self._create_event(serial="device1")
        event3 = self._create_event(serial="device2")

        self.manager.add_operation(event1)
        self.manager.add_operation(event2)
        self.manager.add_operation(event3)

        device1_ops = self.manager.get_device_operations("device1")
        self.assertEqual(len(device1_ops), 2)

        device2_ops = self.manager.get_device_operations("device2")
        self.assertEqual(len(device2_ops), 1)

    def test_get_active_operations(self):
        event1 = self._create_event()
        event2 = self._create_event()

        self.manager.add_operation(event1)
        op_id2 = self.manager.add_operation(event2)
        self.manager.complete_operation(op_id2)

        active = self.manager.get_active_operations()
        self.assertEqual(len(active), 1)

    def test_get_device_active_operation(self):
        event1 = self._create_event(serial="device1")
        event2 = self._create_event(serial="device1")

        self.manager.add_operation(event1)
        self.manager.add_operation(event2)

        active = self.manager.get_device_active_operation("device1")
        self.assertIsNotNone(active)
        self.assertEqual(active.operation_id, event2.operation_id)

    def test_has_active_operations(self):
        self.assertFalse(self.manager.has_active_operations())

        event = self._create_event()
        op_id = self.manager.add_operation(event)

        self.assertTrue(self.manager.has_active_operations())
        self.assertTrue(self.manager.has_active_operations("device1"))
        self.assertFalse(self.manager.has_active_operations("other_device"))

        self.manager.complete_operation(op_id)
        self.assertFalse(self.manager.has_active_operations())

    def test_remove_operation(self):
        removed_signal = MagicMock()
        self.manager.operation_removed.connect(removed_signal)

        event = self._create_event()
        op_id = self.manager.add_operation(event)

        self.manager.remove_operation(op_id)

        self.assertIsNone(self.manager.get_operation(op_id))
        removed_signal.assert_called_once_with(op_id)

    def test_clear_completed(self):
        event1 = self._create_event(serial="device1")
        event2 = self._create_event(serial="device1")
        event3 = self._create_event(serial="device2")

        self.manager.add_operation(event1)
        op_id2 = self.manager.add_operation(event2)
        op_id3 = self.manager.add_operation(event3)

        self.manager.complete_operation(op_id2)
        self.manager.complete_operation(op_id3)

        # Clear only device1's completed
        removed = self.manager.clear_completed("device1")
        self.assertEqual(removed, 1)
        self.assertIsNotNone(self.manager.get_operation(event1.operation_id))
        self.assertIsNone(self.manager.get_operation(op_id2))
        self.assertIsNotNone(self.manager.get_operation(op_id3))

    def test_update_unknown_operation_returns_none(self):
        result = self.manager.update_operation("nonexistent_id")
        self.assertIsNone(result)


class TestStyleManagerOperationStyles(unittest.TestCase):
    """Tests for operation status styles in StyleManager."""

    def test_success_background_color_exists(self):
        from ui.style_manager import _THEME_PRESETS

        light = _THEME_PRESETS["light"]
        dark = _THEME_PRESETS["dark"]

        self.assertIn("success_background", light)
        self.assertIn("success_background", dark)
        self.assertIn("rgba", light["success_background"])
        self.assertIn("rgba", dark["success_background"])

    def test_error_background_color_exists(self):
        from ui.style_manager import _THEME_PRESETS

        light = _THEME_PRESETS["light"]
        dark = _THEME_PRESETS["dark"]

        self.assertIn("error_background", light)
        self.assertIn("error_background", dark)
        self.assertIn("rgba", light["error_background"])
        self.assertIn("rgba", dark["error_background"])

    def test_operation_status_panel_style_renders(self):
        from ui.style_manager import StyleManager

        style = StyleManager.get_operation_status_panel_style()
        self.assertIsInstance(style, str)
        self.assertIn("operation_status_panel", style)

    def test_operation_status_inline_style_renders(self):
        from ui.style_manager import StyleManager

        style = StyleManager.get_operation_status_inline_style()
        self.assertIsInstance(style, str)
        self.assertIn("device_operation", style)


if __name__ == "__main__":
    unittest.main(verbosity=2)
