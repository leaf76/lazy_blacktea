import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock

from PyQt6.QtCore import QObject

from ui.recording_controller import RecordingController
from ui.signal_payloads import RecordingEventType
from ui.error_handler import ErrorCode


class DummySignal(QObject):
    def __init__(self):
        super().__init__()
        self._callbacks = []

    def connect(self, callback):  # pragma: no cover - Qt compatibility shim
        self._callbacks.append(callback)


class RecordingControllerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.dispatcher = MagicMock()
        self.handle = SimpleNamespace(
            completed=DummySignal(),
            failed=DummySignal(),
        )
        self.dispatcher.submit.return_value = self.handle
        self.recording_manager = MagicMock()
        self.recording_manager.start_recording.return_value = True
        self.recording_manager.is_recording.return_value = False
        self.recording_manager.get_active_recordings_count.return_value = 1
        self.recording_manager.get_all_recording_statuses.return_value = {}

        self.error_handler = MagicMock()
        self.output_path_edit = MagicMock()
        self.output_path_edit.text.return_value = ' /tmp/records '

        self.window = SimpleNamespace(
            output_path_edit=self.output_path_edit,
            error_handler=self.error_handler,
            recording_manager=self.recording_manager,
            device_manager=MagicMock(),
            get_checked_devices=MagicMock(return_value=[SimpleNamespace(
                device_serial_num='SER12345',
                device_model='Pixel 7 Pro',
            )]),
            write_to_console=MagicMock(),
            recording_stopped_signal=DummySignal(),
            recording_state_cleared_signal=DummySignal(),
            recording_progress_signal=DummySignal(),
            device_recordings={},
            device_operations={},
            _task_dispatcher=self.dispatcher,
            _register_background_handle=MagicMock(),
            _show_recording_operation_warning=MagicMock(),
            device_dict={'SER12345': SimpleNamespace(device_model='Pixel 7 Pro')},
        )
        self.window.recording_manager = self.recording_manager
        self.window.error_handler.show_warning = MagicMock()

        self.controller = RecordingController(
            window=self.window,
            path_validator=lambda path: path.strip(),
            start_active_checker=lambda: False,
            stop_active_checker=lambda: False,
        )

    def test_start_screen_record_with_invalid_path_reports_error(self) -> None:
        controller = RecordingController(
            window=self.window,
            path_validator=lambda _: '',
            start_active_checker=lambda: False,
            stop_active_checker=lambda: False,
        )
        controller.start_screen_record()

        self.error_handler.handle_error.assert_called_once_with(
            ErrorCode.FILE_NOT_FOUND,
            'Please select a valid output directory first.',
        )

    def test_start_screen_record_dispatches_background_task(self) -> None:
        self.controller.start_screen_record()

        self.dispatcher.submit.assert_called_once()
        args, kwargs = self.dispatcher.submit.call_args
        submitted = args[0]
        self.assertIs(submitted.__self__, self.controller)
        self.assertIs(submitted.__func__, self.controller._start_screen_record_task.__func__)
        self.assertEqual(kwargs['context'].name, 'start_screen_record')
        self.window._register_background_handle.assert_called_once_with(self.handle)

    def test_recording_event_type_enum_contains_segment_value(self) -> None:
        self.assertEqual(RecordingEventType.SEGMENT_COMPLETED.value, 'segment_completed')

    def test_stop_screen_record_with_no_active_sessions_shows_warning(self) -> None:
        self.recording_manager.get_active_recordings_count.return_value = 0
        self.controller.stop_screen_record()

        self.window.error_handler.show_warning.assert_called_once()
        self.dispatcher.submit.assert_not_called()

    def test_stop_screen_record_when_stop_in_progress_shows_operation_warning(self) -> None:
        controller = RecordingController(
            window=self.window,
            path_validator=lambda path: path,
            start_active_checker=lambda: False,
            stop_active_checker=lambda: True,
        )
        controller.stop_screen_record()

        self.window._show_recording_operation_warning.assert_called_once()

    def test_stop_screen_record_dispatches_with_selected_devices(self) -> None:
        self.recording_manager.is_recording.return_value = True
        self.controller.stop_screen_record()

        self.dispatcher.submit.assert_called()
        submitted = self.dispatcher.submit.call_args[0][0]
        self.assertIs(submitted.__self__, self.controller)
        self.assertIs(submitted.__func__, self.controller._stop_screen_record_task.__func__)
        serials_snapshot = self.dispatcher.submit.call_args[0][1]
        self.assertEqual(serials_snapshot, ('SER12345',))


if __name__ == '__main__':
    unittest.main()
