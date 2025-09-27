#!/usr/bin/env python3
"""Async device refresh behaviour tests."""

import os
import unittest
from unittest.mock import MagicMock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from pathlib import Path

_TEST_HOME = Path(__file__).resolve().parents[1] / ".test_home_async_refresh"
os.environ["HOME"] = str(_TEST_HOME)
(_TEST_HOME / ".lazy_blacktea_logs").mkdir(parents=True, exist_ok=True)

from PyQt6.QtWidgets import QApplication

from ui.async_device_manager import (
    AsyncDeviceManager,
    AsyncDeviceWorker,
    DeviceLoadProgress,
    DeviceLoadStatus,
    ADBCommandError,
)
from utils import adb_models


class AsyncDeviceRefreshTests(unittest.TestCase):
    """Verify device refresh logic only triggers when devices change."""

    @classmethod
    def setUpClass(cls):
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.manager = AsyncDeviceManager(tracker_factory=lambda: None)
        self.manager.last_discovered_serials = {"device1", "device2"}
        self.manager.refresh_cycle_count = 0
        self.manager._enumerate_adb_devices = MagicMock(return_value=[])

    def _fake_device(self, serial: str = "ghost") -> adb_models.DeviceInfo:
        """Create a minimal device info stub for tests."""
        return adb_models.DeviceInfo(
            device_serial_num=serial,
            device_usb="usb",
            device_prod="prod",
            device_model="Model",
            wifi_is_on=False,
            bt_is_on=False,
            android_ver="13",
            android_api_level="33",
            gms_version="1.0",
            build_fingerprint="fingerprint",
        )

    def tearDown(self):
        self.manager.cleanup()

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

        mock_discovery.assert_called_once_with(force_reload=True, load_detailed=True)
        self.assertEqual(self.manager.refresh_cycle_count, 1)

    def test_tracked_devices_change_triggers_refresh(self):
        with patch.object(self.manager, 'start_device_discovery') as mock_discovery:
            self.manager._on_tracked_devices_changed([('device1', 'device'), ('device3', 'device')])

        mock_discovery.assert_called_once_with(force_reload=True, load_detailed=True)

    def test_tracked_devices_no_change_skips_refresh(self):
        with patch.object(self.manager, 'start_device_discovery') as mock_discovery:
            self.manager._on_tracked_devices_changed([('device1', 'device'), ('device2', 'device')])

        mock_discovery.assert_not_called()

    def test_tracked_devices_offline_triggers_refresh(self):
        with patch.object(self.manager, 'start_device_discovery') as mock_discovery:
            self.manager._on_tracked_devices_changed([('device1', 'offline')])

        mock_discovery.assert_called_once_with(force_reload=True, load_detailed=True)

    def test_tracked_devices_prefers_latest_status_from_tracker(self):
        self.manager.last_discovered_serials = {"device1"}

        with patch.object(self.manager, 'start_device_discovery') as mock_discovery:
            self.manager._on_tracked_devices_changed([
                ('device1', 'device'),
                ('device1', 'offline'),
            ])

        mock_discovery.assert_called_once_with(force_reload=True, load_detailed=True)

    def test_tracker_aliases_normalize_to_known_serial(self):
        real_serial = "35151FDJH000GQ"
        alias_serial = f"002a{real_serial}"
        self.manager.device_cache[real_serial] = self._fake_device(real_serial)
        self.manager.tracked_device_statuses = {real_serial: 'device'}

        with patch.object(self.manager, 'start_device_discovery') as mock_discovery:
            self.manager._on_tracked_devices_changed([(alias_serial, 'device')])

        mock_discovery.assert_called_once_with(force_reload=True, load_detailed=True)
        self.assertIn(real_serial, self.manager.tracked_device_statuses)
        self.assertNotIn(alias_serial, self.manager.tracked_device_statuses)

    def test_tracker_aliases_cleared_when_device_removed(self):
        real_serial = "35151FDJH000GQ"
        alias_serial = f"002e{real_serial}"
        self.manager.device_cache[real_serial] = self._fake_device(real_serial)
        self.manager.tracked_device_statuses = {real_serial: 'device'}
        self.manager._serial_aliases[alias_serial] = real_serial

        with patch.object(self.manager, 'start_device_discovery') as mock_discovery:
            self.manager._on_tracked_devices_changed([(alias_serial, 'offline')])

        mock_discovery.assert_called_once_with(force_reload=True, load_detailed=True)
        self.assertNotIn(real_serial, self.manager.device_cache)
        self.assertNotIn(alias_serial, self.manager._serial_aliases)

    def test_tracker_alias_with_unseen_prefix_matches_by_suffix(self):
        real_serial = "35151FDJH000GQ"
        alias_serial = f"abcd{real_serial}"
        self.manager.device_cache[real_serial] = self._fake_device(real_serial)
        self.manager.last_discovered_serials = {real_serial}

        with patch.object(self.manager, '_enumerate_adb_devices', return_value=[(real_serial, 'device')]):
            self.manager._on_tracked_devices_changed([(alias_serial, 'device')])

        self.assertEqual(self.manager.tracked_device_statuses.get(real_serial), 'device')
        self.assertEqual(self.manager._serial_aliases.get(alias_serial), real_serial)

    def test_tracker_status_history_with_offline_marks_device_removed(self):
        real_serial = "35151FDJH000GQ"
        alias_serial = f"002f{real_serial}"
        self.manager.device_cache[real_serial] = self._fake_device(real_serial)
        self.manager.tracked_device_statuses = {real_serial: 'device'}

        with patch.object(self.manager, 'start_device_discovery') as mock_discovery:
            self.manager._on_tracked_devices_changed([
                (alias_serial, 'offline'),
                (alias_serial, 'device'),
            ])

        mock_discovery.assert_called_once_with(force_reload=True, load_detailed=True)
        self.assertNotIn(real_serial, self.manager.tracked_device_statuses)
        self.assertNotIn(real_serial, self.manager.device_cache)

    def test_tracker_alias_re_add_after_removal(self):
        real_serial = "35151FDJH000GQ"
        alias_off = f"002a{real_serial}"
        alias_on = f"002b{real_serial}"
        self.manager.device_cache[real_serial] = self._fake_device(real_serial)
        self.manager.tracked_device_statuses = {real_serial: 'device'}

        with patch.object(self.manager, 'start_device_discovery') as mock_discovery_remove:
            self.manager._on_tracked_devices_changed([(alias_off, 'offline')])

        mock_discovery_remove.assert_called_once_with(force_reload=True, load_detailed=True)
        self.assertNotIn(real_serial, self.manager.device_cache)

        with patch.object(self.manager, 'start_device_discovery') as mock_discovery_add:
            self.manager._on_tracked_devices_changed([(alias_on, 'device')])

        mock_discovery_add.assert_called_once_with(force_reload=True, load_detailed=True)
        self.assertTrue(self.manager.tracked_device_statuses)

    def test_tracked_offline_devices_are_removed_from_cache(self):
        serial = "ghost"
        self.manager.device_cache[serial] = self._fake_device(serial)
        self.manager.device_progress[serial] = DeviceLoadProgress(
            serial=serial,
            status=DeviceLoadStatus.BASIC_LOADED,
        )

        basic_spy = MagicMock()
        all_spy = MagicMock()
        self.manager.basic_devices_ready.connect(basic_spy)
        self.manager.all_devices_ready.connect(all_spy)

        try:
            with patch.object(self.manager, 'start_device_discovery') as mock_discovery:
                self.manager._on_tracked_devices_changed([(serial, 'offline')])
        finally:
            self.manager.basic_devices_ready.disconnect(basic_spy)
            self.manager.all_devices_ready.disconnect(all_spy)

        self.assertNotIn(serial, self.manager.device_cache)
        self.assertNotIn(serial, self.manager.device_progress)
        basic_spy.assert_called_once()
        all_spy.assert_not_called()
        mock_discovery.assert_called_once_with(force_reload=True, load_detailed=True)

    def test_tracked_missing_devices_are_pruned(self):
        serial = "phantom"
        self.manager.tracked_device_statuses = {serial: 'device'}
        self.manager.device_cache[serial] = self._fake_device(serial)
        self.manager.device_progress[serial] = DeviceLoadProgress(
            serial=serial,
            status=DeviceLoadStatus.BASIC_LOADED,
        )
        self.manager.last_discovered_serials = {serial}

        basic_spy = MagicMock()
        self.manager.basic_devices_ready.connect(basic_spy)

        try:
            with patch.object(self.manager, 'start_device_discovery') as mock_discovery:
                self.manager._on_tracked_devices_changed([('other', 'device')])
        finally:
            self.manager.basic_devices_ready.disconnect(basic_spy)

        self.assertNotIn(serial, self.manager.device_cache)
        self.assertNotIn(serial, self.manager.device_progress)
        basic_spy.assert_called_once()
        mock_discovery.assert_called_once_with(force_reload=True, load_detailed=True)

    def test_worker_skips_detailed_info_for_untracked_device(self):
        worker = AsyncDeviceWorker()
        worker.set_status_checker(lambda _serial: False)

        with patch('utils.adb_tools.get_device_detailed_info') as mock_get_info:
            result = worker._load_single_device_info('ghost-device')

        mock_get_info.assert_not_called()
        self.assertIsNone(result)

    def test_missing_device_emits_basic_ready(self):
        self.manager.tracked_device_statuses = {'phantom': 'device'}
        self.manager.last_discovered_serials = {'phantom'}

        basic_spy = MagicMock()
        self.manager.basic_devices_ready.connect(basic_spy)

        try:
            with patch.object(self.manager, 'start_device_discovery') as mock_discovery:
                self.manager._on_tracked_devices_changed([('other', 'device')])
        finally:
            self.manager.basic_devices_ready.disconnect(basic_spy)

        basic_spy.assert_called_once()
        mock_discovery.assert_called_once()

    def test_discovery_failure_preserves_cached_devices(self):
        serial = "persist"
        cached_device = self._fake_device(serial)
        self.manager.device_cache[serial] = cached_device
        self.manager.last_discovered_serials = {serial}

        basic_spy = MagicMock()
        self.manager.basic_devices_ready.connect(basic_spy)

        try:
            with patch.object(self.manager, '_get_basic_device_serials', side_effect=ADBCommandError('adb failure')):
                self.manager.start_device_discovery(force_reload=True, load_detailed=True)
        finally:
            self.manager.basic_devices_ready.disconnect(basic_spy)

        basic_spy.assert_called_once()
        emitted_payload = basic_spy.call_args[0][0]
        self.assertIn(serial, emitted_payload)
        self.assertIn(serial, self.manager.device_cache)

    def test_periodic_refresh_triggers_when_no_previous_cache(self):
        self.manager.last_discovered_serials = None
        with patch.object(self.manager, '_get_basic_device_serials', return_value=['deviceA']), \
             patch.object(self.manager, 'start_device_discovery') as mock_discovery:
            self.manager._periodic_refresh()

        mock_discovery.assert_called_once_with(force_reload=True, load_detailed=True)

    def test_disabling_auto_refresh_stops_timer(self):
        self.manager.set_refresh_interval(10)
        self.manager.start_periodic_refresh()
        self.assertTrue(self.manager.refresh_timer.isActive())

        self.manager.set_auto_refresh_enabled(False)
        self.assertFalse(self.manager.refresh_timer.isActive())

        self.manager.set_auto_refresh_enabled(True)
        self.assertTrue(self.manager.refresh_timer.isActive())


if __name__ == '__main__':
    unittest.main()
