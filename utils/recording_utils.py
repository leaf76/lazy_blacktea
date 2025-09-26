"""Recording utilities for device screen recording operations."""

import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable, Dict, List, Optional

from config.constants import RecordingConstants
from utils import adb_models, adb_tools, common


@dataclass
class RecordingSegment:
    """Metadata for an individual recording segment."""

    index: int
    filename: str
    started_at: datetime
    ended_at: Optional[datetime] = None

    @property
    def duration_seconds(self) -> float:
        if not self.ended_at:
            return 0.0
        elapsed = (self.ended_at - self.started_at).total_seconds()
        return max(elapsed, 0.0)


@dataclass
class RecordingInfo:
    """Recording information for a device."""

    device_serial: str
    device_name: str
    start_time: datetime
    output_path: str
    base_filename: str
    is_active: bool = True
    segment_index: int = 0
    total_duration_seconds: float = 0.0
    segments: List[RecordingSegment] = field(default_factory=list)
    segment_thread: Optional[threading.Thread] = field(default=None, repr=False, compare=False)


class RecordingManager:
    """Manages screen recordings for multiple devices."""

    def __init__(self):
        self.active_recordings: Dict[str, RecordingInfo] = {}
        self.logger = common.get_logger('recording')
        self._stop_events: Dict[str, threading.Event] = {}
        self._threads: Dict[str, threading.Thread] = {}
        self._lock = threading.RLock()

    # ---- Public API -------------------------------------------------

    def start_recording(
        self,
        devices: List[adb_models.DeviceInfo],
        output_path: str,
        completion_callback: Optional[Callable] = None,
        progress_callback: Optional[Callable] = None,
    ) -> bool:
        """Start segmented screen recording for multiple devices.

        Args:
            devices: List of device info objects
            output_path: Directory to save recordings
            completion_callback: Called after recording finishes successfully
            progress_callback: Called for progress/error events during recording

        Returns:
            True if at least one device started recording successfully
        """
        start_signals: List[dict] = []
        for device in devices:
            serial = device.device_serial_num
            with self._lock:
                if serial in self.active_recordings:
                    self.logger.warning('Device %s is already recording', serial)
                    continue

                base_filename = self._build_base_filename(device)
                info = RecordingInfo(
                    device_serial=serial,
                    device_name=device.device_model,
                    start_time=datetime.now(),
                    output_path=output_path,
                    base_filename=base_filename,
                )
                self.active_recordings[serial] = info

                stop_event = threading.Event()
                self._stop_events[serial] = stop_event

                start_signal = {'event': threading.Event(), 'success': None}
                start_signals.append(start_signal)

                thread = threading.Thread(
                    target=self._run_recording_loop,
                    args=(
                        device,
                        info,
                        completion_callback,
                        progress_callback,
                        stop_event,
                        start_signal,
                    ),
                    daemon=True,
                )
                self._threads[serial] = thread
                thread.start()

        started_any = False
        for signal in start_signals:
            signal['event'].wait(timeout=self._initial_start_timeout())
            if signal['success']:
                started_any = True

        if not started_any:
            self.logger.warning('No recordings started successfully')

        return started_any

    def stop_recording(self, device_serial: Optional[str] = None) -> List[str]:
        """Stop screen recording for specified device or all devices."""
        with self._lock:
            if device_serial:
                target_serials = [device_serial] if device_serial in self._threads else []
            else:
                target_serials = list(self._threads.keys())

        stopped_devices: List[str] = []
        for serial in target_serials:
            stop_event = self._stop_events.get(serial)
            if stop_event:
                stop_event.set()

            thread = self._threads.get(serial)
            if thread and thread.is_alive():
                thread.join(timeout=self._join_timeout())

            stopped_devices.append(serial)

        return stopped_devices

    def get_recording_status(self, device_serial: str) -> str:
        """Get recording status for a device."""
        with self._lock:
            recording = self.active_recordings.get(device_serial)

        if not recording:
            return 'Idle'

        if not recording.is_active:
            return 'Idle'

        elapsed = recording.total_duration_seconds
        if recording.segments and recording.segments[-1].ended_at is None:
            elapsed += (datetime.now() - recording.segments[-1].started_at).total_seconds()

        duration_str = self._format_duration(elapsed)
        return f'Recording ({duration_str})'

    def get_all_recording_statuses(self) -> Dict[str, str]:
        """Get recording status for all active recordings."""
        statuses: Dict[str, str] = {}
        with self._lock:
            serials = list(self.active_recordings.keys())
        for serial in serials:
            statuses[serial] = self.get_recording_status(serial)
        return statuses

    def is_recording(self, device_serial: str) -> bool:
        """Check if device is currently recording."""
        with self._lock:
            return device_serial in self.active_recordings and self.active_recordings[device_serial].is_active

    def get_active_recordings_count(self) -> int:
        """Get number of active recordings."""
        with self._lock:
            return sum(1 for info in self.active_recordings.values() if info.is_active)

    # ---- Internal helpers -------------------------------------------

    def _run_recording_loop(
        self,
        device: adb_models.DeviceInfo,
        info: RecordingInfo,
        completion_callback: Optional[Callable],
        progress_callback: Optional[Callable],
        stop_event: threading.Event,
        start_signal: dict,
    ) -> None:
        serial = device.device_serial_num
        started_successfully = False
        failure_reason: Optional[str] = None

        try:
            while not stop_event.is_set():
                info.segment_index += 1
                segment_filename = self._build_segment_filename(info.base_filename, info.segment_index)
                segment = RecordingSegment(index=info.segment_index, filename=segment_filename, started_at=datetime.now())
                info.segments.append(segment)

                try:
                    segment_thread = self._start_segment_with_retries(info, segment_filename, stop_event)
                    info.segment_thread = segment_thread
                except Exception as exc:  # pragma: no cover - defensive
                    failure_reason = 'start_failed'
                    self._emit_error(progress_callback, info, segment, 'start', exc)
                    info.segments.pop()
                    break

                if not started_successfully:
                    started_successfully = True
                    start_signal['success'] = True
                    start_signal['event'].set()

                stop_requested = stop_event.wait(self._segment_duration())

                try:
                    self._stop_segment_with_retries(serial)
                except Exception as exc:
                    failure_reason = 'stop_failed'
                    self._emit_error(progress_callback, info, segment, 'stop', exc)
                    break
                finally:
                    self._join_segment_thread(info)

                segment.ended_at = datetime.now()
                segment_duration = segment.duration_seconds
                info.total_duration_seconds += segment_duration

                self._emit_segment_completed(
                    progress_callback,
                    info,
                    segment,
                    stop_requested,
                )

                if stop_requested:
                    break

        except Exception as exc:  # pragma: no cover - unexpected runtime failures
            failure_reason = 'unexpected'
            self.logger.error('Unexpected recording failure for %s: %s', serial, exc)
            self._emit_error(progress_callback, info, None, 'unexpected', exc)

        finally:
            if not started_successfully and not start_signal['event'].is_set():
                start_signal['success'] = False
                start_signal['event'].set()

            self._cleanup_device_state(serial, info)

            if started_successfully and failure_reason is None and info.segments:
                self._emit_completion(completion_callback, info)
            elif not started_successfully and failure_reason is None:
                self.logger.warning('Recording never started for device %s', serial)
                self._emit_error(progress_callback, info, None, 'start', RuntimeError('Recording did not start'))

    def _cleanup_device_state(self, serial: str, info: Optional[RecordingInfo] = None) -> None:
        loop_thread = None
        with self._lock:
            cached_info = self.active_recordings.pop(serial, None)
            if cached_info:
                cached_info.is_active = False
                info = info or cached_info
            self._stop_events.pop(serial, None)
            loop_thread = self._threads.pop(serial, None)

        self._join_segment_thread(info)

        if loop_thread and loop_thread.is_alive() and loop_thread is not threading.current_thread():  # pragma: no cover - defensive clean-up
            loop_thread.join(timeout=self._join_timeout())

    def _emit_segment_completed(
        self,
        progress_callback: Optional[Callable],
        info: RecordingInfo,
        segment: RecordingSegment,
        stop_requested: bool,
    ) -> None:
        if not progress_callback:
            return

        try:
            progress_callback({
                'type': 'segment_completed',
                'device_serial': info.device_serial,
                'device_name': info.device_name,
                'segment_index': segment.index,
                'segment_filename': segment.filename,
                'output_path': info.output_path,
                'duration_seconds': segment.duration_seconds,
                'total_duration_seconds': info.total_duration_seconds,
                'request_origin': 'user' if stop_requested else 'auto',
            })
        except Exception as exc:  # pragma: no cover
            self.logger.error('Progress callback failed for %s: %s', info.device_serial, exc)

    def _emit_completion(self, completion_callback: Optional[Callable], info: RecordingInfo) -> None:
        if not completion_callback:
            return

        duration_str = self._format_duration(info.total_duration_seconds)
        final_segment = info.segments[-1] if info.segments else None
        filename_hint = final_segment.filename if final_segment else f'{info.base_filename}.mp4'

        try:
            completion_callback(
                info.device_name,
                info.device_serial,
                duration_str,
                filename_hint.replace('.mp4', ''),
                info.output_path,
            )
        except Exception as exc:  # pragma: no cover
            self.logger.error('Completion callback failed for %s: %s', info.device_serial, exc)

    def _emit_error(
        self,
        progress_callback: Optional[Callable],
        info: RecordingInfo,
        segment: Optional[RecordingSegment],
        phase: str,
        error: Exception,
    ) -> None:
        if not progress_callback:
            return

        payload = {
            'type': 'error',
            'device_serial': info.device_serial,
            'device_name': info.device_name,
            'phase': phase,
            'message': str(error),
        }

        if segment:
            payload['segment_index'] = segment.index
            payload['segment_filename'] = segment.filename

        try:
            progress_callback(payload)
        except Exception as callback_error:  # pragma: no cover
            self.logger.error('Error callback failed for %s: %s', info.device_serial, callback_error)

    def _start_segment_with_retries(
        self,
        info: RecordingInfo,
        filename: str,
        stop_event: threading.Event,
    ) -> threading.Thread:
        serial = info.device_serial
        output_path = info.output_path
        attempts = 0
        max_attempts = RecordingConstants.START_RETRY_COUNT + 1
        last_error: Optional[Exception] = None

        while attempts < max_attempts and not stop_event.is_set():
            attempts += 1

            thread_error: List[Exception] = []

            def run_recording():
                try:
                    adb_tools.start_screen_record_device(serial, output_path, filename)
                except Exception as exc:  # pragma: no cover - actual adb failure surface
                    thread_error.append(exc)

            segment_thread = threading.Thread(target=run_recording, daemon=True)
            segment_thread.start()

            if self._wait_for_recording_start(serial, stop_event):
                return segment_thread

            if not thread_error:
                self.logger.info(
                    'Start verification timed out for %s; proceeding optimistically',
                    serial,
                )
                return segment_thread

            last_error = thread_error[0] if thread_error else RuntimeError('Recording did not start')
            self.logger.warning(
                'Start recording verification failed for %s (attempt %s/%s)',
                serial,
                attempts,
                max_attempts,
            )

            self._safe_stop_serial(serial)
            self._join_external_thread(segment_thread)

            if attempts < max_attempts and not stop_event.is_set():
                time.sleep(RecordingConstants.START_RETRY_DELAY)

        raise RuntimeError(f'Failed to start recording for {serial}') from last_error

    def _stop_segment_with_retries(self, serial: str) -> None:
        attempts = 0
        last_error: Optional[Exception] = None
        max_attempts = RecordingConstants.STOP_RETRY_COUNT + 1

        while attempts < max_attempts:
            try:
                adb_tools.stop_screen_record_device(serial)
                return
            except Exception as exc:  # pragma: no cover - depends on adb availability
                last_error = exc
                attempts += 1
                self.logger.warning('Stop recording failed for %s (attempt %s/%s): %s', serial, attempts, max_attempts, exc)
                if attempts < max_attempts:
                    time.sleep(RecordingConstants.STOP_RETRY_DELAY)

        raise RuntimeError(f'Failed to stop recording for {serial}') from last_error

    def _wait_for_recording_start(self, serial: str, stop_event: threading.Event) -> bool:
        timeout = self._segment_start_timeout()
        deadline = time.time() + timeout

        while time.time() < deadline:
            if stop_event.is_set():
                return False
            try:
                if adb_tools._verify_recording_started([serial]):
                    return True
            except Exception as exc:  # pragma: no cover - verification best-effort
                self.logger.debug('Verification error for %s: %s', serial, exc)
            time.sleep(RecordingConstants.VERIFICATION_POLL_INTERVAL)

        return False

    def _segment_start_timeout(self) -> float:
        base_timeout = RecordingConstants.START_RETRY_DELAY * (RecordingConstants.START_RETRY_COUNT + 1)
        return max(base_timeout, 5.0)

    def _safe_stop_serial(self, serial: str) -> None:
        try:
            adb_tools.stop_screen_record_device(serial)
        except Exception as exc:  # pragma: no cover - cleanup guard
            self.logger.debug('Safe-stop attempt for %s failed: %s', serial, exc)

    def _join_external_thread(self, thread: Optional[threading.Thread]) -> None:
        if thread and thread.is_alive():
            thread.join(timeout=RecordingConstants.STOP_RETRY_DELAY * (RecordingConstants.STOP_RETRY_COUNT + 1))

    def _join_segment_thread(self, info: Optional[RecordingInfo]) -> None:
        if not info or not info.segment_thread:
            return

        self._join_external_thread(info.segment_thread)
        info.segment_thread = None

    @staticmethod
    def _format_duration(seconds: float) -> str:
        total_seconds = max(int(seconds), 0)
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        secs = total_seconds % 60
        return f'{hours:02d}:{minutes:02d}:{secs:02d}'

    def _segment_duration(self) -> float:
        return RecordingConstants.SEGMENT_DURATION_SECONDS

    def _initial_start_timeout(self) -> float:
        return (
            RecordingConstants.START_RETRY_DELAY * (RecordingConstants.START_RETRY_COUNT + 1)
            + 2.0
        )

    def _join_timeout(self) -> float:
        return self._segment_duration() + RecordingConstants.STOP_RETRY_DELAY * (
            RecordingConstants.STOP_RETRY_COUNT + 1
        )

    @staticmethod
    def _build_base_filename(device: adb_models.DeviceInfo) -> str:
        timestamp = common.current_format_time_utc()
        sanitized_model = device.device_model.replace(' ', '_')
        return f'{timestamp}_{sanitized_model}_{device.device_serial_num}'

    @staticmethod
    def _build_segment_filename(base_filename: str, segment_index: int) -> str:
        return f'{base_filename}_part{segment_index:02d}.mp4'


def validate_recording_path(output_path: str) -> Optional[str]:
    """Validate and normalize recording output path."""
    return common.validate_and_create_output_path(output_path)


def get_recording_quick_actions() -> List[dict]:
    """Get list of quick actions available for recordings."""
    return [
        {
            'name': 'Open Folder',
            'description': 'Open the recordings folder in file manager',
            'icon': '📁',
        },
        {
            'name': 'Play Video',
            'description': 'Play the recorded video',
            'icon': '▶️',
        },
        {
            'name': 'Stop All',
            'description': 'Stop all active recordings',
            'icon': '⏹️',
        },
    ]
