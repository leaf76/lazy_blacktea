import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class FileDialogManagerTest(unittest.TestCase):
    def setUp(self):
        from ui.file_dialog_manager import FileDialogManager

        self.calls = []

        def fake_dialog(parent, title):
            self.calls.append((parent, title))
            return '/tmp/selected'

        self.manager = FileDialogManager(dialog_fn=fake_dialog)
        self.parent = object()

    def test_select_directory_returns_value(self):
        result = self.manager.select_directory(self.parent, 'Pick Folder')
        self.assertEqual(result, '/tmp/selected')
        self.assertEqual(self.calls, [(self.parent, 'Pick Folder')])

    def test_select_directory_none_when_cancelled(self):
        cancel_manager = self.manager.__class__(dialog_fn=lambda parent, title: '')
        result = cancel_manager.select_directory(self.parent, 'Pick Folder')
        self.assertIsNone(result)


if __name__ == '__main__':
    unittest.main()
