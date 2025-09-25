"""Tests for UI inspector utilities."""

import os
import pathlib
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
os.environ["HOME"] = str(PROJECT_ROOT / ".test_home")

import utils.ui_inspector_utils as ui_utils


class CaptureDeviceScreenshotTests(unittest.TestCase):
    """Validate screenshot capture flow for the UI inspector utilities."""

    def test_capture_device_screenshot_uses_binary_capture(self):
        screenshot_bytes = b"PNG\r\nmock-data"
        captured_command = {}

        def fake_run(cmd, **kwargs):
            captured_command["cmd"] = cmd
            self.assertTrue(kwargs.get("check"))
            self.assertTrue(kwargs.get("capture_output"))
            return types.SimpleNamespace(stdout=screenshot_bytes)

        with mock.patch.object(
            ui_utils.common,
            "sp_run_command",
            side_effect=AssertionError(
                "common.sp_run_command should not handle binary screenshots"
            ),
        ), mock.patch.object(
            ui_utils.adb_commands, "get_adb_command", return_value="adb"
        ), mock.patch.object(
            ui_utils,
            "subprocess",
            types.SimpleNamespace(run=fake_run),
            create=True,
        ):
            with tempfile.TemporaryDirectory() as temp_dir:
                output_path = Path(temp_dir) / "screen.png"
                result = ui_utils.capture_device_screenshot(
                    "serial123", str(output_path)
                )

                self.assertTrue(result)
                self.assertEqual(
                    captured_command["cmd"],
                    [
                        "adb",
                        "-s",
                        "serial123",
                        "exec-out",
                        "screencap",
                        "-p",
                    ],
                )
                self.assertEqual(output_path.read_bytes(), screenshot_bytes)


if __name__ == "__main__":
    unittest.main()
