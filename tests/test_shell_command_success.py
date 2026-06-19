"""Regression tests for shell command per-device success (audit finding #6).

Previously a shell command was reported as "Completed" on every device as long
as the adb process produced any output, hiding per-device failures. The task now
captures per-device exit codes and the renderers/dialogs reflect failures.
"""

import os
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt6.QtWidgets import QApplication

from ui.command_execution_manager import CommandExecutionManager
from ui.main_window import WindowMain


class _FakeProc:
    def __init__(self, stdout=b'', stderr=b'', returncode=0):
        self._stdout = stdout
        self._stderr = stderr
        self.returncode = returncode

    def communicate(self, timeout=None):
        return self._stdout, self._stderr

    def poll(self):
        return self.returncode


class _DummyWindow:
    def __init__(self):
        self.info_calls = []

    def show_info(self, title, message):
        self.info_calls.append((title, message))


class ShellCommandSuccessTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_task_captures_per_device_returncodes(self):
        manager = CommandExecutionManager(_DummyWindow())
        procs = {
            'S1': _FakeProc(b'ok\n', b'', 0),
            'S2': _FakeProc(b'', b'error: failed\n', 1),
        }
        with patch(
            'utils.adb_tools.run_cancellable_adb_shell_command', return_value=procs
        ):
            payload = manager._run_cancellable_command_task(['S1', 'S2'], command='cmd')

        self.assertEqual(payload['returncodes'], [0, 1])
        self.assertFalse(payload['success'])

    def test_task_success_when_all_zero(self):
        manager = CommandExecutionManager(_DummyWindow())
        procs = {'S1': _FakeProc(b'ok\n', b'', 0)}
        with patch(
            'utils.adb_tools.run_cancellable_adb_shell_command', return_value=procs
        ):
            payload = manager._run_cancellable_command_task(['S1'], command='cmd')

        self.assertEqual(payload['returncodes'], [0])
        self.assertTrue(payload['success'])

    def test_completion_message_reports_failures(self):
        manager = CommandExecutionManager(_DummyWindow())
        msg = manager._completion_message('cmd', ['S1', 'S2'], [0, 1])
        self.assertIn('failed on 1', msg)

    def test_completion_message_legacy_without_returncodes(self):
        manager = CommandExecutionManager(_DummyWindow())
        msg = manager._completion_message('cmd', ['S1', 'S2'], None)
        self.assertIn('2 device(s)', msg)
        self.assertNotIn('failed', msg)

    def test_log_command_results_marks_failed_devices(self):
        lines = []
        stub = SimpleNamespace(write_to_console=lines.append, device_dict={})
        WindowMain.log_command_results(
            stub, 'cmd', ['S1', 'S2'], [['ok'], ['error']], [0, 1]
        )
        joined = '\n'.join(lines)
        self.assertIn('✅ [S1] Completed', joined)
        self.assertIn('❌ [S2] Failed (exit 1)', joined)

    def test_log_command_results_failed_to_start(self):
        lines = []
        stub = SimpleNamespace(write_to_console=lines.append, device_dict={})
        WindowMain.log_command_results(
            stub, 'cmd', ['S1'], [['Failed to start adb process']], [None]
        )
        self.assertIn('❌ [S1] Failed to start', '\n'.join(lines))

    def test_log_command_results_legacy_output_based(self):
        lines = []
        stub = SimpleNamespace(write_to_console=lines.append, device_dict={})
        # No returncodes -> classify by output presence (legacy behavior).
        WindowMain.log_command_results(stub, 'cmd', ['S1'], [['ok']])
        self.assertIn('✅ [S1] Completed', '\n'.join(lines))


if __name__ == '__main__':
    unittest.main()
