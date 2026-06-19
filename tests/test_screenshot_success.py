"""Regression tests for screenshot success detection (audit finding #4).

Previously screenshots were always reported as "saved" regardless of whether
``adb screencap``/``pull`` actually succeeded. ``_capture_screenshot_for_device``
now returns whether the PNG was really pulled, and ``start_to_screen_shot``
returns a ``serial -> success`` map.
"""

import os
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils import adb_tools


class ScreenshotSuccessTests(unittest.TestCase):
    def test_capture_returns_true_when_png_pulled(self):
        with tempfile.TemporaryDirectory() as out_dir:
            serial, fname = 'SER1', 'cap'
            expected = os.path.join(out_dir, f'{serial}_screenshot_{fname}.png')

            def fake_run(cmd, *args, **kwargs):
                if 'pull' in cmd:
                    with open(expected, 'wb') as handle:
                        handle.write(b'\x89PNG-fake-bytes')
                return ['ok']

            with patch('utils.adb_tools.common.run_command', side_effect=fake_run):
                self.assertTrue(
                    adb_tools._capture_screenshot_for_device(serial, fname, out_dir)
                )

    def test_capture_returns_false_when_png_missing(self):
        with tempfile.TemporaryDirectory() as out_dir:
            with patch('utils.adb_tools.common.run_command', return_value=['error: device offline']):
                self.assertFalse(
                    adb_tools._capture_screenshot_for_device('SER2', 'cap', out_dir)
                )

    def test_capture_returns_false_when_png_empty(self):
        with tempfile.TemporaryDirectory() as out_dir:
            serial, fname = 'SER3', 'cap'
            expected = os.path.join(out_dir, f'{serial}_screenshot_{fname}.png')

            def fake_run(cmd, *args, **kwargs):
                if 'pull' in cmd:
                    open(expected, 'wb').close()  # zero-byte file
                return ['ok']

            with patch('utils.adb_tools.common.run_command', side_effect=fake_run):
                self.assertFalse(
                    adb_tools._capture_screenshot_for_device(serial, fname, out_dir)
                )

    def test_start_to_screen_shot_returns_per_device_success_map(self):
        def fake_capture(serial, file_name, output_path):
            return serial == 'SER1'

        with tempfile.TemporaryDirectory() as out_dir, patch(
            'utils.adb.screenshot._capture_screenshot_for_device', side_effect=fake_capture
        ):
            results = adb_tools.start_to_screen_shot(['SER1', 'SER2'], 'cap', out_dir)

        self.assertEqual(results, {'SER1': True, 'SER2': False})

    def test_start_to_screen_shot_empty_devices_returns_empty_map(self):
        self.assertEqual(adb_tools.start_to_screen_shot([], 'cap', '/tmp'), {})


if __name__ == '__main__':
    unittest.main()
