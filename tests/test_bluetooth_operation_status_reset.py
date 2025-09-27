#!/usr/bin/env python3
"""Tests ensuring device operation status clears after Bluetooth actions."""

import os
import sys
import threading
import time
import unittest
from types import SimpleNamespace

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt6.QtWidgets import QApplication, QMainWindow

from lazy_blacktea_pyqt import WindowMain
from utils.adb_models import DeviceInfo


class DummyDeviceListController:
    """Minimal stub to observe device list refreshes."""

    def __init__(self):
        self.update_calls = 0
        self.last_device_dict = None
        self.filter_calls = 0

    def update_device_list(self, device_dict):
        self.update_calls += 1
        self.last_device_dict = device_dict

    def filter_and_sort_devices(self):
        self.filter_calls += 1


class BluetoothOperationStatusResetTest(unittest.TestCase):
    """Verify Bluetooth operations do not leave stale status text."""

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.window = WindowMain.__new__(WindowMain)
        QMainWindow.__init__(self.window)
        self.window.device_operations = {}
        self.window.device_dict = {}
        self.window.check_devices = {}
        self.window.device_recordings = {}
        self.window.pending_checked_serials = set()
        self.window.virtualized_active = False
        self.window.virtualized_device_list = None
        self.window.checkbox_pool = []

        self.window.device_list_controller = DummyDeviceListController()
        self.window.device_manager = SimpleNamespace(force_refresh=lambda: None)
        self.window.battery_info_manager = SimpleNamespace(refresh_serials=lambda _serials: None)
        self.window.finalize_operation_requested.connect(self.window._finalize_operation)

        self.window.show_error = lambda *args, **kwargs: None
        self.window.show_info = lambda *args, **kwargs: None
        self.window.show_warning = lambda *args, **kwargs: None

        self.window.device_scroll = SimpleNamespace(setUpdatesEnabled=lambda _enabled: None)
        self.window.device_search_manager = SimpleNamespace(
            get_search_text=lambda: "",
            get_sort_mode=lambda: "name",
            search_and_sort_devices=lambda devices, _text, _mode: list(devices),
        )
        self.window.update_selection_count = lambda: None
        self.window.title_label = SimpleNamespace(setText=lambda _text: None)

        self.serial = "SERIAL123"
        self.device_info = DeviceInfo(
            device_serial_num=self.serial,
            device_usb="usb",
            device_prod="product",
            device_model="Pixel",
            wifi_is_on=True,
            bt_is_on=True,
            android_ver="15",
            android_api_level="35",
            gms_version="25.3",
            build_fingerprint="fingerprint",
        )
        self.window.device_dict[self.serial] = self.device_info
        self.window.get_checked_devices = lambda: [self.device_info]

        self.window._refresh_connectivity_info = lambda _serials: True
        self.window.run_in_thread = WindowMain.run_in_thread.__get__(self.window, WindowMain)

    def _wait_for(self, predicate, timeout=1.0):
        deadline = time.time() + timeout
        while time.time() < deadline:
            self.app.processEvents()
            if predicate():
                return True
            time.sleep(0.01)
        return False

    def test_operation_status_cleared_after_bluetooth_action(self):
        completion_event = threading.Event()

        def fake_tool(serials, *_args, **_kwargs):
            self.assertEqual([self.serial], serials)
            completion_event.set()

        self.window._run_adb_tool_on_selected_devices(
            fake_tool,
            "disable Bluetooth",
            show_progress=False,
            refresh_mode="connectivity",
        )

        self.assertTrue(completion_event.wait(timeout=1.0))
        self.assertIn(self.serial, self.window.device_operations)

        cleared = self._wait_for(lambda: self.serial not in self.window.device_operations, timeout=1.5)
        self.assertTrue(cleared, "Bluetooth operation status did not clear in time")


if __name__ == "__main__":
    unittest.main()
