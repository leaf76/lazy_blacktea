import os
import sys
import unittest

# Ensure project root is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ui.command_execution_manager import CommandExecutionManager
from PyQt6.QtWidgets import QApplication


class DummyWindow:
    def __init__(self):
        self.info_calls = []

    def show_info(self, title: str, message: str):
        # Record info dialog invocations for assertions
        self.info_calls.append((title, message))


class ShellCommandCompletionDialogTest(unittest.TestCase):
    def test_completion_triggers_info_dialog(self):
        app = QApplication.instance() or QApplication([])
        parent = DummyWindow()
        manager = CommandExecutionManager(parent)

        command = 'pm list packages'
        serials = ['SERIAL1234', 'SERIAL5678']
        payload = {'results': [['ok'], ['ok']]}

        # Directly invoke completion handler to simulate finished task
        manager._on_shell_command_completed(command, serials, payload)

        # Allow Qt to process the singleShot callback
        app.processEvents()
        app.processEvents()

        self.assertTrue(parent.info_calls, 'Completion should trigger an info dialog')
        title, message = parent.info_calls[-1]
        self.assertIn('Shell Command Completed', title)
        self.assertIn('pm list packages', message)
        self.assertIn('2 device(s)', message)


if __name__ == '__main__':
    unittest.main()
