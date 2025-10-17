#!/usr/bin/env python3
"""
Bug Report 操作按鈕進度狀態測試：
- total <= 0 時應進入 busy 狀態
- total > 0 時應更新為具體進度
"""

import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class BugReportProgressDialogBusyTest(unittest.TestCase):
    def setUp(self):
        from ui.file_operations_manager import FileOperationsManager
        self.window = object()  # minimal stub; dialog is replaced
        self.manager = FileOperationsManager(self.window)

    def test_switch_to_busy_when_total_unknown(self):
        with patch('ui.file_operations_manager.QTimer.singleShot', lambda _ms, fn: fn()):
            self.manager._update_bug_report_progress('Preparing...', current=0, total=0)

        state = self.manager._bug_report_progress_state
        self.assertEqual(state.mode, 'busy')
        self.assertEqual(state.current, 0)
        self.assertEqual(state.total, 0)
        self.assertEqual(state.message, 'Preparing...')

    def test_switch_to_determinate_when_total_known(self):
        with patch('ui.file_operations_manager.QTimer.singleShot', lambda _ms, fn: fn()):
            self.manager._update_bug_report_progress('Generating...', current=3, total=7)

        state = self.manager._bug_report_progress_state
        self.assertEqual(state.mode, 'progress')
        self.assertEqual(state.current, 3)
        self.assertEqual(state.total, 7)
        self.assertEqual(state.message, 'Generating...')


if __name__ == '__main__':
    unittest.main()
