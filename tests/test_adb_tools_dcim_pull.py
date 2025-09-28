#!/usr/bin/env python3
"""Tests for device DCIM pulling helpers."""

import os
import sys
import tempfile
import unittest
from unittest.mock import patch

# Redirect HOME so logger writes inside workspace-friendly location before imports
TEST_HOME = tempfile.mkdtemp(prefix='lazy_blacktea_test_home_')
os.environ['HOME'] = TEST_HOME

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils import adb_tools


class PullDeviceDcimFoldersWithDeviceFolderTest(unittest.TestCase):
    """Ensure the refactored DCIM helper delegates to the legacy implementation."""

    def test_delegates_to_existing_pull_logic(self):
        serials = ['device-1', 'device-2']
        output_path = '/tmp/dcim-output'
        expected = ['ok-device-1', 'ok-device-2']

        with patch('utils.adb_tools.pull_device_dcim', return_value=expected) as mock_pull:
            result = adb_tools.pull_device_dcim_folders_with_device_folder(serials, output_path)

        mock_pull.assert_called_once_with(serials, output_path)
        self.assertEqual(result, expected)


if __name__ == '__main__':
    unittest.main()
