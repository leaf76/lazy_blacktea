"""Tests for operation logging coverage and console output behaviour."""

import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from lazy_blacktea_pyqt import WindowMain


class OperationLoggingTests(unittest.TestCase):
    def _create_partial_window(self) -> WindowMain:
        window = WindowMain.__new__(WindowMain)  # Avoid heavy __init__
        window.logging_manager = Mock()
        window.device_list_controller = Mock()
        window.write_to_console = Mock()
        window.device_dict = {}
        return window

    def test_select_all_devices_logs_start_and_complete(self):
        window = self._create_partial_window()

        window.select_all_devices()

        window.logging_manager.log_operation_start.assert_called_with('Select All Devices')
        window.logging_manager.log_operation_complete.assert_called_with('Select All Devices')
        window.device_list_controller.select_all_devices.assert_called_once()

    def test_select_all_devices_logs_failure(self):
        window = self._create_partial_window()
        window.device_list_controller.select_all_devices.side_effect = RuntimeError('boom')

        with self.assertRaises(RuntimeError):
            window.select_all_devices()

        window.logging_manager.log_operation_start.assert_called_with('Select All Devices')
        window.logging_manager.log_operation_failure.assert_called_with('Select All Devices', 'boom')
        window.logging_manager.log_operation_complete.assert_not_called()

    def test_log_command_results_outputs_all_lines_without_truncation(self):
        window = self._create_partial_window()
        lines = [f'line-{idx}' for idx in range(15)]
        serial = 'SER123456789'
        window.device_dict[serial] = SimpleNamespace(device_model='Pixel Test')

        with self.assertLogs('lazy_blacktea', level='INFO') as captured:
            window.log_command_results('pm list packages', [serial], [lines])

        log_output = '\n'.join(captured.output)
        for line in lines:
            self.assertIn(line, log_output)
        self.assertNotIn('more lines', log_output)


if __name__ == '__main__':
    unittest.main()
