#!/usr/bin/env python3
"""Bug report workflow regression tests."""

import os
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_TEST_HOME = Path(__file__).resolve().parents[1] / ".test_home_bug_report"
os.environ["HOME"] = str(_TEST_HOME)
(_TEST_HOME / ".lazy_blacktea_logs").mkdir(parents=True, exist_ok=True)

from utils import adb_models, adb_tools, file_generation_utils


class _ImmediateThread:
    """Thread stub that runs the target synchronously for testing."""

    def __init__(self, target=None, daemon=None):
        self._target = target

    def start(self):
        if self._target:
            self._target()


class BugReportWorkflowTests(unittest.TestCase):
    """Validate bug report generation progress and error handling."""

    def setUp(self):
        self.success_device = adb_models.DeviceInfo(
            device_serial_num="test-001",
            device_usb="usb-1",
            device_prod="prod-1",
            device_model="Pixel 8 Pro",
            wifi_is_on=True,
            bt_is_on=False,
            android_ver="14",
            android_api_level="34",
            gms_version="23.18",
            build_fingerprint="fingerprint/1",
        )

        self.failure_device = adb_models.DeviceInfo(
            device_serial_num="test-002",
            device_usb="usb-2",
            device_prod="prod-2",
            device_model="Galaxy Ultra",
            wifi_is_on=True,
            bt_is_on=True,
            android_ver="13",
            android_api_level="33",
            gms_version="22.05",
            build_fingerprint="fingerprint/2",
        )

    def test_generate_bug_report_device_includes_command_details_on_failure(self):
        """Failed bug report captures command details for UI feedback."""

        with patch("utils.adb_tools._is_device_available", return_value=True), \
             patch("utils.adb_tools._get_device_manufacturer_info", return_value={"manufacturer": "samsung", "model": "Galaxy Ultra"}), \
             patch("utils.adb_tools._check_bug_report_permissions", return_value=True), \
             patch("utils.adb_tools.common.run_command", return_value=["adb: Permission denied"]), \
             patch("utils.adb_tools.os.path.exists", return_value=False):
            result = adb_tools.generate_bug_report_device("serial-xyz", "/tmp/bug_report_output")

        self.assertFalse(result["success"])
        self.assertIn("Permission denied", result.get("error", ""))
        self.assertIn("adb -s serial-xyz bugreport", result.get("details", ""))

    def test_generate_bug_report_batch_emits_progress_events(self):
        """Batch generation reports progress for each device with sanitized paths."""

        progress_events = []
        completion_payloads = []
        done_event = threading.Event()

        def progress_callback(payload):
            progress_events.append(payload)

        def completion_callback(title, payload, success_count, icon):
            completion_payloads.append((title, payload, success_count, icon))
            done_event.set()

        generated_paths = []

        def fake_generate(serial, filepath, timeout=300):
            generated_paths.append((serial, filepath))
            if serial == "test-001":
                success_output = f"{filepath}.zip"
                return {
                    "success": True,
                    "output_path": success_output,
                    "file_size": 524288,
                    "details": "Captured successfully",
                }
            failure_output = f"{filepath}.zip"
            return {
                "success": False,
                "output_path": failure_output,
                "error": "Permission denied",
                "details": "adb stderr: Permission denied",
            }

        devices = [self.success_device, self.failure_device]

        def fake_exists(path):
            if not generated_paths:
                return False
            # Ensure we only consider paths corresponding to generated reports
            return any(path == f"{device_path}.zip" for _, device_path in generated_paths)

        with patch("utils.file_generation_utils.common.current_format_time_utc", return_value="20250101_000000"), \
             patch("utils.file_generation_utils.os.path.exists", side_effect=fake_exists), \
             patch("utils.file_generation_utils.adb_tools.generate_bug_report_device", side_effect=fake_generate):
            file_generation_utils.generate_bug_report_batch(
                devices,
                "/tmp/output",
                completion_callback,
                progress_callback=progress_callback,
            )
            self.assertTrue(done_event.wait(timeout=1.0))

        self.assertEqual(len(progress_events), 2)

        events_by_serial = {event["device_serial"]: event for event in progress_events}

        self.assertIn("test-001", events_by_serial)
        success_event = events_by_serial["test-001"]
        self.assertTrue(success_event["success"])
        self.assertEqual(success_event["total"], 2)
        self.assertIn(
            "bug_report_Pixel_8_Pro_test-001_20250101_000000.zip",
            success_event["output_path"],
        )

        self.assertIn("test-002", events_by_serial)
        failure_event = events_by_serial["test-002"]
        self.assertFalse(failure_event["success"])
        self.assertIn("Permission denied", failure_event["error_message"])

        self.assertTrue(completion_payloads)
        summary_title, summary_payload, success_count, _ = completion_payloads[0]
        self.assertEqual(success_count, 1)
        self.assertIsInstance(summary_payload, dict)
        self.assertIn("Failed: 1 device", summary_payload.get("summary", ""))
        self.assertTrue(summary_payload.get("output_path", "").startswith("/tmp/output"))
        self.assertEqual(summary_title, "Bug Report Complete")

    def test_generate_bug_report_batch_runs_tasks_concurrently(self):
        """Bug report generation should execute device jobs concurrently."""

        devices = [self.success_device, self.failure_device]

        def fake_generate(_serial, _filepath, timeout=300):
            time.sleep(0.15)
            return {"success": True, "output_path": "dummy.zip"}

        done_event = threading.Event()

        with patch("utils.file_generation_utils.adb_tools.generate_bug_report_device", side_effect=fake_generate), \
             patch("utils.file_generation_utils.common.current_format_time_utc", return_value="20250101_000000"), \
             patch("utils.file_generation_utils.os.makedirs"):
            start = time.perf_counter()
            file_generation_utils.generate_bug_report_batch(
                devices,
                "/tmp/output",
                lambda *_args, **_kwargs: done_event.set(),
                progress_callback=lambda *_args, **_kwargs: None,
            )
            self.assertTrue(done_event.wait(timeout=2.0))
            elapsed = time.perf_counter() - start

        # Sequential execution would take roughly len(devices) * 0.15s (>0.30s)
        self.assertLess(elapsed, 0.25, f"Bug report tasks were not parallelised: {elapsed:.3f}s")

    def test_device_availability_check(self):
        """確認 get-state 輸出 device 時視為連線"""

        with patch("utils.adb_tools.common.run_command", return_value=["device"]):
            self.assertTrue(adb_tools._is_device_available("serial-123"))


if __name__ == "__main__":
    unittest.main()
