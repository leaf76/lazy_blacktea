#!/usr/bin/env python3
"""Extra unit tests for utils.file_generation_utils w/o real ADB calls."""

import os
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils import file_generation_utils as fgu
from utils.adb_models import DeviceInfo


def _mk_device(serial: str, model: str = "ModelX") -> DeviceInfo:
    return DeviceInfo(
        device_serial_num=serial,
        device_usb="usb",
        device_prod="prod",
        device_model=model,
        wifi_is_on=True,
        bt_is_on=True,
        android_ver="11",
        android_api_level="30",
        gms_version="g",
        build_fingerprint="fp",
    )


class TestFileGenerationUtilsExtra(unittest.TestCase):
    def test_sanitize_fragment(self) -> None:
        self.assertEqual(fgu._sanitize_fragment("abc"), "abc")
        self.assertEqual(fgu._sanitize_fragment("a/b:c*?"), "a_b_c")
        self.assertEqual(fgu._sanitize_fragment(""), "unknown")

    def test_claim_and_release_run_state(self) -> None:
        # Ensure clean state
        fgu._release_bug_report_run()
        self.assertFalse(fgu.is_bug_report_generation_active())

        serials = ["s1", "s2"]
        fgu._claim_bug_report_run(serials)
        self.assertTrue(fgu.is_bug_report_generation_active())
        self.assertCountEqual(fgu.get_active_bug_report_serials(), serials)

        # Overlapping claim should raise
        with self.assertRaises(fgu.BugReportInProgressError):
            fgu._claim_bug_report_run(["s2", "s3"])  # overlap s2

        fgu._release_bug_report_run()
        self.assertFalse(fgu.is_bug_report_generation_active())

    def test_validate_file_output_path(self) -> None:
        self.assertIsNone(fgu.validate_file_output_path("   "))
        with tempfile.TemporaryDirectory() as td:
            p = os.path.join(td, "x")
            out = fgu.validate_file_output_path(p)
            self.assertTrue(os.path.isdir(out))

    def test_operations_manifest(self) -> None:
        ops = fgu.get_file_generation_operations()
        names = [op["name"] for op in ops]
        self.assertIn("Bug Report", names)
        self.assertIn("Device Discovery", names)
        self.assertIn("Device Info", names)

    def test_parallel_fetch_with_dummy_fetcher(self) -> None:
        devices = [_mk_device("a"), _mk_device("b")]
        dummy = lambda d: {"serial": d.device_serial_num}

        # Patch logger to a simple object with .warning
        class L:
            def warning(self, *_args, **_kwargs):
                pass

        out = fgu._parallel_fetch(devices, dummy, L(), "err")
        self.assertEqual(set(out.keys()), {"a", "b"})
        self.assertEqual(out["a"], {"serial": "a"})


if __name__ == "__main__":
    unittest.main()
