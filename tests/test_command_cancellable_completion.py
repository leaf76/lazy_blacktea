import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt6.QtWidgets import QApplication
from ui.command_execution_manager import CommandExecutionManager


class DummyWindow:
    def __init__(self):
        self.info_calls = []

    def show_info(self, title: str, message: str):
        self.info_calls.append((title, message))


class CommandCancellableCompletionDialogTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_single_command_completion_dialog(self):
        parent = DummyWindow()
        manager = CommandExecutionManager(parent)

        cmd = 'getprop ro.build.version.release'
        serials = ['ABC123']
        payload = {'results': [['14']]}

        manager._on_cancellable_command_completed(cmd, serials, payload)
        # Pump event loop to process singleShot
        self.app.processEvents()
        self.app.processEvents()

        self.assertTrue(parent.info_calls)
        title, message = parent.info_calls[-1]
        self.assertIn('Command Completed', title)
        self.assertIn(cmd, message)
        self.assertIn('1 device(s)', message)

    def test_batch_command_completion_dialogs(self):
        parent = DummyWindow()
        manager = CommandExecutionManager(parent)

        cmds = ['getprop ro.product.model', 'dumpsys battery']
        serials = ['X1', 'Y2']

        # Prepare a batch state similar to execute_batch_commands
        from utils import common as _common
        batch_id = _common.generate_trace_id()
        manager._batch_states[batch_id] = {
            'expected': len(cmds),
            'done': 0,
            'failed': 0,
            'serials': serials,
        }

        # Simulate two command completions as part of the same batch
        for c in cmds:
            manager._on_cancellable_command_completed(c, serials, {'results': [['ok'], ['ok']]}, is_batch=True, batch_id=batch_id)

        self.app.processEvents()
        self.app.processEvents()

        # Expect a single aggregated info dialog for the batch
        self.assertGreaterEqual(len(parent.info_calls), 1)
        title, message = parent.info_calls[-1]
        self.assertIn('Batch Commands Completed', title)
        self.assertIn('2 command(s)', message)
        # Should include preview of commands
        self.assertIn('Commands:', message)
        self.assertIn('• getprop ro.product.model', message)

    def test_batch_failure_summary(self):
        parent = DummyWindow()
        manager = CommandExecutionManager(parent)

        cmds = ['badcmd', 'goodcmd']
        serials = ['S1']

        from utils import common as _common
        batch_id = _common.generate_trace_id()
        manager._batch_states[batch_id] = {
            'expected': len(cmds),
            'done': 0,
            'failed': 0,
            'serials': serials,
            'commands': list(cmds),
            'completed_commands': [],
            'failed_commands': [],
        }

        # Simulate one failure and one success
        class E(Exception):
            pass

        manager._on_batch_command_failed('badcmd', serials, E('oops failed'), batch_id=batch_id)
        manager._on_cancellable_command_completed('goodcmd', serials, {'results': [['ok']]}, is_batch=True, batch_id=batch_id)

        self.app.processEvents(); self.app.processEvents()

        title, message = parent.info_calls[-1]
        self.assertIn('Batch Commands Completed', title)
        self.assertIn('Failures:', message)
        self.assertIn('badcmd', message)


if __name__ == '__main__':
    unittest.main()
