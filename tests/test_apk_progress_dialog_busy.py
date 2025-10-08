#!/usr/bin/env python3
"""
APK 安裝進度對話框 - 無限循環/可量測模式切換測試

此測試以 stub 取代 QProgressDialog 與 QTimer，驗證：
- 當 total <= 0 時，對話框切換為無限循環（setRange(0, 0)）
- 當 total > 0 時，對話框切換為可量測進度並設定值
"""

import os
import sys
import unittest
from unittest.mock import patch, Mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class DummyProgressDialog:
    def __init__(self, *_args, **_kwargs):
        self.min = None
        self.max = None
        self.value = None
        self.label_text = ''
        self.closed = False

    # QProgressDialog API subset
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

    def show(self):
        pass

    def close(self):
        self.closed = True


class ApkProgressDialogBusyTest(unittest.TestCase):
    def setUp(self):
        from ui.app_management_manager import ApkInstallationManager

        self.parent = Mock()
        self.manager = ApkInstallationManager(self.parent)
        # 直接將 progress_dialog 指向替身，避免真正的 Qt 依賴
        self.manager.progress_dialog = DummyProgressDialog()

    def test_switch_to_busy_when_total_unknown(self):
        # 模擬 QTimer.singleShot 立刻執行 callback
        with patch('ui.app_management_manager.QTimer.singleShot', lambda _ms, fn: fn()):
            self.manager._update_progress('Preparing...', current=0, total=0)

        self.assertEqual(self.manager.progress_dialog.min, 0)
        self.assertEqual(self.manager.progress_dialog.max, 0)
        self.assertEqual(self.manager.progress_dialog.value, 0)
        self.assertEqual(self.manager.progress_dialog.label_text, 'Preparing...')

    def test_switch_to_determinate_when_total_known(self):
        with patch('ui.app_management_manager.QTimer.singleShot', lambda _ms, fn: fn()):
            self.manager._update_progress('Installing...', current=2, total=5)

        self.assertEqual(self.manager.progress_dialog.min, 0)
        self.assertEqual(self.manager.progress_dialog.max, 5)
        self.assertEqual(self.manager.progress_dialog.value, 2)
        self.assertEqual(self.manager.progress_dialog.label_text, 'Installing...')


if __name__ == '__main__':
    unittest.main()

