#!/usr/bin/env python3
"""Extra unit tests for utils.qt_dependency_checker focusing on non-destructive paths."""

import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils import qt_dependency_checker as qdc


class TestQtDependencyCheckerExtra(unittest.TestCase):
    def test_get_linux_distro_unknown_when_os_release_missing(self) -> None:
        with patch("builtins.open", side_effect=FileNotFoundError()):
            self.assertEqual(qdc.get_linux_distro(), "unknown")

    def test_check_and_fix_qt_dependencies_noop_on_non_linux(self) -> None:
        with patch("platform.system", return_value="Darwin"):
            self.assertTrue(qdc.check_and_fix_qt_dependencies())

    def test_install_dependencies_ubuntu_success(self) -> None:
        # Simulate successful subprocess.run with check=True
        class Dummy:
            def __init__(self):
                self.returncode = 0

        with patch("subprocess.run", return_value=Dummy()):
            self.assertTrue(qdc.install_dependencies_ubuntu())

    def test_install_dependencies_ubuntu_failure(self) -> None:
        call_count = {"n": 0}

        def fake_run(*args, **kwargs):
            call_count["n"] += 1
            if call_count["n"] == 1:
                class Dummy:
                    returncode = 0
                return Dummy()
            raise subprocess.CalledProcessError(1, args[0], stderr="failed")

        import subprocess
        with patch("subprocess.run", side_effect=fake_run):
            self.assertFalse(qdc.install_dependencies_ubuntu())

    def test_test_qt_platform_plugin_succeeds_offscreen(self) -> None:
        # Ensure offscreen to avoid platform plugin issues in CI
        with patch.dict(os.environ, {"QT_QPA_PLATFORM": "offscreen"}, clear=False):
            ok, err = qdc.test_qt_platform_plugin()
            self.assertTrue(ok)
            self.assertIsNone(err)

    def test_check_and_fix_qt_dependencies_ci_path_on_linux(self) -> None:
        # In CI on Linux, it should set offscreen and return True early
        with patch("platform.system", return_value="Linux"):
            with patch.dict(os.environ, {"CI": "1"}, clear=False):
                self.assertTrue(qdc.check_and_fix_qt_dependencies())
                self.assertEqual(os.environ.get("QT_QPA_PLATFORM"), "offscreen")


if __name__ == "__main__":
    unittest.main()
