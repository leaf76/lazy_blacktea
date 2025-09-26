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
    QGridLayout, QSplitter, QTabWidget, QTextEdit,
    QCheckBox, QPushButton, QLabel,
    QLineEdit, QGroupBox, QFileDialog, QComboBox,
    QMessageBox, QMenu, QStatusBar, QProgressBar,
    QInputDialog, QListWidget, QListWidgetItem, QDialog, QTreeWidget, QTreeWidgetItem
)
from PyQt6.QtCore import (Qt, QTimer, pyqtSignal, QPoint)
from PyQt6.QtGui import (QFont, QTextCursor, QAction, QIcon, QGuiApplication, QCursor)
from PyQt6.QtWidgets import QToolTip

from utils import adb_models
from utils import adb_tools
from utils import common
from utils import json_utils

# Import configuration and constants
from config.config_manager import ConfigManager
from config.constants import (
    UIConstants, PathConstants, ADBConstants, MessageConstants,
    LoggingConstants, ApplicationConstants
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
from ui.optimized_device_list import VirtualizedDeviceList, DeviceListPerformanceOptimizer
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

        # Create tools panel
        self.create_tools_panel(main_splitter)

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



    def create_tools_panel(self, parent):
        """Create the tools panel with tabs."""
        tools_widget = QWidget()
        tools_layout = QVBoxLayout(tools_widget)

        # Create tab widget
        tab_widget = QTabWidget()
        tools_layout.addWidget(tab_widget)

        # Initialize critical UI elements first to prevent attribute errors
        self.output_path_edit = QLineEdit()
        self.file_gen_output_path_edit = QLineEdit()  # Restore text field for File Generation
        self.groups_listbox = QListWidget()
        self.group_name_edit = QLineEdit()

        # Create all tabs immediately to ensure proper initialization
        # (Lazy loading caused attribute errors with configuration loading)
        self.create_adb_tools_tab(tab_widget)
        self.create_shell_commands_tab(tab_widget)
        self.create_file_generation_tab(tab_widget)
        self.create_device_groups_tab(tab_widget)

        parent.addWidget(tools_widget)


    def create_adb_tools_tab(self, tab_widget):
        """Create the ADB tools tab with categorized functions."""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # Output path section
        output_group = QGroupBox('Output Path')
        output_layout = QHBoxLayout(output_group)

        self.output_path_edit.setPlaceholderText('Select output directory...')
        output_layout.addWidget(self.output_path_edit)

        browse_btn = UIFactory.create_standard_button(
            '📂 Browse',
            ButtonStyle.SECONDARY,
            click_handler=lambda: self.browse_output_path(),
            tooltip='Select output directory'
        )
        output_layout.addWidget(browse_btn)

        layout.addWidget(output_group)

        # Logcat section
        logcat_group = QGroupBox('📄 Logcat')
        logcat_layout = QGridLayout(logcat_group)

        # Clear logcat button
        clear_logcat_btn = UIFactory.create_standard_button(
            '🗑️ Clear Logcat',
            ButtonStyle.DANGER,
            click_handler=lambda: self.clear_logcat(),
            tooltip='Clear logcat on selected devices'
        )
        logcat_layout.addWidget(clear_logcat_btn, 0, 0)

        # Android Bug Report button
        bug_report_btn = UIFactory.create_standard_button(
            '📊 Android Bug Report',
            ButtonStyle.SECONDARY,
            click_handler=lambda: self.generate_android_bug_report(),
            tooltip='Generate Android bug report'
        )
        logcat_layout.addWidget(bug_report_btn, 0, 1)

        layout.addWidget(logcat_group)

        # Device Control section
        device_control_group = QGroupBox('📱 Device Control')
        device_control_layout = QGridLayout(device_control_group)

        device_actions = [
            ('🔄 Reboot Device', self.reboot_device),
            ('📦 Install APK', self.install_apk),
            ('🔵 Enable Bluetooth', self.enable_bluetooth),
            ('🔴 Disable Bluetooth', self.disable_bluetooth),
        ]

        # Add scrcpy action if available
        if self.scrcpy_available:
            device_actions.append(('🖥️ Mirror Device (scrcpy)', self.launch_scrcpy))

        for i, (text, func) in enumerate(device_actions):
            btn = QPushButton(text)
            btn.clicked.connect(lambda checked, f=func: f())
            row, col = divmod(i, 2)
            device_control_layout.addWidget(btn, row, col)

        layout.addWidget(device_control_group)

        # Screen Capture & Recording section (combined)
        capture_group = QGroupBox('📱 Screen Capture & Recording')
        capture_layout = QGridLayout(capture_group)

        # Screenshot button
        self.screenshot_btn = QPushButton('📷 Take Screenshot')
        self.screenshot_btn.clicked.connect(lambda: self.take_screenshot())
        # Set initial default style
        StyleManager.apply_button_style(self.screenshot_btn, ButtonStyle.PRIMARY)
        capture_layout.addWidget(self.screenshot_btn, 0, 0)

        # Recording buttons
        self.start_record_btn = QPushButton('🎥 Start Screen Record')
        self.start_record_btn.clicked.connect(lambda: self.start_screen_record())
        capture_layout.addWidget(self.start_record_btn, 1, 0)

        self.stop_record_btn = QPushButton('⏹️ Stop Screen Record')
        self.stop_record_btn.clicked.connect(lambda: self.stop_screen_record())
        capture_layout.addWidget(self.stop_record_btn, 1, 1)

        # Recording status display
        self.recording_status_label = QLabel('No active recordings')
        StyleManager.apply_label_style(self.recording_status_label, LabelStyle.STATUS)
        capture_layout.addWidget(self.recording_status_label, 2, 0, 1, 2)

        # Recording timer display
        self.recording_timer_label = QLabel('')
        self.recording_timer_label.setStyleSheet(StyleManager.get_status_styles()['recording_active'])
        capture_layout.addWidget(self.recording_timer_label, 3, 0, 1, 2)

        layout.addWidget(capture_group)

        layout.addStretch()
        tab_widget.addTab(tab, 'ADB Tools')

    def update_recording_status(self):
        """Update recording status display using new recording manager."""
        if not hasattr(self, 'recording_status_label'):
            return

        # Get all recording statuses from new manager
        all_statuses = self.recording_manager.get_all_recording_statuses()
        active_recordings = []

        for serial, status in all_statuses.items():
            if 'Recording' in status:
                # Get device model for display
                device_model = 'Unknown'
                if serial in self.device_dict:
                    device_model = self.device_dict[serial].device_model

                # Extract duration from status (format: "Recording (MM:SS)")
                duration_part = status.split('(')[1].rstrip(')')
                active_recordings.append(f"{device_model} ({serial[:8]}...): {duration_part}")

        active_count = self.recording_manager.get_active_recordings_count()

        if active_count > 0:
            status_text = f"🔴 Recording: {active_count} device(s)"
            self.recording_status_label.setText(status_text)
            self.recording_status_label.setStyleSheet(StyleManager.get_status_styles()['recording_active'])

            # Limit display to first 8 recordings to prevent UI overflow
            if len(active_recordings) > 8:
                display_recordings = active_recordings[:8] + [f"... and {len(active_recordings) - 8} more device(s)"]
            else:
                display_recordings = active_recordings

            self.recording_timer_label.setText('\n'.join(display_recordings))
        else:
            self.recording_status_label.setText('No active recordings')
            self.recording_status_label.setStyleSheet(StyleManager.get_status_styles()['recording_inactive'])
            self.recording_timer_label.setText('')

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

    def create_shell_commands_tab(self, tab_widget):
        """Create the enhanced shell commands tab with batch execution and history."""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # Command Templates section
        template_group = QGroupBox('📋 Command Templates')
        template_layout = QGridLayout(template_group)

        template_commands = [
            ('📱 Device Info', 'getprop ro.build.version.release'),
            ('🔋 Battery Info', 'dumpsys battery'),
            ('📊 Memory Info', 'dumpsys meminfo'),
            ('🌐 Network Info', 'dumpsys connectivity'),
            ('📱 App List', 'pm list packages -3'),
            ('🗑️ Clear Cache', 'pm trim-caches 1000000000'),
        ]

        for i, (name, command) in enumerate(template_commands):
            btn = QPushButton(name)
            btn.clicked.connect(lambda checked, cmd=command: self.add_template_command(cmd))
            row, col = divmod(i, 3)
            template_layout.addWidget(btn, row, col)

        layout.addWidget(template_group)

        # Batch Commands section
        batch_group = QGroupBox('📝 Batch Commands')
        batch_layout = QVBoxLayout(batch_group)

        # Commands text area
        self.batch_commands_edit = QTextEdit()
        self.batch_commands_edit.setPlaceholderText(
            'Enter multiple commands (one per line):\n'
            'getprop ro.build.version.release\n'
            'dumpsys battery\n'
            'pm list packages -3\n\n'
            'Use # for comments'
        )
        self.batch_commands_edit.setMaximumHeight(120)
        batch_layout.addWidget(self.batch_commands_edit)

        # Execution buttons
        exec_buttons_layout = QHBoxLayout()

        run_single_btn = QPushButton('▶️ Run Single Command')
        run_single_btn.clicked.connect(lambda: self.run_single_command())
        exec_buttons_layout.addWidget(run_single_btn)

        run_batch_btn = QPushButton('🚀 Run All Commands')
        run_batch_btn.clicked.connect(lambda: self.run_batch_commands())
        exec_buttons_layout.addWidget(run_batch_btn)


        batch_layout.addLayout(exec_buttons_layout)
        layout.addWidget(batch_group)

        # Command History section
        history_group = QGroupBox('📜 Command History')
        history_layout = QVBoxLayout(history_group)

        self.command_history_list = QListWidget()
        self.command_history_list.setMaximumHeight(100)
        self.command_history_list.itemDoubleClicked.connect(self.load_from_history)
        history_layout.addWidget(self.command_history_list)

        history_buttons_layout = QHBoxLayout()

        clear_history_btn = UIFactory.create_standard_button(
            '🗑️ Clear',
            ButtonStyle.DANGER,
            click_handler=lambda: self.clear_command_history(),
            tooltip='Clear command history'
        )
        history_buttons_layout.addWidget(clear_history_btn)

        export_history_btn = QPushButton('📤 Export')
        export_history_btn.clicked.connect(lambda: self.export_command_history())
        history_buttons_layout.addWidget(export_history_btn)

        import_history_btn = QPushButton('📥 Import')
        import_history_btn.clicked.connect(lambda: self.import_command_history())
        history_buttons_layout.addWidget(import_history_btn)

        history_layout.addLayout(history_buttons_layout)
        layout.addWidget(history_group)

        layout.addStretch()

        # Initialize command history display
        self.update_history_display()

        tab_widget.addTab(tab, 'Shell Commands')


    def create_file_generation_tab(self, tab_widget):
        """Create the file generation tab with independent output path."""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # Output path section (matching ADB Tools format)
        output_group = QGroupBox('Output Path')
        output_layout = QHBoxLayout(output_group)

        self.file_gen_output_path_edit.setPlaceholderText('Select output directory...')
        output_layout.addWidget(self.file_gen_output_path_edit)

        browse_btn = UIFactory.create_standard_button(
            '📂 Browse',
            ButtonStyle.SECONDARY,
            click_handler=lambda: self.browse_file_generation_output_path(),
            tooltip='Select output directory for file generation'
        )
        output_layout.addWidget(browse_btn)

        layout.addWidget(output_group)

        # File Generation Tools section
        generation_group = QGroupBox('🛠️ File Generation Tools')
        generation_layout = QGridLayout(generation_group)

        generation_actions = [
            ('🔍 Device Discovery', self.generate_device_discovery_file),
            ('📷 Device DCIM Pull', self.pull_device_dcim_with_folder),
            ('📁 Export UI Hierarchy', self.dump_device_hsv),
        ]

        for i, (text, func) in enumerate(generation_actions):
            btn = QPushButton(text)
            btn.clicked.connect(lambda checked, f=func: f())
            row, col = divmod(i, 2)
            generation_layout.addWidget(btn, row, col)

        layout.addWidget(generation_group)
        layout.addStretch()

        tab_widget.addTab(tab, 'File Generation')

    def create_device_groups_tab(self, tab_widget):
        """Create the device groups management tab."""
        tab = QWidget()
        layout = QHBoxLayout(tab)

        # Left side: Create/Edit Group
        left_group = QGroupBox('Create/Update Group')
        left_layout = QVBoxLayout(left_group)

        # Group name input
        name_layout = QHBoxLayout()
        name_layout.addWidget(QLabel('Group Name:'))
        self.group_name_edit.setPlaceholderText('Enter group name...')
        name_layout.addWidget(self.group_name_edit)
        left_layout.addLayout(name_layout)

        # Save group button
        save_group_btn = QPushButton('Save Current Selection as Group')
        save_group_btn.clicked.connect(lambda: self.save_group())
        left_layout.addWidget(save_group_btn)

        left_layout.addStretch()
        layout.addWidget(left_group)

        # Right side: Group List
        right_group = QGroupBox('Existing Groups')
        right_layout = QVBoxLayout(right_group)

        # Groups list (using pre-initialized widget)
        self.groups_listbox.itemSelectionChanged.connect(self.on_group_select)
        right_layout.addWidget(self.groups_listbox)

        # Group action buttons
        group_buttons_layout = QHBoxLayout()

        select_group_btn = QPushButton('Select Devices in Group')
        select_group_btn.clicked.connect(lambda: self.select_devices_in_group())
        group_buttons_layout.addWidget(select_group_btn)

        delete_group_btn = QPushButton('Delete Selected Group')
        delete_group_btn.clicked.connect(lambda: self.delete_group())
        group_buttons_layout.addWidget(delete_group_btn)

        right_layout.addLayout(group_buttons_layout)
        layout.addWidget(right_group)

        tab_widget.addTab(tab, 'Device Groups')

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
        """Update the device list display with performance optimizations."""
        self.device_dict = device_dict

        device_count = len(device_dict)
        if DeviceListPerformanceOptimizer.should_use_virtualization(device_count):
            preserved_serials = set(self._get_current_checked_serials())
            self._activate_virtualized_view(preserved_serials)
            if self.virtualized_device_list is not None:
                self.virtualized_device_list.update_device_list(device_dict)
                self.virtualized_device_list.set_checked_serials(preserved_serials)
                self.virtualized_device_list.apply_search_and_sort()
            self._update_virtualized_title()
            self.update_selection_count()
            return

        self._deactivate_virtualized_view()

        if device_count > 5:
            logger.debug(f'Updating {device_count} devices using optimized mode')
            self._update_device_list_optimized(device_dict)
            return
        else:
            logger.debug(f'Updating {device_count} devices using standard mode')
            self._perform_standard_device_update(device_dict)

    def _update_device_list_optimized(self, device_dict: Dict[str, adb_models.DeviceInfo]):
        """優化版本的設備列表更新，防止UI卡頓"""
        # 使用定時器分批更新，避免阻塞UI
        if hasattr(self, '_update_timer') and self._update_timer.isActive():
            self._update_timer.stop()

        self._update_timer = QTimer()
        self._update_timer.setSingleShot(True)
        self._update_timer.timeout.connect(lambda: self._perform_batch_device_update(device_dict))
        self._update_timer.start(5)  # 5ms 延遲

    def _perform_batch_device_update(self, device_dict: Dict[str, adb_models.DeviceInfo]):
        """分批執行設備更新，提升性能"""
        try:
            # 暫停UI更新
            self.device_scroll.setUpdatesEnabled(False)

            # 保存當前選擇狀態
            checked_serials = self._get_current_checked_serials()

            # 計算需要更新的設備
            current_serials = set(self.check_devices.keys())
            new_serials = set(device_dict.keys())

            # 分批處理，避免一次性更新太多設備
            self._batch_remove_devices(current_serials - new_serials)
            self._batch_add_devices(new_serials - current_serials, device_dict, checked_serials)
            self._batch_update_existing(current_serials & new_serials, device_dict)

        finally:
            # 恢復UI更新
            self.device_scroll.setUpdatesEnabled(True)
            self.device_scroll.update()
            self.filter_and_sort_devices()
            logger.debug(f'Batch device update completed: {len(device_dict)} devices')

    def _batch_remove_devices(self, devices_to_remove):
        """批次移除設備"""
        for serial in devices_to_remove:
            if serial in self.check_devices:
                checkbox = self.check_devices[serial]
                self.device_layout.removeWidget(checkbox)
                self._release_device_checkbox(checkbox)
                del self.check_devices[serial]

    def _batch_add_devices(self, devices_to_add, device_dict, checked_serials):
        """批次添加設備，使用小批次避免UI阻塞"""
        devices_list = list(devices_to_add)
        batch_size = max(1, DeviceListPerformanceOptimizer.calculate_batch_size(len(device_dict)))

        def process_device_batch(start_idx):
            end_idx = min(start_idx + batch_size, len(devices_list))

            for i in range(start_idx, end_idx):
                serial = devices_list[i]
                if serial in device_dict:
                    self._create_single_device_ui(serial, device_dict[serial], checked_serials)

            # 如果還有更多設備，安排下一批
            if end_idx < len(devices_list):
                QTimer.singleShot(2, lambda: process_device_batch(end_idx))

        if devices_list:
            process_device_batch(0)

    def _get_filtered_sorted_devices(self, device_dict: Optional[Dict[str, adb_models.DeviceInfo]] = None) -> List[adb_models.DeviceInfo]:
        """Return devices filtered & sorted via the search manager."""
        source = list((device_dict or self.device_dict).values())
        return self.device_search_manager.search_and_sort_devices(
            source,
            self.device_search_manager.get_search_text(),
            self.device_search_manager.get_sort_mode()
        )

    def _build_device_display_text(self, device: adb_models.DeviceInfo, serial: str) -> str:
        """Compose the display string for a device checkbox."""
        operation_status = self._get_device_operation_status(serial)
        recording_status = self._get_device_recording_status(serial)

        android_ver = device.android_ver or 'Unknown'
        android_api = device.android_api_level or 'Unknown'
        gms_display = device.gms_version if device.gms_version and device.gms_version != 'N/A' else 'N/A'

        return (
            f'{operation_status}{recording_status}📱 {device.device_model:<20} | '
            f'🆔 {device.device_serial_num:<20} | '
            f'🤖 Android {android_ver:<7} (API {android_api:<7}) | '
            f'🎯 GMS: {gms_display:<12} | '
            f'📶 WiFi: {self._get_on_off_status(device.wifi_is_on):<3} | '
            f'🔵 BT: {self._get_on_off_status(device.bt_is_on)}'
        )

    def _apply_checkbox_content(self, checkbox: QCheckBox, serial: str, device: adb_models.DeviceInfo) -> None:
        """Update a checkbox's text and tooltip to match device data."""
        checkbox.setText(self._build_device_display_text(device, serial))
        tooltip_text = self._create_device_tooltip(device, serial)
        checkbox.enterEvent = lambda event, txt=tooltip_text, cb=checkbox: self._show_custom_tooltip(cb, txt, event)
        checkbox.leaveEvent = lambda event: QToolTip.hideText()

    def _configure_device_checkbox(self, checkbox: QCheckBox, serial: str, device: adb_models.DeviceInfo,
                                   checked_serials: Iterable[str]) -> None:
        """Apply common styling, state, and event bindings to a device checkbox."""
        checked_set = set(checked_serials)
        checkbox.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        checkbox.customContextMenuRequested.connect(
            lambda pos, s=serial, cb=checkbox: self.show_device_context_menu(pos, s, cb)
        )
        checkbox.setFont(QFont('Segoe UI', 10))
        self._apply_device_checkbox_style(checkbox)
        self._apply_checkbox_content(checkbox, serial, device)

        is_checked = serial in checked_set
        checkbox.blockSignals(True)
        checkbox.setChecked(is_checked)
        checkbox.blockSignals(False)

        checkbox.stateChanged.connect(self.update_selection_count)
        checkbox.stateChanged.connect(
            lambda state, cb=checkbox: self._update_checkbox_visual_state(cb, state)
        )

    def _initialize_virtualized_checkbox(self, checkbox: QCheckBox, serial: str,
                                         device: adb_models.DeviceInfo, checked_serials: Iterable[str]) -> None:
        """Wrapper so the virtualized list can configure checkboxes consistently."""
        self._configure_device_checkbox(checkbox, serial, device, checked_serials)

    def _get_current_checked_serials(self) -> set:
        """Return the serials currently marked as selected across views."""
        if self.virtualized_active and self.virtualized_device_list is not None:
            return set(self.virtualized_device_list.checked_devices)
        selected = {serial for serial, cb in self.check_devices.items() if cb.isChecked()}
        if selected:
            self.pending_checked_serials = set(selected)
            return selected
        return set(self.pending_checked_serials)

    def _release_all_standard_checkboxes(self) -> None:
        """Return all standard checkboxes to the pool."""
        for serial, checkbox in list(self.check_devices.items()):
            if isinstance(checkbox, QCheckBox):
                self.device_layout.removeWidget(checkbox)
                self._release_device_checkbox(checkbox)
        self.check_devices.clear()

    def _activate_virtualized_view(self, checked_serials: Optional[Iterable[str]] = None) -> None:
        """Switch the device list rendering to the virtualized implementation."""
        if self.virtualized_device_list is None or self.virtualized_active:
            return

        preserved_serials = set(checked_serials or [])
        self.pending_checked_serials = set(preserved_serials)

        self._release_all_standard_checkboxes()

        current_widget = self.device_scroll.takeWidget()
        if current_widget is not None and current_widget is not self.virtualized_widget:
            self.standard_device_widget = current_widget

        if self.virtualized_widget.parent() is not None:
            self.virtualized_widget.setParent(None)
        self.device_scroll.setWidget(self.virtualized_widget)
        self.virtualized_active = True

    def _deactivate_virtualized_view(self) -> None:
        """Return to the standard device list rendering."""
        if not self.virtualized_active:
            return

        if self.virtualized_device_list is not None:
            self.pending_checked_serials = set(self.virtualized_device_list.checked_devices)

        current_widget = self.device_scroll.takeWidget()
        if current_widget is not None and current_widget is self.virtualized_widget:
            self.virtualized_widget.setParent(None)

        if self.standard_device_widget is not None:
            self.device_scroll.setWidget(self.standard_device_widget)

        # 清理虛擬化組件至池中，避免重複
        if self.virtualized_device_list is not None:
            self.virtualized_device_list.clear_widgets()

        self.virtualized_active = False

    def _update_virtualized_title(self) -> None:
        """Update the device title label to reflect virtualized counts."""
        if not hasattr(self, 'title_label') or self.title_label is None:
            return

        total = len(self.device_dict)
        visible = len(self.virtualized_device_list.sorted_devices) if self.virtualized_device_list else total
        selected = len(self.virtualized_device_list.checked_devices) if self.virtualized_device_list else 0

        search_text = self.device_search_manager.get_search_text() if hasattr(self, 'device_search_manager') else ''

        if search_text:
            self.title_label.setText(f'Connected Devices ({visible}/{total}) - Selected: {selected}')
        else:
            self.title_label.setText(f'Connected Devices ({total}) - Selected: {selected}')

    def _handle_virtualized_selection_change(self, serial: str, is_checked: bool) -> None:
        """Synchronize UI state after a virtualized checkbox toggle."""
        if not self.virtualized_active:
            return

        checkbox = self.check_devices.get(serial)
        if checkbox is not None and checkbox.isChecked() != is_checked:
            checkbox.blockSignals(True)
            checkbox.setChecked(is_checked)
            checkbox.blockSignals(False)

        self._update_virtualized_title()

    def _acquire_device_checkbox(self) -> QCheckBox:
        """Fetch a checkbox from the pool or create a new one."""
        checkbox = self.checkbox_pool.pop() if self.checkbox_pool else QCheckBox()

        # Reset connection state before reuse
        try:
            checkbox.stateChanged.disconnect()
        except TypeError:
            pass

        try:
            checkbox.customContextMenuRequested.disconnect()
        except TypeError:
            pass

        checkbox.blockSignals(True)
        checkbox.setChecked(False)
        checkbox.blockSignals(False)
        checkbox.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        checkbox.setFont(QFont('Segoe UI', 10))
        checkbox.setToolTip('')
        checkbox.enterEvent = lambda event, cb=checkbox: QCheckBox.enterEvent(cb, event)
        checkbox.leaveEvent = lambda event, cb=checkbox: QCheckBox.leaveEvent(cb, event)
        self._apply_device_checkbox_style(checkbox)
        checkbox.setVisible(True)
        return checkbox

    def _release_device_checkbox(self, checkbox: QCheckBox) -> None:
        """Recycle checkbox widgets to reduce churn during list updates."""
        checkbox.blockSignals(True)
        checkbox.setChecked(False)
        checkbox.blockSignals(False)
        checkbox.hide()

        try:
            checkbox.stateChanged.disconnect()
        except TypeError:
            pass

        try:
            checkbox.customContextMenuRequested.disconnect()
        except TypeError:
            pass

        checkbox.enterEvent = lambda event, cb=checkbox: QCheckBox.enterEvent(cb, event)
        checkbox.leaveEvent = lambda event, cb=checkbox: QCheckBox.leaveEvent(cb, event)
        checkbox.setParent(None)
        self.checkbox_pool.append(checkbox)

    def _create_single_device_ui(self, serial, device, checked_serials):
        """創建單個設備的UI組件，優化版本"""
        checkbox = self._acquire_device_checkbox()
        self._configure_device_checkbox(checkbox, serial, device, checked_serials)

        self.check_devices[serial] = checkbox
        insert_index = self.device_layout.count() - 1
        self.device_layout.insertWidget(insert_index, checkbox)

    def _batch_update_existing(self, devices_to_update, device_dict):
        """批次更新現有設備信息"""
        for serial in devices_to_update:
            if serial in self.check_devices and serial in device_dict:
                device = device_dict[serial]
                checkbox = self.check_devices[serial]
                self._apply_checkbox_content(checkbox, serial, device)

    def _perform_standard_device_update(self, device_dict: Dict[str, adb_models.DeviceInfo]):
        """標準版本的設備更新（5個以下設備）"""
        # 暫停UI更新
        self.device_scroll.setUpdatesEnabled(False)

        # 保存當前選擇狀態
        checked_serials = self._get_current_checked_serials()

        # 計算需要更新的設備
        current_serials = set(self.check_devices.keys())
        new_serials = set(device_dict.keys())

        # 移除不存在的設備
        for serial in current_serials - new_serials:
            if serial in self.check_devices:
                checkbox = self.check_devices[serial]
                self.device_layout.removeWidget(checkbox)
                self._release_device_checkbox(checkbox)
                del self.check_devices[serial]

        # 添加新設備
        for serial in new_serials - current_serials:
            if serial in device_dict:
                device = device_dict[serial]
                self._create_standard_device_ui(serial, device, checked_serials)

        # 更新現有設備信息
        for serial in current_serials & new_serials:
            if serial in self.check_devices and serial in device_dict:
                device = device_dict[serial]
                checkbox = self.check_devices[serial]
                self._update_device_checkbox_text(checkbox, device, serial)

        # 恢復UI更新
        self.device_scroll.setUpdatesEnabled(True)
        self.filter_and_sort_devices()

    def _create_standard_device_ui(self, serial, device, checked_serials):
        """創建標準設備UI組件（用於小量設備）"""
        checkbox = self._acquire_device_checkbox()
        self._configure_device_checkbox(checkbox, serial, device, checked_serials)

        self.check_devices[serial] = checkbox
        # Insert before the stretch item (which is always the last item)
        insert_index = self.device_layout.count() - 1
        self.device_layout.insertWidget(insert_index, checkbox)

    def _update_device_checkbox_text(self, checkbox, device, serial):
        """更新設備checkbox的文字內容"""
        self._apply_checkbox_content(checkbox, serial, device)

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
        """Copy selected device information to clipboard with comprehensive details."""
        checked_devices = self.get_checked_devices()
        if not checked_devices:
            self.error_handler.show_info('Info', 'No devices selected.')
            return

        device_info_sections = []

        for i, device in enumerate(checked_devices):
            # Generate comprehensive device information in plain text
            device_info = []
            device_info.append(f"Device #{i+1}")
            device_info.append("=" * 50)

            # Basic Information
            device_info.append("BASIC INFORMATION:")
            device_info.append(f"Model: {device.device_model}")
            device_info.append(f"Serial Number: {device.device_serial_num}")
            device_info.append(f"Product: {device.device_prod}")
            device_info.append(f"USB: {device.device_usb}")
            device_info.append("")

            # System Information
            device_info.append("SYSTEM INFORMATION:")
            device_info.append(f"Android Version: {device.android_ver if device.android_ver else 'Unknown'}")
            device_info.append(f"API Level: {device.android_api_level if device.android_api_level else 'Unknown'}")
            device_info.append(f"GMS Version: {device.gms_version if device.gms_version else 'Unknown'}")
            device_info.append(f"Build Fingerprint: {device.build_fingerprint if device.build_fingerprint else 'Unknown'}")
            device_info.append("")

            # Connectivity
            device_info.append("CONNECTIVITY:")
            device_info.append(f"WiFi Status: {self._get_on_off_status(device.wifi_is_on)}")
            device_info.append(f"Bluetooth Status: {self._get_on_off_status(device.bt_is_on)}")
            device_info.append("")

            # Try to get additional hardware information
            try:
                additional_info = self._get_additional_device_info(device.device_serial_num)
                device_info.append("HARDWARE INFORMATION:")
                device_info.append(f"Screen Size: {additional_info.get('screen_size', 'Unknown')}")
                device_info.append(f"Screen Density: {additional_info.get('screen_density', 'Unknown')}")
                device_info.append(f"CPU Architecture: {additional_info.get('cpu_arch', 'Unknown')}")
                device_info.append("")
                device_info.append("BATTERY INFORMATION:")
                device_info.append(f"Battery Level: {additional_info.get('battery_level', 'Unknown')}")
                device_info.append(f"Battery Capacity: {additional_info.get('battery_capacity_mah', 'Unknown')}")
                device_info.append(f"Battery mAs: {additional_info.get('battery_mas', 'Unknown')}")
                device_info.append(f"Estimated DOU: {additional_info.get('battery_dou_hours', 'Unknown')}")
            except Exception as e:
                device_info.append("HARDWARE INFORMATION:")
                device_info.append("Hardware information unavailable")
                logger.warning(f"Could not get additional info for {device.device_serial_num}: {e}")

            device_info_sections.append('\n'.join(device_info))

        # Combine all device information
        header = f"ANDROID DEVICE INFORMATION REPORT\nGenerated: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\nTotal Devices: {len(checked_devices)}\n\n"
        footer = "\n" + "=" * 50 + "\nReport generated by lazy blacktea PyQt6 version"

        full_info_text = header + '\n\n'.join(device_info_sections) + footer

        # Copy to clipboard
        clipboard = QApplication.clipboard()
        clipboard.setText(full_info_text)

        self.show_info('Success', f'Copied comprehensive information for {len(checked_devices)} device(s) to clipboard.\n\nInformation includes:\n• Basic device details\n• System information\n• Connectivity status\n• Hardware specifications')
        logger.info(f'Copied comprehensive device info to clipboard: {len(checked_devices)} devices')

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

    def _get_on_off_status(self, status):
        """Convert boolean status to On/Off string, similar to original Tkinter version."""
        if status is None or status == 'None':
            return 'Unknown'
        return 'On' if status else 'Off'

    def _get_device_operation_status(self, serial: str) -> str:
        """Get operation status indicator for device."""
        if serial in self.device_operations:
            operation = self.device_operations[serial]
            return f'⚙️ {operation.upper()} | '
        return ''

    def _get_device_recording_status(self, serial: str) -> str:
        """Get recording status indicator for device."""
        if (serial in self.device_recordings and
            self.device_recordings[serial] and
            self.device_recordings[serial].get('active', False)):
            return '🔴 REC | '
        return ''

    def _create_device_tooltip(self, device, serial):
        """Create enhanced tooltip with device information - unified method."""
        base_tooltip = (
            f'📱 Device Information\n'
            f'━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n'
            f'Model: {device.device_model}\n'
            f'Serial: {device.device_serial_num}\n'
            f'Android: {device.android_ver if device.android_ver else "Unknown"} (API Level {device.android_api_level if device.android_api_level else "Unknown"})\n'
            f'GMS Version: {device.gms_version if device.gms_version else "Unknown"}\n'
            f'Product: {device.device_prod}\n'
            f'USB: {device.device_usb}\n'
            f'━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n'
            f'📡 Connectivity\n'
            f'WiFi: {self._get_on_off_status(device.wifi_is_on)}\n'
            f'Bluetooth: {self._get_on_off_status(device.bt_is_on)}\n'
            f'━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n'
            f'🔧 Build Information\n'
            f'Build Fingerprint: {(device.build_fingerprint[:50] + "...") if device.build_fingerprint else "Unknown"}'
        )

        # Try to get additional info, but don't block UI for it
        try:
            additional_info = self._get_additional_device_info(serial)
            extended_tooltip = base_tooltip + (
                f'\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n'
                f'🖥️ Hardware Information\n'
                f'Screen Size: {additional_info.get("screen_size", "Unknown")}\n'
                f'Screen Density: {additional_info.get("screen_density", "Unknown")}\n'
                f'CPU Architecture: {additional_info.get("cpu_arch", "Unknown")}\n'
                f'━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n'
                f'🔋 Battery Information\n'
                f'Battery Level: {additional_info.get("battery_level", "Unknown")}\n'
                f'Battery Capacity: {additional_info.get("battery_capacity_mah", "Unknown")}\n'
                f'Battery mAs: {additional_info.get("battery_mas", "Unknown")}\n'
                f'Estimated DOU: {additional_info.get("battery_dou_hours", "Unknown")}'
            )
            return extended_tooltip
        except Exception as e:
            if hasattr(self, 'logging_manager'):
                self.logging_manager.debug(f'Failed to create device tooltip: {e}')
            return base_tooltip

    def _get_additional_device_info(self, serial_num):
        """Get additional device information for enhanced display."""
        try:
            # Use utils functions where possible
            return adb_tools.get_additional_device_info(serial_num)
        except Exception as e:
            logger.error(f'Error getting additional device info for {serial_num}: {e}')
            return {
                'screen_density': 'Unknown',
                'screen_size': 'Unknown',
                'battery_level': 'Unknown',
                'battery_capacity_mah': 'Unknown',
                'battery_mas': 'Unknown',
                'battery_dou_hours': 'Unknown',
                'cpu_arch': 'Unknown'
            }

    def _apply_device_checkbox_style(self, checkbox):
        """Apply visual styling to device checkbox for better selection feedback."""
        checkbox.setStyleSheet(StyleManager.get_checkbox_style())

    def _update_checkbox_visual_state(self, checkbox, state):
        """Update visual state of checkbox when selection changes."""
        # The styling is handled by CSS, but we can add additional visual feedback here if needed
        if state == 2:  # Checked state
            # Add selected visual indicator (handled by CSS)
            pass
        else:  # Unchecked state
            # Remove selected visual indicator (handled by CSS)
            pass

    def _create_custom_tooltip_checkbox(self, device_text, tooltip_text):
        """Create a checkbox with custom tooltip positioning."""
        checkbox = QCheckBox(device_text)

        # Remove default tooltip and add custom event handling
        checkbox.setToolTip("")  # Clear default tooltip
        checkbox.enterEvent = lambda event: self._show_custom_tooltip(checkbox, tooltip_text, event)
        checkbox.leaveEvent = lambda event: QToolTip.hideText()

        return checkbox

    def _show_custom_tooltip(self, widget, tooltip_text, event):
        """Show custom positioned tooltip near cursor."""
        # Get global cursor position
        cursor_pos = QCursor.pos()

        # Offset tooltip very close to cursor (5px right, 5px down)
        tooltip_pos = QPoint(cursor_pos.x() + 5, cursor_pos.y() + 5)

        # Show tooltip at custom position
        QToolTip.showText(tooltip_pos, tooltip_text, widget)

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
        """Show context menu for individual device."""
        if device_serial not in self.device_dict:
            return

        device = self.device_dict[device_serial]
        context_menu = QMenu(self)
        # Use system default styling for context menu
        context_menu.setStyleSheet(StyleManager.get_menu_style())

        # Device info header
        device_name = f'📱 {device.device_model} ({device_serial[:8]}...)'
        header_action = context_menu.addAction(device_name)
        header_action.setEnabled(False)
        # Note: QAction doesn't support setStyleSheet, styling is handled by QMenu
        context_menu.addSeparator()

        # Quick selection actions
        select_only_action = context_menu.addAction('✅ Select Only This Device')
        select_only_action.triggered.connect(lambda: self.select_only_device(device_serial))

        deselect_action = context_menu.addAction('❌ Deselect This Device')
        deselect_action.triggered.connect(lambda: self.deselect_device(device_serial))

        view_logcat_action = context_menu.addAction('👁️ View Logcat')
        view_logcat_action.triggered.connect(lambda: self.view_logcat_for_device(device_serial))

        context_menu.addSeparator()

        # UI Inspector action (always available for any device)
        ui_inspector_action = context_menu.addAction('🔍 Launch UI Inspector')
        ui_inspector_action.triggered.connect(lambda: self.launch_ui_inspector_for_device(device_serial))
        context_menu.addSeparator()

        # Device-specific actions
        reboot_action = context_menu.addAction('🔄 Reboot Device')
        reboot_action.triggered.connect(lambda: self.reboot_single_device(device_serial))

        screenshot_action = context_menu.addAction('📷 Take Screenshot')
        screenshot_action.triggered.connect(lambda: self.take_screenshot_single_device(device_serial))

        scrcpy_action = context_menu.addAction('🖥️ Mirror Device (scrcpy)')
        scrcpy_action.triggered.connect(lambda: self.launch_scrcpy_single_device(device_serial))

        context_menu.addSeparator()

        # Copy device info
        copy_info_action = context_menu.addAction('📋 Copy Device Info')
        copy_info_action.triggered.connect(lambda: self.copy_single_device_info(device_serial))

        # Show context menu
        global_pos = checkbox_widget.mapToGlobal(position)
        context_menu.exec(global_pos)

    def select_only_device(self, target_serial):
        """Select only the specified device, deselect all others."""
        if self.virtualized_active and self.virtualized_device_list is not None:
            if target_serial in self.device_dict:
                self.virtualized_device_list.set_checked_serials({target_serial})
            else:
                self.virtualized_device_list.set_checked_serials(set())
            return

        for serial, checkbox in self.check_devices.items():
            checkbox.setChecked(serial == target_serial)

    def deselect_device(self, target_serial):
        """Deselect the specified device."""
        if self.virtualized_active and self.virtualized_device_list is not None:
            current = set(self.virtualized_device_list.checked_devices)
            if target_serial in current:
                current.discard(target_serial)
                self.virtualized_device_list.set_checked_serials(current)
            return

        if target_serial in self.check_devices:
            self.check_devices[target_serial].setChecked(False)

    def launch_ui_inspector_for_device(self, device_serial):
        """Launch UI Inspector for a specific device using the unified UI Inspector functionality."""
        if device_serial in self.device_dict:
            device = self.device_dict[device_serial]
            # Temporarily select only this device for the UI Inspector operation
            original_selections = self._backup_device_selections()
            self.select_only_device(device_serial)

            # Use the same UI Inspector function as tabs
            self.launch_ui_inspector()

            # Restore original selections
            self._restore_device_selections(original_selections)
        else:
            self.show_error('Error', f'Device {device_serial} not found.')

    def reboot_single_device(self, device_serial):
        """Reboot a single device using the unified reboot functionality."""
        if device_serial in self.device_dict:
            device = self.device_dict[device_serial]
            # Temporarily select only this device for the reboot operation
            original_selections = self._backup_device_selections()
            self.select_only_device(device_serial)

            # Use the same reboot function as tabs
            self.reboot_device()

            # Restore original selections
            self._restore_device_selections(original_selections)
        else:
            self.show_error('Error', f'Device {device_serial} not found.')

    def take_screenshot_single_device(self, device_serial):
        """Take screenshot for a single device using the unified screenshot functionality."""
        if device_serial in self.device_dict:
            device = self.device_dict[device_serial]
            # Temporarily select only this device for the screenshot operation
            original_selections = self._backup_device_selections()
            self.select_only_device(device_serial)

            # Use the same screenshot function as tabs
            self.take_screenshot()

            # Restore original selections
            self._restore_device_selections(original_selections)
        else:
            self.show_error('Error', f'Device {device_serial} not found.')

    def launch_scrcpy_single_device(self, device_serial):
        """Launch scrcpy for a single device."""
        self.app_management_manager.launch_scrcpy_for_device(device_serial)

    def _backup_device_selections(self):
        """Backup current device selections."""
        if self.virtualized_active and self.virtualized_device_list is not None:
            return {serial: True for serial in self.virtualized_device_list.checked_devices}

        selections = {}
        for serial, checkbox in self.check_devices.items():
            selections[serial] = checkbox.isChecked()
        return selections

    def _restore_device_selections(self, selections):
        """Restore device selections from backup."""
        if self.virtualized_active and self.virtualized_device_list is not None:
            selected_serials = {serial for serial, is_checked in selections.items() if is_checked}
            self.virtualized_device_list.set_checked_serials(selected_serials)
            return

        for serial, checkbox in self.check_devices.items():
            if serial in selections:
                checkbox.setChecked(selections[serial])




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
        """Copy information for a single device."""
        if device_serial in self.device_dict:
            device = self.device_dict[device_serial]
            device_info = f'''Device Information:
Model: {device.device_model}
Serial: {device.device_serial_num}
Android Version: {device.android_ver if device.android_ver else 'Unknown'} (API Level {device.android_api_level if device.android_api_level else 'Unknown'})
GMS Version: {device.gms_version if device.gms_version else 'Unknown'}
Product: {device.device_prod}
USB: {device.device_usb}
WiFi Status: {self._get_on_off_status(device.wifi_is_on)}
Bluetooth Status: {self._get_on_off_status(device.bt_is_on)}
Build Fingerprint: {device.build_fingerprint}'''

            try:
                clipboard = QGuiApplication.clipboard()
                clipboard.setText(device_info)
                self.show_info('📋 Copied!', f'Device information copied to clipboard for:\n{device.device_model}')
                logger.info(f'📋 Copied device info to clipboard: {device_serial}')
            except Exception as e:
                logger.error(f'❌ Failed to copy device info to clipboard: {e}')
                self.show_error('Error', f'Could not copy to clipboard:\n{e}')

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

        # Use new recording manager with callback
        def recording_callback(device_name, device_serial, duration, filename, output_path):
            self.recording_stopped_signal.emit(device_name, device_serial, duration, filename, output_path)

        success = self.recording_manager.start_recording(devices, validated_path, recording_callback)
        if not success:
            self.error_handler.handle_error(ErrorCode.COMMAND_FAILED, 'Failed to start recording')

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
