#!/usr/bin/env python3
"""Recording manager regression tests for segmented recording and retries."""

import os
import threading
import time
import unittest
from unittest.mock import patch


_TEST_HOME = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", ".test_home")
)
os.environ["HOME"] = _TEST_HOME
os.makedirs(os.path.join(_TEST_HOME, ".lazy_blacktea_logs"), exist_ok=True)

from config.constants import RecordingConstants
from utils import adb_models
from utils.recording_utils import RecordingManager


class RecordingManagerRefactorTest(unittest.TestCase):
    """Verify enhanced recording manager behaviours."""

    def setUp(self):
        self.manager = RecordingManager()
        self.device = adb_models.DeviceInfo(
            device_serial_num="TEST_SERIAL",
            device_usb="usb",
            device_prod="prod",
            device_model="TestModel",
            wifi_is_on=True,
            bt_is_on=True,
            android_ver="13",
            android_api_level="33",
            gms_version="Test",
            build_fingerprint="fingerprint",
        )

    def tearDown(self):
        # Ensure all recordings are stopped between tests
        self.manager.stop_recording()
        time.sleep(0.05)

    def test_segmented_recording_emits_progress_events(self):
        """Recording manager should emit progress for segmented recordings."""
        progress_events = []
        completion_event = threading.Event()
        second_segment_ready = threading.Event()

        def progress_callback(event: dict):
            progress_events.append(event)
            if event.get("type") == "segment_completed" and event.get("segment_index", 0) >= 2:
                second_segment_ready.set()

        completion_results = {}

        def completion_callback(device_name, device_serial, duration, filename, output_path):
            completion_results["data"] = (device_name, device_serial, duration, filename, output_path)
            completion_event.set()

        with patch.object(RecordingConstants, "SEGMENT_DURATION_SECONDS", 0.05), \
             patch.object(RecordingConstants, "VERIFICATION_POLL_INTERVAL", 0.01), \
             patch("utils.recording_utils.adb_tools.start_screen_record_device") as mock_start, \
             patch("utils.recording_utils.adb_tools.stop_screen_record_device") as mock_stop, \
             patch.object(RecordingManager, "_wait_for_recording_start", return_value=True):
            mock_start.side_effect = lambda serial, output_path, filename: None
            mock_stop.side_effect = lambda serial: None

            started = self.manager.start_recording(
                [self.device],
                "/tmp",
                completion_callback=completion_callback,
                progress_callback=progress_callback,
            )

            self.assertTrue(started)
            self.assertTrue(second_segment_ready.wait(1.0))

            stopped_devices = self.manager.stop_recording(self.device.device_serial_num)
            self.assertIn(self.device.device_serial_num, stopped_devices)
            self.assertTrue(completion_event.wait(1.0))

        segment_events = [e for e in progress_events if e.get("type") == "segment_completed"]
        self.assertGreaterEqual(len(segment_events), 2)
        self.assertEqual(self.manager.get_active_recordings_count(), 0)
        self.assertIn("data", completion_results)
        self.assertEqual(completion_results["data"][1], self.device.device_serial_num)

    def test_start_failures_trigger_retries_and_cleanup(self):
        """Start failures should retry and report error without leaving active state."""
        progress_events = []
        error_event = threading.Event()
        completion_called = threading.Event()

        def progress_callback(event: dict):
            progress_events.append(event)
            if event.get("type") == "error":
                error_event.set()

        def completion_callback(*args, **kwargs):
            completion_called.set()

        with patch.object(RecordingConstants, "START_RETRY_DELAY", 0.01), \
             patch.object(RecordingConstants, "VERIFICATION_POLL_INTERVAL", 0.01), \
             patch("utils.recording_utils.adb_tools.start_screen_record_device") as mock_start, \
             patch.object(RecordingManager, "_wait_for_recording_start", return_value=False):
            mock_start.side_effect = RuntimeError("boom")

            started = self.manager.start_recording(
                [self.device],
                "/tmp",
                completion_callback=completion_callback,
                progress_callback=progress_callback,
            )

            self.assertFalse(started)
            self.assertTrue(error_event.wait(1.0))
            self.assertFalse(completion_called.is_set())
            self.assertEqual(self.manager.get_active_recordings_count(), 0)

        error_events = [e for e in progress_events if e.get("type") == "error"]
        self.assertGreaterEqual(len(error_events), 1)


if __name__ == "__main__":
    unittest.main()
