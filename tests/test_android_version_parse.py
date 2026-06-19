"""Regression tests for Android version parsing (audit finding #34)."""

import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils import adb_tools


class AndroidVersionParseTests(unittest.TestCase):
    def _version(self, raw):
        with patch('utils.adb_tools.common.run_command', return_value=[raw]):
            return adb_tools.get_android_version('S')

    def test_integer_release_preserved(self):
        self.assertEqual(self._version('13'), '13')

    def test_dotted_release_no_longer_zero(self):
        # Previously '13.0' / '4.4.2' became 0 -> "Android 0".
        self.assertEqual(self._version('13.0'), '13.0')
        self.assertEqual(self._version('4.4.2'), '4.4.2')

    def test_codename_release_preserved(self):
        self.assertEqual(self._version('UpsideDownCake'), 'UpsideDownCake')

    def test_unavailable_returns_unknown(self):
        with patch('utils.adb_tools.common.run_command', return_value=[]):
            self.assertEqual(adb_tools.get_android_version('S'), 'Unknown')


if __name__ == '__main__':
    unittest.main()
