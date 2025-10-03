#!/usr/bin/env python3
"""Unit tests for recording progress integration in WindowMain."""

import datetime
import sys
import types
from types import SimpleNamespace
from typing import Dict, List, Optional, Set
import unittest


if 'PyQt6' not in sys.modules:
    class _DummySignal:
        def connect(self, *args, **kwargs):
            return None

        def emit(self, *args, **kwargs):
            return None

    def _dummy_pyqt_signal(*_args, **_kwargs):
        return _DummySignal()

    def _dummy_pyqt_slot(*_args, **_kwargs):
        def _decorator(func):
            return func

        return _decorator

    class _DummyQTimer:
        def __init__(self, *args, **kwargs):
            self.timeout = _DummySignal()

        def start(self, *args, **kwargs):
            return None

        def stop(self):
            return None

        @staticmethod
        def singleShot(_milliseconds, callback):
            callback()

    def _make_dummy_class(name):
        def _init(self, *args, **kwargs):
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
            self.QObject = _make_dummy_class('QObject')

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

    sys.modules.setdefault('PyQt6', dummy_pyqt6)
    sys.modules.setdefault('PyQt6.QtWidgets', dummy_qtwidgets)
    sys.modules.setdefault('PyQt6.QtCore', dummy_qtcore)
    sys.modules.setdefault('PyQt6.QtGui', dummy_qtgui)


from lazy_blacktea_pyqt import WindowMain
from utils.recording_utils import RecordingOperationInProgressError


class RecordingProgressUITest(unittest.TestCase):
    """Validate recording progress callbacks update UI state."""

    def setUp(self):
        self.window = WindowMain.__new__(WindowMain)
        self.window.device_recordings = {}
        self.window.device_operations = {}
        self.console_messages = []
        self.warning_messages = []
        self.status_updates = 0

        self.window.write_to_console = lambda message: self.console_messages.append(message)
        self.window.error_handler = SimpleNamespace(
            show_warning=lambda title, message: self.warning_messages.append((title, message))
        )
        self.window.update_recording_status = lambda: setattr(self, 'status_updates', self.status_updates + 1)

    def test_segment_completed_event_updates_records(self):
        event_payload = {
            'type': 'segment_completed',
            'device_serial': 'ABC123',
            'device_name': 'PixelTest',
            'segment_index': 2,
            'segment_filename': 'record_part02.mp4',
            'duration_seconds': 12.5,
            'total_duration_seconds': 25.0,
            'output_path': '/tmp/output',
        }

        self.window._on_recording_progress_event(event_payload)

        self.assertIn('ABC123', self.window.device_recordings)
        record = self.window.device_recordings['ABC123']
        self.assertTrue(record['active'])
        self.assertEqual(record['device_name'], 'PixelTest')
        self.assertEqual(record['output_path'], '/tmp/output')
        self.assertIn('Recording', self.window.device_operations.values())
        self.assertEqual(len(record['segments']), 1)
        segment = record['segments'][0]
        self.assertEqual(segment['index'], 2)
        self.assertAlmostEqual(segment['duration_seconds'], 12.5)
        self.assertAlmostEqual(segment['total_duration_seconds'], 25.0)
        self.assertEqual(record['elapsed_before_current'], 25.0)
        self.assertIsNotNone(record['ongoing_start'])
        self.assertIsInstance(record['ongoing_start'], datetime.datetime)
        self.assertEqual(record['display_seconds'], 25)
        self.assertEqual(self.status_updates, 1)
        self.assertEqual(len(self.console_messages), 1)
        self.assertEqual(self.warning_messages, [])

    def test_error_event_marks_recording_inactive(self):
        self.window.device_recordings['XYZ789'] = {
            'active': True,
            'segments': [],
            'output_path': '/tmp/output',
            'device_name': 'GalaxyTest',
            'elapsed_before_current': 10.0,
            'ongoing_start': datetime.datetime.now(),
        }
        self.window.device_operations['XYZ789'] = 'Recording'

        event_payload = {
            'type': 'error',
            'device_serial': 'XYZ789',
            'device_name': 'GalaxyTest',
            'message': 'ADB disconnected',
        }

        self.window._on_recording_progress_event(event_payload)

        record = self.window.device_recordings['XYZ789']
        self.assertFalse(record['active'])
        self.assertIsNone(record['ongoing_start'])
        self.assertEqual(record['display_seconds'], 10)
        self.assertNotIn('XYZ789', self.window.device_operations)
        self.assertEqual(self.status_updates, 1)
        self.assertEqual(len(self.warning_messages), 1)
        self.assertIn('ADB disconnected', self.warning_messages[0][1])


class RecordingAsyncTaskTest(unittest.TestCase):
    """Validate helper task methods for asynchronous recording control."""

    class _FakeRecordingManager:
        def __init__(self):
            self.start_calls: List[tuple] = []
            self.stop_calls: List[Optional[str]] = []
            self.start_result: bool | Exception = True
            self.stop_result_map: Dict[Optional[str], List[str]] = {}
            self.is_recording_serials: Set[str] = set()

        def start_recording(self, devices, output_path, completion_callback=None, progress_callback=None):
            if isinstance(self.start_result, Exception):
                raise self.start_result
            serials = tuple(getattr(d, 'device_serial_num', None) for d in devices)
            self.start_calls.append((serials, output_path))
            return self.start_result

        def stop_recording(self, device_serial: Optional[str] = None):
            result_key = device_serial if device_serial is not None else None
            if result_key in self.stop_result_map and isinstance(self.stop_result_map[result_key], Exception):
                raise self.stop_result_map[result_key]
            self.stop_calls.append(device_serial)
            if device_serial is None:
                return list(self.stop_result_map.get(None, []))
            return list(self.stop_result_map.get(device_serial, [device_serial] if device_serial else []))

        def is_recording(self, device_serial: str) -> bool:
            return device_serial in self.is_recording_serials

    def setUp(self):
        self.window = WindowMain.__new__(WindowMain)
        self.window.device_recordings = {}
        self.window.device_operations = {}
        self.window.device_dict = {}
        self.window.write_to_console = lambda *_args, **_kwargs: None
        self.window.update_recording_status = lambda: None
        self.fake_manager = self._FakeRecordingManager()
        self.window.recording_manager = self.fake_manager

    def test_start_screen_record_task_success(self):
        devices = [SimpleNamespace(device_serial_num='SER1', device_model='Model-1')]
        result = self.window._start_screen_record_task(devices, output_path='/tmp/out')
        self.assertEqual(result, {'success': True})
        self.assertEqual(self.fake_manager.start_calls, [(('SER1',), '/tmp/out')])

    def test_start_screen_record_task_propagates_error(self):
        self.fake_manager.start_result = RecordingOperationInProgressError('busy')
        devices = [SimpleNamespace(device_serial_num='SER2', device_model='Model-2')]
        with self.assertRaises(RecordingOperationInProgressError):
            self.window._start_screen_record_task(devices, output_path='/tmp/out')

    def test_stop_screen_record_task_collects_serials(self):
        self.fake_manager.stop_result_map['SER3'] = ['SER3']
        self.fake_manager.stop_result_map['SER4'] = ['SER4']
        result = self.window._stop_screen_record_task(('SER3', 'SER4'))
        self.assertEqual(sorted(result['stopped']), ['SER3', 'SER4'])
        self.assertEqual(self.fake_manager.stop_calls, ['SER3', 'SER4'])

    def test_on_start_task_completed_updates_state(self):
        devices = [SimpleNamespace(device_serial_num='SER5', device_model='Model-5')]
        self.fake_manager.is_recording_serials.add('SER5')
        payload = {'success': True}
        self.window._on_start_screen_record_task_completed(payload, devices, '/tmp/out')
        self.assertIn('SER5', self.window.device_recordings)
        record = self.window.device_recordings['SER5']
        self.assertTrue(record['active'])
        self.assertEqual(record['output_path'], '/tmp/out')
        self.assertEqual(record['device_name'], 'Model-5')
        self.assertEqual(self.window.device_operations['SER5'], 'Recording')


if __name__ == '__main__':
    unittest.main()
