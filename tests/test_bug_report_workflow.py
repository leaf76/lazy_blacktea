#!/usr/bin/env python3
"""Bug report workflow regression tests."""

import os
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

import types
import sys


class _DummySignal:
    """Lightweight stand-in for PyQt signals used in tests."""

    def __init__(self):
        self._subscribers = []

    def connect(self, slot):  # pragma: no cover - helpers for completeness
        self._subscribers.append(slot)

    def emit(self, *args, **kwargs):
        for slot in list(self._subscribers):
            slot(*args, **kwargs)


class _DummySignalDescriptor:
    def __set_name__(self, owner, name):
        self._storage_name = f"__signal_{name}"

    def __get__(self, instance, owner):
        if instance is None:
            return self
        signal = getattr(instance, self._storage_name, None)
        if signal is None:
            signal = _DummySignal()
            setattr(instance, self._storage_name, signal)
        return signal


def _dummy_pyqt_signal(*_args, **_kwargs):
    return _DummySignalDescriptor()


def _dummy_pyqt_slot(*_args, **_kwargs):
    def _decorator(func):
        return func

    return _decorator


class _DummyQTimer:
    @staticmethod
    def singleShot(_msec, callback):
        callback()


class _DummyQObject:
    def __init__(self, *_args, **_kwargs):
        return None


class _DummyMutex:
    def lock(self):
        return None

    def unlock(self):
        return None


class _DummyMutexLocker:
    def __init__(self, mutex):
        self._mutex = mutex
        self._mutex.lock()

    def __enter__(self):  # pragma: no cover - context manager compatibility
        return self

    def __exit__(self, _exc_type, _exc_value, _traceback):
        self._mutex.unlock()
        return False


class _DummyQRunnable:
    def __init__(self, *args, **_kwargs):
        self._auto_delete = False

    def setAutoDelete(self, value):  # pragma: no cover - compatibility shim
        self._auto_delete = bool(value)

    def run(self):  # pragma: no cover - override in subclasses
        return None


class _DummyThreadPool:
    _instance = None

    def __init__(self):
        self._max_thread_count = None

    @classmethod
    def globalInstance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def setMaxThreadCount(self, count):  # pragma: no cover - configuration helper
        self._max_thread_count = count

    def start(self, runnable):
        runnable.run()


dummy_qtcore = types.ModuleType("PyQt6.QtCore")
dummy_qtcore.QObject = _DummyQObject
dummy_qtcore.pyqtSignal = _dummy_pyqt_signal
dummy_qtcore.pyqtSlot = _dummy_pyqt_slot
dummy_qtcore.QTimer = _DummyQTimer
dummy_qtcore.QMutex = _DummyMutex
dummy_qtcore.QMutexLocker = _DummyMutexLocker
dummy_qtcore.QRunnable = _DummyQRunnable
dummy_qtcore.QThreadPool = _DummyThreadPool
dummy_qtcore.Qt = types.SimpleNamespace(
    Orientation=types.SimpleNamespace(Horizontal=1, Vertical=2),
    ItemDataRole=types.SimpleNamespace(UserRole=32, DisplayRole=0, DecorationRole=1),
    AlignmentFlag=types.SimpleNamespace(AlignLeft=1, AlignVCenter=2),
    CheckState=types.SimpleNamespace(Checked=2, PartiallyChecked=1, Unchecked=0),
    SortOrder=types.SimpleNamespace(AscendingOrder=0, DescendingOrder=1),
)


def _core_getattr(name):
    value = type(name, (), {})
    setattr(dummy_qtcore, name, value)
    return value


dummy_qtcore.__getattr__ = _core_getattr

class _WidgetModule(types.ModuleType):
    def __getattr__(self, name):
        value = type(name, (), {})
        setattr(self, name, value)
        return value

dummy_qtwidgets = _WidgetModule("PyQt6.QtWidgets")
dummy_qtwidgets.QFileDialog = object

class _GuiModule(types.ModuleType):
    def __getattr__(self, name):
        value = type(name, (), {})
        setattr(self, name, value)
        return value

dummy_qtgui = _GuiModule("PyQt6.QtGui")

dummy_pyqt6 = types.ModuleType("PyQt6")
dummy_pyqt6.QtCore = dummy_qtcore
dummy_pyqt6.QtWidgets = dummy_qtwidgets
dummy_pyqt6.QtGui = dummy_qtgui

sys.modules["PyQt6"] = dummy_pyqt6
sys.modules["PyQt6.QtCore"] = dummy_qtcore
sys.modules["PyQt6.QtWidgets"] = dummy_qtwidgets
sys.modules["PyQt6.QtGui"] = dummy_qtgui

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_TEST_HOME = Path(__file__).resolve().parents[1] / ".test_home_bug_report"
os.environ["HOME"] = str(_TEST_HOME)
(_TEST_HOME / ".lazy_blacktea_logs").mkdir(parents=True, exist_ok=True)

from utils import adb_models, adb_tools, file_generation_utils
from ui import file_operations_manager


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

    def test_generate_bug_report_batch_rejects_parallel_invocation(self):
        """Concurrent bug report requests should be rejected while a run is active."""

        devices = [self.success_device]

        start_event = threading.Event()
        release_event = threading.Event()
        completion_event = threading.Event()
        self.addCleanup(release_event.set)

        def blocking_generate(_serial, filepath, timeout=300):
            start_event.set()
            if not release_event.wait(timeout=5.0):
                raise TimeoutError("Test gate did not release bug report worker in time")
            return {"success": True, "output_path": f"{filepath}.zip"}

        with patch("utils.file_generation_utils.adb_tools.generate_bug_report_device", side_effect=blocking_generate), \
             patch("utils.file_generation_utils.common.current_format_time_utc", return_value="20250101_000000"), \
             patch("utils.file_generation_utils.os.makedirs"):
            file_generation_utils.generate_bug_report_batch(
                devices,
                "/tmp/output",
                lambda *_args, **_kwargs: completion_event.set(),
                progress_callback=lambda *_args, **_kwargs: None,
            )

            self.assertTrue(start_event.wait(timeout=1.0), "Bug report worker did not start in time")

            with self.assertRaises(file_generation_utils.BugReportInProgressError):
                file_generation_utils.generate_bug_report_batch(
                    devices,
                    "/tmp/output",
                    lambda *_args, **_kwargs: None,
                    progress_callback=lambda *_args, **_kwargs: None,
                )

            release_event.set()
            self.assertTrue(completion_event.wait(timeout=1.0), "Bug report worker did not finish in time")

    def test_file_operations_manager_rejects_when_global_run_active(self):
        """File operations manager should prevent duplicate runs across instances."""

        class _WindowStub:
            def __init__(self):
                self.warned = []

            def show_warning(self, title, message):
                self.warned.append((title, message))

            def show_error(self, title, message):  # pragma: no cover - defensive for test stub
                raise AssertionError(f"Unexpected error dialog: {title}: {message}")

        window = _WindowStub()
        manager = file_operations_manager.FileOperationsManager(window)

        failures = []

        def on_failure(message):
            failures.append(message)

        with patch("ui.file_operations_manager.validate_file_output_path", return_value="/tmp/output"), \
             patch("ui.file_operations_manager.is_bug_report_generation_active", return_value=True), \
             patch("ui.file_operations_manager.get_active_bug_report_serials", return_value=[self.success_device.device_serial_num]), \
             patch("ui.file_operations_manager.generate_bug_report_batch") as mock_generate:
            result = manager.generate_android_bug_report(
                [self.success_device],
                "/tmp/output",
                on_failure=on_failure,
            )

        self.assertFalse(result)
        self.assertTrue(failures)
        self.assertIn("Bug report already in progress", failures[0])
        self.assertTrue(window.warned)
        mock_generate.assert_not_called()

    def test_file_operations_manager_waits_for_bug_report_completion(self):
        """Manager should emit completion only after bug report workers finish."""

        window = types.SimpleNamespace(
            show_warning=lambda *_args, **_kwargs: None,
            show_error=lambda *_args, **_kwargs: None,
        )
        manager = file_operations_manager.FileOperationsManager(window)

        devices = [self.success_device]
        start_event = threading.Event()
        release_event = threading.Event()
        self.addCleanup(release_event.set)

        def fake_batch(_devices, _output_path, callback, progress_callback=None, completion_event=None):
            start_event.set()
            if not release_event.wait(timeout=1.0):
                raise TimeoutError('Release signal not received in time')
            callback(
                'Bug Report Complete',
                {'summary': 'done', 'output_path': _output_path},
                len(_devices),
                '🐛'
            )
            if completion_event is not None:
                completion_event.set()

        with patch('ui.file_operations_manager.validate_file_output_path', return_value='/tmp/output'), \
             patch('ui.file_operations_manager.generate_bug_report_batch', side_effect=fake_batch), \
             patch('utils.file_generation_utils.os.makedirs'), \
             patch('utils.file_generation_utils.common.current_format_time_utc', return_value='20250101_000000'):

            def release_worker():
                self.assertTrue(start_event.wait(timeout=0.2), 'Bug report worker did not start in time')
                time.sleep(0.05)
                release_event.set()

            threading.Thread(target=release_worker, daemon=True).start()

            start = time.perf_counter()
            result = manager._generate_bug_report_task(devices, output_path='/tmp/output')
            elapsed = time.perf_counter() - start

        self.assertGreaterEqual(elapsed, 0.05)
        self.assertEqual(result['success_count'], len(devices))

    def test_device_availability_check(self):
        """確認 get-state 輸出 device 時視為連線"""

        with patch("utils.adb_tools.common.run_command", return_value=["device"]):
            self.assertTrue(adb_tools._is_device_available("serial-123"))


if __name__ == "__main__":
    unittest.main()
