"""A PyQt6 GUI application for simplifying Android ADB and automation tasks."""

import datetime
import glob
import logging
import os
import platform
import subprocess
import sys
import threading
import webbrowser
from typing import Dict, List, Iterable, Optional, Set
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QSplitter, QTextEdit,
    QCheckBox, QPushButton, QLabel,
    QGroupBox, QFileDialog,
    QMessageBox, QMenu, QStatusBar, QProgressBar,
    QDialog
)
from PyQt6.QtCore import (Qt, QTimer, pyqtSignal)
from PyQt6.QtGui import (QFont, QTextCursor, QAction, QIcon, QGuiApplication)

from utils import adb_models
from utils import adb_tools
from utils import common
from utils import json_utils

# Import configuration and constants
from config.config_manager import ConfigManager
from config.constants import (
    UIConstants, PathConstants, ADBConstants, MessageConstants,
    LoggingConstants, ApplicationConstants, PanelText
)

# Import new modular components
from ui.error_handler import ErrorHandler, ErrorCode, global_error_handler, setup_exception_hook
from ui.command_executor import CommandExecutor, ensure_devices_selected
from ui.device_manager import DeviceManager
from ui.panels_manager import PanelsManager
from ui.device_search_manager import DeviceSearchManager
from ui.ui_factory import UIFactory
from ui.device_operations_manager import DeviceOperationsManager
from ui.file_operations_manager import FileOperationsManager, CommandHistoryManager, UIHierarchyManager
from ui.command_execution_manager import CommandExecutionManager
from ui.style_manager import StyleManager, ButtonStyle, LabelStyle, ThemeManager
from ui.app_management_manager import AppManagementManager
from ui.logging_manager import LoggingManager, DiagnosticsManager, ConsoleHandler
from ui.optimized_device_list import VirtualizedDeviceList
from ui.device_list_controller import DeviceListController
from ui.device_actions_controller import DeviceActionsController
from ui.tools_panel_controller import ToolsPanelController
from ui.screenshot_widget import ClickableScreenshotLabel
from ui.ui_inspector_dialog import UIInspectorDialog

# Import new utils modules
from utils.screenshot_utils import take_screenshots_batch, validate_screenshot_path
from utils.recording_utils import RecordingManager, validate_recording_path
# File generation utilities are now handled by FileOperationsManager
from utils.debounced_refresh import (
    DeviceListDebouncedRefresh, BatchedUIUpdater, PerformanceOptimizedRefresh
)
from utils.qt_dependency_checker import check_and_fix_qt_dependencies

logger = common.get_logger('lazy_blacktea')


# Logcat classes moved to ui.logcat_viewer
from ui.logcat_viewer import LogcatWindow


class WindowMain(QMainWindow):
    """Main PyQt6 application window."""

    # Define custom signals for thread-safe UI updates
    recording_stopped_signal = pyqtSignal(str, str, str, str, str)  # device_name, device_serial, duration, filename, output_path
    recording_state_cleared_signal = pyqtSignal(str)  # device_serial
    recording_progress_signal = pyqtSignal(dict)  # progress payload
    screenshot_completed_signal = pyqtSignal(str, int, list)  # output_path, device_count, device_models
    file_generation_completed_signal = pyqtSignal(str, str, int, str)  # operation_name, output_path, device_count, icon
    console_output_signal = pyqtSignal(str)  # message

    def __init__(self):
        super().__init__()

        # Initialize new modular components
        self.config_manager = ConfigManager()
        self.error_handler = ErrorHandler(self)
        self.command_executor = CommandExecutor(self)
        self.device_manager = DeviceManager(self)
        self.recording_manager = RecordingManager()
        self.panels_manager = PanelsManager(self)

        # Connect device manager signals to main UI update
        self.device_manager.device_found.connect(self._on_device_found_from_manager)
        self.device_manager.device_lost.connect(self._on_device_lost_from_manager)
        self.device_manager.status_updated.connect(self._on_device_status_updated)

        # Setup global error handler and exception hook
        global_error_handler.parent = self
        setup_exception_hook()

        # Initialize variables (keeping some for compatibility)
        self.device_dict: Dict[str, adb_models.DeviceInfo] = {}
        self.check_devices: Dict[str, QCheckBox] = {}
        self.checkbox_pool: List[QCheckBox] = []
        self.virtualized_device_list = None
        self.virtualized_widget = None
        self.virtualized_active = False
        self.standard_device_widget = None
        self.pending_checked_serials: Set[str] = set()
        self.device_groups: Dict[str, List[str]] = {}
        self.refresh_interval = 5

        # Initialize device search manager
        self.device_search_manager = DeviceSearchManager(main_window=self)

        # Initialize controller handling device list rendering
        self.device_list_controller = DeviceListController(self)
        self.tools_panel_controller = ToolsPanelController(self)
        self.device_actions_controller = DeviceActionsController(self)

        # Initialize UI factory for creating UI components
        self.ui_factory = UIFactory(parent_window=self)

        # Initialize file operations and command execution managers
        self.file_operations_manager = FileOperationsManager(self)
        self.command_history_manager = CommandHistoryManager(self)
        self.ui_hierarchy_manager = UIHierarchyManager(self)
        self.command_execution_manager = CommandExecutionManager(self)

        # Initialize device operations manager
        self.device_operations_manager = DeviceOperationsManager(parent_window=self)

        # Initialize application management manager
        self.app_management_manager = AppManagementManager(self)

        # Initialize logging and diagnostics manager
        self.logging_manager = LoggingManager(self)
        self.diagnostics_manager = DiagnosticsManager(self)


        self.flag_actions = {}

        # Multi-device operation state management
        self.device_recordings: Dict[str, Dict] = {}  # Track recordings per device
        self.device_operations: Dict[str, str] = {}  # Track ongoing operations per device
        self.recording_timer = QTimer()
        self.recording_timer.timeout.connect(self.update_recording_status)
        self.recording_timer.start(500)  # Update every second

        # Connect custom signals for thread-safe UI updates
        self.recording_stopped_signal.connect(self._on_recording_stopped)
        self.recording_state_cleared_signal.connect(self._on_recording_state_cleared)
        self.recording_progress_signal.connect(self._on_recording_progress_event)
        self.screenshot_completed_signal.connect(self._on_screenshot_completed)
        self.file_generation_completed_signal.connect(self._on_file_generation_completed)
        self.console_output_signal.connect(self._on_console_output)

        # Connect device operations manager signals
        self.device_operations_manager.recording_stopped_signal.connect(self._on_recording_stopped)
        self.device_operations_manager.recording_state_cleared_signal.connect(self._on_recording_state_cleared)
        self.device_operations_manager.screenshot_completed_signal.connect(self._on_screenshot_completed)
        self.device_operations_manager.operation_completed_signal.connect(self._on_device_operation_completed)

        # Connect file operations manager signals
        self.file_operations_manager.file_generation_completed_signal.connect(self._on_file_generation_completed)

        # Connect panels_manager signals to device operations manager
        self.panels_manager.screenshot_requested.connect(self.device_operations_manager.take_screenshot)
        self.panels_manager.recording_start_requested.connect(self.device_operations_manager.start_screen_record)
        self.panels_manager.recording_stop_requested.connect(self.device_operations_manager.stop_screen_record)

        self.user_scale = 1.0

        # Initialize app management and check scrcpy availability
        self.app_management_manager.initialize()
        self.scrcpy_available = self.app_management_manager.scrcpy_available

        # Check if ADB is installed
        if not adb_tools.is_adb_installed():
            QMessageBox.critical(
                self,
                'ADB Not Found',
                'ADB is not installed or not in your system\'s PATH. '
                'Please install ADB to use lazy blacktea.'
            )
            sys.exit(1)

        # Log scrcpy availability (don't show popup on startup)
        if not self.scrcpy_available:
            logger.debug('scrcpy is not available - device mirroring feature will be disabled')
        else:
            logger.info(f'scrcpy is available (version {getattr(self, "scrcpy_major_version", "unknown")})')

        self.init_ui()
        self.load_config()

        # Initialize groups list (now that UI is created)
        self.update_groups_listbox()

        # Start device refresh with delay to avoid GUI blocking (after config is loaded)
        QTimer.singleShot(500, self.device_manager.start_device_refresh)

    def init_ui(self):
        """Initialize the user interface."""
        logger.info('[INIT] init_ui method started')
        self.setWindowTitle(f'🍵 {ApplicationConstants.APP_NAME}')
        self.setGeometry(100, 100, UIConstants.WINDOW_WIDTH, UIConstants.WINDOW_HEIGHT)


        # Set application icon
        self.set_app_icon()

        # Set global tooltip styling for better positioning and appearance
        self.setStyleSheet(self.styleSheet() + StyleManager.get_tooltip_style())

        # Remove the problematic attribute setting as it's not needed for tooltip positioning

        # Create central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # Create main layout
        main_layout = QVBoxLayout(central_widget)

        # Create menu bar
        self.panels_manager.create_menu_bar(self)

        # Create main splitter
        main_splitter = QSplitter(Qt.Orientation.Horizontal)
        main_layout.addWidget(main_splitter)

        # Create device list panel
        # Create device panel using panels_manager
        device_components = self.panels_manager.create_device_panel(main_splitter, self)
        self.title_label = device_components['title_label']
        self.device_scroll = device_components['device_scroll']
        self.device_widget = device_components['device_widget']
        self.device_layout = device_components['device_layout']
        self.no_devices_label = device_components['no_devices_label']

        self.standard_device_widget = self.device_widget
        self.virtualized_device_list = VirtualizedDeviceList(self.device_widget, main_window=self)
        self.virtualized_widget = self.virtualized_device_list.get_widget()

        # Create tools panel via controller
        self.tools_panel_controller.create_tools_panel(main_splitter)

        # Set splitter proportions
        main_splitter.setSizes([400, 800])

        # Create console panel at bottom
        self.create_console_panel(main_layout)

        # Create status bar
        self.create_status_bar()

    def set_app_icon(self):
        """Set the application icon."""

        # Try different icon formats based on the platform
        icon_paths = [
            'assets/icons/icon_128x128.png',  # Default for cross-platform
            'assets/icons/AppIcon.icns',      # macOS format
            'assets/icons/app_icon.ico'       # Windows format
        ]

        for icon_path in icon_paths:
            if os.path.exists(icon_path):
                try:
                    # Set window icon
                    self.setWindowIcon(QIcon(icon_path))
                    # Set application icon (for taskbar/dock)
                    QApplication.instance().setWindowIcon(QIcon(icon_path))
                    logger.debug(f"Successfully loaded app icon from {icon_path}")
                    break
                except Exception as e:
                    logger.warning(f"Failed to load icon from {icon_path}: {e}")
                    continue
        else:
            logger.warning("No suitable app icon found")

    def _setup_async_device_signals(self):
        """設置異步設備管理器的信號連接（通過DeviceManager）"""
        # Note: Signal connections are now handled by DeviceManager
        # No direct AsyncDeviceManager signals needed in main window
        pass



    def update_recording_status(self):
        """Update recording status display using new recording manager."""
        if not hasattr(self, 'recording_status_label'):
            return

        # Get all recording statuses from new manager
        all_statuses = self.recording_manager.get_all_recording_statuses()
        active_records_text = []
        now = datetime.datetime.now()
        handled_serials: Set[str] = set()

        for serial, record in self.device_recordings.items():
            if not record.get('active'):
                continue

            elapsed = record.get('elapsed_before_current', 0.0)
            ongoing_start = record.get('ongoing_start')
            if ongoing_start:
                elapsed += (now - ongoing_start).total_seconds()
            elif elapsed <= 0 and serial in all_statuses and 'Recording' in all_statuses[serial]:
                duration_part = all_statuses[serial].split('(')[1].rstrip(')')
                elapsed = self._parse_duration_to_seconds(duration_part)

            seconds_int = max(int(elapsed), 0)
            last_display = record.get('display_seconds', 0)
            if seconds_int < last_display:
                seconds_int = last_display
            else:
                record['display_seconds'] = seconds_int

            device_model = record.get('device_name') or 'Unknown'
            if serial in self.device_dict:
                device_model = self.device_dict[serial].device_model

            active_records_text.append(
                f"{device_model} ({serial[:8]}...): {self._format_seconds_to_clock(seconds_int)}"
            )
            handled_serials.add(serial)

        for serial, status in all_statuses.items():
            if 'Recording' not in status or serial in handled_serials:
                continue

            device_model = 'Unknown'
            if serial in self.device_dict:
                device_model = self.device_dict[serial].device_model
            duration_part = status.split('(')[1].rstrip(')')
            elapsed = self._parse_duration_to_seconds(duration_part)
            seconds_int = max(int(elapsed), 0)
            active_records_text.append(
                f"{device_model} ({serial[:8]}...): {self._format_seconds_to_clock(seconds_int)}"
            )

        active_count = self.recording_manager.get_active_recordings_count()

        if active_count > 0:
            status_text = PanelText.LABEL_RECORDING_PREFIX.format(count=active_count)
            self.recording_status_label.setText(status_text)
            self.recording_status_label.setStyleSheet(StyleManager.get_status_styles()['recording_active'])

            # Limit display to first 8 recordings to prevent UI overflow
            if len(active_records_text) > 8:
                display_recordings = active_records_text[:8] + [f"... and {len(active_records_text) - 8} more device(s)"]
            else:
                display_recordings = active_records_text

            self.recording_timer_label.setText('\n'.join(display_recordings))
        else:
            self.recording_status_label.setText(PanelText.LABEL_NO_RECORDING)
            self.recording_status_label.setStyleSheet(StyleManager.get_status_styles()['recording_inactive'])
            self.recording_timer_label.setText('')

    @staticmethod
    def _format_seconds_to_clock(seconds: float) -> str:
        total_seconds = max(int(seconds), 0)
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        secs = total_seconds % 60
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"

    @staticmethod
    def _parse_duration_to_seconds(duration_str: str) -> float:
        try:
            parts = duration_str.split(':')
            if len(parts) == 3:
                hours, minutes, seconds = [int(part) for part in parts]
                return hours * 3600 + minutes * 60 + seconds
        except (ValueError, TypeError):  # pragma: no cover - defensive parsing
            logger.debug(f'Unable to parse duration string: {duration_str}')
        return 0.0

    def show_recording_warning(self, serial):
        """Show warning when recording approaches 3-minute ADB limit."""
        device_model = 'Unknown'
        if serial in self.device_dict:
            device_model = self.device_dict[serial].device_model

        self.show_warning(
            'Recording Time Warning',
            f'Recording on {device_model} ({serial}) is approaching the 3-minute ADB limit.\n\n'
            'The recording will automatically stop soon. You can start a new recording afterwards.'
        )

    def create_console_panel(self, parent_layout):
        """Create the console output panel."""
        console_group = QGroupBox('Console Output')
        console_layout = QVBoxLayout(console_group)

        self.console_text = QTextEdit()
        self.console_text.setReadOnly(True)
        # Use system monospace font instead of specific 'Courier' to avoid font lookup delays
        console_font = QFont()
        console_font.setFamily('Monaco' if platform.system() == 'Darwin' else 'Consolas' if platform.system() == 'Windows' else 'monospace')
        console_font.setPointSize(9)
        self.console_text.setFont(console_font)
        # Allow console to expand - set minimum height but no maximum
        self.console_text.setMinimumHeight(150)
        # Set size policy to allow expansion
        from PyQt6.QtWidgets import QSizePolicy
        self.console_text.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        # Ensure console is visible with clear styling
        self.console_text.setStyleSheet(StyleManager.get_console_style())

        # Add a welcome message to verify the console is working
        welcome_msg = """🍵 Console Output Ready - Logging initialized

"""
        self.console_text.setPlainText(welcome_msg)
        logger.info('Console widget initialized and ready')
        self.write_to_console("✅ Console output system ready")

        # Enable context menu for console
        self.console_text.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.console_text.customContextMenuRequested.connect(self.show_console_context_menu)

        console_layout.addWidget(self.console_text)

        # Delegate logging pipeline setup to LoggingManager to avoid duplicate handlers
        self.logging_manager.initialize_logging(self.console_text)

        parent_layout.addWidget(console_group)


    def create_status_bar(self):
        """Create the status bar."""
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)

        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.status_bar.addPermanentWidget(self.progress_bar)

        self.status_bar.showMessage('Ready')

    def get_checked_devices(self) -> List[adb_models.DeviceInfo]:
        """Get list of checked devices."""
        if self.virtualized_active and self.virtualized_device_list is not None:
            return self.virtualized_device_list.get_checked_devices()

        checked_devices = []
        for serial, checkbox in self.check_devices.items():
            if checkbox.isChecked() and serial in self.device_dict:
                checked_devices.append(self.device_dict[serial])
        return checked_devices

    def show_info(self, title: str, message: str):
        """Show info message box."""
        QMessageBox.information(self, title, message)

    def show_warning(self, title: str, message: str):
        """Show warning message box."""
        QMessageBox.warning(self, title, message)

    def show_error(self, title: str, message: str):
        """Show error message box."""
        QMessageBox.critical(self, title, message)

    def set_ui_scale(self, scale: float):
        """Set UI scale factor."""
        self.user_scale = scale
        font = self.font()
        font.setPointSize(int(10 * scale))
        self.setFont(font)
        logger.debug(f'UI scale set to {scale}')

    def set_refresh_interval(self, interval: int):
        """Set device refresh interval."""
        self.refresh_interval = interval
        if hasattr(self, 'device_manager'):
            self.device_manager.set_refresh_interval(interval)
            logger.info(f'Refresh interval set to {interval} seconds and applied to DeviceManager')
        else:
            logger.warning(f'Refresh interval set to {interval} seconds but DeviceManager not yet available')

    def update_device_list(self, device_dict: Dict[str, adb_models.DeviceInfo]):
        self.device_list_controller.update_device_list(device_dict)

    def _update_device_list_optimized(self, device_dict: Dict[str, adb_models.DeviceInfo]):
        self.device_list_controller._update_device_list_optimized(device_dict)

    def _perform_batch_device_update(self, device_dict: Dict[str, adb_models.DeviceInfo]):
        self.device_list_controller._perform_batch_device_update(device_dict)

    def _batch_remove_devices(self, devices_to_remove):
        self.device_list_controller._batch_remove_devices(devices_to_remove)

    def _batch_add_devices(self, devices_to_add, device_dict, checked_serials):
        self.device_list_controller._batch_add_devices(devices_to_add, device_dict, checked_serials)

    def _get_filtered_sorted_devices(
        self, device_dict: Optional[Dict[str, adb_models.DeviceInfo]] = None
    ) -> List[adb_models.DeviceInfo]:
        return self.device_list_controller._get_filtered_sorted_devices(device_dict)

    def _build_device_display_text(self, device: adb_models.DeviceInfo, serial: str) -> str:
        return self.device_list_controller._build_device_display_text(device, serial)

    def _apply_checkbox_content(self, checkbox: QCheckBox, serial: str, device: adb_models.DeviceInfo) -> None:
        self.device_list_controller._apply_checkbox_content(checkbox, serial, device)

    def _configure_device_checkbox(
        self,
        checkbox: QCheckBox,
        serial: str,
        device: adb_models.DeviceInfo,
        checked_serials: Iterable[str],
    ) -> None:
        self.device_list_controller._configure_device_checkbox(checkbox, serial, device, checked_serials)

    def _initialize_virtualized_checkbox(
        self,
        checkbox: QCheckBox,
        serial: str,
        device: adb_models.DeviceInfo,
        checked_serials: Iterable[str],
    ) -> None:
        self.device_list_controller._initialize_virtualized_checkbox(checkbox, serial, device, checked_serials)

    def _get_current_checked_serials(self) -> set:
        return self.device_list_controller._get_current_checked_serials()

    def _release_all_standard_checkboxes(self) -> None:
        self.device_list_controller._release_all_standard_checkboxes()

    def _activate_virtualized_view(self, checked_serials: Optional[Iterable[str]] = None) -> None:
        self.device_list_controller._activate_virtualized_view(checked_serials)

    def _deactivate_virtualized_view(self) -> None:
        self.device_list_controller._deactivate_virtualized_view()

    def _update_virtualized_title(self) -> None:
        self.device_list_controller._update_virtualized_title()

    def _handle_virtualized_selection_change(self, serial: str, is_checked: bool) -> None:
        self.device_list_controller.handle_virtualized_selection_change(serial, is_checked)

    def _acquire_device_checkbox(self) -> QCheckBox:
        return self.device_list_controller.acquire_device_checkbox()

    def _release_device_checkbox(self, checkbox: QCheckBox) -> None:
        self.device_list_controller.release_device_checkbox(checkbox)

    def _create_single_device_ui(self, serial, device, checked_serials):
        self.device_list_controller._create_single_device_ui(serial, device, checked_serials)

    def _batch_update_existing(self, devices_to_update, device_dict):
        self.device_list_controller._batch_update_existing(devices_to_update, device_dict)

    def _perform_standard_device_update(self, device_dict: Dict[str, adb_models.DeviceInfo]):
        self.device_list_controller._perform_standard_device_update(device_dict)

    def _create_standard_device_ui(self, serial, device, checked_serials):
        self.device_list_controller._create_standard_device_ui(serial, device, checked_serials)

    def _update_device_checkbox_text(self, checkbox, device, serial):
        self.device_list_controller._update_device_checkbox_text(checkbox, device, serial)

    def filter_and_sort_devices(self):
        self.device_list_controller.filter_and_sort_devices()

    def on_search_changed(self, text: str):
        self.device_list_controller.on_search_changed(text)

    def on_sort_changed(self, sort_mode: str):
        self.device_list_controller.on_sort_changed(sort_mode)

    def refresh_device_list(self):
        """Manually refresh device list with progressive discovery."""
        try:
            logger.info('🔄 Manual device refresh requested (using DeviceManager)')

            # Use DeviceManager for unified device management
            self.device_manager.force_refresh()

            # Update status to show loading
            if hasattr(self, 'status_bar'):
                self.status_bar.showMessage('🔄 Discovering devices...', 5000)

        except Exception as e:
            logger.error(f'Error starting device refresh: {e}')
            self.error_handler.handle_error(ErrorCode.DEVICE_NOT_FOUND, f'Failed to start refresh: {e}')

            # Fallback to original synchronous method if needed
            try:
                logger.info('Falling back to synchronous device refresh')
                devices = adb_tools.get_devices_list()
                device_dict = {device.device_serial_num: device for device in devices}
                self.update_device_list(device_dict)
                logger.info('Device list refreshed (fallback mode)')
            except Exception as fallback_error:
                logger.error(f'Fallback refresh also failed: {fallback_error}')
                self.error_handler.handle_error(ErrorCode.DEVICE_NOT_FOUND, f'All refresh methods failed: {fallback_error}')

    def select_all_devices(self):
        """Select all connected devices."""
        if self.virtualized_active and self.virtualized_device_list is not None:
            self.virtualized_device_list.select_all_devices()
            logger.info(f'Selected all {len(self.virtualized_device_list.checked_devices)} devices (virtualized)')
            return

        for checkbox in self.check_devices.values():
            checkbox.setChecked(True)
        logger.info(f'Selected all {len(self.check_devices)} devices')

    def select_no_devices(self):
        """Deselect all devices."""
        if self.virtualized_active and self.virtualized_device_list is not None:
            self.virtualized_device_list.deselect_all_devices()
            logger.info('Deselected all devices (virtualized)')
            return

        for checkbox in self.check_devices.values():
            checkbox.setChecked(False)
        logger.info('Deselected all devices')

    # Device Groups functionality
    def save_group(self):
        """Save the currently selected devices as a group."""
        group_name = self.group_name_edit.text().strip()
        if not group_name:
            self.error_handler.show_error('Error', 'Group name cannot be empty.')
            return

        checked_devices = self.get_checked_devices()
        if not checked_devices:
            self.error_handler.show_warning('Warning', 'No devices selected to save in the group.')
            return

        # Check if group already exists
        if group_name in self.device_groups:
            reply = QMessageBox.question(
                self,
                'Confirm',
                f"Group '{group_name}' already exists. Do you want to overwrite it?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply != QMessageBox.StandardButton.Yes:
                return

        serial_numbers = [device.device_serial_num for device in checked_devices]
        self.device_groups[group_name] = serial_numbers

        self.show_info(
            'Success',
            f"Group '{group_name}' saved with {len(serial_numbers)} devices."
        )
        self.update_groups_listbox()
        logger.info(f"Saved group '{group_name}' with devices: {serial_numbers}")

    def delete_group(self):
        """Delete the selected group."""
        current_item = self.groups_listbox.currentItem()
        if not current_item:
            self.show_error('Error', 'No group selected to delete.')
            return

        group_name = current_item.text()
        reply = QMessageBox.question(
            self,
            'Confirm',
            f"Are you sure you want to delete group '{group_name}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            if group_name in self.device_groups:
                del self.device_groups[group_name]
                logger.info(f"Group '{group_name}' deleted.")
                self.update_groups_listbox()
                self.group_name_edit.clear()

    def select_devices_in_group(self):
        """Select devices in the phone list that belong to the selected group."""
        current_item = self.groups_listbox.currentItem()
        if not current_item:
            self.show_error('Error', 'No group selected.')
            return

        group_name = current_item.text()
        self.select_devices_in_group_by_name(group_name)

    def select_devices_in_group_by_name(self, group_name: str):
        """Select devices in the phone list that belong to the given group name."""
        serials_in_group = self.device_groups.get(group_name, [])
        if not serials_in_group:
            logger.info(f"Group '{group_name}' is empty.")
            return

        # First, clear all selections
        self.select_no_devices()

        # Select devices that are in the group and currently connected
        connected_devices = 0
        missing_devices = []

        if self.virtualized_active and self.virtualized_device_list is not None:
            connected_serials = [serial for serial in serials_in_group if serial in self.device_dict]
            missing_devices = [serial for serial in serials_in_group if serial not in self.device_dict]
            self.virtualized_device_list.set_checked_serials(set(connected_serials))
            connected_devices = len(connected_serials)
        else:
            for serial in serials_in_group:
                if serial in self.check_devices:
                    self.check_devices[serial].setChecked(True)
                    connected_devices += 1
                else:
                    missing_devices.append(serial)

        if missing_devices:
            self.show_info(
                'Info',
                f"The following devices from group '{group_name}' are not currently connected:\n" +
                '\n'.join(missing_devices)
            )

        logger.info(f"Selected {connected_devices} devices in group '{group_name}'.")

    def update_groups_listbox(self):
        """Update the listbox with current group names."""
        self.groups_listbox.clear()
        for group_name in sorted(self.device_groups.keys()):
            self.groups_listbox.addItem(group_name)

    def on_group_select(self):
        """Handle selection of a group in the listbox."""
        current_item = self.groups_listbox.currentItem()
        if current_item:
            group_name = current_item.text()
            self.group_name_edit.setText(group_name)

    # Context Menu functionality
    def show_device_list_context_menu(self, position):
        """Show context menu for device list."""
        context_menu = QMenu(self)

        # Basic actions
        refresh_action = context_menu.addAction('Refresh')
        refresh_action.triggered.connect(lambda: self.device_manager.force_refresh())

        select_all_action = context_menu.addAction('Select All')
        select_all_action.triggered.connect(lambda: self.select_all_devices())

        clear_all_action = context_menu.addAction('Clear All')
        clear_all_action.triggered.connect(lambda: self.select_no_devices())

        copy_info_action = context_menu.addAction('Copy Selected Device Info')
        copy_info_action.triggered.connect(lambda: self.copy_selected_device_info())

        context_menu.addSeparator()

        # Group selection submenu
        if self.device_groups:
            group_menu = context_menu.addMenu('Select Group')
            for group_name in sorted(self.device_groups.keys()):
                group_action = group_menu.addAction(group_name)
                group_action.triggered.connect(
                    lambda checked, g=group_name: self.select_devices_in_group_by_name(g)
                )
        else:
            group_action = context_menu.addAction('Select Group')
            group_action.setEnabled(False)
            group_action.setText('No groups available')

        context_menu.addSeparator()

        # Device-specific actions (if devices are selected)
        checked_devices = self.get_checked_devices()
        if checked_devices:
            reboot_action = context_menu.addAction('Reboot Selected')
            reboot_action.triggered.connect(lambda: self.reboot_device())

            enable_bt_action = context_menu.addAction('Enable Bluetooth')
            enable_bt_action.triggered.connect(lambda: self.enable_bluetooth())

            disable_bt_action = context_menu.addAction('Disable Bluetooth')
            disable_bt_action.triggered.connect(lambda: self.disable_bluetooth())

        # Show menu at the cursor position
        global_pos = self.device_scroll.mapToGlobal(position)
        context_menu.exec(global_pos)

    def copy_selected_device_info(self):
        self.device_actions_controller.copy_selected_device_info()

    def show_console_context_menu(self, position):
        """Show context menu for console."""
        context_menu = QMenu(self)

        # Copy action
        copy_action = context_menu.addAction('Copy')
        copy_action.triggered.connect(lambda: self.copy_console_text())

        # Clear action
        clear_action = context_menu.addAction('Clear Console')
        clear_action.triggered.connect(lambda: self.clear_console())

        # Show menu at the cursor position
        global_pos = self.console_text.mapToGlobal(position)
        context_menu.exec(global_pos)

    def copy_console_text(self):
        """Copy selected console text to clipboard."""
        cursor = self.console_text.textCursor()
        if cursor.hasSelection():
            selected_text = cursor.selectedText()
            clipboard = QApplication.clipboard()
            clipboard.setText(selected_text)
            logger.info('Copied selected console text to clipboard')
        else:
            # If no selection, copy all console text
            all_text = self.console_text.toPlainText()
            clipboard = QApplication.clipboard()
            clipboard.setText(all_text)
            logger.info('Copied all console text to clipboard')

    def clear_console(self):
        """Clear the console output."""
        self.console_text.clear()
        logger.info('Console cleared')

    def _check_scrcpy_available(self):
        """Check if scrcpy is available (deprecated - use app_management_manager)."""
        return self.app_management_manager.check_scrcpy_available()

    def update_selection_count(self):
        """Update the title to show current selection count."""
        if self.virtualized_active and self.virtualized_device_list is not None:
            self._update_virtualized_title()
            return

        device_count = len(self.device_dict)
        selected_count = len(self.get_checked_devices())
        search_text = self.device_search_manager.get_search_text()
        if search_text:
            visible_count = sum(1 for checkbox in self.check_devices.values() if checkbox.isVisible())
            self.title_label.setText(f'Connected Devices ({visible_count}/{device_count}) - Selected: {selected_count}')
        else:
            self.title_label.setText(f'Connected Devices ({device_count}) - Selected: {selected_count}')

    def show_device_context_menu(self, position, device_serial, checkbox_widget):
        """Delegate context menu handling to the device actions controller."""
        self.device_actions_controller.show_context_menu(position, device_serial, checkbox_widget)

    def select_only_device(self, target_serial):
        """Expose device selection through the controller."""
        self.device_actions_controller.select_only_device(target_serial)

    def deselect_device(self, target_serial):
        """Expose deselection through the controller."""
        self.device_actions_controller.deselect_device(target_serial)

    def launch_ui_inspector_for_device(self, device_serial):
        self.device_actions_controller.launch_ui_inspector_for_device(device_serial)

    def reboot_single_device(self, device_serial):
        self.device_actions_controller.reboot_single_device(device_serial)

    def take_screenshot_single_device(self, device_serial):
        self.device_actions_controller.take_screenshot_single_device(device_serial)

    def launch_scrcpy_single_device(self, device_serial):
        self.device_actions_controller.launch_scrcpy_single_device(device_serial)

    def filter_and_sort_devices(self):
        """Filter and sort devices based on current search and sort settings."""
        if self.virtualized_active and self.virtualized_device_list is not None:
            self.virtualized_device_list.apply_search_and_sort()
            self._update_virtualized_title()
            return

        if not hasattr(self, 'device_layout'):
            return

        # Get all devices
        devices = list(self.device_dict.values())

        # Use search manager to filter and sort
        sorted_devices = self.device_search_manager.search_and_sort_devices(
            devices,
            self.device_search_manager.get_search_text(),
            self.device_search_manager.get_sort_mode()
        )

        # Create device items with checkboxes
        device_items = []
        for device in sorted_devices:
            serial = device.device_serial_num
            if serial in self.check_devices:
                checkbox = self.check_devices[serial]
                device_items.append((serial, device, checkbox))

        # Reorder widgets in layout
        visible_serials = set()
        for i, (serial, device, checkbox) in enumerate(device_items):
            # Remove from layout
            self.device_layout.removeWidget(checkbox)
            # Insert at correct position (before the stretch item)
            self.device_layout.insertWidget(i, checkbox)
            checkbox.setVisible(True)
            visible_serials.add(serial)

        # Hide devices that don't match search
        for serial, checkbox in self.check_devices.items():
            if serial not in visible_serials:
                checkbox.setVisible(False)

        # Update device count
        visible_count = len(device_items)
        total_count = len(self.device_dict)
        if hasattr(self, 'title_label'):
            search_text = self.device_search_manager.get_search_text()
            if search_text:
                self.title_label.setText(f'Connected Devices ({visible_count}/{total_count})')
            else:
                self.title_label.setText(f'Connected Devices ({total_count})')

    def on_search_changed(self, text: str):
        """Handle search text change."""
        self.device_search_manager.set_search_text(text.strip())
        self.filter_and_sort_devices()

    def on_sort_changed(self, sort_mode: str):
        """Handle sort mode change."""
        self.device_search_manager.set_sort_mode(sort_mode)
        self.filter_and_sort_devices()

    def copy_single_device_info(self, device_serial):
        self.device_actions_controller.copy_single_device_info(device_serial)

    def browse_output_path(self):
        """Browse for output directory."""
        directory = QFileDialog.getExistingDirectory(self, 'Select Output Directory')
        if directory:
            # Use common.py to ensure proper path handling
            normalized_path = common.make_gen_dir_path(directory)
            self.output_path_edit.setText(normalized_path)

    def browse_file_generation_output_path(self):
        """Browse and select file generation output directory."""
        directory = QFileDialog.getExistingDirectory(self, 'Select File Generation Output Directory')
        if directory:
            # Use common.py to ensure proper path handling
            normalized_path = common.make_gen_dir_path(directory)
            self.file_gen_output_path_edit.setText(normalized_path)
            logger.info(f'Selected file generation output directory: {normalized_path}')


    def run_in_thread(self, func, *args):
        """Run function in a separate thread with enhanced error handling."""
        def wrapper():
            try:
                logger.info(f'Starting background operation: {func.__name__}')
                result = func(*args)
                logger.info(f'Background operation completed: {func.__name__}')
                return result
            except FileNotFoundError as e:
                error_msg = f'File not found: {str(e)}'
                logger.error(f'{func.__name__}: {error_msg}')
                QTimer.singleShot(0, lambda: self.show_error('File Error', error_msg))
            except PermissionError as e:
                error_msg = f'Permission denied: {str(e)}'
                logger.error(f'{func.__name__}: {error_msg}')
                QTimer.singleShot(0, lambda: self.show_error('Permission Error', error_msg))
            except ConnectionError as e:
                error_msg = f'Device connection error: {str(e)}'
                logger.error(f'{func.__name__}: {error_msg}')
                QTimer.singleShot(0, lambda: self.show_error('Connection Error', error_msg))
            except Exception as e:
                error_msg = f'Operation failed: {str(e)}'
                logger.error(f'Error in {func.__name__}: {e}', exc_info=True)
                QTimer.singleShot(0, lambda: self.show_error('Error', error_msg))

        thread = threading.Thread(target=wrapper, daemon=True, name=f'BG-{func.__name__}')
        thread.start()

    def _run_adb_tool_on_selected_devices(self, tool_func, description: str, *args, show_progress=True, **kwargs):
        """Run ADB tool on selected devices with enhanced progress feedback and operation tracking."""
        devices = self.get_checked_devices()
        if not devices:
            self.show_error('Error', 'No devices selected.')
            return

        serials = [d.device_serial_num for d in devices]
        device_count = len(devices)
        device_models = [d.device_model for d in devices]

        logger.info(f'Running {description} on {device_count} device(s): {serials}')

        # Set operation status for all devices
        for serial in serials:
            self.device_operations[serial] = description

        # Trigger device list refresh to show operation status
        QTimer.singleShot(100, self.device_manager.force_refresh)

        if show_progress:
            device_list = ', '.join(device_models[:3])
            if len(device_models) > 3:
                device_list += f'... (and {len(device_models)-3} more)'

            self.show_info(
                f'{description.title()} In Progress',
                f'Running {description} on {device_count} device(s):\n{device_list}\n\nPlease wait...'
            )

        def wrapper():
            try:
                tool_func(serials, *args, **kwargs)
                if show_progress:
                    # Success notification on main thread
                    QTimer.singleShot(0, lambda: self.show_info(
                        f'{description.title()} Complete',
                        f'Successfully completed {description} on {device_count} device(s)'
                    ))
            except Exception as e:
                if show_progress:
                    # Error notification on main thread
                    QTimer.singleShot(0, lambda: self.show_error(
                        f'{description.title()} Failed',
                        f'Failed to complete {description}:\n{str(e)}'
                    ))
                raise e  # Re-raise to be handled by run_in_thread
            finally:
                # Clear operation status for all devices
                QTimer.singleShot(0, lambda: self._clear_device_operations(serials))

        self.run_in_thread(wrapper)

    def _clear_device_operations(self, serials):
        """Clear operation status for specified devices."""
        for serial in serials:
            if serial in self.device_operations:
                del self.device_operations[serial]
        # Refresh device list to update display
        self.device_manager.force_refresh()

    # ADB Server methods
    def adb_start_server(self):
        """Start ADB server."""
        self.run_in_thread(adb_tools.start_adb_server)
        logger.info('Starting ADB server...')

    def adb_kill_server(self):
        """Kill ADB server."""
        self.run_in_thread(adb_tools.kill_adb_server)
        logger.info('Killing ADB server...')

    # ADB Tools methods
    @ensure_devices_selected
    def reboot_device(self):
        """Reboot selected devices."""
        self._run_adb_tool_on_selected_devices(adb_tools.start_reboot, 'reboot')


    @ensure_devices_selected
    def install_apk(self):
        """Install APK on selected devices."""
        self.app_management_manager.install_apk_dialog()

    def _install_apk_with_progress(self, devices, apk_file, apk_name):
        """Install APK with device-by-device progress updates."""
        total_devices = len(devices)
        successful_installs = 0
        failed_installs = 0

        for index, device in enumerate(devices, 1):
            try:
                # Update progress
                progress_msg = f'Installing {apk_name} on device {index}/{total_devices}\n\n' \
                             f'📱 Current: {device.device_model} ({device.device_serial_num})\n' \
                             f'✅ Success: {successful_installs}\n' \
                             f'❌ Failed: {failed_installs}'

                # Show progress update (using QTimer to ensure thread safety)
                QTimer.singleShot(0, lambda msg=progress_msg:
                    self.error_handler.show_info('📦 APK Installation Progress', msg))

                # Install on current device
                result = adb_tools.install_the_apk([device.device_serial_num], apk_file)

                if result and any('Success' in str(r) for r in result):
                    successful_installs += 1
                    logger.info(f'APK installed successfully on {device.device_model}')
                else:
                    failed_installs += 1
                    logger.warning(f'APK installation failed on {device.device_model}: {result}')

            except Exception as e:
                failed_installs += 1
                logger.error(f'APK installation error on {device.device_model}: {e}')

        # Final result
        final_msg = f'APK Installation Complete!\n\n' \
                   f'📄 APK: {apk_name}\n' \
                   f'📱 Total Devices: {total_devices}\n' \
                   f'✅ Successful: {successful_installs}\n' \
                   f'❌ Failed: {failed_installs}'

        QTimer.singleShot(0, lambda:
            self.error_handler.show_info('📦 Installation Complete', final_msg))


    @ensure_devices_selected
    def take_screenshot(self):
        """Take screenshot of selected devices using new utils module."""
        output_path = self.output_path_edit.text().strip()

        # Validate output path using utils
        validated_path = validate_screenshot_path(output_path)
        if not validated_path:
            self.error_handler.handle_error(ErrorCode.FILE_NOT_FOUND,
                                           'Please select a valid output directory first.')
            return

        devices = self.get_checked_devices()
        device_count = len(devices)
        device_models = [d.device_model for d in devices]

        # Set devices as in operation (Screenshot)
        for device in devices:
            self.device_manager.set_device_operation_status(device.device_serial_num, 'Screenshot')
        self.device_manager.force_refresh()

        # Update UI state
        self._update_screenshot_button_state(True)

        # Remove the progress notification - user will see the completion notification only

        # Use new screenshot utils with callback
        def screenshot_callback(output_path, device_count, device_models):
            logger.info(f'🔧 [CALLBACK RECEIVED] Screenshot callback called with output_path={output_path}, device_count={device_count}, device_models={device_models}')
            # Use signal emission to safely execute in main thread instead of QTimer
            logger.info(f'🔧 [CALLBACK RECEIVED] About to emit screenshot_completed_signal')
            try:
                # Only use the signal to avoid duplicate notifications
                self.screenshot_completed_signal.emit(output_path, device_count, device_models)
                logger.info(f'🔧 [CALLBACK RECEIVED] screenshot_completed_signal emitted successfully')
                # Clean up device operation status
                for device in devices:
                    self.device_manager.clear_device_operation_status(device.device_serial_num)
                self.device_manager.force_refresh()
            except Exception as signal_error:
                logger.error(f'🔧 [CALLBACK RECEIVED] Signal emission failed: {signal_error}')
                import traceback
                logger.error(f'🔧 [CALLBACK RECEIVED] Traceback: {traceback.format_exc()}')

        take_screenshots_batch(devices, validated_path, screenshot_callback)

    @ensure_devices_selected
    def start_screen_record(self):
        """Start screen recording using new recording manager."""
        output_path = self.output_path_edit.text().strip()

        # Validate output path using utils
        validated_path = validate_recording_path(output_path)
        if not validated_path:
            self.error_handler.handle_error(ErrorCode.FILE_NOT_FOUND,
                                           'Please select a valid output directory first.')
            return

        devices = self.get_checked_devices()

        # Check if any devices are already recording
        already_recording = []
        for device in devices:
            if self.recording_manager.is_recording(device.device_serial_num):
                already_recording.append(f"{device.device_model} ({device.device_serial_num[:8]}...)")

        if already_recording:
            self.error_handler.show_warning(
                'Devices Already Recording',
                f'The following devices are already recording:\n\n'
                f'{chr(10).join(already_recording)}\n\n'
                f'Please stop these recordings first or select different devices.'
            )
            return

        device_count = len(devices)

        # Show info about recording
        self.error_handler.show_info(
            'Screen Recording Started',
            f'Starting recording on {device_count} device(s)...\n\n'
            f'📍 Important Notes:\n'
            f'• ADB has a 3-minute recording limit per session\n'
            f'• Each device records independently\n'
            f'• You can stop recording manually or it will auto-stop\n\n'
            f'Files will be saved to: {validated_path}'
        )

        # Use new recording manager with callbacks
        def recording_callback(device_name, device_serial, duration, filename, output_path):
            self.recording_stopped_signal.emit(device_name, device_serial, duration, filename, output_path)
            self.recording_state_cleared_signal.emit(device_serial)

        def recording_progress(event_payload: dict):
            self.recording_progress_signal.emit(event_payload)

        success = self.recording_manager.start_recording(
            devices,
            validated_path,
            completion_callback=recording_callback,
            progress_callback=recording_progress,
        )
        if not success:
            self.error_handler.handle_error(ErrorCode.COMMAND_FAILED, 'Failed to start recording')
            return

        # Track active recordings locally for UI updates
        for device in devices:
            serial = device.device_serial_num
            if self.recording_manager.is_recording(serial):
                self.device_recordings[serial] = {
                    'active': True,
                    'output_path': validated_path,
                    'device_name': device.device_model,
                    'segments': [],
                    'elapsed_before_current': 0.0,
                    'ongoing_start': datetime.datetime.now(),
                    'display_seconds': 0,
                }
                self.device_operations[serial] = 'Recording'
                self.write_to_console(
                    f"🎬 Recording started for {device.device_model} ({serial[:8]}...)"
                )

        self.update_recording_status()

    def _on_recording_stopped(self, device_name, device_serial, duration, filename, output_path):
        """Handle recording stopped signal in main thread."""
        logger.info(f'🔴 [SIGNAL] _on_recording_stopped executing in main thread for {device_serial}')
        self.show_info(
            'Recording Stopped',
            f'Recording stopped for {device_name}\n'
            f'Duration: {duration}\n'
            f'File: {filename}.mp4\n'
            f'Location: {output_path}'
        )

        record = self.device_recordings.setdefault(device_serial, {
            'segments': [],
            'elapsed_before_current': 0.0,
            'ongoing_start': None,
            'display_seconds': 0,
        })
        record['active'] = False
        record['last_duration'] = duration
        record['last_filename'] = f'{filename}.mp4'
        record['output_path'] = output_path
        record['device_name'] = device_name
        record['elapsed_before_current'] = self._parse_duration_to_seconds(duration)
        record['ongoing_start'] = None
        record['display_seconds'] = int(record['elapsed_before_current'])

        if device_serial in self.device_operations:
            del self.device_operations[device_serial]

        self.write_to_console(
            f"✅ Recording stopped for {device_name} ({device_serial[:8]}...) -> {filename}.mp4 ({duration})"
        )
        self.update_recording_status()
        logger.info(f'🔴 [SIGNAL] _on_recording_stopped completed for {device_serial}')

    def _on_recording_state_cleared(self, device_serial):
        """Handle recording state cleared signal in main thread."""
        logger.info(f'🔄 [SIGNAL] _on_recording_state_cleared executing in main thread for {device_serial}')
        if device_serial in self.device_recordings:
            logger.info(f'🔄 [SIGNAL] Setting active=False for {device_serial}')
            self.device_recordings[device_serial]['active'] = False
        if device_serial in self.device_operations:
            logger.info(f'🔄 [SIGNAL] Removing operation for {device_serial}')
            del self.device_operations[device_serial]
        logger.info(f'🔄 [SIGNAL] Triggering UI refresh for {device_serial}')
        self.device_manager.force_refresh()
        self.update_recording_status()
        logger.info(f'🔄 [SIGNAL] _on_recording_state_cleared completed for {device_serial}')

    def _on_recording_progress_event(self, event_payload: dict):
        """Handle asynchronous recording progress updates."""
        try:
            event_type = event_payload.get('type')
            device_serial = event_payload.get('device_serial')
            if not event_type or not device_serial:
                return

            device_name = event_payload.get('device_name', device_serial)
            record = self.device_recordings.setdefault(
                device_serial,
                {
                    'active': True,
                    'output_path': event_payload.get('output_path'),
                    'device_name': device_name,
                    'segments': [],
                    'elapsed_before_current': 0.0,
                    'ongoing_start': datetime.datetime.now(),
                    'display_seconds': 0,
                },
            )
            record['device_name'] = device_name

            if event_type == 'segment_completed':
                segment_index = event_payload.get('segment_index')
                try:
                    segment_index_display = int(segment_index)
                except (TypeError, ValueError):
                    segment_index_display = None

                segment_filename = event_payload.get('segment_filename', 'unknown')
                duration_seconds = float(event_payload.get('duration_seconds', 0.0) or 0.0)
                total_duration = float(event_payload.get('total_duration_seconds', 0.0) or 0.0)

                record['active'] = True
                record['output_path'] = event_payload.get('output_path') or record.get('output_path')
                record.setdefault('segments', [])
                record['segments'].append(
                    {
                        'index': segment_index_display,
                        'filename': segment_filename,
                        'duration_seconds': duration_seconds,
                        'total_duration_seconds': total_duration,
                    }
                )

                # Keep only the latest 20 segments to prevent unbounded growth
                if len(record['segments']) > 20:
                    record['segments'] = record['segments'][-20:]

                self.device_operations[device_serial] = 'Recording'

                record['elapsed_before_current'] = total_duration
                record['ongoing_start'] = None if event_payload.get('request_origin') == 'user' else datetime.datetime.now()
                record['display_seconds'] = int(total_duration)

                duration_display = f"{duration_seconds:.1f}s"
                segment_label = (
                    f"{segment_index_display:02d}" if isinstance(segment_index_display, int) else "?"
                )
                self.write_to_console(
                    f"🎬 Segment {segment_label} saved for {device_name} ({device_serial[:8]}...) -> {segment_filename} ({duration_display})"
                )
                self.update_recording_status()

            elif event_type == 'error':
                message = event_payload.get('message', 'Unknown error')
                self.write_to_console(
                    f"❌ Recording error on {device_name} ({device_serial[:8]}...): {message}"
                )
                self.error_handler.show_warning(
                    'Recording Warning',
                    f'Device {device_name} encountered an issue:\n{message}'
                )
                if device_serial in self.device_recordings:
                    self.device_recordings[device_serial]['active'] = False
                    self.device_recordings[device_serial]['ongoing_start'] = None
                    self.device_recordings[device_serial]['display_seconds'] = int(
                        self.device_recordings[device_serial].get('elapsed_before_current', 0.0)
                    )
                if device_serial in self.device_operations:
                    del self.device_operations[device_serial]
                self.update_recording_status()

        except Exception as exc:  # pragma: no cover - UI defensive handling
            logger.error(f'Failed to process recording progress event: {exc}')

    def _on_device_operation_completed(self, operation, device_serial, success, message):
        """Handle device operation completed signal."""
        status_icon = "✅" if success else "❌"
        self.write_to_console(f"{status_icon} {operation} on device {device_serial}: {message}")

        if not success:
            # Show error for failed operations
            self.show_error(f"{operation.capitalize()} Failed", f"Device {device_serial}: {message}")

    def _on_screenshot_completed(self, output_path, device_count, device_models):
        """Handle screenshot completed signal in main thread."""
        logger.info(f'📷 [SIGNAL] _on_screenshot_completed executing in main thread')

        # Create enhanced success message
        device_list = ', '.join(device_models[:3])
        if len(device_models) > 3:
            device_list += f' and {len(device_models) - 3} more'

        # Show a simple success notification instead of modal dialog
        self.show_info('📷 Screenshots Completed',
                      f'✅ Successfully captured {device_count} screenshot(s)\n'
                      f'📱 Devices: {device_list}\n'
                      f'📁 Location: {output_path}')

        # Restore screenshot button state
        self._update_screenshot_button_state(False)

        logger.info(f'📷 [SIGNAL] _on_screenshot_completed notification shown')
        return  # Skip the dialog creation


    def _open_folder(self, path):
        """Open the specified folder in system file manager."""

        try:
            if platform.system() == 'Darwin':  # macOS
                subprocess.run(['open', path])
            elif platform.system() == 'Windows':  # Windows
                subprocess.run(['explorer', path])
            else:  # Linux
                subprocess.run(['xdg-open', path])
            logger.info(f'📁 Opened folder: {path}')
        except Exception as e:
            logger.error(f'❌ Failed to open folder: {e}')
            self.show_error('Error', f'Could not open folder:\n{path}\n\nError: {e}')

    def _show_screenshot_quick_actions(self, output_path, device_models):
        """Show quick actions menu for screenshots."""

        dialog = QDialog(self)
        dialog.setWindowTitle('⚡ Screenshot Quick Actions')
        dialog.setModal(True)
        dialog.resize(350, 250)

        layout = QVBoxLayout(dialog)

        # Title
        title_label = QLabel('⚡ Quick Actions for Screenshots')
        StyleManager.apply_label_style(title_label, LabelStyle.HEADER)
        layout.addWidget(title_label)

        # Find screenshot files
        screenshot_files = []
        try:
            # Look for common screenshot file patterns
            patterns = ['*.png', '*.jpg', '*.jpeg']
            for pattern in patterns:
                screenshot_files.extend(glob.glob(os.path.join(output_path, pattern)))
            screenshot_files = sorted(screenshot_files, key=os.path.getmtime, reverse=True)
        except Exception as e:
            logger.error(f'Error finding screenshots: {e}')

        # Info label
        info_label = QLabel(f'📱 Screenshots from: {", ".join(device_models[:2])}{"..." if len(device_models) > 2 else ""}')
        StyleManager.apply_label_style(info_label, LabelStyle.INFO)
        layout.addWidget(info_label)

        # Action buttons use centralized style
        button_style = StyleManager.get_action_button_style()

        # Take another screenshot
        another_screenshot_btn = QPushButton('📷 Take Another Screenshot')
        another_screenshot_btn.setStyleSheet(button_style)
        another_screenshot_btn.clicked.connect(lambda: (dialog.accept(), self.take_screenshot()))
        layout.addWidget(another_screenshot_btn)

        # Start recording
        start_recording_btn = QPushButton('🎥 Start Recording Same Devices')
        start_recording_btn.setStyleSheet(button_style)
        start_recording_btn.clicked.connect(lambda: (dialog.accept(), self.start_screen_record()))
        layout.addWidget(start_recording_btn)

        # Copy path to clipboard
        copy_path_btn = QPushButton('📋 Copy Folder Path')
        copy_path_btn.setStyleSheet(button_style)
        copy_path_btn.clicked.connect(lambda: self._copy_to_clipboard(output_path))
        layout.addWidget(copy_path_btn)

        # Show file count if available
        if screenshot_files:
            file_count_label = QLabel(f'📁 Found {len(screenshot_files)} screenshot file(s)')
            StyleManager.apply_label_style(file_count_label, LabelStyle.INFO)
            layout.addWidget(file_count_label)

        # Close button
        close_btn = QPushButton('Close')
        StyleManager.apply_button_style(close_btn, ButtonStyle.NEUTRAL)
        close_btn.clicked.connect(dialog.accept)
        layout.addWidget(close_btn)

        dialog.exec()

    def _copy_to_clipboard(self, text):
        """Copy text to system clipboard."""
        try:
            clipboard = QGuiApplication.clipboard()
            clipboard.setText(text)
            self.show_info('📋 Copied!', f'Path copied to clipboard:\n{text}')
            logger.info(f'📋 Copied to clipboard: {text}')
        except Exception as e:
            logger.error(f'❌ Failed to copy to clipboard: {e}')
            self.show_error('Error', f'Could not copy to clipboard:\n{e}')

    def _handle_screenshot_completion(self, output_path, device_count, device_models, devices):
        """Handle screenshot completion in main thread."""
        logger.info(f'📷 [MAIN THREAD] Screenshot completion handler executing with params: output_path={output_path}, device_count={device_count}, device_models={device_models}')

        # Emit signal in main thread
        logger.info(f'📷 [MAIN THREAD] About to emit screenshot_completed_signal')
        try:
            self.screenshot_completed_signal.emit(output_path, device_count, device_models)
            logger.info(f'📷 [MAIN THREAD] screenshot_completed_signal emitted successfully')
        except Exception as signal_error:
            logger.error(f'📷 [MAIN THREAD] Signal emission failed: {signal_error}')

        # Clear operation status
        for device in devices:
            self.device_manager.set_device_operation_status(device.device_serial_num, 'Idle')

        # Refresh UI
        logger.info(f'📷 [MAIN THREAD] About to refresh device list')
        self.device_manager.force_refresh()
        logger.info(f'📷 [MAIN THREAD] About to reset screenshot button state')
        self._update_screenshot_button_state(False)
        logger.info(f'📷 [MAIN THREAD] Screenshot completion handler finished')

    def _update_screenshot_button_state(self, in_progress: bool):
        """Update screenshot button state."""
        logger.info(f'🔧 [BUTTON STATE] Updating screenshot button state, in_progress={in_progress}')
        if not self.screenshot_btn:
            logger.warning(f'🔧 [BUTTON STATE] screenshot_btn is None, cannot update state')
            return

        if in_progress:
            self.screenshot_btn.setText('📷 Taking Screenshots...')
            self.screenshot_btn.setEnabled(False)
            self.screenshot_btn.setStyleSheet(StyleManager.get_status_styles()['screenshot_processing'])
        else:
            logger.info(f'🔧 [BUTTON STATE] Resetting screenshot button to default state')
            self.screenshot_btn.setText('📷 Take Screenshot')
            self.screenshot_btn.setEnabled(True)
            # Set proper default style
            self.screenshot_btn.setStyleSheet(StyleManager.get_status_styles()['screenshot_ready'])
            logger.info('📷 [BUTTON STATE] Screenshot button reset to default state successfully')

    def _on_file_generation_completed(self, operation_name, output_path, device_count, icon):
        """Handle file generation completed signal in main thread."""
        logger.info(f'{icon} [SIGNAL] _on_file_generation_completed executing in main thread')

        # Create enhanced success dialog similar to screenshot completion
        dialog = QDialog(self)
        dialog.setWindowTitle(f'{icon} {operation_name} Completed')
        dialog.setModal(True)
        dialog.resize(450, 200)

        layout = QVBoxLayout(dialog)

        # Success message
        success_label = QLabel(f'✅ Successfully completed {operation_name.lower()}')
        StyleManager.apply_label_style(success_label, LabelStyle.SUCCESS)
        layout.addWidget(success_label)

        # Device info
        device_label = QLabel(f'📱 Processed: {device_count} device(s)')
        StyleManager.apply_label_style(device_label, LabelStyle.INFO)
        layout.addWidget(device_label)

        # Path info
        path_label = QLabel(f'📁 Location: {output_path}')
        StyleManager.apply_label_style(path_label, LabelStyle.INFO)
        path_label.setWordWrap(True)
        layout.addWidget(path_label)

        # Button layout
        button_layout = QHBoxLayout()

        # Open folder button
        open_folder_btn = QPushButton('🗂️ Open Folder')
        StyleManager.apply_button_style(open_folder_btn, ButtonStyle.SECONDARY)
        open_folder_btn.clicked.connect(lambda: self._open_folder(output_path))
        button_layout.addWidget(open_folder_btn)

        # Close button
        close_btn = QPushButton('Close')
        StyleManager.apply_button_style(close_btn, ButtonStyle.NEUTRAL)
        close_btn.clicked.connect(dialog.accept)
        button_layout.addWidget(close_btn)

        layout.addWidget(QLabel())  # Spacer
        layout.addLayout(button_layout)

        dialog.exec()
        logger.info(f'{icon} [SIGNAL] _on_file_generation_completed dialog closed')

    def _on_console_output(self, message):
        """Handle console output signal in main thread."""
        try:
            if hasattr(self, 'console_text') and self.console_text:
                cursor = self.console_text.textCursor()
                cursor.movePosition(QTextCursor.MoveOperation.End)
                cursor.insertText(f'{message}\n')
                self.console_text.setTextCursor(cursor)
                # Ensure scroll to bottom
                self.console_text.ensureCursorVisible()
        except Exception as e:
            logger.error(f'Error in _on_console_output: {e}')

    def _handle_installation_completed(self, successful_installs: int, failed_installs: int, apk_name: str):
        """處理APK安裝完成信號"""
        try:
            total_devices = successful_installs + failed_installs

            if successful_installs > 0 and failed_installs == 0:
                # 全部成功
                self.show_info(
                    '✅ APK Installation Successful',
                    f'Successfully installed {apk_name} on all {successful_installs} device(s)!'
                )
            elif successful_installs > 0 and failed_installs > 0:
                # 部分成功
                self.show_warning(
                    '⚠️ APK Installation Partially Successful',
                    f'APK: {apk_name}\n\n'
                    f'✅ Successful: {successful_installs}\n'
                    f'❌ Failed: {failed_installs}\n'
                    f'📊 Total: {total_devices}'
                )
            else:
                # 全部失敗
                self.show_error(
                    '❌ APK Installation Failed',
                    f'Failed to install {apk_name} on all {total_devices} device(s).'
                )

            logger.info(f'APK installation completed: {successful_installs} successful, {failed_installs} failed')

        except Exception as e:
            logger.error(f'Error in _handle_installation_completed: {e}')
            self.show_error('Installation Error', f'Error processing installation results: {str(e)}')

    def _handle_installation_progress(self, message: str, current: int, total: int):
        """處理APK安裝進度信號（可選，用於額外的進度處理）"""
        pass

    def _handle_installation_error(self, error_message: str):
        """處理APK安裝錯誤信號"""
        try:
            self.show_error('APK Installation Error', error_message)
            logger.error(f'APK installation error: {error_message}')
        except Exception as e:
            logger.error(f'Error in _handle_installation_error: {e}')

    def _clear_device_recording(self, serial):
        """Clear recording state for a specific device."""
        if serial in self.device_recordings:
            self.device_recordings[serial]['active'] = False
            # Also remove from device operations if it exists
            if serial in self.device_operations and self.device_operations[serial] == 'Recording':
                del self.device_operations[serial]
            # Force refresh device list to update display
            self.device_manager.force_refresh()
            # Update recording status panel
            self.update_recording_status()
        else:
            pass

    def stop_screen_record(self):
        """Stop screen recording using new recording manager."""
        # Check if there are any active recordings
        if self.recording_manager.get_active_recordings_count() == 0:
            self.error_handler.show_warning('No Active Recordings',
                                           'No active recordings found.\n\n'
                                           'Please start recording first, or the recordings may have already stopped automatically.')
            return

        # Get selected devices to determine which recordings to stop
        selected_devices = self.get_checked_devices()

        if selected_devices:
            # Stop recording only on selected devices
            devices_to_stop = []
            for device in selected_devices:
                if self.recording_manager.is_recording(device.device_serial_num):
                    devices_to_stop.append(device.device_serial_num)

            if not devices_to_stop:
                # Show which devices are currently recording
                all_statuses = self.recording_manager.get_all_recording_statuses()
                recording_list = []
                for serial, status in all_statuses.items():
                    if 'Recording' in status and serial in self.device_dict:
                        device_name = self.device_dict[serial].device_model
                        recording_list.append(f"{device_name} ({serial[:8]}...)")

                self.error_handler.show_warning(
                    'No Selected Devices Recording',
                    f'None of the selected devices are currently recording.\n\n'
                    f'Currently recording devices:\n{chr(10).join(recording_list)}\n\n'
                    f'Please select the devices you want to stop recording.'
                )
                return

            # Stop recording on specific devices
            for serial in devices_to_stop:
                self.recording_manager.stop_recording(serial)
                logger.info(f'Stopped recording for device: {serial}')
        else:
            # Stop all recordings if no devices are selected
            stopped_devices = self.recording_manager.stop_recording()
            logger.info(f'Stopped all recordings on {len(stopped_devices)} devices')

    @ensure_devices_selected
    def enable_bluetooth(self):
        """Enable Bluetooth on selected devices."""
        def bluetooth_wrapper(serials):
            adb_tools.switch_bluetooth_enable(serials, True)
            # Trigger device list refresh to update status
            QTimer.singleShot(1000, self.device_manager.force_refresh)

        # Disable progress dialog, only show completion notification
        self._run_adb_tool_on_selected_devices(bluetooth_wrapper, 'enable Bluetooth', show_progress=False)

        # Show completion notification immediately
        devices = self.get_checked_devices()
        device_count = len(devices)
        self.show_info('🔵 Enable Bluetooth Complete',
                      f'✅ Successfully enabled Bluetooth on {device_count} device(s)')

    @ensure_devices_selected
    def disable_bluetooth(self):
        """Disable Bluetooth on selected devices."""
        def bluetooth_wrapper(serials):
            adb_tools.switch_bluetooth_enable(serials, False)
            # Trigger device list refresh to update status
            QTimer.singleShot(1000, self.device_manager.force_refresh)

        # Disable progress dialog, only show completion notification
        self._run_adb_tool_on_selected_devices(bluetooth_wrapper, 'disable Bluetooth', show_progress=False)

        # Show completion notification immediately
        devices = self.get_checked_devices()
        device_count = len(devices)
        self.show_info('🔴 Disable Bluetooth Complete',
                      f'✅ Successfully disabled Bluetooth on {device_count} device(s)')

    @ensure_devices_selected
    def clear_logcat(self):
        """Clear logcat on selected devices using logging manager."""
        self.logging_manager.logcat_manager.clear_logcat_selected_devices()

    def _open_logcat_for_device(self, device: adb_models.DeviceInfo) -> None:
        """Create and show the logcat window for a device."""
        if not device:
            self.show_error('Error', 'Selected device is not available.')
            return

        try:
            self.logcat_window = LogcatWindow(device, self)
            self.logcat_window.show()
        except Exception as exc:
            logger.error('Failed to open logcat window: %s', exc)
            self.show_error('Logcat Error', f'Unable to launch Logcat viewer.\n\nDetails: {exc}')

    @ensure_devices_selected
    def show_logcat(self):
        """Show logcat viewer for the single selected device."""
        selected_devices = self.get_checked_devices()
        if not selected_devices:
            self.show_error('Error', 'Please select a device.')
            return

        if len(selected_devices) > 1:
            self.show_error('Error', 'Please select only one device for logcat viewing.')
            return

        self._open_logcat_for_device(selected_devices[0])

    def view_logcat_for_device(self, device_serial: str) -> None:
        """Launch the logcat viewer for the device under the context menu pointer."""
        device = self.device_dict.get(device_serial)
        if not device:
            self.show_error('Logcat Error', 'Target device is no longer available.')
            return

        self._open_logcat_for_device(device)

    # Shell commands
    @ensure_devices_selected
    def run_shell_command(self):
        """Run shell command on selected devices using command execution manager."""
        command = self.shell_cmd_edit.text().strip()
        devices = self.get_checked_devices()
        self.command_execution_manager.run_shell_command(command, devices)

    # Enhanced command execution methods
    def add_template_command(self, command):
        """Add a template command to the batch commands area using command execution manager."""
        self.command_execution_manager.add_template_command(command)

    @ensure_devices_selected
    def run_single_command(self):
        """Run the currently selected/first command from batch area."""
        text = self.batch_commands_edit.toPlainText().strip()
        if not text:
            self.show_error('Error', 'Please enter commands in the batch area.')
            return

        # Get cursor position to determine which line to execute
        cursor = self.batch_commands_edit.textCursor()
        current_line = cursor.blockNumber()

        lines = text.split('\n')
        if current_line < len(lines):
            command = lines[current_line].strip()
        else:
            command = lines[0].strip()  # Default to first line

        # Skip comments and empty lines
        if not command or command.startswith('#'):
            self.show_error('Error', 'Selected line is empty or a comment.')
            return

        self.execute_single_command(command)

    @ensure_devices_selected
    def run_batch_commands(self):
        """Run all commands simultaneously using command execution manager."""
        commands = self.get_valid_commands()
        devices = self.get_checked_devices()
        self.command_execution_manager.execute_batch_commands(commands, devices)


    def execute_single_command(self, command):
        """Execute a single command and add to history using command execution manager."""
        devices = self.get_checked_devices()
        self.command_execution_manager.execute_single_command(command, devices)

    def log_command_results(self, command, serials, results):
        """Log command results to console with proper formatting."""
        logger.info(f'🔍 Processing results for command: {command}')

        if not results:
            logger.warning(f'❌ No results for command: {command}')
            self.write_to_console(f'❌ No results: {command}')
            return

        # Convert results to list if it's not already
        results_list = list(results) if not isinstance(results, list) else results
        logger.info(f'🔍 Found {len(results_list)} result set(s)')

        for serial, result in zip(serials, results_list):
            # Get device name for better display
            device_name = serial
            if hasattr(self, 'device_dict') and serial in self.device_dict:
                device_name = f"{self.device_dict[serial].device_model} ({serial[:8]}...)"

            logger.info(f'📱 [{device_name}] Command: {command}')
            self.write_to_console(f'📱 [{device_name}] {command}')

            if result and len(result) > 0:
                # Show first few lines of output
                max_lines = 10  # Reduced for cleaner display
                output_lines = result[:max_lines] if len(result) > max_lines else result

                logger.info(f'📱 [{device_name}] 📋 Output ({len(result)} lines total):')
                self.write_to_console(f'📋 {len(result)} lines output:')

                for line_num, line in enumerate(output_lines):
                    if line and line.strip():  # Skip empty lines
                        output_line = f'  {line.strip()}'  # Simplified format
                        logger.info(f'📱 [{device_name}] {line_num+1:2d}▶️ {line.strip()}')
                        self.write_to_console(output_line)

                if len(result) > max_lines:
                    truncated_msg = f'  ... {len(result) - max_lines} more lines'
                    logger.info(f'📱 [{device_name}] ... and {len(result) - max_lines} more lines (truncated)')
                    self.write_to_console(truncated_msg)

                success_msg = f'✅ [{device_name}] Completed'
                logger.info(f'📱 [{device_name}] ✅ Command completed successfully')
                self.write_to_console(success_msg)
            else:
                error_msg = f'❌ [{device_name}] No output'
                logger.warning(f'📱 [{device_name}] ❌ No output or command failed')
                self.write_to_console(error_msg)

        logger.info(f'🏁 Results display completed for command: {command}')
        logger.info('─' * 50)  # Separator line
        self.write_to_console('─' * 30)  # Shorter separator line

    def write_to_console(self, message):
        """Write message to console widget using signal."""
        try:
            # Use signal for thread-safe console output
            self.console_output_signal.emit(message)
        except Exception as e:
            logger.error(f'Error emitting console signal: {e}')

    def _write_to_console_safe(self, message):
        """Thread-safe method to write to console."""
        try:
            cursor = self.console_text.textCursor()
            cursor.movePosition(QTextCursor.MoveOperation.End)
            cursor.insertText(f'{message}\n')
            self.console_text.setTextCursor(cursor)
            self.console_text.ensureCursorVisible()
        except Exception as e:
            logger.error(f'Error in _write_to_console_safe: {e}')


    def get_valid_commands(self):
        """Extract valid commands from batch text area using command execution manager."""
        text = self.batch_commands_edit.toPlainText().strip()
        return self.command_execution_manager.get_valid_commands_from_text(text)

    def add_to_history(self, command):
        """Add command to history using command history manager."""
        self.command_history_manager.add_to_history(command)
        self.update_history_display()

    def update_history_display(self):
        """Update the history list widget."""
        self.command_history_list.clear()
        for command in reversed(self.command_history_manager.command_history):  # Show most recent first
            self.command_history_list.addItem(command)

    def load_from_history(self, item):
        """Load selected history item to batch commands area."""
        command = item.text()
        current_text = self.batch_commands_edit.toPlainText()
        if current_text:
            new_text = current_text + '\n' + command
        else:
            new_text = command
        self.batch_commands_edit.setPlainText(new_text)

    def clear_command_history(self):
        """Clear command history using command history manager."""
        self.command_history_manager.clear_history()

    def export_command_history(self):
        """Export command history to file using command history manager."""
        self.command_history_manager.export_command_history()

    def import_command_history(self):
        """Import command history from file using command history manager."""
        self.command_history_manager.import_command_history()

    def load_command_history_from_config(self):
        """Load command history from config file using command history manager."""
        # This method is now handled by the command history manager during initialization
        pass

    def save_command_history_to_config(self):
        """Save command history to config file using command history manager."""
        # This method is now handled by the command history manager automatically
        pass

    # scrcpy functionality
    @ensure_devices_selected
    def launch_scrcpy(self):
        """Launch scrcpy for selected devices."""
        self.app_management_manager.launch_scrcpy_for_selected_devices()

    def show_scrcpy_installation_guide(self):
        """Show detailed installation guide for scrcpy."""

        # Detect operating system
        system = platform.system().lower()

        if system == "darwin":  # macOS
            title = "scrcpy Not Found - Installation Guide for macOS"
            message = """scrcpy is not installed on your system.

scrcpy is a powerful tool that allows you to display and control Android devices connected via USB or wirelessly.

🍺 RECOMMENDED: Install using Homebrew
1. Install Homebrew if you haven't already:
   /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

2. Install scrcpy:
   brew install scrcpy

📦 ALTERNATIVE: Download from GitHub
1. Visit: https://github.com/Genymobile/scrcpy/releases
2. Download the latest macOS release
3. Extract and follow installation instructions

After installation, restart lazy blacktea to use device mirroring functionality."""

        elif system == "linux":  # Linux
            title = "scrcpy Not Found - Installation Guide for Linux"
            message = """scrcpy is not installed on your system.

scrcpy is a powerful tool that allows you to display and control Android devices connected via USB or wirelessly.

📦 RECOMMENDED: Install using package manager

Ubuntu/Debian:
   sudo apt update
   sudo apt install scrcpy

Fedora:
   sudo dnf install scrcpy

Arch Linux:
   sudo pacman -S scrcpy

🔧 ALTERNATIVE: Install from Snap
   sudo snap install scrcpy

📦 ALTERNATIVE: Download from GitHub
1. Visit: https://github.com/Genymobile/scrcpy/releases
2. Download the latest Linux release
3. Extract and follow installation instructions

After installation, restart lazy blacktea to use device mirroring functionality."""

        elif system == "windows":  # Windows
            title = "scrcpy Not Found - Installation Guide for Windows"
            message = """scrcpy is not installed on your system.

scrcpy is a powerful tool that allows you to display and control Android devices connected via USB or wirelessly.

🍫 RECOMMENDED: Install using Chocolatey
1. Install Chocolatey if you haven't already:
   Visit: https://chocolatey.org/install

2. Install scrcpy:
   choco install scrcpy

🪟 ALTERNATIVE: Install using Scoop
1. Install Scoop: https://scoop.sh/
2. Install scrcpy:
   scoop install scrcpy

📦 ALTERNATIVE: Download from GitHub
1. Visit: https://github.com/Genymobile/scrcpy/releases
2. Download the latest Windows release
3. Extract to a folder and add to PATH

After installation, restart lazy blacktea to use device mirroring functionality."""

        else:
            title = "scrcpy Not Found - Installation Guide"
            message = """scrcpy is not installed on your system.

scrcpy is a powerful tool that allows you to display and control Android devices connected via USB or wirelessly.

📦 Installation:
Visit the official GitHub repository for installation instructions:
https://github.com/Genymobile/scrcpy

After installation, restart lazy blacktea to use device mirroring functionality."""

        # Create a detailed message box with installation guide
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle(title)
        msg_box.setText(message)
        msg_box.setIcon(QMessageBox.Icon.Information)

        # Add buttons for easy access
        install_button = msg_box.addButton("Open Installation Guide", QMessageBox.ButtonRole.ActionRole)
        close_button = msg_box.addButton("Close", QMessageBox.ButtonRole.RejectRole)

        msg_box.setDefaultButton(close_button)
        msg_box.exec()

        # Handle button clicks
        if msg_box.clickedButton() == install_button:
            self.open_scrcpy_website()

    def open_scrcpy_website(self):
        """Open scrcpy GitHub releases page in web browser."""

        system = platform.system().lower()

        if system == "darwin":  # macOS
            url = "https://brew.sh/"  # Homebrew installation page
        else:
            url = "https://github.com/Genymobile/scrcpy/releases"

        try:
            webbrowser.open(url)
            logger.info(f"Opened scrcpy installation guide: {url}")
        except Exception as e:
            logger.error(f"Failed to open web browser: {e}")
            self.show_error("Browser Error", f"Could not open web browser.\n\nPlease manually visit:\n{url}")


    # File generation methods
    @ensure_devices_selected
    def generate_android_bug_report(self):
        """Generate Android bug report using file operations manager."""
        devices = self.get_checked_devices()
        output_path = self.file_gen_output_path_edit.text().strip()
        self.file_operations_manager.generate_android_bug_report(devices, output_path)

    @ensure_devices_selected
    def generate_device_discovery_file(self):
        """Generate device discovery file using file operations manager."""
        devices = self.get_checked_devices()
        output_path = self.file_gen_output_path_edit.text().strip()
        self.file_operations_manager.generate_device_discovery_file(devices, output_path)

    @ensure_devices_selected
    def pull_device_dcim_with_folder(self):
        """Pull DCIM folder from devices using file operations manager."""
        devices = self.get_checked_devices()
        output_path = self.file_gen_output_path_edit.text().strip()
        self.file_operations_manager.pull_device_dcim_folder(devices, output_path)

    @ensure_devices_selected
    def dump_device_hsv(self):
        """Dump device UI hierarchy using UI hierarchy manager."""
        output_path = self.file_gen_output_path_edit.text().strip()
        self.ui_hierarchy_manager.export_hierarchy(output_path)

    @ensure_devices_selected
    def launch_ui_inspector(self):
        """Launch the interactive UI Inspector for selected devices."""
        devices = self.get_checked_devices()
        if len(devices) != 1:
            self.show_warning('Single Device Required',
                            'UI Inspector requires exactly one device to be selected.\n\n'
                            'Please select only one device and try again.')
            return

        device = devices[0]
        serial = device.device_serial_num
        model = device.device_model

        logger.info(f'Launching UI Inspector for device: {model} ({serial})')

        # Create and show UI Inspector dialog
        ui_inspector = UIInspectorDialog(self, serial, model)
        ui_inspector.exec()

    def show_about_dialog(self):
        """Show about dialog."""
        QMessageBox.about(
            self,
            'About lazy blacktea',
            'lazy blacktea - PyQt6 Version\n\n'
            'A GUI application for simplifying Android ADB and automation tasks.\n\n'
            'Converted from Tkinter to PyQt6 for enhanced user experience.'
        )

    def load_config(self):
        """Load configuration from file using ConfigManager."""
        try:
            config = self.config_manager.load_config()

            # Load output path from old config format for compatibility
            old_config = json_utils.read_config_json()
            if old_config.get('output_path'):
                self.output_path_edit.setText(old_config['output_path'])

            # Load file generation output path
            file_gen_path = old_config.get('file_gen_output_path', '').strip()
            if file_gen_path:
                self.file_gen_output_path_edit.setText(file_gen_path)
            else:
                # Use main output path as default for file generation
                main_output_path = old_config.get('output_path', '')
                if main_output_path:
                    self.file_gen_output_path_edit.setText(main_output_path)

            # Load refresh interval from new config (set minimum 5 seconds for packaged apps)
            self.refresh_interval = max(5, config.device.refresh_interval)
            self.device_manager.set_refresh_interval(self.refresh_interval)

            # Load UI scale from new config
            self.set_ui_scale(config.ui.ui_scale)

            # Load device groups from old config for compatibility
            if old_config.get('device_groups'):
                self.device_groups = old_config['device_groups']

            # Load command history from new config
            if config.command_history:
                self.command_executor.set_command_history(config.command_history)

            logger.info('Configuration loaded successfully')
        except Exception as e:
            logger.warning(f'Could not load config: {e}')
            self.error_handler.handle_error(ErrorCode.CONFIG_LOAD_FAILED, str(e))

    def save_config(self):
        """Save configuration to file using ConfigManager."""
        try:
            # Update the new config manager
            self.config_manager.update_ui_settings(ui_scale=self.user_scale)
            self.config_manager.update_device_settings(refresh_interval=self.refresh_interval)

            # Save command history to new config
            if hasattr(self, 'command_executor'):
                config = self.config_manager.load_config()
                config.command_history = self.command_executor.get_command_history()
                self.config_manager.save_config(config)

            # Also save to old config format for compatibility
            old_config = {
                'output_path': self.output_path_edit.text(),
                'file_gen_output_path': self.file_gen_output_path_edit.text(),
                'refresh_interval': self.refresh_interval,
                'ui_scale': self.user_scale,
                'device_groups': self.device_groups
            }
            json_utils.save_config_json(old_config)
            logger.info('Configuration saved successfully')
        except Exception as e:
            logger.error(f'Could not save config: {e}')
            self.error_handler.handle_error(ErrorCode.CONFIG_INVALID, str(e))

    def closeEvent(self, event):
        """Handle window close event with immediate response."""
        # Hide window immediately for better user experience
        self.hide()

        # Process any pending events to ensure UI updates
        QApplication.processEvents()

        self.save_config()

        # Clean up timers to prevent memory leaks
        if hasattr(self, 'recording_timer'):
            self.recording_timer.stop()

        # Clean up new modular components
        if hasattr(self, 'device_manager'):
            self.device_manager.cleanup()

        if hasattr(self, 'recording_manager'):
            # Stop any active recordings
            self.recording_manager.stop_recording()

        # Clean up device management threads aggressively for immediate shutdown
        if hasattr(self, 'device_manager'):
            self.device_manager.cleanup()

        logger.info('Application shutdown complete')
        event.accept()

    def _on_device_found_from_manager(self, serial: str, device_info):
        """處理從DeviceManager發來的新設備發現事件"""
        logger.info(f'Device found from manager: {serial} - {device_info.device_model}')
        # 更新設備字典
        self.device_dict[serial] = device_info
        # 觸發完整的UI更新（包括複選框）
        self.update_device_list(self.device_dict)

    def _on_device_lost_from_manager(self, serial: str):
        """處理從DeviceManager發來的設備丟失事件"""
        logger.info(f'Device lost from manager: {serial}')
        # 從設備字典中移除
        if serial in self.device_dict:
            del self.device_dict[serial]
        # 觸發完整的UI更新
        self.update_device_list(self.device_dict)

    def _on_device_status_updated(self, status: str):
        """處理從DeviceManager發來的狀態更新事件"""
        if hasattr(self, 'status_bar'):
            self.status_bar.showMessage(status, 2000)


def main():
    """Main application entry point."""
    # Check Qt dependencies on Linux before creating QApplication
    if not check_and_fix_qt_dependencies():
        sys.exit(1)

    app = QApplication(sys.argv)
    app.setApplicationName('lazy blacktea')
    app.setApplicationVersion('0.0.1')

    window = WindowMain()
    window.show()

    sys.exit(app.exec())


if __name__ == '__main__':
    main()
