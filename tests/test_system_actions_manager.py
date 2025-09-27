import os
import sys
import unittest
from unittest.mock import call

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class DummyWindow:
    def __init__(self):
        self.info_messages = []
        self.error_messages = []

    def show_info(self, title, message):
        self.info_messages.append((title, message))

    def show_error(self, title, message):
        self.error_messages.append((title, message))


class ClipboardDouble:
    def __init__(self):
        self.text = None

    def setText(self, text):
        self.text = text


class SystemActionsManagerTest(unittest.TestCase):
    def setUp(self):
        from ui.system_actions_manager import SystemActionsManager

        self.window = DummyWindow()
        self.clipboard = ClipboardDouble()
        self.subprocess_calls = []

        def fake_run(cmd, check=False):
            self.subprocess_calls.append(cmd)
            if cmd[0] == 'raise':
                raise RuntimeError('boom')

        self.manager = SystemActionsManager(
            window=self.window,
            clipboard_provider=lambda: self.clipboard,
            subprocess_runner=fake_run,
            platform_resolver=lambda: 'Linux',
        )

    def test_copy_to_clipboard_success(self):
        self.manager.copy_to_clipboard('/tmp/path')
        self.assertEqual(self.clipboard.text, '/tmp/path')
        self.assertEqual(len(self.window.info_messages), 1)
        self.assertFalse(self.window.error_messages)

    def test_copy_to_clipboard_failure(self):
        failing_manager = self.manager.__class__(
            window=self.window,
            clipboard_provider=lambda: (_ for _ in ()).throw(RuntimeError('fail')),
        )
        failing_manager.copy_to_clipboard('/tmp/other')
        self.assertEqual(len(self.window.error_messages), 1)

    def test_open_folder_linux(self):
        self.manager.open_folder('/tmp/folder')
        self.assertIn(['xdg-open', '/tmp/folder'], self.subprocess_calls)

    def test_open_folder_failure_reports(self):
        failing_manager = self.manager.__class__(
            window=self.window,
            subprocess_runner=lambda cmd, check=False: (_ for _ in ()).throw(RuntimeError('boom')),
            platform_resolver=lambda: 'Linux',
        )
        failing_manager.open_folder('/tmp/folder')
        self.assertEqual(len(self.window.error_messages), 1)


if __name__ == '__main__':
    unittest.main()
