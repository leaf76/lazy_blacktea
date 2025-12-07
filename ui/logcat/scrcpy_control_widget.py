"""Scrcpy control widget for device preview.

Provides controls for launching and managing scrcpy as an external window
for device screen mirroring within the logcat viewer.
"""

import os
import subprocess
from typing import Optional, Callable, Tuple, TYPE_CHECKING

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel
)
from PyQt6.QtCore import pyqtSignal, QTimer

from utils import adb_tools
from config.config_manager import ScrcpySettings

if TYPE_CHECKING:
    from utils.adb_models import DeviceInfo


class ScrcpyControlWidget(QWidget):
    """Widget for controlling scrcpy device preview.

    Provides buttons to launch/stop scrcpy, configure settings,
    and displays the current scrcpy status.

    Note: Uses subprocess.Popen with argument list (not shell=True)
    which is safe from shell injection vulnerabilities.

    Signals:
        scrcpy_launched: Emitted when scrcpy is launched (device_serial)
        scrcpy_stopped: Emitted when scrcpy stops
        scrcpy_error: Emitted on error (error_message)
    """

    scrcpy_launched = pyqtSignal(str)  # device_serial
    scrcpy_stopped = pyqtSignal()
    scrcpy_error = pyqtSignal(str)  # error_message

    # Status constants
    STATUS_IDLE = "idle"
    STATUS_RUNNING = "running"
    STATUS_ERROR = "error"

    def __init__(
        self,
        device: "DeviceInfo",
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self._device = device
        self._scrcpy_process: Optional[subprocess.Popen] = None
        self._scrcpy_available: Optional[bool] = None
        self._scrcpy_version: int = 2
        self._status = self.STATUS_IDLE
        self._settings = ScrcpySettings()

        # Callback to get window position for side-by-side layout
        self._position_callback: Optional[Callable[[], Tuple[int, int]]] = None

        # Process monitor timer
        self._monitor_timer = QTimer(self)
        self._monitor_timer.setInterval(1000)
        self._monitor_timer.timeout.connect(self._check_process_status)

        self._init_ui()
        self._check_scrcpy_availability()

    def _init_ui(self) -> None:
        """Initialize the widget UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        # Status indicator
        status_row = QHBoxLayout()
        status_row.setSpacing(6)

        status_label = QLabel("Status:")
        status_label.setStyleSheet("font-weight: bold;")
        status_row.addWidget(status_label)

        self._status_indicator = QLabel()
        self._update_status_display()
        status_row.addWidget(self._status_indicator)
        status_row.addStretch()

        layout.addLayout(status_row)

        # Control buttons
        btn_row = QHBoxLayout()
        btn_row.setSpacing(6)

        self._launch_btn = QPushButton("Launch Preview")
        self._launch_btn.setToolTip("Launch scrcpy to mirror device screen")
        self._launch_btn.clicked.connect(self._on_launch_clicked)
        btn_row.addWidget(self._launch_btn)

        self._stop_btn = QPushButton("Stop")
        self._stop_btn.setToolTip("Stop scrcpy preview")
        self._stop_btn.clicked.connect(self._on_stop_clicked)
        self._stop_btn.setEnabled(False)
        btn_row.addWidget(self._stop_btn)

        layout.addLayout(btn_row)

        # Settings button
        settings_row = QHBoxLayout()

        self._settings_btn = QPushButton("Settings...")
        self._settings_btn.setToolTip("Configure scrcpy settings")
        self._settings_btn.clicked.connect(self._on_settings_clicked)
        settings_row.addWidget(self._settings_btn)
        settings_row.addStretch()

        layout.addLayout(settings_row)

        # Info label
        self._info_label = QLabel()
        self._info_label.setWordWrap(True)
        self._info_label.setStyleSheet("color: #888; font-size: 11px;")
        layout.addWidget(self._info_label)

        layout.addStretch()

    def _check_scrcpy_availability(self) -> None:
        """Check if scrcpy is available on the system."""
        is_available, version_output = adb_tools.check_tool_availability("scrcpy")
        self._scrcpy_available = is_available

        if is_available:
            self._scrcpy_version = self._parse_scrcpy_version(version_output)
            self._info_label.setText(
                f"scrcpy v{self._scrcpy_version}.x detected\n"
                "Press 'Launch Preview' to start device mirroring."
            )
            self._launch_btn.setEnabled(True)
        else:
            self._info_label.setText(
                "scrcpy not found.\n"
                "Install scrcpy to enable device preview.\n"
                "https://github.com/Genymobile/scrcpy"
            )
            self._info_label.setStyleSheet("color: #c44; font-size: 11px;")
            self._launch_btn.setEnabled(False)

    def _parse_scrcpy_version(self, version_output: str) -> int:
        """Parse scrcpy version from output."""
        try:
            if "scrcpy" in version_output:
                version_line = version_output.split("\n")[0]
                version_str = version_line.split()[1]
                return int(version_str.split(".")[0])
        except (IndexError, ValueError):
            pass
        return 2

    def _update_status_display(self) -> None:
        """Update the status indicator display."""
        if self._status == self.STATUS_RUNNING:
            self._status_indicator.setText("Running")
            self._status_indicator.setStyleSheet("color: #4c4; font-weight: bold;")
        elif self._status == self.STATUS_ERROR:
            self._status_indicator.setText("Error")
            self._status_indicator.setStyleSheet("color: #c44; font-weight: bold;")
        else:
            self._status_indicator.setText("Idle")
            self._status_indicator.setStyleSheet("color: #888;")

    def _on_launch_clicked(self) -> None:
        """Handle launch button click."""
        if not self._scrcpy_available:
            self.scrcpy_error.emit("scrcpy is not available")
            return

        if self._scrcpy_process is not None:
            return

        self.launch_scrcpy()

    def _on_stop_clicked(self) -> None:
        """Handle stop button click."""
        self.stop_scrcpy()

    def _on_settings_clicked(self) -> None:
        """Handle settings button click."""
        from ui.scrcpy_settings_dialog import ScrcpySettingsDialog

        dialog = ScrcpySettingsDialog(self._settings, self)
        if dialog.exec():
            self._settings = dialog.get_settings()

    def launch_scrcpy(self) -> bool:
        """Launch scrcpy for the device.

        Uses subprocess.Popen with argument list (safe from injection).

        Returns:
            True if scrcpy was launched successfully
        """
        if self._scrcpy_process is not None:
            return False

        cmd_args = self._build_scrcpy_command()

        try:
            # Platform-specific process creation
            # Using Popen with list args (not shell=True) for security
            if os.name == "nt":
                self._scrcpy_process = subprocess.Popen(
                    cmd_args,
                    creationflags=subprocess.CREATE_NEW_CONSOLE,
                )
            else:
                self._scrcpy_process = subprocess.Popen(
                    cmd_args,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )

            self._status = self.STATUS_RUNNING
            self._update_status_display()
            self._launch_btn.setEnabled(False)
            self._stop_btn.setEnabled(True)
            self._monitor_timer.start()

            self.scrcpy_launched.emit(self._device.device_serial_num)
            return True

        except FileNotFoundError:
            self._status = self.STATUS_ERROR
            self._update_status_display()
            self.scrcpy_error.emit("scrcpy executable not found")
            return False
        except OSError as e:
            self._status = self.STATUS_ERROR
            self._update_status_display()
            self.scrcpy_error.emit(f"Failed to launch scrcpy: {e}")
            return False

    def _build_scrcpy_command(self) -> list:
        """Build the scrcpy command arguments as a list."""
        cmd = ["scrcpy", "-s", self._device.device_serial_num]

        # Window title for identification
        cmd.extend([
            "--window-title",
            f"Preview - {self._device.device_model}",
        ])

        # Window position for side-by-side layout
        if self._position_callback is not None:
            try:
                x, y = self._position_callback()
                cmd.extend(["--window-x", str(x)])
                cmd.extend(["--window-y", str(y)])
            except Exception:
                pass  # Ignore position errors, use default placement

        # Apply settings
        if self._settings.stay_awake:
            cmd.append("--stay-awake")

        if self._settings.turn_screen_off:
            cmd.append("--turn-screen-off")

        if self._settings.disable_screensaver:
            cmd.append("--disable-screensaver")

        if self._settings.bitrate:
            bitrate = self._settings.bitrate
            # Normalize bitrate format
            if not bitrate.endswith(("M", "K", "m", "k")):
                bitrate = f"{bitrate}M"
            cmd.extend(["--video-bit-rate", bitrate])

        if self._settings.max_size > 0:
            cmd.extend(["--max-size", str(self._settings.max_size)])

        # Audio (scrcpy 3.x+)
        if self._scrcpy_version >= 3 and self._settings.enable_audio_playback:
            cmd.append("--audio-codec=opus")

        # Extra arguments - parsed safely using shlex
        if self._settings.extra_args:
            import shlex
            extra = shlex.split(self._settings.extra_args)
            cmd.extend(extra)

        return cmd

    def stop_scrcpy(self) -> None:
        """Stop the scrcpy process."""
        if self._scrcpy_process is None:
            return

        self._monitor_timer.stop()

        try:
            self._scrcpy_process.terminate()
            self._scrcpy_process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            self._scrcpy_process.kill()
        except OSError:
            pass

        self._scrcpy_process = None
        self._status = self.STATUS_IDLE
        self._update_status_display()
        self._launch_btn.setEnabled(True)
        self._stop_btn.setEnabled(False)

        self.scrcpy_stopped.emit()

    def _check_process_status(self) -> None:
        """Check if the scrcpy process is still running."""
        if self._scrcpy_process is None:
            self._monitor_timer.stop()
            return

        poll = self._scrcpy_process.poll()
        if poll is not None:
            # Process has terminated
            self._scrcpy_process = None
            self._status = self.STATUS_IDLE
            self._update_status_display()
            self._launch_btn.setEnabled(True)
            self._stop_btn.setEnabled(False)
            self._monitor_timer.stop()
            self.scrcpy_stopped.emit()

    @property
    def is_running(self) -> bool:
        """Check if scrcpy is currently running."""
        return self._scrcpy_process is not None

    @property
    def settings(self) -> ScrcpySettings:
        """Get the current scrcpy settings."""
        return self._settings

    @settings.setter
    def settings(self, value: ScrcpySettings) -> None:
        """Set the scrcpy settings."""
        self._settings = value

    def set_position_callback(
        self, callback: Optional[Callable[[], Tuple[int, int]]]
    ) -> None:
        """Set a callback to get the scrcpy window position.

        The callback should return (x, y) coordinates where scrcpy
        window should be positioned for side-by-side viewing.

        Args:
            callback: Function returning (x, y) tuple, or None to disable
        """
        self._position_callback = callback

    def cleanup(self) -> None:
        """Clean up resources."""
        self._monitor_timer.stop()
        if self._scrcpy_process is not None:
            self.stop_scrcpy()
