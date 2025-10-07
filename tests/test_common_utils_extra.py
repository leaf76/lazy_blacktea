#!/usr/bin/env python3
"""Extra unit tests for utils.common focusing on pure logic and safe I/O paths."""

import os
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils import common


class TestCommonUtilsExtra(unittest.TestCase):
    def test_trace_id_lifecycle_and_filter(self) -> None:
        # Default trace id
        self.assertEqual(common.get_trace_id(), "-")

        # Direct set/reset
        token = common.set_trace_id("abc123")
        self.assertEqual(common.get_trace_id(), "abc123")
        common.reset_trace_id(token)
        self.assertEqual(common.get_trace_id(), "-")

        # Context manager
        with common.trace_id_scope("zzz"):
            self.assertEqual(common.get_trace_id(), "zzz")
        self.assertEqual(common.get_trace_id(), "-")

    def test_resolve_logs_dir_linux_variants(self) -> None:
        with patch("platform.system", return_value="Linux"), \
             patch.dict(os.environ, {"XDG_DATA_HOME": "/tmp/xdg"}, clear=False):
            path = common._resolve_logs_dir()  # type: ignore[attr-defined]
            self.assertTrue(str(path).endswith("/tmp/xdg/lazy_blacktea/logs"))

        with patch("platform.system", return_value="Linux"), \
             patch.dict(os.environ, {"XDG_DATA_HOME": ""}, clear=False):
            path = common._resolve_logs_dir()  # type: ignore[attr-defined]
            self.assertIn("lazy_blacktea/logs", str(path))

    def test_get_logger_creates_and_cleans_logs(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            # Fake logs dir and add stale log
            stale = os.path.join(td, "lazy_blacktea_19990101_000000.log")
            with open(stale, "w", encoding="utf-8") as f:
                f.write("old")

            # Reset module guard and route logs to temp dir
            common._logs_cleaned_today = False  # type: ignore[attr-defined]

            with patch("utils.common._resolve_logs_dir", return_value=__import__("pathlib").Path(td)):
                logger = common.get_logger("lazy_blacktea")
                logger.info("hello")

            # Stale file should be removed, new log should exist
            names = os.listdir(td)
            self.assertNotIn(os.path.basename(stale), names)
            self.assertTrue(any(name.startswith("lazy_blacktea_") and name.endswith(".log") for name in names))

    def test_read_file_and_path_helpers(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            fp = os.path.join(td, "a.txt")
            with open(fp, "w", encoding="utf-8") as f:
                f.write("x\n y \n")
            self.assertEqual(common.read_file(fp), ["x", "y"])
            self.assertEqual(common.read_file(os.path.join(td, "nope")), [])

            # Directory helpers
            out = common.make_gen_dir_path(os.path.join(td, "d1", "d2"))
            self.assertTrue(os.path.isdir(out))
            self.assertTrue(common.check_exists_dir(out))

            # Make extension and join
            p = common.make_file_extension(os.path.join(td, "f"), ".log")
            self.assertTrue(p.endswith(".log"))
            j = common.make_full_path(td, "b", "c")
            self.assertTrue(j.endswith("/b/c"))

    def test_time_and_validation_helpers(self) -> None:
        # timestamp_to_format_time returns fixed-length template
        s = common.timestamp_to_format_time(0)
        self.assertEqual(len(s), 15)
        self.assertIn("_", s)

        # ms input
        ms = int(1_600_000_000_000)
        s2 = common.timestamp_to_format_time(ms)
        self.assertEqual(len(s2), 15)

        # invalid input returns placeholder
        self.assertEqual(common.timestamp_to_format_time("bad"), "0000000000")

        # validate_and_create_output_path
        self.assertIsNone(common.validate_and_create_output_path("   "))
        with tempfile.TemporaryDirectory() as td:
            target = os.path.join(td, "x")
            norm = common.validate_and_create_output_path(target)
            self.assertTrue(os.path.isdir(norm))

    def test_subprocess_wrappers(self) -> None:
        import sys as _sys
        # sp_run_command with Python printing one line
        out = common.sp_run_command([_sys.executable, "-c", "print('hello')"])
        self.assertEqual(out, ["hello"])

        # mp_run_command similar
        out2 = common.mp_run_command([_sys.executable, "-c", "print('foo')"])
        self.assertEqual(out2, ["foo"])

        # run_command alias
        out3 = common.run_command([_sys.executable, "-c", "print('bar')"])
        self.assertEqual(out3, ["bar"])

        # create_cancellable_process
        proc = common.create_cancellable_process([_sys.executable, "-c", "print('x')"])
        self.assertIsNotNone(proc)
        if proc is not None:
            stdout, stderr = proc.communicate(timeout=5)
            self.assertEqual(proc.returncode, 0)


if __name__ == "__main__":
    unittest.main()

