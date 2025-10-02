#!/usr/bin/env python3
"""Tests for device file browser manager and supporting adb tools helpers."""

import os
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from PyQt6.QtCore import QCoreApplication
from PyQt6.QtCore import Qt, QPoint
from PyQt6.QtWidgets import QTreeWidgetItem

# Ensure a Qt application instance exists for signal delivery
if QCoreApplication.instance() is None:  # pragma: no cover - guard
    QCoreApplication([])

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils import adb_models, adb_tools
from ui.device_file_browser_manager import DeviceFileBrowserManager
from lazy_blacktea_pyqt import (
    WindowMain,
    DEVICE_FILE_IS_DIR_ROLE,
    DEVICE_FILE_PATH_ROLE,
)
from config.constants import PanelText


class DeviceFileBrowserManagerTests(unittest.TestCase):
    """Verify manager emits signals and delegates to adb tools."""

    def setUp(self):
        self.manager = DeviceFileBrowserManager()
        self.listings = []
        self.downloads = []
        self.errors = []
        self.previews = []

        self.manager.directory_listing_ready.connect(self._record_listing)
        self.manager.download_completed.connect(self._record_download)
        self.manager.operation_failed.connect(self.errors.append)
        self.manager.preview_ready.connect(self._record_preview)

    def _record_listing(self, serial, path, listing):
        self.listings.append((serial, path, listing))

    def _record_download(self, serial, output_path, remote_paths, results):
        self.downloads.append((serial, output_path, remote_paths, results))

    def _record_preview(self, serial, remote_path, local_path):
        self.previews.append((serial, remote_path, local_path))

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

    def test_preview_file_emits_preview_ready(self):
        """Previewing a file should pull it to a temp path and emit the preview signal."""
        with patch('utils.adb_tools.pull_device_file_preview', return_value='/tmp/preview/file.txt') as mock_pull:
            self.manager.preview_file('SER123', '/sdcard/file.txt', use_thread=False)

        mock_pull.assert_called_once_with('SER123', '/sdcard/file.txt')
        self.assertEqual(self.previews, [('SER123', '/sdcard/file.txt', '/tmp/preview/file.txt')])
        self.assertFalse(self.errors)

    def test_preview_file_failure_emits_error(self):
        """Errors during preview should emit operation_failed."""
        with patch('utils.adb_tools.pull_device_file_preview', side_effect=RuntimeError('preview failed')):
            self.manager.preview_file('SER123', '/sdcard/file.txt', use_thread=False)

        self.assertEqual(len(self.errors), 1)
        self.assertIn('preview failed', self.errors[0])


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

    def test_pull_device_file_preview_creates_temp_file(self):
        """pull_device_file_preview should fetch a single file into a temp directory."""
        with patch('tempfile.mkdtemp', return_value='/tmp/preview_dir') as mock_mkdtemp, \
             patch('utils.adb_commands.cmd_pull_device_file', return_value='adb pull') as mock_cmd, \
             patch('utils.common.run_command', return_value=['ok']) as mock_run:
            local_path = adb_tools.pull_device_file_preview('SER42', 'sdcard/test.log')

        mock_mkdtemp.assert_called_once()
        mock_cmd.assert_called_once_with('SER42', '/sdcard/test.log', '/tmp/preview_dir/test.log')
        mock_run.assert_called_once_with('adb pull')
        self.assertEqual(local_path, '/tmp/preview_dir/test.log')

    def test_pull_device_file_preview_rejects_directory(self):
        """pull_device_file_preview should raise ValueError when given a directory path."""
        with self.assertRaises(ValueError):
            adb_tools.pull_device_file_preview('SER42', '/sdcard/folder/')


class WindowMainDeviceFileInteractionTests(unittest.TestCase):
    """Validate WindowMain interactions for device file browser."""

    def setUp(self):
        self.window = WindowMain.__new__(WindowMain)
        self.window.refresh_device_file_browser = MagicMock()
        self.window.preview_selected_device_file = MagicMock()
        self.window.device_file_tree = MagicMock()
        self.window.device_file_browser_path_edit = MagicMock()
        self.window.show_warning = MagicMock()
        self.window.show_error = MagicMock()
        self.window._set_device_file_status = MagicMock()
        self.window.device_file_browser_manager = MagicMock()

    def test_double_click_directory_refreshes_listing(self):
        """Double-clicking a directory should navigate into it."""
        item = QTreeWidgetItem(['Download'])
        item.setData(0, DEVICE_FILE_IS_DIR_ROLE, True)
        item.setData(0, DEVICE_FILE_PATH_ROLE, '/sdcard/Download')

        self.window.on_device_file_item_double_clicked(item, 0)

        self.window.refresh_device_file_browser.assert_called_once_with('/sdcard/Download')
        self.window.preview_selected_device_file.assert_not_called()

    def test_double_click_file_triggers_preview(self):
        """Double-clicking a file should trigger preview without toggling selection."""
        item = QTreeWidgetItem(['file.txt'])
        item.setData(0, DEVICE_FILE_IS_DIR_ROLE, False)
        item.setData(0, DEVICE_FILE_PATH_ROLE, '/sdcard/file.txt')
        item.setCheckState(0, Qt.CheckState.Unchecked)

        self.window.on_device_file_item_double_clicked(item, 0)

        self.window.preview_selected_device_file.assert_called_once_with(item)
        self.assertEqual(item.checkState(0), Qt.CheckState.Unchecked)

    def test_copy_device_file_path_sets_clipboard(self):
        """Copying device file path should place path on clipboard."""
        clipboard = MagicMock()
        with patch('lazy_blacktea_pyqt.QGuiApplication.clipboard', return_value=clipboard):
            item = QTreeWidgetItem(['file.txt'])
            item.setData(0, DEVICE_FILE_PATH_ROLE, '/sdcard/file.txt')
            self.window.copy_device_file_path(item)

        clipboard.setText.assert_called_once_with('/sdcard/file.txt')

    def test_download_device_file_item_delegates_to_manager(self):
        """Downloading from context menu should pull single path via manager."""
        item = QTreeWidgetItem(['file.txt'])
        item.setData(0, DEVICE_FILE_PATH_ROLE, '/sdcard/file.txt')

        device = SimpleNamespace(device_serial_num='SERIAL123')
        self.window.require_single_device_selection = MagicMock(return_value=device)
        self.window._get_file_generation_output_path = MagicMock(return_value='/tmp/out')
        self.window._set_device_file_status = MagicMock()
        manager_mock = MagicMock()
        self.window.device_file_browser_manager = manager_mock

        self.window.download_device_file_item(item)

        manager_mock.download_paths.assert_called_once_with('SERIAL123', ['/sdcard/file.txt'], '/tmp/out')
        self.window._set_device_file_status.assert_called()


class WindowMainDefaultsTests(unittest.TestCase):
    """Validate default configuration for WindowMain."""

    def test_default_path_constant_is_sdcard(self):
        """Default device browser path constant should target /sdcard."""
        self.assertTrue(hasattr(WindowMain, 'DEVICE_FILE_BROWSER_DEFAULT_PATH'))
        self.assertEqual(WindowMain.DEVICE_FILE_BROWSER_DEFAULT_PATH, '/sdcard')

    def test_normalize_empty_path_defaults_to_sdcard(self):
        """Normalizing empty paths should produce the default device path."""
        result = WindowMain._normalize_device_remote_path('')
        self.assertEqual(result, '/sdcard')


class WindowMainContextMenuTests(unittest.TestCase):
    """Ensure context menu wiring includes preview, copy, and download."""

    def test_context_menu_adds_expected_actions(self):
        window = WindowMain.__new__(WindowMain)
        window.device_file_tree = MagicMock()
        window._device_file_widgets_ready = MagicMock(return_value=True)

        item = QTreeWidgetItem(['file.txt'])
        item.setData(0, DEVICE_FILE_IS_DIR_ROLE, False)
        item.setData(0, DEVICE_FILE_PATH_ROLE, '/sdcard/file.txt')

        window.device_file_tree.itemAt.return_value = item
        viewport = MagicMock()
        window.device_file_tree.viewport.return_value = viewport
        viewport.mapToGlobal.return_value = QPoint(10, 20)

        with patch('lazy_blacktea_pyqt.QMenu') as mock_menu_ctor:
            menu_instance = MagicMock()
            mock_menu_ctor.return_value = menu_instance
            window.on_device_file_context_menu(QPoint(0, 0))

        added_texts = [call.args[0] for call in menu_instance.addAction.call_args_list]
        self.assertIn(PanelText.BUTTON_PREVIEW_SELECTED, added_texts)
        self.assertIn(PanelText.BUTTON_COPY_PATH, added_texts)
        self.assertIn(PanelText.BUTTON_DOWNLOAD_ITEM, added_texts)


if __name__ == '__main__':
    unittest.main()
