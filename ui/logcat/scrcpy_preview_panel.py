"""Scrcpy preview panel for logcat viewer.

Provides a collapsible side panel containing device preview controls
and recording functionality with logcat synchronization.
"""

from typing import Optional, TYPE_CHECKING

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QSizePolicy
from PyQt6.QtCore import pyqtSignal

from ui.collapsible_panel import CollapsiblePanel
from ui.logcat.scrcpy_control_widget import ScrcpyControlWidget
from ui.logcat.recording_control_widget import RecordingControlWidget
from ui.logcat.recording_sync_manager import RecordingSyncManager

if TYPE_CHECKING:
    from utils.adb_models import DeviceInfo
    from ui.logcat_viewer import LogcatListModel
    from config.config_manager import ConfigManager


class ScrcpyPreviewPanel(QWidget):
    """Side panel for device preview and recording controls.

    Contains collapsible sections for:
    - Device Preview: scrcpy launch controls
    - Recording: Screen recording with logcat sync

    Signals:
        recording_started: Emitted when recording starts
        recording_stopped: Emitted when recording stops (video_path)
        error_occurred: Emitted on error (message)
    """

    recording_started = pyqtSignal()
    recording_stopped = pyqtSignal(str)  # video_path
    error_occurred = pyqtSignal(str)  # error_message

    def __init__(
        self,
        device: "DeviceInfo",
        log_model: "LogcatListModel",
        config_manager: Optional["ConfigManager"] = None,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self._device = device
        self._log_model = log_model
        self._config_manager = config_manager
        self._parent_window = parent  # Reference to LogcatWindow for positioning

        # Create sync manager for logcat-recording synchronization
        self._sync_manager = RecordingSyncManager(log_model, parent=self)

        self._init_ui()
        self._connect_signals()
        self._setup_scrcpy_positioning()
        self._setup_recording_integration()

    def _init_ui(self) -> None:
        """Initialize the panel UI."""
        self.setObjectName("scrcpy_preview_panel")
        self.setStyleSheet("""
            QWidget#scrcpy_preview_panel {
                background-color: #252526;
                border-left: 1px solid #3e3e3e;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Device Preview section
        self._scrcpy_widget = ScrcpyControlWidget(self._device, parent=self)
        self._preview_panel = CollapsiblePanel(
            title="Device Preview",
            content=self._scrcpy_widget,
            collapsed=False,
            parent=self,
        )
        layout.addWidget(self._preview_panel)

        # Recording section
        self._recording_widget = RecordingControlWidget(
            device=self._device,
            sync_manager=self._sync_manager,
            config_manager=self._config_manager,
            parent=self,
        )
        self._recording_panel = CollapsiblePanel(
            title="Recording",
            content=self._recording_widget,
            collapsed=False,
            parent=self,
        )
        layout.addWidget(self._recording_panel)

        # Stretch at bottom
        layout.addStretch()

        # Set size policy
        self.setSizePolicy(
            QSizePolicy.Policy.Preferred,
            QSizePolicy.Policy.Expanding,
        )
        self.setMinimumWidth(250)

    def _connect_signals(self) -> None:
        """Connect internal signals."""
        # Forward scrcpy errors
        self._scrcpy_widget.scrcpy_error.connect(self.error_occurred.emit)

        # Forward recording signals
        self._recording_widget.recording_started.connect(
            lambda *_: self.recording_started.emit()
        )
        self._recording_widget.recording_stopped.connect(
            lambda _, path: self.recording_stopped.emit(path)
        )
        self._recording_widget.recording_error.connect(self.error_occurred.emit)

        # Forward sync manager signals
        self._sync_manager.logs_exported.connect(self._on_logs_exported)

    def _setup_scrcpy_positioning(self) -> None:
        """Setup scrcpy window positioning for side-by-side layout."""
        self._scrcpy_widget.set_position_callback(self._calculate_scrcpy_position)

    def _setup_recording_integration(self) -> None:
        """Setup integration between recording and preview scrcpy.

        Stops preview scrcpy when recording starts to avoid duplicate windows.
        """
        self._recording_widget.set_stop_preview_callback(
            self._scrcpy_widget.stop_scrcpy
        )

    def _calculate_scrcpy_position(self) -> tuple:
        """Calculate the position for scrcpy window next to logcat viewer.

        Returns:
            (x, y) tuple for scrcpy window position
        """
        if self._parent_window is None:
            return (100, 100)

        # Get the logcat window's geometry
        window_geom = self._parent_window.frameGeometry()
        screen = self._parent_window.screen()

        # Position scrcpy to the right of the logcat window
        x = window_geom.x() + window_geom.width() + 10  # 10px gap

        # Keep same Y position as logcat window
        y = window_geom.y()

        # Check if it would go off-screen and adjust if needed
        if screen is not None:
            screen_geom = screen.availableGeometry()
            # Estimate scrcpy window width (phones are typically ~400px at reasonable size)
            estimated_width = 400

            # If scrcpy would go off right edge, try to position it on the left
            if x + estimated_width > screen_geom.right():
                x = max(screen_geom.left(), window_geom.x() - estimated_width - 10)

        return (x, y)

    def _on_logs_exported(self, recording_id: str, log_path: str) -> None:
        """Handle log export completion."""
        # Could show a notification here
        pass

    @property
    def scrcpy_widget(self) -> ScrcpyControlWidget:
        """Get the scrcpy control widget."""
        return self._scrcpy_widget

    @property
    def recording_widget(self) -> RecordingControlWidget:
        """Get the recording control widget."""
        return self._recording_widget

    @property
    def sync_manager(self) -> RecordingSyncManager:
        """Get the recording sync manager."""
        return self._sync_manager

    @property
    def is_scrcpy_running(self) -> bool:
        """Check if scrcpy is running."""
        return self._scrcpy_widget.is_running

    @property
    def is_recording(self) -> bool:
        """Check if recording is active."""
        return self._recording_widget.is_recording

    def set_preview_collapsed(self, collapsed: bool) -> None:
        """Set the preview panel collapsed state."""
        self._preview_panel.set_collapsed(collapsed)

    def set_recording_collapsed(self, collapsed: bool) -> None:
        """Set the recording panel collapsed state."""
        self._recording_panel.set_collapsed(collapsed)

    def cleanup(self) -> None:
        """Clean up resources."""
        self._scrcpy_widget.cleanup()
        self._recording_widget.cleanup()
