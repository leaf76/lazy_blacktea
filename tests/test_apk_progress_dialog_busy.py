#!/usr/bin/env python3
"""
APK 安裝按鈕進度狀態測試：
- total <= 0 時應進入 busy 狀態
- total > 0 時應更新為具體進度
"""

import os
import sys
import unittest
from unittest.mock import patch, Mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class ApkProgressDialogBusyTest(unittest.TestCase):
    def setUp(self):
        from ui.app_management_manager import ApkInstallationManager

        self.parent = Mock()
        self.manager = ApkInstallationManager(self.parent)

    def test_switch_to_busy_when_total_unknown(self):
        # 模擬 QTimer.singleShot 立刻執行 callback
        with patch('ui.app_management_manager.QTimer.singleShot', lambda _ms, fn: fn()):
            self.manager._update_progress('Preparing...', current=0, total=0)

        state = self.manager._installation_progress_state
        self.assertEqual(state.mode, 'busy')
        self.assertEqual(state.current, 0)
        self.assertEqual(state.total, 0)
        self.assertEqual(state.message, 'Preparing...')

    def test_switch_to_determinate_when_total_known(self):
        with patch('ui.app_management_manager.QTimer.singleShot', lambda _ms, fn: fn()):
            self.manager._update_progress('Installing...', current=2, total=5)

        state = self.manager._installation_progress_state
        self.assertEqual(state.mode, 'progress')
        self.assertEqual(state.current, 2)
        self.assertEqual(state.total, 5)
        self.assertEqual(state.message, 'Installing...')


if __name__ == '__main__':
    unittest.main()
