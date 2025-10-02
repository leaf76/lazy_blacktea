"""Ensure UI Inspector prerequisites guard all DeviceOperationsManager entry points."""

import os
import unittest
from unittest.mock import patch

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PyQt6.QtWidgets import QApplication

from ui.device_operations_manager import DeviceOperationsManager


class UIInspectorPrerequisiteEnforcementTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.manager = DeviceOperationsManager(parent_window=None)
        # silence UI interactions during tests
        self.manager._show_info = lambda *args, **kwargs: None
        self.manager._show_warning = lambda *args, **kwargs: None
        self.manager._log_console = lambda *args, **kwargs: None
        if hasattr(self.manager, 'recording_timer'):
            self.manager.recording_timer.stop()

    def tearDown(self):
        if hasattr(self.manager, 'recording_timer'):
            self.manager.recording_timer.stop()

    def test_launch_ui_inspector_blocks_when_prerequisites_fail(self):
        errors: list[tuple[str, str]] = []
        self.manager._show_error = lambda title, message: errors.append((title, message))

        with patch('ui.device_operations_manager.check_ui_inspector_prerequisites', return_value=(False, 'issue'), create=True), \
             patch('ui.device_operations_manager.UIInspectorDialog'):
            result = self.manager.launch_ui_inspector(['serial-1'])

        self.assertFalse(result)
        self.assertEqual(errors, [('UI Inspector Unavailable', 'issue')])

    def test_launch_ui_inspector_for_device_blocks_when_prerequisites_fail(self):
        errors: list[tuple[str, str]] = []
        self.manager._show_error = lambda title, message: errors.append((title, message))

        with patch('ui.device_operations_manager.check_ui_inspector_prerequisites', return_value=(False, 'issue'), create=True), \
             patch('ui.device_operations_manager.UIInspectorDialog'):
            result = self.manager.launch_ui_inspector_for_device('serial-2')

        self.assertFalse(result)
        self.assertEqual(errors, [('UI Inspector Unavailable', 'issue')])


if __name__ == '__main__':
    unittest.main()
