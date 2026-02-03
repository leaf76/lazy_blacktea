import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ui.terminal_manager import TerminalManager
from utils import adb_models
from utils.task_dispatcher import TaskContext, TaskHandle, TaskCancelledError


class _FakeProcess:
    def __init__(self, *, returncode: int = 0):
        self.returncode = returncode
        self._terminated = False
        self._killed = False

    def poll(self):
        return None

    def terminate(self):
        self._terminated = True

    def wait(self, timeout=None):
        return self.returncode

    def kill(self):
        self._killed = True

    def communicate(self, timeout=None):
        return b"ok\n", b""


class _DummyWindow:
    def get_checked_devices(self):
        return []


def _device(serial: str, model: str = "") -> adb_models.DeviceInfo:
    return adb_models.DeviceInfo(
        device_serial_num=serial,
        device_usb="usb",
        device_prod="prod",
        device_model=model,
        wifi_is_on=False,
        bt_is_on=False,
        android_ver="",
        android_api_level="",
        gms_version="",
        build_fingerprint="",
    )


class TerminalManagerTest(unittest.TestCase):
    def test_execute_shell_on_devices_reports_missing_process(self):
        manager = TerminalManager(_DummyWindow())
        devices = [_device("S1", "Model1"), _device("S2", "Model2")]
        fake_proc = _FakeProcess(returncode=0)

        with patch(
            "utils.adb_tools.run_cancellable_adb_shell_command",
            return_value={"S1": fake_proc, "S2": None},
        ), patch.object(
            TerminalManager,
            "_collect_process_output",
            return_value=(b"hello\n", b""),
        ):
            payload = manager._execute_shell_on_devices(devices, "echo hello")

        results = payload["results"]
        self.assertIn("S1", results)
        self.assertIn("S2", results)
        self.assertFalse(results["S1"]["is_error"])
        self.assertTrue(results["S2"]["is_error"])
        self.assertIn("Failed to start adb process", results["S2"]["lines"][0])

    def test_execute_shell_on_devices_honours_task_cancellation(self):
        manager = TerminalManager(_DummyWindow())
        devices = [_device("S1")]
        task_handle = TaskHandle(TaskContext(name="test"))
        task_handle.cancel()

        fake_proc = _FakeProcess(returncode=0)

        with patch(
            "utils.adb_tools.run_cancellable_adb_shell_command",
            return_value={"S1": fake_proc},
        ), patch.object(TerminalManager, "_terminate_processes") as terminate_mock:
            with self.assertRaises(TaskCancelledError):
                manager._execute_shell_on_devices(
                    devices, "echo hello", task_handle=task_handle
                )
            terminate_mock.assert_called()


if __name__ == "__main__":
    unittest.main()

