"""Regression tests for newly parallelised multi-device workflows."""

import os
import tempfile
import threading
import time
import unittest
from types import SimpleNamespace
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication

from ui.device_operations_manager import DeviceOperationsManager
from ui.file_operations_manager import UIHierarchyManager
from utils import adb_tools, file_generation_utils


class _DummyWindow:
    """Minimal stub to satisfy UI hierarchy manager dependencies."""

    def __init__(self, devices):
        self._devices = devices
        self.logger = None

    def get_checked_devices(self):
        return self._devices

    def show_error(self, *_args, **_kwargs):
        raise AssertionError("Unexpected show_error call during tests")

    def show_info(self, *_args, **_kwargs):
        pass


class ParallelEnhancementTests(unittest.TestCase):
    """Validate that the refactored helpers execute work in parallel."""

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.devices = [
            SimpleNamespace(
                device_serial_num=f"serial-{idx}",
                device_model=f"Model-{idx}",
                device_status='device',
                transport_id='usb'
            )
            for idx in range(3)
        ]

    def test_start_to_screen_shot_is_parallel(self):
        serials = [d.device_serial_num for d in self.devices]
        calls = []

        def fake_run_command(cmd, *args, **kwargs):
            start = time.perf_counter()
            time.sleep(0.05)
            calls.append((cmd, start))
            return ["ok"]

        with tempfile.TemporaryDirectory() as tmp_dir, \
             patch("utils.adb_tools.common.run_command", side_effect=fake_run_command):
            started = time.perf_counter()
            adb_tools.start_to_screen_shot(serials, "capture", tmp_dir)
            elapsed = time.perf_counter() - started

        # Sequential would be >= len(serials) * 3 * 0.05 (~0.45s)
        self.assertLess(elapsed, 0.25, f"Screenshot workflow took too long: {elapsed:.3f}s")
        self.assertEqual(len(calls), len(serials) * 3)

    def test_start_screen_record_devices_parallel(self):
        serials = [d.device_serial_num for d in self.devices]
        call_order = []

        def fake_mp_run(cmd, *args, **kwargs):
            start = time.perf_counter()
            time.sleep(0.05)
            call_order.append((cmd, start))
            return ["pid"]

        with patch("utils.adb_tools.common.mp_run_command", side_effect=fake_mp_run):
            started = time.perf_counter()
            adb_tools.start_to_record_android_devices(serials, "demo.mp4")
            elapsed = time.perf_counter() - started

        self.assertLess(elapsed, 0.25, f"Screen recording start was sequential: {elapsed:.3f}s")
        started_commands = {cmd for cmd, _ in call_order if 'shell screenrecord' in cmd and '/sdcard/' in cmd}
        self.assertEqual(len(started_commands), len(serials))

    def test_reboot_device_parallelises_execution(self):
        manager = DeviceOperationsManager(parent_window=None)
        manager._show_info = lambda *args, **kwargs: None
        manager._show_error = lambda *args, **kwargs: None
        manager._show_warning = lambda *args, **kwargs: None
        manager._log_console = lambda *args, **kwargs: None

        serials = [d.device_serial_num for d in self.devices]

        def fake_run(cmd):
            time.sleep(0.05)
            return SimpleNamespace(returncode=0, stderr="")

        started = time.perf_counter()
        with patch("ui.device_operations_manager.adb_tools.run_adb_command", side_effect=fake_run, create=True):
            result = manager.reboot_device(device_serials=serials)
        elapsed = time.perf_counter() - started

        self.assertTrue(result)
        self.assertLess(elapsed, 0.25, f"Reboot workflow took too long: {elapsed:.3f}s")

    def test_ui_hierarchy_export_runs_parallel(self):
        window = _DummyWindow(self.devices)
        manager = UIHierarchyManager(window)

        timestamps = []

        def fake_generate(serial, output):
            time.sleep(0.05)
            timestamps.append((serial, time.perf_counter()))

        with tempfile.TemporaryDirectory() as tmp_dir, \
             patch("utils.dump_device_ui.generate_process", side_effect=fake_generate):
            started = time.perf_counter()
            manager.export_hierarchy(tmp_dir)
            elapsed = time.perf_counter() - started

        self.assertLess(elapsed, 0.12, f"UI export took too long: {elapsed:.3f}s")
        self.assertEqual(len(timestamps), len(self.devices))

    def test_device_info_generation_fetches_properties_in_parallel(self):
        captured_serials = []

        def fake_get_version(serial):
            time.sleep(0.05)
            captured_serials.append(("version", serial, time.perf_counter()))
            return "14"

        def fake_get_props(serial):
            time.sleep(0.05)
            captured_serials.append(("props", serial, time.perf_counter()))
            return {"ro.build.fingerprint": "test"}

        with tempfile.TemporaryDirectory() as tmp_dir, \
             patch("utils.file_generation_utils.adb_tools.get_android_version", side_effect=fake_get_version), \
             patch("utils.file_generation_utils.adb_tools.get_device_properties", side_effect=fake_get_props, create=True):
            start = time.perf_counter()
            file_generation_utils.generate_device_info_batch(self.devices, tmp_dir)
            elapsed = time.perf_counter() - start
            time.sleep(0.3)

        self.assertLess(elapsed, 0.1, "generate_device_info_batch should return quickly with background execution")
        self.assertEqual(len(captured_serials), len(self.devices) * 2)

    def test_device_discovery_properties_fetch_parallel(self):
        captured_serials = []

        def fake_get_props(serial):
            time.sleep(0.05)
            captured_serials.append(serial)
            return {"prop": "value"}

        with tempfile.TemporaryDirectory() as tmp_dir, \
             patch("utils.file_generation_utils.adb_tools.get_device_properties", side_effect=fake_get_props, create=True):
            start = time.perf_counter()
            file_generation_utils.generate_device_discovery_file(self.devices, tmp_dir)
            elapsed = time.perf_counter() - start
            time.sleep(0.3)

        self.assertLess(elapsed, 0.1, "generate_device_discovery_file should return quickly with background execution")
        self.assertEqual(len(captured_serials), len(self.devices))

    def test_ui_inspector_launch_runs_async_for_multiple_devices(self):
        manager = DeviceOperationsManager(parent_window=None)
        manager._show_info = lambda *args, **kwargs: None
        manager._show_warning = lambda *args, **kwargs: None
        manager._show_error = lambda *args, **kwargs: None
        manager._log_console = lambda *args, **kwargs: None

        serials = [device.device_serial_num for device in self.devices]
        call_count = 0
        call_lock = threading.Lock()

        def fake_impl(serial: str) -> bool:
            nonlocal call_count
            with call_lock:
                call_count += 1
            time.sleep(0.01)
            return True

        manager._launch_ui_inspector_for_device_impl = fake_impl  # type: ignore[attr-defined]

        start = time.perf_counter()
        self.assertTrue(manager.launch_ui_inspector(serials))
        elapsed = time.perf_counter() - start
        self.assertLess(elapsed, 0.05, 'UI Inspector launch should schedule work without blocking')

        timeout = start + 1.0
        while call_count < len(serials) and time.perf_counter() < timeout:
            QApplication.processEvents()
            time.sleep(0.005)

        self.assertEqual(call_count, len(serials))


if __name__ == "__main__":
    unittest.main()
