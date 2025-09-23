"""Recording utilities for device screen recording operations."""

import threading
from typing import List, Dict, Callable, Optional
from dataclasses import dataclass
from datetime import datetime
from utils import adb_models, adb_tools, common


@dataclass
class RecordingInfo:
    """Recording information for a device."""
    device_serial: str
    device_name: str
    start_time: datetime
    output_path: str
    filename: str
    is_active: bool = True


class RecordingManager:
    """Manages screen recordings for multiple devices."""

    def __init__(self):
        self.active_recordings: Dict[str, RecordingInfo] = {}
        self.logger = common.get_logger('recording')

    def start_recording(self, devices: List[adb_models.DeviceInfo],
                       output_path: str,
                       callback: Optional[Callable] = None) -> bool:
        """Start screen recording for multiple devices.

        Args:
            devices: List of device info objects
            output_path: Directory to save recordings
            callback: Optional callback function

        Returns:
            True if recording started successfully
        """
        try:
            timestamp = common.current_format_time_utc()

            for device in devices:
                if device.device_serial_num in self.active_recordings:
                    self.logger.warning(f'Device {device.device_serial_num} is already recording')
                    continue

                # Generate device-specific filename
                device_filename = f"{timestamp}_{device.device_model}_{device.device_serial_num}.mp4"

                # Start recording in background thread
                recording_info = RecordingInfo(
                    device_serial=device.device_serial_num,
                    device_name=device.device_model,
                    start_time=datetime.now(),
                    output_path=output_path,
                    filename=device_filename
                )

                self.active_recordings[device.device_serial_num] = recording_info

                def recording_worker(serial=device.device_serial_num, filename=device_filename):
                    try:
                        adb_tools.start_screen_record_device(serial, output_path, filename)
                        if callback:
                            callback(device.device_model, serial, self._get_recording_duration(serial),
                                   filename, output_path)
                    except Exception as e:
                        self.logger.error(f'Recording failed for {serial}: {e}')
                        self._remove_recording(serial)

                thread = threading.Thread(target=recording_worker, daemon=True)
                thread.start()

            return len(self.active_recordings) > 0

        except Exception as e:
            self.logger.error(f'Failed to start recording: {e}')
            return False

    def stop_recording(self, device_serial: Optional[str] = None) -> List[str]:
        """Stop screen recording for specified device or all devices.

        Args:
            device_serial: Specific device serial, or None for all devices

        Returns:
            List of device serials that were stopped
        """
        stopped_devices = []

        try:
            if device_serial:
                # Stop specific device
                if device_serial in self.active_recordings:
                    adb_tools.stop_screen_record_device(device_serial)
                    self._remove_recording(device_serial)
                    stopped_devices.append(device_serial)
            else:
                # Stop all recordings
                for serial in list(self.active_recordings.keys()):
                    try:
                        adb_tools.stop_screen_record_device(serial)
                        self._remove_recording(serial)
                        stopped_devices.append(serial)
                    except Exception as e:
                        self.logger.error(f'Failed to stop recording for {serial}: {e}')

        except Exception as e:
            self.logger.error(f'Failed to stop recording: {e}')

        return stopped_devices

    def get_recording_status(self, device_serial: str) -> str:
        """Get recording status for a device.

        Args:
            device_serial: Device serial number

        Returns:
            Status string ('Recording', 'Idle', etc.)
        """
        if device_serial in self.active_recordings:
            recording = self.active_recordings[device_serial]
            if recording.is_active:
                duration = self._get_recording_duration(device_serial)
                return f'Recording ({duration})'
        return 'Idle'

    def get_all_recording_statuses(self) -> Dict[str, str]:
        """Get recording status for all active recordings.

        Returns:
            Dictionary mapping device serial to status string
        """
        statuses = {}
        for serial in self.active_recordings:
            statuses[serial] = self.get_recording_status(serial)
        return statuses

    def is_recording(self, device_serial: str) -> bool:
        """Check if device is currently recording.

        Args:
            device_serial: Device serial number

        Returns:
            True if device is recording
        """
        return device_serial in self.active_recordings

    def get_active_recordings_count(self) -> int:
        """Get number of active recordings.

        Returns:
            Number of devices currently recording
        """
        return len(self.active_recordings)

    def _get_recording_duration(self, device_serial: str) -> str:
        """Get formatted recording duration for a device.

        Args:
            device_serial: Device serial number

        Returns:
            Formatted duration string (e.g., "00:02:15")
        """
        if device_serial not in self.active_recordings:
            return "00:00:00"

        recording = self.active_recordings[device_serial]
        duration = datetime.now() - recording.start_time
        total_seconds = int(duration.total_seconds())

        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        seconds = total_seconds % 60

        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

    def _remove_recording(self, device_serial: str):
        """Remove recording from active recordings.

        Args:
            device_serial: Device serial number
        """
        if device_serial in self.active_recordings:
            del self.active_recordings[device_serial]
            self.logger.debug(f'Removed recording for device {device_serial}')


def validate_recording_path(output_path: str) -> Optional[str]:
    """Validate and normalize recording output path.

    Args:
        output_path: Path to validate

    Returns:
        Normalized path if valid, None if invalid
    """
    return common.validate_and_create_output_path(output_path)


def get_recording_quick_actions() -> List[dict]:
    """Get list of quick actions available for recordings.

    Returns:
        List of action dictionaries with 'name' and 'description'
    """
    return [
        {
            'name': 'Open Folder',
            'description': 'Open the recordings folder in file manager',
            'icon': '📁'
        },
        {
            'name': 'Play Video',
            'description': 'Play the recorded video',
            'icon': '▶️'
        },
        {
            'name': 'Stop All',
            'description': 'Stop all active recordings',
            'icon': '⏹️'
        }
    ]