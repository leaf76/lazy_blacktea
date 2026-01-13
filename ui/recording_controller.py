"""Recording orchestration extracted from WindowMain."""

from __future__ import annotations

import datetime
from typing import Any, Callable, Dict, Iterable, List, Optional, TYPE_CHECKING

from PyQt6.QtCore import QObject

from ui.error_handler import ErrorCode
from ui.signal_payloads import RecordingEventType, RecordingProgressEvent
from utils import common, time_formatting
from utils.recording_utils import (
    RecordingManager,
    RecordingOperationInProgressError,
    get_active_start_recording_serials,
    get_active_stop_recording_serials,
    is_start_recording_operation_active,
    is_stop_recording_operation_active,
    validate_recording_path,
)
from utils.task_dispatcher import TaskContext, TaskHandle, get_task_dispatcher

if TYPE_CHECKING:  # pragma: no cover
    from lazy_blacktea_pyqt import WindowMain


logger = common.get_logger("recording_controller")


class RecordingController(QObject):
    """Manage screen recording flows for the main window."""

    def __init__(
        self,
        window: "WindowMain",
        *,
        path_validator: Callable[[str], str | None] = validate_recording_path,
        start_active_checker: Callable[[], bool] = is_start_recording_operation_active,
        stop_active_checker: Callable[[], bool] = is_stop_recording_operation_active,
        dispatcher=None,
        recording_manager: Optional[RecordingManager] = None,
    ) -> None:
        parent = window if isinstance(window, QObject) else None
        super().__init__(parent)
        self.window = window
        self._path_validator = path_validator
        self._start_active_checker = start_active_checker
        self._stop_active_checker = stop_active_checker
        if dispatcher is None:
            dispatcher = getattr(window, "_task_dispatcher", get_task_dispatcher())
        self._dispatcher = dispatcher
        self._recording_manager = recording_manager or window.recording_manager

    # ---- Public API ----------------------------------------------------------

    def start_screen_record(self) -> None:
        output_path = self.window.output_path_edit.text().strip()
        if not output_path:
            output_path = self.window._get_global_output_path()
        validated_path = self._path_validator(output_path)
        if not validated_path:
            self.window.error_handler.handle_error(
                ErrorCode.FILE_NOT_FOUND,
                "Please select a valid output directory first.",
            )
            return

        devices = self.window.get_checked_devices()

        if self._start_active_checker():
            active_serials = get_active_start_recording_serials()
            self.window._show_recording_operation_warning(
                "Screen Recording In Progress",
                "Another screen recording start request is already running.\nPlease wait for it to finish before starting a new one.",
                active_serials,
            )
            return

        already_recording = []
        for device in devices:
            if self._recording_manager.is_recording(device.device_serial_num):
                already_recording.append(
                    f"{device.device_model} ({device.device_serial_num[:8]}...)"
                )

        if already_recording:
            self.window.error_handler.show_warning(
                "Devices Already Recording",
                f"The following devices are already recording:\n\n"
                f"{chr(10).join(already_recording)}\n\n"
                f"Please stop these recordings first or select different devices.",
            )
            return

        from ui.signal_payloads import (
            DeviceOperationEvent,
            OperationType,
            OperationStatus,
        )

        operation_events = {}
        for device in devices:
            event = DeviceOperationEvent.create(
                device_serial=device.device_serial_num,
                operation_type=OperationType.RECORDING,
                device_name=device.device_model or device.device_serial_num,
                message="Starting recording...",
            )
            operation_events[device.device_serial_num] = event
            self.window._on_operation_started(event)

        device_count = len(devices)
        self.window.error_handler.show_info(
            "Screen Recording Started",
            f"Starting recording on {device_count} device(s)...\n\n"
            f"📍 Important Notes:\n"
            f"• ADB has a 3-minute recording limit per session\n"
            f"• Each device records independently\n"
            f"• You can stop recording manually or it will auto-stop\n\n"
            f"Files will be saved to: {validated_path}",
        )

        def recording_callback(
            device_name, device_serial, duration, filename, output_path
        ):
            if device_serial in operation_events:
                event = operation_events[device_serial]
                completed_event = event.with_status(
                    OperationStatus.COMPLETED,
                    message=f"Recording saved ({duration:.1f}s)",
                )
                self.window._on_operation_finished(completed_event)

            self.window.recording_stopped_signal.emit(
                device_name, device_serial, duration, filename, output_path
            )
            self.window.recording_state_cleared_signal.emit(device_serial)

        def recording_progress(event_payload: dict):
            try:
                event = RecordingProgressEvent.from_payload(event_payload)
            except ValueError:
                return
            self.window.recording_progress_signal.emit(event)

        devices_snapshot = list(devices)
        context = TaskContext(name="start_screen_record", category="recording")
        handle = self._dispatcher.submit(
            self._start_screen_record_task,
            devices_snapshot,
            output_path=validated_path,
            completion_callback=recording_callback,
            progress_callback=recording_progress,
            context=context,
        )
        handle.completed.connect(
            lambda payload,
            ds=devices_snapshot,
            path=validated_path: self._on_start_screen_record_task_completed(
                payload, ds, path
            )
        )
        handle.failed.connect(
            lambda exc: self._on_start_screen_record_task_failed(exc, operation_events)
        )
        self.window._register_background_handle(handle)

    def enqueue_stop(self, serials: Optional[List[str]]) -> None:
        context = TaskContext(name="stop_screen_record", category="recording")
        serials_snapshot = tuple(serials) if serials is not None else None
        handle = self._dispatcher.submit(
            self._stop_screen_record_task,
            serials_snapshot,
            context=context,
        )
        handle.completed.connect(
            lambda payload,
            requested=serials_snapshot: self._on_stop_screen_record_task_completed(
                payload, requested
            )
        )
        handle.failed.connect(self._on_stop_screen_record_task_failed)
        self.window._register_background_handle(handle)

    def stop_screen_record(self) -> None:
        if self._recording_manager.get_active_recordings_count() == 0:
            self.window.error_handler.show_warning(
                "No Active Recordings",
                "No active recordings found.\n\n"
                "Please start recording first, or the recordings may have already stopped automatically.",
            )
            return

        if self._stop_active_checker():
            active_serials = get_active_stop_recording_serials()
            self.window._show_recording_operation_warning(
                "Stop Recording In Progress",
                "Another stop recording request is already running.\nPlease wait for it to finish before issuing a new stop request.",
                active_serials,
            )
            return

        selected_devices = self.window.get_checked_devices()

        if selected_devices:
            devices_to_stop = [
                device.device_serial_num
                for device in selected_devices
                if self._recording_manager.is_recording(device.device_serial_num)
            ]

            if not devices_to_stop:
                statuses = getattr(
                    self._recording_manager, "get_all_recording_statuses", lambda: {}
                )()
                recording_list: list[str] = []
                device_dict = getattr(self.window, "device_dict", {})
                for serial, status in statuses.items():
                    if "Recording" in status and serial in device_dict:
                        device_name = device_dict[serial].device_model
                        recording_list.append(f"{device_name} ({serial[:8]}...)")

                details = (
                    "None of the selected devices are currently recording.\n\n"
                    f"Currently recording devices:\n{chr(10).join(recording_list)}\n\n"
                    "Please select the devices you want to stop recording."
                )
                self.window.error_handler.show_warning(
                    "No Selected Devices Recording", details
                )
                return

            self.enqueue_stop(devices_to_stop)
            return

        self.enqueue_stop(None)

    # ---- Background tasks ----------------------------------------------------

    def _start_screen_record_task(
        self,
        devices: List[Any],
        *,
        output_path: str,
        completion_callback: Optional[Callable] = None,
        progress_callback: Optional[Callable] = None,
        task_handle: Optional[TaskHandle] = None,
    ) -> Dict[str, Any]:
        success = self._recording_manager.start_recording(
            devices,
            output_path,
            completion_callback=completion_callback,
            progress_callback=progress_callback,
        )
        return {"success": bool(success)}

    def _on_start_screen_record_task_completed(
        self,
        payload: Dict[str, Any],
        devices: List[Any],
        output_path: str,
    ) -> None:
        if not payload.get("success"):
            self.window.error_handler.handle_error(
                ErrorCode.COMMAND_FAILED, "Failed to start recording"
            )
            return

        for device in devices:
            serial = device.device_serial_num
            if not self._recording_manager.is_recording(serial):
                continue
            self.window.device_recordings[serial] = {
                "active": True,
                "output_path": output_path,
                "device_name": device.device_model,
                "segments": [],
                "elapsed_before_current": 0.0,
                "ongoing_start": datetime.datetime.now(),
                "display_seconds": 0,
            }
            self.window.device_operations[serial] = "Recording"
            self.window.write_to_console(
                f"🎬 Recording started for {device.device_model} ({serial[:8]}...)"
            )

        self.window.update_recording_status()

    def _on_start_screen_record_task_failed(
        self, exc: Exception, operation_events: dict = None
    ) -> None:
        if operation_events:
            from ui.signal_payloads import OperationStatus

            for serial, event in operation_events.items():
                failed_event = event.with_status(
                    OperationStatus.FAILED, error_message=str(exc)
                )
                self.window._on_operation_finished(failed_event)

        if isinstance(exc, RecordingOperationInProgressError):
            self.window._show_recording_operation_warning(  # type: ignore[attr-defined]
                "Screen Recording In Progress",
                "Another screen recording start request is already running.\nPlease wait for it to finish before starting a new one.",
                get_active_start_recording_serials(),
            )
            return

        logger.error(
            "Asynchronous screen recording start failed: %s", exc, exc_info=True
        )
        self.window.error_handler.handle_error(
            ErrorCode.COMMAND_FAILED,
            f"Failed to start recording: {exc}",
        )

    def _stop_screen_record_task(
        self,
        serials: Optional[Iterable[str]],
        *,
        task_handle: Optional[TaskHandle] = None,
    ) -> Dict[str, Any]:
        if serials is None:
            stopped = self._recording_manager.stop_recording()
        else:
            stopped: List[str] = []
            for serial in serials:
                stopped.extend(self._recording_manager.stop_recording(serial))
        return {"stopped": stopped}

    def _on_stop_screen_record_task_completed(
        self,
        payload: Dict[str, Any],
        requested_serials: Optional[Iterable[str]],
    ) -> None:
        stopped = list(payload.get("stopped") or [])
        if not stopped:
            logger.info(
                "Stop recording request completed with no active sessions to stop"
            )
            return

        logger.info("Stopped recording on %s device(s): %s", len(stopped), stopped)
        for serial in stopped:
            device_info = (
                self.window.device_dict.get(serial)
                if hasattr(self.window, "device_dict")
                else None
            )
            device_name = getattr(device_info, "device_model", serial)
            self.window.write_to_console(
                f"🛑 Stop recording request completed for {device_name} ({serial[:8]}...)"
            )

    def _on_stop_screen_record_task_failed(self, exc: Exception) -> None:
        if isinstance(exc, RecordingOperationInProgressError):
            self.window._show_recording_operation_warning(
                "Stop Recording In Progress",
                "Another stop recording request is already running.\nPlease wait for it to finish before issuing a new stop request.",
                get_active_stop_recording_serials(),
            )
            return

        logger.error("Asynchronous stop recording failed: %s", exc, exc_info=True)
        self.window.error_handler.handle_error(
            ErrorCode.COMMAND_FAILED,
            f"Failed to stop recording: {exc}",
        )

    # ---- Signal handlers -----------------------------------------------------

    def handle_recording_stopped(
        self, device_name, device_serial, duration, filename, output_path
    ):
        self.window.show_info(
            "Recording Stopped",
            f"Recording stopped for {device_name}\n"
            f"Duration: {duration}\n"
            f"File: {filename}.mp4\n"
            f"Location: {output_path}",
        )

        record = self.window.device_recordings.setdefault(
            device_serial,
            {
                "segments": [],
                "elapsed_before_current": 0.0,
                "ongoing_start": None,
                "display_seconds": 0,
            },
        )
        record["active"] = False
        record["last_duration"] = duration
        record["last_filename"] = f"{filename}.mp4"
        record["output_path"] = output_path
        record["device_name"] = device_name
        record["elapsed_before_current"] = time_formatting.parse_duration_to_seconds(
            duration
        )
        record["ongoing_start"] = None
        record["display_seconds"] = int(record["elapsed_before_current"])

        if device_serial in self.window.device_operations:
            del self.window.device_operations[device_serial]

        self.window.write_to_console(
            f"✅ Recording stopped for {device_name} ({device_serial[:8]}...) -> {filename}.mp4 ({duration})"
        )
        self.window.update_recording_status()

    def handle_recording_state_cleared(self, device_serial):
        if device_serial in self.window.device_recordings:
            self.window.device_recordings[device_serial]["active"] = False
        if device_serial in self.window.device_operations:
            del self.window.device_operations[device_serial]
        self.window.device_manager.force_refresh()
        self.window.update_recording_status()

    def handle_progress_event(self, event: RecordingProgressEvent | Dict[str, Any]):
        if isinstance(event, dict):
            try:
                event = RecordingProgressEvent.from_payload(event)
            except ValueError:
                return
        if event.event_type == RecordingEventType.SEGMENT_COMPLETED:
            self._handle_segment_completed(event)
        elif event.event_type == RecordingEventType.ERROR:
            self._handle_recording_error(event)

    # ---- Helper operations ---------------------------------------------------

    def _handle_segment_completed(self, event: RecordingProgressEvent) -> None:
        device_serial = event.device_serial
        device_name = event.device_name or device_serial
        record = self.window.device_recordings.setdefault(
            device_serial,
            {
                "active": True,
                "output_path": event.output_path,
                "device_name": device_name,
                "segments": [],
                "elapsed_before_current": 0.0,
                "ongoing_start": datetime.datetime.now(),
                "display_seconds": 0,
            },
        )
        record["device_name"] = device_name
        record["active"] = True
        if event.output_path:
            record["output_path"] = event.output_path
        record.setdefault("segments", [])
        record["segments"].append(
            {
                "index": event.segment_index,
                "filename": event.segment_filename or "unknown",
                "duration_seconds": event.duration_seconds or 0.0,
                "total_duration_seconds": event.total_duration_seconds or 0.0,
            }
        )
        if len(record["segments"]) > 20:
            record["segments"] = record["segments"][-20:]

        self.window.device_operations[device_serial] = "Recording"
        if event.total_duration_seconds is not None:
            record["elapsed_before_current"] = event.total_duration_seconds
            if event.request_origin == "user":
                record["ongoing_start"] = None
            else:
                record["ongoing_start"] = datetime.datetime.now()
            record["display_seconds"] = int(event.total_duration_seconds)

        duration_display = f"{(event.duration_seconds or 0.0):.1f}s"
        segment_label = (
            f"{event.segment_index:02d}"
            if isinstance(event.segment_index, int)
            else "?"
        )
        self.window.write_to_console(
            f"🎬 Segment {segment_label} saved for {device_name} ({device_serial[:8]}...) -> "
            f"{event.segment_filename or 'unknown'} ({duration_display})"
        )
        self.window.update_recording_status()

    def _handle_recording_error(self, event: RecordingProgressEvent) -> None:
        device_serial = event.device_serial
        device_name = event.device_name or device_serial
        message = event.message or "Unknown error"
        self.window.write_to_console(
            f"❌ Recording error on {device_name} ({device_serial[:8]}...): {message}"
        )
        self.window.error_handler.show_warning(
            "Recording Warning",
            f"Device {device_name} encountered an issue:\n{message}",
        )
        if device_serial in self.window.device_recordings:
            record = self.window.device_recordings[device_serial]
            record["active"] = False
            record["ongoing_start"] = None
            record["display_seconds"] = int(record.get("elapsed_before_current", 0.0))
        if device_serial in self.window.device_operations:
            del self.window.device_operations[device_serial]
        self.window.update_recording_status()
