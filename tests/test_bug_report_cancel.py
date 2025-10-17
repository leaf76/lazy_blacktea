#!/usr/bin/env python3
"""
Bug Report 取消按鈕行為測試：
- 點擊取消後，應設置取消事件、呼叫 TaskHandle.cancel()、並將進度對話框切換為 Busy 並顯示取消中文案。
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class DummyHandle:
    def __init__(self):
        self.cancel_called = False

    def cancel(self):
        self.cancel_called = True


class BugReportCancelTest(unittest.TestCase):
    def setUp(self):
        from ui.file_operations_manager import FileOperationsManager
        self.window = object()
        self.manager = FileOperationsManager(self.window)

        self.handle = DummyHandle()
        self.manager._bug_report_handle = self.handle

        import threading
        self.manager._bug_report_cancel_event = threading.Event()

    def test_cancel_sets_event_and_updates_ui(self):
        from unittest.mock import patch
        with patch('ui.file_operations_manager.QTimer.singleShot', lambda _ms, fn: fn()):
            self.manager._cancel_bug_report_generation()

        self.assertTrue(self.manager._bug_report_cancel_event.is_set())
        self.assertTrue(self.handle.cancel_called)
        state = self.manager._bug_report_progress_state
        self.assertEqual(state.mode, 'cancelling')
        self.assertEqual(state.total, 0)
        self.assertEqual(state.current, 0)
        self.assertEqual(state.message, 'Cancelling bug report generation...')


if __name__ == '__main__':
    unittest.main()
