import os
import sys
import unittest

from PyQt6.QtWidgets import QApplication, QMainWindow

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ui.dialog_manager import DialogManager


class DialogManagerClipboardTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.window = QMainWindow()
        self.manager = DialogManager(self.window)
        self.clipboard = QApplication.clipboard()
        self.clipboard.clear()

    def tearDown(self):
        self.window.deleteLater()

    def test_copy_to_clipboard_sets_text(self):
        sample = "adb shell ls /sdcard"
        self.manager.copy_to_clipboard(sample)
        self.assertEqual(self.clipboard.text(), sample)


if __name__ == '__main__':
    unittest.main()
