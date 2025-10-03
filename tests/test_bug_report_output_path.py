#!/usr/bin/env python3
"""Unit tests ensuring bug report output path matches ADB Tools setting."""

import sys
import types
import unittest


if 'PyQt6' not in sys.modules or not hasattr(sys.modules.get('PyQt6', types.ModuleType('PyQt6')), 'QtGui'):
    class _DummySignal:
        def connect(self, *_args, **_kwargs):
            return None

        def emit(self, *_args, **_kwargs):
            return None

    def _dummy_pyqt_signal(*_args, **_kwargs):
        return _DummySignal()

    def _dummy_pyqt_slot(*_args, **_kwargs):
        def _decorator(func):
            return func

        return _decorator

    class _DummyQTimer:
        def __init__(self, *_args, **_kwargs):
            self.timeout = _DummySignal()

        def start(self, *_args, **_kwargs):
            return None

        def stop(self):
            return None

        @staticmethod
        def singleShot(_milliseconds, callback):
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

        def __enter__(self):  # pragma: no cover - helper for context manager usage
            return self

        def __exit__(self, _exc_type, _exc, _tb):
            self._mutex.unlock()
            return False

    class _DummyQRunnable:
        def __init__(self, *args, **kwargs):
            self._auto_delete = False

        def setAutoDelete(self, value):  # pragma: no cover - compatibility shim
            self._auto_delete = bool(value)

        def run(self):  # pragma: no cover - overridden in subclasses
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

        def setMaxThreadCount(self, value):  # pragma: no cover - configuration helper
            self._max_thread_count = value

        def start(self, runnable):
            runnable.run()

    def _make_dummy_class(name):
        def _init(self, *_args, **_kwargs):
            return None

        return type(name, (), {"__init__": _init})

    class _LazyWidgetModule(types.ModuleType):
        def __getattr__(self, name):
            value = _make_dummy_class(name)
            setattr(self, name, value)
            return value

    dummy_qtwidgets = _LazyWidgetModule('PyQt6.QtWidgets')

    class _LazyCoreModule(types.ModuleType):
        def __init__(self, name):
            super().__init__(name)
            self.Qt = types.SimpleNamespace(
                Orientation=types.SimpleNamespace(Horizontal=1, Vertical=2),
                ItemDataRole=types.SimpleNamespace(UserRole=32, DisplayRole=0, DecorationRole=1),
                AlignmentFlag=types.SimpleNamespace(AlignLeft=1, AlignVCenter=2),
                CheckState=types.SimpleNamespace(Checked=2, PartiallyChecked=1, Unchecked=0),
                SortOrder=types.SimpleNamespace(AscendingOrder=0, DescendingOrder=1),
            )
            self.QTimer = _DummyQTimer
            self.pyqtSignal = _dummy_pyqt_signal
            self.pyqtSlot = _dummy_pyqt_slot
            self.QObject = _DummyQObject
            self.QMutex = _DummyMutex
            self.QMutexLocker = _DummyMutexLocker
            self.QRunnable = _DummyQRunnable
            self.QThreadPool = _DummyThreadPool

        def __getattr__(self, name):
            value = _make_dummy_class(name)
            setattr(self, name, value)
            return value

    dummy_qtcore = _LazyCoreModule('PyQt6.QtCore')

    class _LazyGuiModule(types.ModuleType):
        def __getattr__(self, name):
            value = _make_dummy_class(name)
            setattr(self, name, value)
            return value

    dummy_qtgui = _LazyGuiModule('PyQt6.QtGui')

    dummy_pyqt6 = types.ModuleType('PyQt6')
    dummy_pyqt6.QtWidgets = dummy_qtwidgets
    dummy_pyqt6.QtCore = dummy_qtcore
    dummy_pyqt6.QtGui = dummy_qtgui

    sys.modules['PyQt6'] = dummy_pyqt6
    sys.modules['PyQt6.QtWidgets'] = dummy_qtwidgets
    sys.modules['PyQt6.QtCore'] = dummy_qtcore
    sys.modules['PyQt6.QtGui'] = dummy_qtgui


from lazy_blacktea_pyqt import WindowMain
from utils import adb_models


class _LineEditStub:
    def __init__(self, text: str):
        self._text = text

    def text(self) -> str:
        return self._text

    def setText(self, text: str):
        self._text = text


class _FileOperationsManagerStub:
    def __init__(self):
        self.in_progress = False
        self.active_devices: list[str] = []
        self.calls: list[dict[str, object]] = []
        self.discovery_calls: list[dict[str, object]] = []

    def get_active_bug_report_devices(self) -> list[str]:
        return list(self.active_devices)

    def is_bug_report_in_progress(self) -> bool:
        return self.in_progress

    def generate_android_bug_report(self, devices, output_path, *, on_complete=None, on_failure=None):
        self.calls.append(
            {
                'devices': list(devices),
                'output_path': output_path,
                'on_complete': on_complete,
                'on_failure': on_failure,
            }
        )
        return True

    def generate_device_discovery_file(self, devices, output_path):
        self.discovery_calls.append(
            {
                'devices': list(devices),
                'output_path': output_path,
            }
        )


class BugReportOutputPathTests(unittest.TestCase):
    """Verify WindowMain delegates bug reports to ADB Tools output directory."""

    def setUp(self):
        self.window = WindowMain.__new__(WindowMain)
        self.window.output_path_edit = _LineEditStub('/tmp/adb_tools_path')
        self.window.file_gen_output_path_edit = _LineEditStub('/tmp/device_file_path')
        self.window.file_operations_manager = _FileOperationsManagerStub()

        device = adb_models.DeviceInfo(
            device_serial_num='SER123',
            device_usb='usb1',
            device_prod='prod1',
            device_model='Pixel',
            wifi_is_on=True,
            bt_is_on=False,
            android_ver='14',
            android_api_level='34',
            gms_version='1',
            build_fingerprint='build/1',
        )
        self.devices = [device]

        self.window.get_checked_devices = lambda: list(self.devices)
        self.window.show_warning = lambda *_args, **_kwargs: None
        self.window._log_operation_start = lambda *_args, **_kwargs: None
        self.window._log_operation_complete = lambda *_args, **_kwargs: None
        self.window._log_operation_failure = lambda *_args, **_kwargs: None
        self.window._execute_with_operation_logging = lambda _op, action, **_kwargs: action()

    def test_generate_bug_report_uses_adb_tools_output_path(self):
        """Bug report generation should use the ADB Tools output path."""
        WindowMain.generate_android_bug_report(self.window)

        self.assertTrue(self.window.file_operations_manager.calls, 'Manager was not invoked')
        call = self.window.file_operations_manager.calls[-1]
        self.assertEqual(call['output_path'], '/tmp/adb_tools_path')
        self.assertEqual(call['devices'][0].device_serial_num, 'SER123')

    def test_generate_device_discovery_uses_adb_tools_output_path(self):
        """Device discovery export should honour the ADB Tools output path."""
        WindowMain.generate_device_discovery_file(self.window)

        self.assertTrue(self.window.file_operations_manager.discovery_calls, 'Discovery was not invoked')
        call = self.window.file_operations_manager.discovery_calls[-1]
        self.assertEqual(call['output_path'], '/tmp/adb_tools_path')
        self.assertEqual(call['devices'][0].device_serial_num, 'SER123')

    def test_bug_report_bootstraps_output_path_when_manager_available(self):
        """Bug report generation ensures an output path via manager bootstrap."""

        class _OutputPathManagerStub:
            def __init__(self):
                self.ensure_calls = 0

            def ensure_primary_output_path(self):
                self.ensure_calls += 1
                return '/tmp/adb_tools_path'

            def get_adb_tools_output_path(self):
                return ''

        path_manager = _OutputPathManagerStub()
        self.window.output_path_manager = path_manager

        WindowMain.generate_android_bug_report(self.window)

        self.assertEqual(path_manager.ensure_calls, 1)
        self.assertTrue(self.window.file_operations_manager.calls, 'Manager should be invoked with ensured path')
        call = self.window.file_operations_manager.calls[-1]
        self.assertEqual(call['output_path'], '/tmp/adb_tools_path')


if __name__ == '__main__':  # pragma: no cover
    unittest.main()
