#!/usr/bin/env python3
"""Async device refresh behaviour tests."""

import os
import unittest
from unittest.mock import patch, MagicMock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from pathlib import Path

_TEST_HOME = Path(__file__).resolve().parents[1] / ".test_home_async_refresh"
os.environ["HOME"] = str(_TEST_HOME)
(_TEST_HOME / ".lazy_blacktea_logs").mkdir(parents=True, exist_ok=True)

from PyQt6.QtWidgets import QApplication

from ui.async_device_manager import AsyncDeviceManager


class AsyncDeviceRefreshTests(unittest.TestCase):
    """Verify device refresh logic only triggers when devices change."""

    @classmethod
    def setUpClass(cls):
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.manager = AsyncDeviceManager(tracker_factory=lambda: None)
        self.manager.last_discovered_serials = {"device1", "device2"}
        self.manager.refresh_cycle_count = 0

    def test_periodic_refresh_skips_when_devices_unchanged(self):
        with patch.object(self.manager, '_get_basic_device_serials', return_value=['device1', 'device2']), \
             patch.object(self.manager, 'start_device_discovery') as mock_discovery:
            self.manager._periodic_refresh()

        self.assertEqual(mock_discovery.call_count, 0)
        self.assertEqual(self.manager.refresh_cycle_count, 1)

    def test_periodic_refresh_triggers_on_device_change(self):
        with patch.object(self.manager, '_get_basic_device_serials', return_value=['device1', 'device3']), \
             patch.object(self.manager, 'start_device_discovery') as mock_discovery:
            self.manager._periodic_refresh()

        mock_discovery.assert_called_once_with(force_reload=True, load_detailed=True, serials=['device1', 'device3'])
        self.assertEqual(self.manager.refresh_cycle_count, 1)

    def test_tracked_devices_change_triggers_refresh(self):
        with patch.object(self.manager, 'start_device_discovery') as mock_discovery:
            self.manager._on_tracked_devices_changed(['device1', 'device3'])

        mock_discovery.assert_called_once_with(force_reload=True, load_detailed=True, serials=['device1', 'device3'])

    def test_tracked_devices_no_change_skips_refresh(self):
        with patch.object(self.manager, 'start_device_discovery') as mock_discovery:
            self.manager._on_tracked_devices_changed(['device1', 'device2'])

        mock_discovery.assert_not_called()

    def test_periodic_refresh_triggers_when_no_previous_cache(self):
        self.manager.last_discovered_serials = None
        with patch.object(self.manager, '_get_basic_device_serials', return_value=['deviceA']), \
             patch.object(self.manager, 'start_device_discovery') as mock_discovery:
            self.manager._periodic_refresh()

        mock_discovery.assert_called_once_with(force_reload=True, load_detailed=True, serials=['deviceA'])


if __name__ == '__main__':
    unittest.main()
