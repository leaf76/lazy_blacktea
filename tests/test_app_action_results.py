"""Regression tests for app-action result honesty (audit finding #18).

``force_stop_app`` and ``open_app_info`` used to always return True regardless of
the adb result. They now reflect the real outcome.
"""

import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils import adb_tools, common


class ForceStopAppTests(unittest.TestCase):
    def test_returns_true_on_exit_zero(self):
        with patch('utils.adb_tools.common.run_command_with_status', return_value=(0, [], [])):
            self.assertTrue(adb_tools.force_stop_app('S', 'com.example'))

    def test_returns_false_on_nonzero_exit(self):
        with patch(
            'utils.adb_tools.common.run_command_with_status',
            return_value=(1, [], ['error: device offline']),
        ):
            self.assertFalse(adb_tools.force_stop_app('S', 'com.example'))


class OpenAppInfoTests(unittest.TestCase):
    def test_returns_true_when_primary_succeeds(self):
        with patch(
            'utils.adb_tools.common.run_command_with_status',
            return_value=(0, ['Starting: Intent { ... }'], []),
        ) as runner:
            self.assertTrue(adb_tools.open_app_info('S', 'com.example'))
        self.assertEqual(runner.call_count, 1)  # legacy not needed

    def test_falls_back_to_legacy_then_succeeds(self):
        side = [
            (0, [], ['Error: Activity not started']),
            (0, ['Starting: Intent'], []),
        ]
        with patch(
            'utils.adb_tools.common.run_command_with_status', side_effect=side
        ) as runner:
            self.assertTrue(adb_tools.open_app_info('S', 'com.example'))
        self.assertEqual(runner.call_count, 2)

    def test_returns_false_when_both_fail(self):
        side = [
            (0, [], ['Error: Activity not started']),
            (255, [], ['unable to resolve Intent']),
        ]
        with patch('utils.adb_tools.common.run_command_with_status', side_effect=side):
            self.assertFalse(adb_tools.open_app_info('S', 'com.example'))


class RunCommandWithStatusTests(unittest.TestCase):
    def test_captures_returncode_and_streams(self):
        rc, out, err = common.run_command_with_status(
            [sys.executable, '-c', "import sys; print('hi'); sys.stderr.write('boom'); sys.exit(3)"]
        )
        self.assertEqual(rc, 3)
        self.assertIn('hi', out)
        self.assertIn('boom', err)

    def test_success_exit_zero(self):
        rc, _out, _err = common.run_command_with_status(
            [sys.executable, '-c', 'pass']
        )
        self.assertEqual(rc, 0)


if __name__ == '__main__':
    unittest.main()
