#!/usr/bin/env python3
"""Tests ensuring multi-device operations execute concurrently."""

import os
import time
import unittest
from types import SimpleNamespace
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from pathlib import Path

_TEST_HOME = Path(__file__).resolve().parents[1] / ".test_home_device_ops"
os.environ["HOME"] = str(_TEST_HOME)
(_TEST_HOME / ".lazy_blacktea_logs").mkdir(parents=True, exist_ok=True)

from PyQt6.QtWidgets import QApplication

from ui.device_operations_manager import DeviceOperationsManager


class DeviceOperationConcurrencyTests(unittest.TestCase):
    """Validate that high-latency device actions run in parallel."""

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.manager = DeviceOperationsManager(parent_window=None)

        # Suppress UI interactions during tests
        self.manager._show_info = lambda *args, **kwargs: None
        self.manager._show_error = lambda *args, **kwargs: None
        self.manager._show_warning = lambda *args, **kwargs: None
        self.manager._log_console = lambda *args, **kwargs: None

    def tearDown(self):
        # Ensure timers are stopped to avoid side effects between tests
        if hasattr(self.manager, "recording_timer"):
            self.manager.recording_timer.stop()

    def test_enable_bluetooth_executes_parallel_commands(self):
        serials = ["serial-a", "serial-b", "serial-c"]
        call_count = 0

        def fake_run_adb_command(_cmd):
            nonlocal call_count
            call_count += 1
            time.sleep(0.15)
            return SimpleNamespace(returncode=0, stderr="")

        start = time.perf_counter()
        with patch("ui.device_operations_manager.adb_tools.run_adb_command", side_effect=fake_run_adb_command, create=True):
            result = self.manager.enable_bluetooth(device_serials=serials)

        elapsed = time.perf_counter() - start

        self.assertTrue(result)
        self.assertEqual(call_count, len(serials))
        # Sequential execution would take roughly len(serials) * 0.15s (>0.45s)
        self.assertLess(elapsed, 0.35, f"Bluetooth command took too long: {elapsed:.3f}s")

    def test_install_apk_runs_parallel_per_device(self):
        serials = ["serial-a", "serial-b", "serial-c"]
        apk_path = "/tmp/test.apk"

        def fake_get_device_info(serial):
            return SimpleNamespace(device_model=f"Model-{serial}")

        def fake_run_adb_command(_cmd):
            time.sleep(0.15)
            return SimpleNamespace(returncode=0, stderr="")

        with patch("ui.device_operations_manager.adb_tools.run_adb_command", side_effect=fake_run_adb_command, create=True), \
             patch.object(self.manager, "_get_device_info", side_effect=fake_get_device_info):
            start = time.perf_counter()
            self.manager._install_apk_with_progress(serials, apk_path, "test.apk")
            elapsed = time.perf_counter() - start

        self.assertLess(elapsed, 0.35, f"APK install took too long: {elapsed:.3f}s")


if __name__ == "__main__":
    unittest.main()
