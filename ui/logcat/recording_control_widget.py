"""Recording control widget for screen recording with logcat sync.

Provides controls for starting/stopping screen recording using either
scrcpy --record or ADB screenrecord, with optional logcat synchronization.
"""

import os
import subprocess
from datetime import datetime
from typing import Callable, Optional, TYPE_CHECKING

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QRadioButton, QButtonGroup, QCheckBox
)
from PyQt6.QtCore import pyqtSignal, QTimer

from utils import adb_tools
from config.config_manager import ScrcpySettings, ConfigManager

if TYPE_CHECKING:
    from utils.adb_models import DeviceInfo
    from ui.logcat.recording_sync_manager import RecordingSyncManager


class RecordingControlWidget(QWidget):
    """Widget for controlling screen recording with dual method support.

    Supports both scrcpy --record and ADB screenrecord methods,
    with optional synchronized logcat export.

    Signals:
        recording_started: Emitted when recording starts (device_serial, method)
        recording_stopped: Emitted when recording stops (device_serial, video_path)
        recording_error: Emitted on error (error_message)
    """

    recording_started = pyqtSignal(str, str)  # device_serial, method
    recording_stopped = pyqtSignal(str, str)  # device_serial, video_path
    recording_error = pyqtSignal(str)  # error_message

    # Recording method constants
    METHOD_SCRCPY = "scrcpy"
    METHOD_ADB = "adb"

    def __init__(
        self,
        device: "DeviceInfo",
        sync_manager: Optional["RecordingSyncManager"] = None,
        config_manager: Optional[ConfigManager] = None,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self._device = device
        self._sync_manager = sync_manager
        self._config_manager = config_manager
        self._is_recording = False
        self._current_method: Optional[str] = None
        self._current_video_path: Optional[str] = None
        self._current_session_dir: Optional[str] = None
        self._recording_start_time: Optional[datetime] = None

        # Callback to stop preview scrcpy when recording starts
        self._stop_preview_callback: Optional[Callable[[], None]] = None

        # Process handles
        self._scrcpy_process: Optional[subprocess.Popen] = None
        self._adb_recording_active = False

        # Check scrcpy availability
        self._scrcpy_available, _ = adb_tools.check_tool_availability("scrcpy")

        # Duration timer
        self._duration_timer = QTimer(self)
        self._duration_timer.setInterval(1000)
        self._duration_timer.timeout.connect(self._update_duration_display)

        self._init_ui()

    def _init_ui(self) -> None:
        """Initialize the widget UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(6)

        # Recording method selection (compact)
        method_group = QButtonGroup(self)
        method_row = QHBoxLayout()
        method_row.setSpacing(8)

        self._scrcpy_radio = QRadioButton("scrcpy")
        self._scrcpy_radio.setToolTip(
            "Record using scrcpy\n• Supports audio (v3+)\n• Unlimited duration\n• Opens preview window"
        )
        self._scrcpy_radio.setEnabled(self._scrcpy_available)
        method_group.addButton(self._scrcpy_radio)
        method_row.addWidget(self._scrcpy_radio)

        self._adb_radio = QRadioButton("ADB")
        self._adb_radio.setToolTip(
            "Record using ADB screenrecord\n• Max 180 seconds\n• No audio\n• Background recording"
        )
        self._adb_radio.setChecked(True)
        method_group.addButton(self._adb_radio)
        method_row.addWidget(self._adb_radio)

        # Logcat sync checkbox (inline)
        self._sync_checkbox = QCheckBox("+ Logcat")
        self._sync_checkbox.setChecked(True)
        self._sync_checkbox.setToolTip("Save logcat logs with recording")
        self._sync_checkbox.setEnabled(self._sync_manager is not None)
        method_row.addWidget(self._sync_checkbox)

        method_row.addStretch()
        layout.addLayout(method_row)

        # Control buttons and status (single row)
        control_row = QHBoxLayout()
        control_row.setSpacing(6)

        self._start_btn = QPushButton("● Rec")
        self._start_btn.setFixedWidth(60)
        self._start_btn.setStyleSheet(
            "QPushButton { background-color: #2d5a2d; padding: 4px 8px; }"
            "QPushButton:hover { background-color: #3d7a3d; }"
        )
        self._start_btn.setToolTip("Start Recording")
        self._start_btn.clicked.connect(self._on_start_clicked)
        control_row.addWidget(self._start_btn)

        self._stop_btn = QPushButton("■ Stop")
        self._stop_btn.setFixedWidth(60)
        self._stop_btn.setStyleSheet(
            "QPushButton { background-color: #5a2d2d; padding: 4px 8px; }"
            "QPushButton:hover { background-color: #7a3d3d; }"
        )
        self._stop_btn.setToolTip("Stop Recording")
        self._stop_btn.setEnabled(False)
        self._stop_btn.clicked.connect(self._on_stop_clicked)
        control_row.addWidget(self._stop_btn)

        # Status and duration inline
        self._status_value = QLabel("Idle")
        self._status_value.setStyleSheet("color: #888;")
        control_row.addWidget(self._status_value)

        self._duration_value = QLabel("")
        self._duration_value.setStyleSheet("color: #4c4; font-family: monospace;")
        control_row.addWidget(self._duration_value)

        control_row.addStretch()
        layout.addLayout(control_row)

        # File output display (only visible when recording)
        self._file_value = QLabel("")
        self._file_value.setWordWrap(True)
        self._file_value.setStyleSheet("color: #888; font-size: 10px;")
        self._file_value.setVisible(False)
        layout.addWidget(self._file_value)

    def _get_default_output_path(self) -> str:
        """Get the default output path for recordings from config."""
        # Try to get from config manager first
        if self._config_manager:
            saved_path = self._config_manager.get_ui_settings().default_output_path
            if saved_path and os.path.isdir(saved_path):
                return saved_path

        # Fall back to Desktop or home directory
        desktop = os.path.join(os.path.expanduser("~"), "Desktop")
        if os.path.isdir(desktop):
            return desktop
        return os.path.expanduser("~")

    def _on_start_clicked(self) -> None:
        """Handle start button click."""
        if self._is_recording:
            return

        output_dir = self._get_default_output_path()
        if not output_dir or not os.path.isdir(output_dir):
            self.recording_error.emit("Please configure output path in Settings first")
            return

        method = self.METHOD_SCRCPY if self._scrcpy_radio.isChecked() else self.METHOD_ADB
        self.start_recording(method, output_dir)

    def _on_stop_clicked(self) -> None:
        """Handle stop button click."""
        self.stop_recording()

    def start_recording(self, method: str, output_dir: str) -> bool:
        """Start screen recording.

        Args:
            method: Recording method (METHOD_SCRCPY or METHOD_ADB)
            output_dir: Directory to save the recording

        Returns:
            True if recording started successfully
        """
        if self._is_recording:
            return False

        # Generate folder and filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        model = self._device.device_model.replace(" ", "_")
        serial_short = self._device.device_serial_num[:8]

        # Create a dedicated folder for this recording session
        folder_name = f"recording_{timestamp}_{model}_{serial_short}"
        session_dir = os.path.join(output_dir, folder_name)
        os.makedirs(session_dir, exist_ok=True)

        filename = "video.mp4"
        video_path = os.path.join(session_dir, filename)

        # Store session directory for logcat export
        self._current_session_dir = session_dir

        # Start sync session if enabled
        if self._sync_manager and self._sync_checkbox.isChecked():
            self._sync_manager.start_session(method=method)

        # Stop preview scrcpy before starting scrcpy recording to avoid duplicate windows
        if method == self.METHOD_SCRCPY and self._stop_preview_callback:
            try:
                self._stop_preview_callback()
            except Exception:
                pass

        # Start recording based on method
        if method == self.METHOD_SCRCPY:
            success = self._start_scrcpy_recording(video_path)
        else:
            success = self._start_adb_recording(video_path)

        if success:
            self._is_recording = True
            self._current_method = method
            self._current_video_path = video_path
            self._recording_start_time = datetime.now()

            self._update_ui_for_recording(True)
            self._duration_timer.start()

            self.recording_started.emit(self._device.device_serial_num, method)

        return success

    def _start_scrcpy_recording(self, video_path: str) -> bool:
        """Start recording using scrcpy --record."""
        cmd = [
            "scrcpy",
            "-s", self._device.device_serial_num,
            "--record", video_path,
            "--window-title", f"Recording - {self._device.device_model}",
        ]

        try:
            if os.name == "nt":
                self._scrcpy_process = subprocess.Popen(
                    cmd,
                    creationflags=subprocess.CREATE_NEW_CONSOLE,
                )
            else:
                self._scrcpy_process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            return True
        except (FileNotFoundError, OSError) as e:
            self.recording_error.emit(f"Failed to start scrcpy recording: {e}")
            return False

    def _start_adb_recording(self, video_path: str) -> bool:
        """Start recording using ADB screenrecord."""
        try:
            # Start recording on device
            remote_path = f"/sdcard/screenrecord_{self._device.device_serial_num}.mp4"
            cmd = [
                "adb", "-s", self._device.device_serial_num,
                "shell", "screenrecord", "--time-limit", "180", remote_path
            ]

            if os.name == "nt":
                subprocess.Popen(
                    cmd,
                    creationflags=subprocess.CREATE_NO_WINDOW,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            else:
                subprocess.Popen(
                    cmd,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )

            self._adb_recording_active = True
            return True
        except (FileNotFoundError, OSError) as e:
            self.recording_error.emit(f"Failed to start ADB recording: {e}")
            return False

    def stop_recording(self) -> Optional[str]:
        """Stop the current recording.

        Returns:
            Path to the recorded video file, or None if no recording was active
        """
        if not self._is_recording:
            return None

        video_path = self._current_video_path
        method = self._current_method

        self._duration_timer.stop()

        # Stop recording based on method
        if method == self.METHOD_SCRCPY:
            self._stop_scrcpy_recording()
        else:
            self._stop_adb_recording()

        # Export logs if sync enabled
        if self._sync_manager and self._sync_checkbox.isChecked():
            session = self._sync_manager.stop_session(video_path=video_path)
            if session:
                # Use session directory for log export
                self._sync_manager.export_session_logs(session, self._current_session_dir)

        self._is_recording = False
        self._current_method = None
        self._current_video_path = None
        self._current_session_dir = None
        self._recording_start_time = None

        self._update_ui_for_recording(False)

        if video_path:
            self.recording_stopped.emit(self._device.device_serial_num, video_path)

        return video_path

    def _stop_scrcpy_recording(self) -> None:
        """Stop scrcpy recording."""
        if self._scrcpy_process is not None:
            try:
                self._scrcpy_process.terminate()
                self._scrcpy_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._scrcpy_process.kill()
            except OSError:
                pass
            self._scrcpy_process = None

    def _stop_adb_recording(self) -> None:
        """Stop ADB recording and pull file."""
        if not self._adb_recording_active:
            return

        serial = self._device.device_serial_num
        remote_path = f"/sdcard/screenrecord_{serial}.mp4"

        try:
            # Stop screenrecord process
            subprocess.run(
                ["adb", "-s", serial, "shell", "pkill", "-SIGINT", "screenrecord"],
                capture_output=True,
                timeout=5,
            )
        except (subprocess.TimeoutExpired, OSError):
            pass

        # Schedule file pull after delay (non-blocking)
        QTimer.singleShot(1000, lambda: self._finalize_adb_recording(serial, remote_path))

    def _finalize_adb_recording(self, serial: str, remote_path: str) -> None:
        """Finalize ADB recording by pulling and cleaning up the file."""
        try:
            # Pull file from device
            if self._current_video_path:
                subprocess.run(
                    ["adb", "-s", serial, "pull", remote_path, self._current_video_path],
                    capture_output=True,
                    timeout=30,
                )

            # Remove file from device
            subprocess.run(
                ["adb", "-s", serial, "shell", "rm", remote_path],
                capture_output=True,
                timeout=5,
            )
        except (subprocess.TimeoutExpired, OSError):
            pass

        self._adb_recording_active = False

    def _update_ui_for_recording(self, is_recording: bool) -> None:
        """Update UI elements based on recording state."""
        self._start_btn.setEnabled(not is_recording)
        self._stop_btn.setEnabled(is_recording)
        self._scrcpy_radio.setEnabled(not is_recording and self._scrcpy_available)
        self._adb_radio.setEnabled(not is_recording)

        if is_recording:
            self._status_value.setText("● REC")
            self._status_value.setStyleSheet("color: #c44; font-weight: bold;")
            if self._current_session_dir:
                # Show the session folder name
                folder_name = os.path.basename(self._current_session_dir)
                self._file_value.setText(f"→ {folder_name}/")
                self._file_value.setVisible(True)
        else:
            self._status_value.setText("Idle")
            self._status_value.setStyleSheet("color: #888;")
            self._duration_value.setText("")
            self._file_value.setVisible(False)

    def _update_duration_display(self) -> None:
        """Update the duration display."""
        if self._recording_start_time is None:
            return

        elapsed = datetime.now() - self._recording_start_time
        total_seconds = int(elapsed.total_seconds())
        minutes = total_seconds // 60
        seconds = total_seconds % 60
        self._duration_value.setText(f"{minutes:02d}:{seconds:02d}")

        # Check if scrcpy process has stopped unexpectedly
        if self._current_method == self.METHOD_SCRCPY and self._scrcpy_process:
            if self._scrcpy_process.poll() is not None:
                # Process terminated
                self.stop_recording()

    @property
    def is_recording(self) -> bool:
        """Check if recording is currently active."""
        return self._is_recording

    @property
    def sync_enabled(self) -> bool:
        """Check if logcat sync is enabled."""
        return self._sync_checkbox.isChecked()

    @sync_enabled.setter
    def sync_enabled(self, value: bool) -> None:
        """Set logcat sync enabled state."""
        self._sync_checkbox.setChecked(value)

    def set_sync_manager(self, manager: "RecordingSyncManager") -> None:
        """Set the sync manager for logcat synchronization."""
        self._sync_manager = manager
        self._sync_checkbox.setEnabled(manager is not None)

    def set_stop_preview_callback(self, callback: Callable[[], None]) -> None:
        """Set callback to stop preview scrcpy before recording.

        This prevents duplicate scrcpy windows when recording with scrcpy method.
        """
        self._stop_preview_callback = callback

    def cleanup(self) -> None:
        """Clean up resources."""
        self._duration_timer.stop()
        if self._is_recording:
            self.stop_recording()
