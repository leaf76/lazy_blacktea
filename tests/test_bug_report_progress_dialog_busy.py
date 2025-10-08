#!/usr/bin/env python3
"""
Bug Report 進度對話框 - 無限循環/可量測模式切換測試

以 stub 取代 QProgressDialog 與 QTimer，驗證 FileOperationsManager：
- 當 total <= 0 時，切換為無限循環（setRange(0, 0)）
- 當 total > 0 時，切換為可量測進度並設定值
"""

import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class DummyProgressDialog:
    def __init__(self, *_args, **_kwargs):
        self.min = None
        self.max = None
        self.value = None
        self.label_text = ''
        self.closed = False

    def setRange(self, minimum, maximum):
        self.min = minimum
        self.max = maximum

    def setLabelText(self, text):
        self.label_text = text

    def setValue(self, value):
        self.value = value

    def setWindowTitle(self, *_):
        pass

    def setWindowModality(self, *_):
        pass

    def setMinimumDuration(self, *_):
        pass

    def setAutoClose(self, *_):
        pass

    def setAutoReset(self, *_):
        pass

    def setStyleSheet(self, *_):
        pass

    def show(self):
        pass

    def close(self):
        self.closed = True


class BugReportProgressDialogBusyTest(unittest.TestCase):
    def setUp(self):
        from ui.file_operations_manager import FileOperationsManager
        self.window = object()  # minimal stub; dialog is replaced
        self.manager = FileOperationsManager(self.window)
        self.manager.progress_dialog = DummyProgressDialog()

    def test_switch_to_busy_when_total_unknown(self):
        with patch('ui.file_operations_manager.QTimer.singleShot', lambda _ms, fn: fn()):
            self.manager._update_bug_report_progress('Preparing...', current=0, total=0)

        self.assertEqual(self.manager.progress_dialog.min, 0)
        self.assertEqual(self.manager.progress_dialog.max, 0)
        self.assertEqual(self.manager.progress_dialog.value, 0)
        self.assertEqual(self.manager.progress_dialog.label_text, 'Preparing...')

    def test_switch_to_determinate_when_total_known(self):
        with patch('ui.file_operations_manager.QTimer.singleShot', lambda _ms, fn: fn()):
            self.manager._update_bug_report_progress('Generating...', current=3, total=7)

        self.assertEqual(self.manager.progress_dialog.min, 0)
        self.assertEqual(self.manager.progress_dialog.max, 7)
        self.assertEqual(self.manager.progress_dialog.value, 3)
        self.assertEqual(self.manager.progress_dialog.label_text, 'Generating...')


if __name__ == '__main__':
    unittest.main()

