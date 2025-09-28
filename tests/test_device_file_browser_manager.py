#!/usr/bin/env python3
"""Tests for device file browser manager and supporting adb tools helpers."""

import os
import sys
import tempfile
import unittest
from unittest.mock import patch

from PyQt6.QtCore import QCoreApplication

# Ensure a Qt application instance exists for signal delivery
if QCoreApplication.instance() is None:  # pragma: no cover - guard
    QCoreApplication([])

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils import adb_models, adb_tools
from ui.device_file_browser_manager import DeviceFileBrowserManager


class DeviceFileBrowserManagerTests(unittest.TestCase):
    """Verify manager emits signals and delegates to adb tools."""

    def setUp(self):
        self.manager = DeviceFileBrowserManager()
        self.listings = []
        self.downloads = []
        self.errors = []

        self.manager.directory_listing_ready.connect(self._record_listing)
        self.manager.download_completed.connect(self._record_download)
        self.manager.operation_failed.connect(self.errors.append)

    def _record_listing(self, serial, path, listing):
        self.listings.append((serial, path, listing))

    def _record_download(self, serial, output_path, remote_paths, results):
        self.downloads.append((serial, output_path, remote_paths, results))

    def test_fetch_directory_emits_listing(self):
        """Fetching a directory should emit the parsed listing when successful."""
        entries = [
            adb_models.DeviceFileEntry(name='Download', path='/sdcard/Download', is_dir=True),
            adb_models.DeviceFileEntry(name='file.txt', path='/sdcard/file.txt', is_dir=False),
        ]
        listing = adb_models.DeviceDirectoryListing(serial='ABC123', path='/sdcard', entries=entries)

        with patch('utils.adb_tools.list_device_directory', return_value=listing) as mock_list:
            self.manager.fetch_directory('ABC123', '/sdcard', use_thread=False)

        mock_list.assert_called_once_with('ABC123', '/sdcard')
        self.assertEqual(len(self.listings), 1)
        serial, path, received_listing = self.listings[0]
        self.assertEqual(serial, 'ABC123')
        self.assertEqual(path, '/sdcard')
        self.assertEqual(received_listing.entries, entries)
        self.assertFalse(self.errors)

    def test_fetch_directory_failure_emits_error(self):
        """Errors during fetch should emit operation_failed."""
        with patch('utils.adb_tools.list_device_directory', side_effect=RuntimeError('boom')):
            self.manager.fetch_directory('XYZ', '/does/not/exist', use_thread=False)

        self.assertEqual(len(self.errors), 1)
        self.assertIn('boom', self.errors[0])

    def test_download_paths_emits_completion(self):
        """Downloading selected entries should delegate to adb_tools and emit results."""
        with patch('utils.adb_tools.pull_device_paths', return_value=['ok']) as mock_pull:
            self.manager.download_paths('ABC123', ['/sdcard/file.txt'], '/tmp/output', use_thread=False)

        mock_pull.assert_called_once_with('ABC123', ['/sdcard/file.txt'], '/tmp/output')
        self.assertEqual(len(self.downloads), 1)
        serial, output_path, remote_paths, results = self.downloads[0]
        self.assertEqual(serial, 'ABC123')
        self.assertEqual(output_path, '/tmp/output')
        self.assertEqual(remote_paths, ['/sdcard/file.txt'])
        self.assertEqual(results, ['ok'])


class AdbToolsDeviceFileTests(unittest.TestCase):
    """Ensure adb_tools helpers for device file browsing behave as expected."""

    def setUp(self):
        # Redirect HOME so logger writes to workspace-safe location
        self.test_home = tempfile.mkdtemp(prefix='lazy_blacktea_test_home_')
        os.environ['HOME'] = self.test_home

    def tearDown(self):
        try:
            for root, _, files in os.walk(self.test_home, topdown=False):
                for name in files:
                    try:
                        os.remove(os.path.join(root, name))
                    except FileNotFoundError:
                        pass
                try:
                    os.rmdir(root)
                except OSError:
                    pass
        except Exception:
            pass

    def test_list_device_directory_parses_entries(self):
        """list_device_directory should parse ls output into entries."""
        with patch('utils.adb_commands.cmd_list_device_directory', return_value='adb ls cmd') as mock_cmd, \
             patch('utils.common.run_command', return_value=['Download/', 'file.txt', 'script.sh']):
            listing = adb_tools.list_device_directory('SER123', '/sdcard')

        mock_cmd.assert_called_once_with('SER123', '/sdcard')
        names = [entry.name for entry in listing.entries]
        self.assertIn('Download', names)
        self.assertIn('file.txt', names)
        download_entry = next(entry for entry in listing.entries if entry.name == 'Download')
        file_entry = next(entry for entry in listing.entries if entry.name == 'file.txt')
        self.assertTrue(download_entry.is_dir)
        self.assertFalse(file_entry.is_dir)
        self.assertEqual(download_entry.path, '/sdcard/Download')
        self.assertEqual(file_entry.path, '/sdcard/file.txt')

    def test_pull_device_paths_builds_commands(self):
        """pull_device_paths should build adb pull commands per selection."""
        with patch('utils.common.make_gen_dir_path', side_effect=lambda p: p), \
             patch('utils.common.make_full_path', side_effect=lambda root, name: f"{root}/{name}"), \
             patch('utils.adb_commands.cmd_pull_device_file', side_effect=lambda serial, remote, local: f'pull {serial} {remote} {local}') as mock_cmd, \
             patch('utils.adb_tools._execute_commands_parallel_native', return_value=[['ok-a'], ['ok-b']]) as mock_native:
            results = adb_tools.pull_device_paths('SER123', ['/a/b', '/c/d'], '/tmp/out')

        self.assertEqual(results, ['ok-a', 'ok-b'])
        mock_cmd.assert_any_call('SER123', '/a/b', '/tmp/out/device_SER123')
        mock_cmd.assert_any_call('SER123', '/c/d', '/tmp/out/device_SER123')
        mock_native.assert_called_once()


if __name__ == '__main__':
    unittest.main()
