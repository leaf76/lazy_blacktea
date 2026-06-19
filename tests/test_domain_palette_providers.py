"""Tests for the Devices / Recent-tasks command-palette providers (#14)."""

import os
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ui.shell.domain_palette_providers import (
    DevicesPaletteProvider,
    RecentTasksPaletteProvider,
)


class DevicesProviderTests(unittest.TestCase):
    def test_entries_one_per_device_with_model_and_serial(self):
        window = SimpleNamespace(
            device_dict={
                'SER1': SimpleNamespace(device_model='Pixel 7'),
                'SER2': SimpleNamespace(device_model='Galaxy S24'),
            }
        )
        entries = DevicesPaletteProvider(window).entries('')
        titles = {e.title for e in entries}
        self.assertIn('Pixel 7 · SER1', titles)
        self.assertIn('Galaxy S24 · SER2', titles)

    def test_invoke_sets_active_device_and_opens_pane(self):
        shell = MagicMock()
        window = SimpleNamespace(
            device_dict={'SER1': SimpleNamespace(device_model='Pixel 7')},
            select_only_device=MagicMock(),
            app_shell=shell,
            PANE_DEVICES='devices',
        )
        entries = DevicesPaletteProvider(window).entries('')
        entries[0].invoke()
        window.select_only_device.assert_called_once_with('SER1')
        shell.set_active_pane.assert_called_once_with('devices')

    def test_no_devices_returns_empty(self):
        self.assertEqual(DevicesPaletteProvider(SimpleNamespace(device_dict={})).entries(''), [])


class RecentTasksProviderTests(unittest.TestCase):
    def _op(self, name, device, completed_at, terminal=True):
        return SimpleNamespace(
            is_terminal=terminal,
            completed_at=completed_at,
            operation_type=SimpleNamespace(display_name=name),
            device_name=device,
            device_serial=device,
            status=SimpleNamespace(value='completed'),
        )

    def test_only_terminal_ops_most_recent_first_capped(self):
        ops = [self._op(f'Op{i}', f'D{i}', completed_at=i) for i in range(15)]
        ops.append(self._op('Running', 'DX', completed_at=99, terminal=False))
        window = SimpleNamespace(
            device_operation_status_manager=SimpleNamespace(
                get_all_operations=lambda: ops
            )
        )
        entries = RecentTasksPaletteProvider(window).entries('')
        self.assertEqual(len(entries), 10)  # capped
        self.assertNotIn('Running', [e.title for e in entries])  # non-terminal excluded
        self.assertIn('Op14', entries[0].title)  # most recent first

    def test_invoke_opens_tasks_pane(self):
        shell = MagicMock()
        window = SimpleNamespace(
            device_operation_status_manager=SimpleNamespace(
                get_all_operations=lambda: [self._op('Reboot', 'D1', 1)]
            ),
            app_shell=shell,
            PANE_TASKS='tasks',
        )
        entries = RecentTasksPaletteProvider(window).entries('')
        entries[0].invoke()
        shell.set_active_pane.assert_called_once_with('tasks')


if __name__ == '__main__':
    unittest.main()
