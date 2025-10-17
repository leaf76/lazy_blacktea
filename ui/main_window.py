"""A PyQt6 GUI application for simplifying Android ADB and automation tasks."""

from __future__ import annotations

import logging
import math
import os
import platform
import sys
import threading
import webbrowser
from typing import Dict, List, Iterable, Optional, Set, Callable, Any

from utils.qt_plugin_loader import configure_qt_plugin_path

configure_qt_plugin_path()

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout,
    QSplitter,
    QTreeWidget,
    QTreeWidgetItem,
    QMessageBox,
    QProgressDialog,
)
from PyQt6.QtCore import (Qt, QTimer, QPoint, QRect, pyqtSignal)
from PyQt6.QtGui import (QTextCursor, QAction, QIcon, QGuiApplication)

from utils import adb_models
from utils import adb_tools
from utils import common
from utils import json_utils

# Import configuration and constants
from config.config_manager import AppConfig, ConfigManager, LogcatSettings, UISettings
from config.constants import (
    UIConstants, PathConstants, ADBConstants,
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
from ui.device_file_browser_manager import DeviceFileBrowserManager
from ui.device_file_preview_window import DeviceFilePreviewWindow
from ui.command_execution_manager import CommandExecutionManager
from ui.style_manager import StyleManager, ButtonStyle, LabelStyle, ThemeManager
from ui.app_management_manager import AppManagementManager
from ui.logging_manager import LoggingManager, DiagnosticsManager, ConsoleHandler
from ui.operation_logging_mixin import OperationLoggingMixin
from ui.device_list_controller import DeviceListController
from ui.device_actions_controller import DeviceActionsController
from ui.tools_panel_controller import ToolsPanelController
from ui.screenshot_widget import ClickableScreenshotLabel
from ui.output_path_manager import OutputPathManager
from ui.ui_inspector_dialog import UIInspectorDialog
from ui.device_group_manager import DeviceGroupManager
from ui.console_manager import ConsoleManager
from ui.device_list_context_menu import DeviceListContextMenuManager
from ui.completion_dialog_manager import CompletionDialogManager
from ui.dialog_manager import DialogManager
from ui.status_bar_manager import StatusBarManager
from ui.recording_status_view import update_recording_status_view
from ui.system_actions_manager import SystemActionsManager
from ui.file_dialog_manager import FileDialogManager
from ui.battery_info_manager import BatteryInfoManager
from ui.device_detail_dialog import DeviceDetailDialog
from ui.device_selection_manager import DeviceSelectionManager
from ui.bluetooth_monitor_window import BluetoothMonitorWindow
from ui.constants import DEVICE_FILE_IS_DIR_ROLE, DEVICE_FILE_PATH_ROLE
from ui.device_file_controller import DeviceFileController
from ui.recording_controller import RecordingController
from ui.signal_payloads import RecordingProgressEvent
from ui.scrcpy_settings_dialog import ScrcpySettingsDialog
from ui.apk_install_settings_dialog import ApkInstallSettingsDialog
from ui.capture_settings_dialog import CaptureSettingsDialog
from ui.device_files_facade import DeviceFilesFacade
from ui.device_groups_facade import DeviceGroupsFacade
from ui.commands_facade import CommandsFacade
from ui.device_actions_facade import DeviceActionsFacade
from ui.logcat_facade import LogcatFacade
from ui.button_progress_overlay import ButtonProgressOverlay

# Import new utils modules
from utils.screenshot_utils import take_screenshots_batch, validate_screenshot_path
from utils.recording_utils import RecordingManager
from utils.ui_inspector_utils import check_ui_inspector_prerequisites
# File generation utilities are now handled by FileOperationsManager
from utils.qt_dependency_checker import check_and_fix_qt_dependencies
from utils.icon_resolver import iter_icon_paths
from utils.task_dispatcher import TaskContext, TaskHandle, get_task_dispatcher

logger = common.get_logger('lazy_blacktea')

os.environ.setdefault('QT_DELAY_BEFORE_TIP', '300')


# Logcat classes moved to ui.logcat_viewer
from ui.logcat_viewer import LogcatWindow


class WindowMain(QMainWindow, OperationLoggingMixin):
    finalize_operation_requested = pyqtSignal(list, str)
    """Main PyQt6 application window."""

    DEVICE_FILE_BROWSER_DEFAULT_PATH = PanelText.PLACEHOLDER_DEVICE_FILE_PATH

    # Define custom signals for thread-safe UI updates
    recording_stopped_signal = pyqtSignal(str, str, str, str, str)  # device_name, device_serial, duration, filename, output_path
    recording_state_cleared_signal = pyqtSignal(str)  # device_serial
    recording_progress_signal = pyqtSignal(object)  # RecordingProgressEvent payload
    screenshot_completed_signal = pyqtSignal(str, int, list)  # output_path, device_count, device_models
    file_generation_completed_signal = pyqtSignal(str, str, int, str)  # operation_name, output_path, device_count, icon
    console_output_signal = pyqtSignal(str)  # message

    def __init__(self):
        super().__init__()

        # Initialize new modular components
        self.config_manager = ConfigManager()
        self.theme_manager = ThemeManager()
        self.theme_actions: Dict[str, QAction] = {}
        self._current_theme = 'light'
        initial_config = self.config_manager.load_config()
        self._initial_ui_settings: UISettings = initial_config.ui
        self._initial_single_selection = getattr(self._initial_ui_settings, 'single_selection', True)
        self._current_theme = self.theme_manager.set_theme(initial_config.ui.theme)
        self.error_handler = ErrorHandler(self)
        self.command_executor = CommandExecutor(self)
        self.device_manager = DeviceManager(self)
        self.recording_manager = RecordingManager()
        self.recording_controller = RecordingController(self)
        self.panels_manager = PanelsManager(self)
        self.device_file_browser_manager = DeviceFileBrowserManager(self)
        self.device_file_controller = DeviceFileController(self)
        self.device_files_facade = DeviceFilesFacade(self, self.device_file_controller)
        self.device_groups_facade = DeviceGroupsFacade(self)
        self.commands_facade = CommandsFacade(self)
        self.device_selection_manager = DeviceSelectionManager()

        self.tool_action_handlers: Dict[str, Callable[[], None]] = {}
        self.tool_buttons: Dict[str, Any] = {}
        self.tool_progress_bars: Dict[str, Any] = {}
        self._operation_overlays: Dict[str, ButtonProgressOverlay] = {}
        self._tool_cancel_hooks: Dict[str, Callable[[], None]] = {}
        self.bug_report_button = None
        self.install_apk_button = None

        self.show_console_panel = self._initial_ui_settings.show_console_panel
        self.console_panel_action: Optional[QAction] = None
        self.console_panel = None

        # Background task dispatcher
        self._task_dispatcher = get_task_dispatcher()
        self._background_task_handles: List[TaskHandle] = []

        # Connect device manager signals to main UI update
        self.device_manager.device_found.connect(self._on_device_found_from_manager)
        self.device_manager.device_lost.connect(self._on_device_lost_from_manager)
        self.device_manager.status_updated.connect(self._on_device_status_updated)
        self.device_file_browser_manager.directory_listing_ready.connect(self.device_file_controller.on_directory_listing)
        self.device_file_browser_manager.download_completed.connect(self.device_file_controller.on_download_completed)
        self.device_file_browser_manager.preview_ready.connect(self.device_file_controller.on_preview_ready)
        self.device_file_browser_manager.operation_failed.connect(self.device_file_controller.on_operation_failed)

        # Setup global error handler and exception hook
        global_error_handler.parent = self
        setup_exception_hook()

        # Initialize variables (keeping some for compatibility)
        self.device_dict: Dict[str, adb_models.DeviceInfo] = {}
        self.virtualized_active = False
        self.virtualized_device_list = None
        self.check_devices: Dict[str, object] = {}
        self.device_groups: Dict[str, List[str]] = {}
        self.refresh_interval = 30
        self.refresh_interval_actions: Dict[int, QAction] = {}
        self.auto_refresh_action: Optional[QAction] = None
        self.auto_refresh_enabled = True
        self.device_file_tree: Optional[QTreeWidget] = None
        self.device_file_browser_path_edit = None
        self.device_file_status_label = None
        self.device_file_browser_device_label = None
        self.device_file_browser_current_serial: Optional[str] = None
        self.device_file_browser_current_path: str = self.DEVICE_FILE_BROWSER_DEFAULT_PATH
        self.device_file_preview_window: Optional[DeviceFilePreviewWindow] = None
        self.selection_summary_label = None
        self.device_overview_widget = None
        self.ui_scale_actions: Dict[float, QAction] = {}
        self.logcat_settings: Optional[LogcatSettings] = None
        self.bluetooth_windows: Dict[str, BluetoothMonitorWindow] = {}

        # Initialize device search manager
        self.device_search_manager = DeviceSearchManager(main_window=self)

        # Initialize controller handling device list rendering
        self.device_list_controller = DeviceListController(self)
        self.tools_panel_controller = ToolsPanelController(self)
        self.device_actions_controller = DeviceActionsController(self)
        self.device_actions_facade = DeviceActionsFacade(self)

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

        # Initialize device group manager
        self.device_group_manager = DeviceGroupManager(self)

        # Initialize console manager
        self.console_manager = ConsoleManager(self)

        # Initialize device list context menu manager
        self.device_list_context_menu_manager = DeviceListContextMenuManager(self)

        # Initialize dialog manager
        self.dialog_manager = DialogManager(self)

        # Initialize status bar manager
        self.status_bar_manager = StatusBarManager(self)

        # Initialize completion dialog manager
        self.completion_dialog_manager = CompletionDialogManager(self)

        # Initialize system actions manager
        self.system_actions_manager = SystemActionsManager(self)

        # Initialize file dialog manager
        self.file_dialog_manager = FileDialogManager()

        # Initialize battery info manager
        self.battery_info_manager = BatteryInfoManager(self)

        # Initialize logging and diagnostics manager
        self.logging_manager = LoggingManager(self)
        self.diagnostics_manager = DiagnosticsManager(self)
        self.logcat_facade = LogcatFacade(self)


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
        self.finalize_operation_requested.connect(self._finalize_operation)

        # Connect device operations manager signals
        self.device_operations_manager.recording_stopped_signal.connect(self._on_recording_stopped)
        self.device_operations_manager.recording_state_cleared_signal.connect(self._on_recording_state_cleared)
        self.device_operations_manager.screenshot_completed_signal.connect(self._on_screenshot_completed)
        self.device_operations_manager.operation_completed_signal.connect(self._on_device_operation_completed)

        # Connect file operations manager signals
        self.file_operations_manager.file_generation_completed_signal.connect(self._on_file_generation_completed)
        self.file_operations_manager.file_generation_progress_signal.connect(self._on_file_generation_progress)

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
        self.apply_theme(self._current_theme, persist=False, initial=True)
        self.output_path_manager = OutputPathManager(self, self.file_dialog_manager)
        self.load_config(initial_config)

        # Initialize groups list (now that UI is created)
        self.device_group_manager.update_groups_listbox()

        # Start device refresh with delay to avoid GUI blocking (after config is loaded)
        QTimer.singleShot(500, self.device_manager.start_device_refresh)

        # Start periodic battery info refresh
        self.battery_info_manager.start()
        QTimer.singleShot(2000, self.battery_info_manager.refresh_all)

    def _apply_window_geometry(self, ui_settings: Optional[UISettings]) -> None:
        """Apply initial window geometry derived from configuration and screen bounds."""
        screen = QGuiApplication.primaryScreen()
        if screen is not None:
            available_rect = QRect(screen.availableGeometry())
        else:
            available_rect = QRect(0, 0, UIConstants.WINDOW_WIDTH, UIConstants.WINDOW_HEIGHT)

        default_width = UIConstants.WINDOW_WIDTH
        default_height = UIConstants.WINDOW_HEIGHT
        default_x = 100
        default_y = 100

        if ui_settings is not None:
            if ui_settings.window_width > 0:
                default_width = ui_settings.window_width
            if ui_settings.window_height > 0:
                default_height = ui_settings.window_height
            default_x = ui_settings.window_x
            default_y = ui_settings.window_y

        width = max(UIConstants.WINDOW_MIN_WIDTH, default_width)
        height = max(UIConstants.WINDOW_MIN_HEIGHT, default_height)

        width = min(width, available_rect.width()) if available_rect.width() > 0 else width
        height = min(height, available_rect.height()) if available_rect.height() > 0 else height

        max_x = available_rect.left() + max(0, available_rect.width() - width)
        max_y = available_rect.top() + max(0, available_rect.height() - height)

        x = max(available_rect.left(), min(default_x, max_x)) if available_rect.width() > 0 else default_x
        y = max(available_rect.top(), min(default_y, max_y)) if available_rect.height() > 0 else default_y

        self.setGeometry(x, y, width, height)

    def init_ui(self):
        """Initialize the user interface."""
        logger.info('[INIT] init_ui method started')
        self.setWindowTitle(f'🍵 {ApplicationConstants.APP_NAME} v{ApplicationConstants.APP_VERSION}')

        self.setMinimumSize(UIConstants.WINDOW_MIN_WIDTH, UIConstants.WINDOW_MIN_HEIGHT)
        self._apply_window_geometry(getattr(self, '_initial_ui_settings', None))


        # Set application icon
        self.set_app_icon()

        # Remove the problematic attribute setting as it's not needed for tooltip positioning

        # Create central widget
        central_widget = QWidget()
        central_widget.setObjectName('mainCentralWidget')
        self.setCentralWidget(central_widget)

        # Create main layout container
        main_layout = QVBoxLayout(central_widget)

        # Menu bar
        self.panels_manager.create_menu_bar(self)

        # Build a vertical splitter so the bottom console is resizable
        vertical_splitter = QSplitter(Qt.Orientation.Vertical)
        main_layout.addWidget(vertical_splitter)

        # Top: existing horizontal splitter for device list and tools
        main_splitter = QSplitter(Qt.Orientation.Horizontal)
        vertical_splitter.addWidget(main_splitter)

        # Create device list panel
        # Create device panel using panels_manager
        device_components = self.panels_manager.create_device_panel(main_splitter, self)
        self.title_label = device_components['title_label']
        self.device_table = device_components['device_table']
        self.no_devices_label = device_components['no_devices_label']
        self.device_panel_stack = device_components['device_panel_stack']
        self.selection_summary_label = device_components['selection_summary_label']
        # New selection mode + hint references
        self.selection_hint_label = device_components.get('selection_hint_label')
        self.selection_mode_checkbox = device_components.get('selection_mode_checkbox')
        # Control buttons references for selection mode dependent state
        self.select_all_btn = device_components.get('select_all_btn')
        self.select_none_btn = device_components.get('select_none_btn')

        self.device_list_controller.attach_table(self.device_table)
        self.device_list_controller.update_selection_count()

        # Create tools panel via controller
        self.tools_panel_controller.create_tools_panel(main_splitter)
        self.update_device_overview()

        # Set splitter proportions (default 50/50 but still resizable)
        default_width = UIConstants.WINDOW_WIDTH
        left_width = max(1, int(default_width * 0.4))
        right_width = max(1, default_width - left_width)
        main_splitter.setSizes([left_width, right_width])
        main_splitter.setStretchFactor(0, 1)
        main_splitter.setStretchFactor(1, 1)

        # Bottom: console panel (resizable via the vertical splitter)
        self.create_console_panel(vertical_splitter)

        # Set initial proportions for vertical splitter (e.g., ~80% top / 20% bottom)
        try:
            total_h = max(self.height(), UIConstants.WINDOW_HEIGHT)
            top_h = max(300, int(total_h * 0.8))
            bottom_h = max(180, total_h - top_h)
            vertical_splitter.setSizes([top_h, bottom_h])
        except Exception:
            # Fallback sizes if geometry is not yet stable
            vertical_splitter.setSizes([UIConstants.WINDOW_HEIGHT - 220, 220])

        # Encourage the top area to take remaining space when resizing
        vertical_splitter.setStretchFactor(0, 5)
        vertical_splitter.setStretchFactor(1, 1)

        # Create status bar
        self.create_status_bar()

        # Apply persisted selection mode after UI is ready
        try:
            # Ensure manager state
            self.device_selection_manager.set_single_selection(self._initial_single_selection)
            # Sync checkbox without emitting signals
            if self.selection_mode_checkbox is not None:
                prev = self.selection_mode_checkbox.blockSignals(True)
                self.selection_mode_checkbox.setChecked(self._initial_single_selection)
                self.selection_mode_checkbox.blockSignals(prev)
            # Update dependent UI and status label
            self._sync_selection_mode_dependent_ui()
            self.status_bar_manager.update_selection_mode(self.device_selection_manager.is_single_selection())
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning('Failed to apply initial selection mode: %s', exc)

    # ------------------------------------------------------------------
    # Tools panel button registration & progress overlays
    # ------------------------------------------------------------------
    def register_tool_action(self, action_key: str, handler: Callable[[], None], button, progress_bar=None) -> None:
        """Register a tools panel button for centralized action handling."""
        self.tool_action_handlers[action_key] = handler
        self.tool_buttons[action_key] = button

        if progress_bar is not None:
            self.tool_progress_bars[action_key] = progress_bar
        else:
            self.tool_progress_bars.pop(action_key, None)

        if action_key in {'bug_report', 'install_apk'}:
            self._tool_cancel_hooks[action_key] = lambda key=action_key: self._invoke_cancel_for_action(key)

    def handle_tool_action(self, action_key: str) -> None:
        """Dispatch tool button clicks with support for cancellation."""
        overlay = self._operation_overlays.get(action_key)
        if overlay and overlay.is_active:
            cancel_hook = self._tool_cancel_hooks.get(action_key)
            if cancel_hook and overlay.is_cancellable:
                cancel_hook()
                return
            # Ignore double clicks when the operation is busy and not cancellable.
            return

        if action_key == 'bug_report' and self.file_operations_manager.is_bug_report_in_progress():
            cancel = self._tool_cancel_hooks.get(action_key)
            if cancel:
                cancel()
            return

        if action_key == 'install_apk' and self.app_management_manager.apk_manager.is_installation_in_progress():
            cancel = self._tool_cancel_hooks.get(action_key)
            if cancel:
                cancel()
            return

        handler = self.tool_action_handlers.get(action_key)
        if handler:
            handler()

    def _invoke_cancel_for_action(self, action_key: str) -> None:
        if action_key == 'bug_report':
            self.file_operations_manager.cancel_bug_report_generation()
        elif action_key == 'install_apk':
            self.app_management_manager.cancel_apk_installation()

    def _ensure_operation_overlay(self, action_key: str) -> Optional[ButtonProgressOverlay]:
        if action_key not in {'bug_report', 'install_apk'}:
            return None
        overlay = self._operation_overlays.get(action_key)
        if overlay is not None:
            return overlay
        button = self.tool_buttons.get(action_key)
        progress_bar = self.tool_progress_bars.get(action_key)
        if button is None:
            return None
        overlay = ButtonProgressOverlay(button, progress_bar)
        overlay.set_cancellable(True)
        self._operation_overlays[action_key] = overlay
        return overlay

    def _apply_progress_state_to_overlay(self, action_key: str, state) -> None:
        overlay = self._ensure_operation_overlay(action_key)
        if overlay is None or state is None:
            return

        mode = getattr(state, 'mode', 'idle') or 'idle'
        message = getattr(state, 'message', '')
        current = getattr(state, 'current', 0) or 0
        total = getattr(state, 'total', 0) or 0

        if mode == 'idle':
            overlay.reset()
        elif mode == 'busy':
            overlay.set_busy(message)
        elif mode == 'progress':
            overlay.set_progress(current, max(1, total), message)
        elif mode == 'cancelling':
            overlay.set_cancelling(message)
        elif mode in {'completed', 'cancelled'}:
            overlay.finish(message or None)
        elif mode == 'failed':
            overlay.fail(message or None)

    def on_bug_report_progress_reset(self) -> None:
        state = self.file_operations_manager.get_bug_report_progress_state()
        self._apply_progress_state_to_overlay('bug_report', state)

    def on_apk_install_progress_reset(self) -> None:
        state = self.app_management_manager.apk_manager.get_installation_progress_state()
        self._apply_progress_state_to_overlay('install_apk', state)

    # ------------------------------------------------------------------
    # Device selection mode
    # ------------------------------------------------------------------
    def handle_selection_mode_toggle(self, enabled: bool) -> None:
        """Toggle between single-select and multi-select for the device list."""
        try:
            self.device_selection_manager.set_single_selection(bool(enabled))
            # If switching to single, collapse selection is already handled by manager
            selected = self.device_selection_manager.get_selected_serials()
            active = self.device_selection_manager.get_active_serial()
            # Re-sync UI selection and labels
            self.device_list_controller._set_selection(selected, active_serial=active)
            self.device_list_controller.update_selection_count()
            # Update UI controls and status indicator
            self._sync_selection_mode_dependent_ui()
            self.status_bar_manager.update_selection_mode(self.device_selection_manager.is_single_selection())
            # Persist setting
            try:
                self.config_manager.update_ui_settings(single_selection=self.device_selection_manager.is_single_selection())
            except Exception as exc:  # pragma: no cover - defensive
                logger.warning('Failed to persist selection mode: %s', exc)
            logger.info('Selection mode changed: %s', 'single' if enabled else 'multi')
        except Exception as exc:  # pragma: no cover - safety
            logger.error('Failed to toggle selection mode: %s', exc)

    def _sync_selection_mode_dependent_ui(self) -> None:
        """Update widgets (buttons, tips, labels) based on selection mode state."""
        single = self.device_selection_manager.is_single_selection()
        # Panel buttons
        if getattr(self, 'select_all_btn', None) is not None:
            try:
                # Update label and tooltip instead of disabling in single mode
                if single:
                    self.select_all_btn.setText('Select Last Visible')
                    self.select_all_btn.setToolTip('Select the last visible device (single-select mode)')
                else:
                    self.select_all_btn.setText('Select All')
                    self.select_all_btn.setToolTip('Select all devices')
            except Exception:  # pragma: no cover - compatibility
                pass

    def set_app_icon(self):
        """Set the application icon across supported platforms."""

        app = QApplication.instance()
        for icon_path in iter_icon_paths():
            try:
                resolved_path = os.fspath(icon_path)
                icon = QIcon(resolved_path)
            except Exception as exc:  # pragma: no cover - defensive
                logger.warning(f"Failed to instantiate icon from {icon_path}: {exc}")
                continue

            if icon.isNull():
                logger.warning(f"Icon at {icon_path} could not be loaded (null icon)")
                continue

            self.setWindowIcon(icon)
            if app is not None:
                app.setWindowIcon(icon)
            logger.debug(f"Successfully loaded app icon from {icon_path}")
            return

        # As a fallback for Linux environments, attempt to load a theme icon
        if platform.system().lower() == 'linux':
            theme_icon = QIcon.fromTheme('lazyblacktea')
            if theme_icon.isNull():
                theme_icon = QIcon.fromTheme('applications-utilities')
            if not theme_icon.isNull():
                self.setWindowIcon(theme_icon)
                if app is not None:
                    app.setWindowIcon(theme_icon)
                logger.info('Using theme icon fallback for Linux desktop environment')
                return

        logger.warning('No suitable app icon found')

    def _setup_async_device_signals(self):
        """設置異步設備管理器的信號連接（通過DeviceManager）"""
        # Note: Signal connections are now handled by DeviceManager
        # No direct AsyncDeviceManager signals needed in main window
        pass



    def update_recording_status(self):
        """Update recording status display using new recording manager."""
        if not hasattr(self, 'recording_status_label'):
            return

        update_recording_status_view(self)

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
        self.console_manager.create_console_panel(parent_layout)
        self.set_console_panel_visibility(self.show_console_panel, persist=False)
        QTimer.singleShot(0, lambda: self.set_console_panel_visibility(self.show_console_panel, persist=False))

    def register_console_panel_action(self, action: QAction) -> None:
        """Register the menu action controlling console visibility."""
        self.console_panel_action = action
        self._sync_console_panel_action()

    def handle_console_panel_toggle(self, visible: bool) -> None:
        """Respond to menu toggle requests for console visibility."""
        self.set_console_panel_visibility(visible)

    def set_console_panel_visibility(self, visible: bool, persist: bool = True) -> None:
        """Show or hide the console panel, optionally persisting the state."""
        self.show_console_panel = bool(visible)

        if self.console_panel is not None:
            if self.show_console_panel:
                self.console_panel.show()
            else:
                self.console_panel.hide()

        self._sync_console_panel_action()

        if persist:
            try:
                self.config_manager.update_ui_settings(show_console_panel=self.show_console_panel)
            except Exception as exc:  # pragma: no cover - defensive logging
                logger.warning('Failed to persist console visibility: %s', exc)

    def _sync_console_panel_action(self) -> None:
        """Ensure the console toggle action matches current visibility state."""
        if self.console_panel_action is None:
            return

        previous = self.console_panel_action.blockSignals(True)
        self.console_panel_action.setChecked(self.show_console_panel)
        self.console_panel_action.blockSignals(previous)


    def create_status_bar(self):
        """Create the status bar."""
        self.status_bar_manager.create_status_bar()
        # Ensure initial selection mode indicator is shown
        self.status_bar_manager.update_selection_mode(self.device_selection_manager.is_single_selection())

    def get_checked_devices(self) -> List[adb_models.DeviceInfo]:
        """Get list of checked devices."""
        selected_serials = self.device_selection_manager.get_selected_serials()
        return [
            self.device_dict[serial]
            for serial in selected_serials
            if serial in self.device_dict
        ]

    def require_single_device_selection(self, action_label: str) -> Optional[adb_models.DeviceInfo]:
        """Validate that exactly one device is selected for a single-target action."""
        valid, serials, message = self.device_selection_manager.require_single_device(action_label)
        if not valid:
            self.show_warning('Device Selection', message)
            return None

        serial = serials[0]
        device = self.device_dict.get(serial)
        if device is None:
            self.show_error('Device Selection', f'The selected device ({serial}) is no longer available.')
            return None
        return device

    def show_info(self, title: str, message: str):
        """Show info message box."""
        self.dialog_manager.show_info(title, message)

    def show_warning(self, title: str, message: str):
        """Show warning message box."""
        self.dialog_manager.show_warning(title, message)

    def show_error(self, title: str, message: str):
        """Show error message box."""
        self.dialog_manager.show_error(title, message)

    def open_scrcpy_settings_dialog(self) -> None:
        """Display the scrcpy settings dialog and persist updates."""
        current_settings = self.config_manager.get_scrcpy_settings()
        dialog = ScrcpySettingsDialog(current_settings, self)
        dialog.exec()

        updated_settings = dialog.get_settings()
        if not updated_settings:
            return

        self.config_manager.set_scrcpy_settings(updated_settings)
        self.show_info(
            'scrcpy Settings Updated',
            'scrcpy will use your new preferences the next time you launch mirroring.'
        )

    def open_apk_install_settings_dialog(self) -> None:
        """Display the APK install settings dialog and persist updates."""
        current_settings = self.config_manager.get_apk_install_settings()
        dialog = ApkInstallSettingsDialog(current_settings, self)
        dialog.exec()

        updated_settings = dialog.get_settings()
        if not updated_settings:
            return

        self.config_manager.set_apk_install_settings(updated_settings)
        self.show_info(
            'APK Install Settings Updated',
            'New adb install flags will be applied to future installs.'
        )

    def open_capture_settings_dialog(self) -> None:
        """Display the Capture (Screenshot & Screen Record) settings dialog and persist updates."""
        ss = self.config_manager.get_screenshot_settings()
        rec = self.config_manager.get_screen_record_settings()
        dialog = CaptureSettingsDialog(ss, rec, self)
        dialog.exec()

        new_ss, new_rec = dialog.get_settings()
        changed = False
        if new_ss is not None:
            self.config_manager.set_screenshot_settings(new_ss)
            changed = True
        if new_rec is not None:
            self.config_manager.set_screen_record_settings(new_rec)
            changed = True
        if changed:
            self.show_info('Capture Settings Updated', 'New screenshot and recording parameters will apply to future actions.')

    # Operation logging helpers moved to OperationLoggingMixin

    def _format_device_label(self, serial: str) -> str:
        device = self.device_dict.get(serial) if hasattr(self, 'device_dict') else None
        name = getattr(device, 'device_model', serial)
        short_serial = f"{serial[:8]}..." if len(serial) > 8 else serial
        return f"{name} ({short_serial})"

    def _show_recording_operation_warning(self, title: str, body_intro: str, serials: list[str]) -> None:
        if serials:
            devices_text = '\n'.join(f"• {self._format_device_label(serial)}" for serial in serials)
        else:
            devices_text = '• Unknown device(s)'
        message = f"{body_intro}\n\nActive devices:\n{devices_text}"
        self.error_handler.show_warning(title, message)

    def register_ui_scale_actions(self, actions: Dict[float, QAction]):
        """Register UI scale actions so menu state stays in sync."""
        self.ui_scale_actions = actions or {}
        self._update_ui_scale_actions(self.user_scale)

    def _update_ui_scale_actions(self, active_scale: float):
        """Sync UI scale menu actions with the current scale."""
        if not self.ui_scale_actions:
            return

        matched_scale: Optional[float] = None
        for scale in self.ui_scale_actions:
            if math.isclose(scale, active_scale, rel_tol=1e-6, abs_tol=1e-3):
                matched_scale = scale
                break

        for scale, action in self.ui_scale_actions.items():
            previous_state = action.blockSignals(True)
            action.setChecked(scale == matched_scale)
            action.blockSignals(previous_state)

    def handle_ui_scale_selection(self, scale: float):
        """Apply user-selected UI scale and persist the preference."""
        self.set_ui_scale(scale)
        if hasattr(self, 'config_manager') and self.config_manager is not None:
            try:
                self.config_manager.update_ui_settings(ui_scale=self.user_scale)
            except Exception as exc:
                logger.error('Failed to persist UI scale preference: %s', exc)

    def set_ui_scale(self, scale: float):
        """Set UI scale factor."""
        self.user_scale = max(0.5, min(scale, 3.0))
        font = self.font()
        base_size = max(6, int(round(10 * self.user_scale)))
        font.setPointSize(base_size)
        self.setFont(font)

        app = QApplication.instance()
        if app is not None:
            app_font = app.font()
            app_font.setPointSize(base_size)
            app.setFont(app_font)

        self._update_ui_scale_actions(self.user_scale)
        logger.debug(f'UI scale set to {self.user_scale}')

    def set_refresh_interval(self, interval: int):
        """Set device refresh interval."""
        interval = max(5, interval)
        self.refresh_interval = interval
        if hasattr(self, 'device_manager'):
            self.device_manager.set_refresh_interval(interval)
            logger.info(f'Refresh interval set to {interval} seconds and applied to DeviceManager')
        else:
            logger.warning(f'Refresh interval set to {interval} seconds but DeviceManager not yet available')
        self._update_refresh_interval_actions(interval)

    def set_auto_refresh_enabled(self, enabled: bool):
        """Enable or disable automatic device refresh."""
        self.auto_refresh_enabled = enabled
        if hasattr(self, 'device_manager'):
            self.device_manager.set_auto_refresh_enabled(enabled)
        self._update_auto_refresh_action(enabled)
        message = '🔁 Auto refresh enabled' if enabled else '⏸️ Auto refresh paused'
        self.status_bar_manager.show_message(message, 4000)

    def _update_refresh_interval_actions(self, interval: int):
        """Sync refresh interval menu state with the current value."""
        for value, action in getattr(self, 'refresh_interval_actions', {}).items():
            block = action.blockSignals(True)
            action.setChecked(value == interval)
            action.blockSignals(block)

    def _update_auto_refresh_action(self, enabled: bool):
        """Sync auto refresh menu action state."""
        action = getattr(self, 'auto_refresh_action', None)
        if action is None:
            return
        block = action.blockSignals(True)
        action.setChecked(enabled)
        action.blockSignals(block)

    def update_device_list(self, device_dict: Dict[str, adb_models.DeviceInfo]):
        self.device_list_controller.update_device_list(device_dict)

    def _update_device_list_optimized(self, device_dict: Dict[str, adb_models.DeviceInfo]):
        self.device_list_controller._update_device_list_optimized(device_dict)

    def filter_and_sort_devices(self):
        self.device_list_controller.filter_and_sort_devices()

    def on_search_changed(self, text: str):
        self.device_list_controller.on_search_changed(text)

    def on_sort_changed(self, sort_mode: str):
        self.device_list_controller.on_sort_changed(sort_mode)

    def refresh_device_list(self):
        """Manually refresh device list with progressive discovery."""
        operation = 'Refresh Device List'
        self._log_operation_start(operation)
        try:
            logger.info('🔄 Manual device refresh requested (using DeviceManager)')

            # Use DeviceManager for unified device management
            self.device_manager.force_refresh()

            # Update status to show loading
            self.status_bar_manager.show_message('🔄 Discovering devices...', 5000)
            self._log_operation_complete(operation, 'Async refresh scheduled')

        except Exception as e:
            logger.error(f'Error starting device refresh: {e}')
            self._log_operation_failure(operation, str(e))
            self.error_handler.handle_error(ErrorCode.DEVICE_NOT_FOUND, f'Failed to start refresh: {e}')

            # Fallback to original synchronous method if needed
            try:
                logger.info('Falling back to synchronous device refresh')
                devices = adb_tools.get_devices_list()
                device_dict = {device.device_serial_num: device for device in devices}
                self.update_device_list(device_dict)
                logger.info('Device list refreshed (fallback mode)')
                self._log_operation_complete(operation, 'Fallback succeeded')
            except Exception as fallback_error:
                logger.error(f'Fallback refresh also failed: {fallback_error}')
                self.error_handler.handle_error(ErrorCode.DEVICE_NOT_FOUND, f'All refresh methods failed: {fallback_error}')
                self._log_operation_failure(operation, str(fallback_error))

    def select_all_devices(self):
        """Select all connected devices."""
        self._execute_with_operation_logging(
            'Select All Devices',
            self.device_list_controller.select_all_devices,
        )

    def select_no_devices(self):
        """Deselect all devices."""
        self._execute_with_operation_logging(
            'Deselect All Devices',
            self.device_list_controller.select_no_devices,
        )

    def handle_select_all_action(self):
        """Context-aware handler for the Select All panel/menu action.

        - In multi-select mode: selects all devices.
        - In single-select mode: selects the last visible device.
        """
        if self.device_selection_manager.is_single_selection():
            self._execute_with_operation_logging(
                'Select Last Visible Device',
                self.device_list_controller.select_last_visible_device,
            )
        else:
            self.select_all_devices()

    # Device Groups functionality
    def save_group(self):
        self._execute_with_operation_logging(
            'Save Device Group',
            self.device_groups_facade.save_group,
        )

    def delete_group(self):
        self._execute_with_operation_logging(
            'Delete Device Group',
            self.device_groups_facade.delete_group,
        )

    def select_devices_in_group(self):
        self._execute_with_operation_logging(
            'Select Devices In Group',
            self.device_groups_facade.select_devices_in_group,
        )

    def select_devices_in_group_by_name(self, group_name: str):
        self._execute_with_operation_logging(
            f'Select Group: {group_name}',
            lambda: self.device_groups_facade.select_devices_in_group_by_name(group_name),
        )

    def update_groups_listbox(self):
        self._execute_with_operation_logging(
            'Update Group List',
            self.device_groups_facade.update_groups_listbox,
        )

    def on_group_select(self):
        self._execute_with_operation_logging(
            'Handle Group Selection',
            self.device_groups_facade.on_group_select,
        )

    # Context Menu functionality
    def show_device_list_context_menu(self, position):
        """Show context menu for device list."""
        self.device_list_context_menu_manager.show_context_menu(position)

    def copy_selected_device_info(self):
        self._execute_with_operation_logging(
            'Copy Selected Device Info',
            self.device_actions_facade.copy_selected_device_info,
        )

    def show_console_context_menu(self, position):
        """Show context menu for console."""
        self.console_manager.show_console_context_menu(position)

    def copy_console_text(self):
        """Copy selected console text to clipboard."""
        self._execute_with_operation_logging(
            'Copy Console Text',
            self.console_manager.copy_console_text,
        )

    def clear_console(self):
        """Clear the console output."""
        self._execute_with_operation_logging(
            'Clear Console',
            self.console_manager.clear_console,
        )

    def _check_scrcpy_available(self):
        """Check if scrcpy is available (deprecated - use app_management_manager)."""
        return self.app_management_manager.check_scrcpy_available()

    def update_selection_count(self):
        """Update the title to show current selection count."""
        self.device_list_controller.update_selection_count()

    def update_device_overview(self) -> None:
        """Synchronise the overview tab with the active selection."""
        widget = getattr(self, 'device_overview_widget', None)
        if widget is None:
            return

        active_serial = self.device_selection_manager.get_active_serial()
        device = self.device_dict.get(active_serial) if active_serial else None

        if device is None:
            widget.set_overview(None, None, None)
            return

        try:
            detail_text = self.device_list_controller.get_device_detail_text(
                device,
                active_serial,
                include_additional=False,
                include_identity=False,
                include_connectivity=False,
                include_status=True,
            )
        except Exception as exc:  # pragma: no cover - defensive safeguard
            logger.warning('Failed to build overview details for %s: %s', active_serial, exc)
            detail_text = 'Details unavailable.'

        widget.set_overview(device, active_serial, detail_text)

    def refresh_active_device_overview(self) -> None:
        """Trigger a detail refresh for the active device and update the overview."""
        widget = getattr(self, 'device_overview_widget', None)
        if widget is None:
            return

        active_serial = self.device_selection_manager.get_active_serial()
        if not active_serial:
            self.show_warning('Device Selection', 'Select a device before refreshing the overview.')
            return

        device = self.device_dict.get(active_serial)
        if device is None:
            self.show_error('Device Selection', f'Device {active_serial} is no longer available.')
            widget.set_overview(None, None, None)
            return

        try:
            self._refresh_device_detail_and_get_text(active_serial)
        except Exception as exc:  # pragma: no cover - defensive safeguard
            logger.error('Failed to refresh overview for %s: %s', active_serial, exc)
            self.show_error('Refresh Failed', str(exc))
            return

        self.update_device_overview()

    def copy_active_device_overview(self) -> None:
        """Copy the current overview details to the clipboard."""
        widget = getattr(self, 'device_overview_widget', None)
        if widget is None:
            return

        detail_text = widget.get_current_detail_text()
        if not detail_text.strip():
            self.show_warning('Copy Failed', 'No device details available to copy.')
            return

        active_serial = widget.get_active_serial()
        device_model = widget.get_active_model() or 'Unknown Device'
        self._copy_device_detail_text(active_serial or 'Unknown Serial', device_model, detail_text)

    def show_device_context_menu(self, position, device_serial, checkbox_widget):
        """Delegate context menu handling to the device actions controller."""
        self.device_actions_facade.show_context_menu(position, device_serial, checkbox_widget)

    def select_only_device(self, target_serial):
        """Expose device selection through the controller."""
        self._execute_with_operation_logging(
            f'Select Only Device {target_serial}',
            lambda: self.device_actions_facade.select_only_device(target_serial),
        )

    def deselect_device(self, target_serial):
        """Expose deselection through the controller."""
        self._execute_with_operation_logging(
            f'Deselect Device {target_serial}',
            lambda: self.device_actions_facade.deselect_device(target_serial),
        )

    def launch_ui_inspector_for_device(self, device_serial):
        self._execute_with_operation_logging(
            f'Launch UI Inspector ({device_serial})',
            lambda: self.device_actions_facade.launch_ui_inspector_for_device(device_serial),
        )

    def reboot_single_device(self, device_serial):
        self._execute_with_operation_logging(
            f'Reboot Device ({device_serial})',
            lambda: self.device_actions_facade.reboot_single_device(device_serial),
        )

    def take_screenshot_single_device(self, device_serial):
        self._execute_with_operation_logging(
            f'Take Screenshot ({device_serial})',
            lambda: self.device_actions_facade.take_screenshot_single_device(device_serial),
        )

    def launch_scrcpy_single_device(self, device_serial):
        self._execute_with_operation_logging(
            f'Launch scrcpy ({device_serial})',
            lambda: self.device_actions_facade.launch_scrcpy_single_device(device_serial),
        )

    def filter_and_sort_devices(self):
        """Delegate filtering to the device list controller."""
        self.device_list_controller.filter_and_sort_devices()

    def on_search_changed(self, text: str):
        """Handle search text change."""
        self.device_search_manager.set_search_text(text.strip())
        self.filter_and_sort_devices()

    def on_sort_changed(self, sort_mode: str):
        """Handle sort mode change."""
        self.device_search_manager.set_sort_mode(sort_mode)
        self.filter_and_sort_devices()

    def show_device_details(self, device_serial: str) -> None:
        device = self.device_dict.get(device_serial)
        if device is None:
            self.show_error('Device Not Available', f'Device {device_serial} is no longer connected.')
            return

        detail_text = self.device_list_controller.get_device_detail_text(device, device_serial)
        dialog = DeviceDetailDialog(
            self,
            device,
            detail_text,
            lambda: self._refresh_device_detail_and_get_text(device_serial),
            lambda text: self._copy_device_detail_text(device_serial, device.device_model, text),
        )
        dialog.exec()

    def copy_single_device_info(self, device_serial):
        self.device_actions_facade.copy_single_device_info(device_serial)

    def _copy_device_detail_text(self, device_serial: str, device_model: str, detail_text: str) -> None:
        try:
            clipboard = QGuiApplication.clipboard()
            clipboard.setText(detail_text)
            self.show_info('📋 Copied!', f'Device details copied to clipboard for:\n{device_model}')
            logger.info('Copied device details for %s', device_serial)
        except Exception as exc:  # pragma: no cover - defensive UI path
            logger.error('Failed to copy device details for %s: %s', device_serial, exc)
            self.show_error('Error', f'Could not copy device details:\n{exc}')

    def _refresh_device_detail_and_get_text(self, device_serial: str) -> str:
        device = self.device_dict.get(device_serial)
        if not device:
            raise RuntimeError(f'Device {device_serial} is no longer connected')

        detail_info = adb_tools.get_device_detailed_info(device_serial)

        wifi_status = detail_info.get('wifi_status')
        if wifi_status is not None:
            try:
                device.wifi_is_on = bool(int(wifi_status))
            except (ValueError, TypeError):
                device.wifi_is_on = bool(wifi_status)

        bt_status = detail_info.get('bluetooth_status')
        if bt_status is not None:
            try:
                device.bt_is_on = bool(int(bt_status))
            except (ValueError, TypeError):
                device.bt_is_on = bool(bt_status)

        android_ver = detail_info.get('android_version')
        if android_ver and android_ver != 'Unknown':
            device.android_ver = android_ver

        android_api = detail_info.get('android_api_level')
        if android_api and android_api != 'Unknown':
            device.android_api_level = android_api

        gms_version = detail_info.get('gms_version')
        if gms_version and gms_version != 'Unknown':
            device.gms_version = gms_version

        build_fp = detail_info.get('build_fingerprint')
        if build_fp and build_fp != 'Unknown':
            device.build_fingerprint = build_fp

        audio_state = detail_info.get('audio_state')
        if audio_state:
            device.audio_state = audio_state

        bt_manager_state = detail_info.get('bluetooth_manager_state')
        if bt_manager_state:
            device.bluetooth_manager_state = bt_manager_state

        # Refresh battery/additional info cache so detail view stays fresh
        additional_info = {}
        try:
            additional_info = adb_tools.get_additional_device_info(device_serial)
        finally:
            battery_cache = getattr(self, 'battery_info_manager', None)
            if battery_cache is not None and additional_info:
                battery_cache.update_cache(device_serial, additional_info)

        self.device_dict[device_serial] = device
        self.device_manager.device_dict[device_serial] = device
        self.device_manager.update_device_list(self.device_dict)

        detail_text = self.device_list_controller.get_device_detail_text(device, device_serial)

        widget = getattr(self, 'device_overview_widget', None)
        if widget is not None and widget.get_active_serial() == device_serial:
            condensed_text = self.device_list_controller.get_device_detail_text(
                device,
                device_serial,
                include_additional=False,
                include_identity=False,
                include_connectivity=False,
                include_status=True,
            )
            widget.set_overview(device, device_serial, condensed_text)

        return detail_text

    def browse_output_path(self):
        """Browse for unified output directory used by screenshots/recordings."""
        if hasattr(self, 'output_path_manager'):
            self.output_path_manager.browse_primary_output_path()
            return

        directory = self.file_dialog_manager.select_directory(self, 'Select Output Directory')
        if directory:
            normalized_path = common.make_gen_dir_path(directory)
            self.output_path_edit.setText(normalized_path)
            current_file_gen = self.file_gen_output_path_edit.text().strip()
            if not current_file_gen:
                self.file_gen_output_path_edit.setText(normalized_path)

    def browse_file_generation_output_path(self):
        """Browse and select file generation output directory."""
        if hasattr(self, 'output_path_manager'):
            path = self.output_path_manager.browse_file_generation_output_path()
            if path:
                logger.info(f'Selected file generation output directory: {path}')
            return

        directory = self.file_dialog_manager.select_directory(self, 'Select File Generation Output Directory')
        if directory:
            normalized_path = common.make_gen_dir_path(directory)
            self.file_gen_output_path_edit.setText(normalized_path)
            logger.info(f'Selected file generation output directory: {normalized_path}')

    def _ensure_output_path_initialized(self) -> str:
        """Make sure we have a usable primary output path."""
        if hasattr(self, 'output_path_manager'):
            return self.output_path_manager.ensure_primary_output_path()

        path = self.output_path_edit.text().strip()
        if path:
            return path

        fallback = self.file_gen_output_path_edit.text().strip()
        if fallback:
            self.output_path_edit.setText(fallback)
            if not self.file_gen_output_path_edit.text().strip():
                self.file_gen_output_path_edit.setText(fallback)
            return fallback

        default_dir = common.make_gen_dir_path(PathConstants.DEFAULT_OUTPUT_DIR)
        self.output_path_edit.setText(default_dir)
        if not self.file_gen_output_path_edit.text().strip():
            self.file_gen_output_path_edit.setText(default_dir)
        return default_dir

    def get_primary_output_path(self) -> str:
        """Return the current effective output path used for screenshots/recordings."""
        if hasattr(self, 'output_path_manager'):
            return self.output_path_manager.get_primary_output_path()
        return self._ensure_output_path_initialized()


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

    def _register_background_handle(self, handle: TaskHandle) -> None:
        """Track TaskHandle lifetimes to prevent premature GC."""

        self._background_task_handles.append(handle)

        def _cleanup() -> None:
            try:
                self._background_task_handles.remove(handle)
            except ValueError:
                pass

        handle.finished.connect(_cleanup)

    def _run_adb_tool_on_selected_devices(
        self,
        tool_func,
        description: str,
        *args,
        show_progress: bool = True,
        refresh_mode: str = 'full',
        **kwargs,
    ):
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
        self.device_list_controller.update_device_list(self.device_dict)

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
                self.finalize_operation_requested.emit(list(serials), refresh_mode)

        self.run_in_thread(wrapper)

    def _clear_device_operations(self, serials: Iterable[str]) -> None:
        """Clear operation status for specified devices."""
        for serial in serials:
            self.device_operations.pop(serial, None)

    def _finalize_operation(self, serials: List[str], refresh_mode: str) -> None:
        """Finalize long-running ADB operations with appropriate UI updates."""
        self._clear_device_operations(serials)

        if refresh_mode == 'full':
            self.device_manager.force_refresh()
            return

        if refresh_mode == 'connectivity':
            updated = self._refresh_connectivity_info(serials)
            self.battery_info_manager.refresh_serials(serials)
            if updated:
                self._refresh_device_list_snapshot()
                return

        self._refresh_device_list_snapshot()

    def _refresh_device_list_snapshot(self) -> None:
        """Force a fresh device list update to clear stale operation messages."""
        snapshot = {serial: device for serial, device in self.device_dict.items()}
        self.device_list_controller.update_device_list(snapshot)
        self.device_dict = snapshot
        self.device_list_controller.filter_and_sort_devices()

    def _refresh_connectivity_info(self, serials: Iterable[str]) -> bool:
        """Refresh Bluetooth/WiFi status for a subset of devices without full scan."""
        updated = False
        for serial in serials:
            if serial not in self.device_dict:
                continue
            try:
                bt_on = adb_tools.check_bluetooth_is_on(serial)
                self.device_dict[serial].bt_is_on = bt_on
                updated = True
            except Exception as exc:  # pragma: no cover - defensive logging
                logger.debug('Failed to refresh connectivity for %s: %s', serial, exc)
        if updated:
            self.device_list_controller.update_device_list(self.device_dict)
        return updated

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
        self.recording_controller.start_screen_record()

    def _start_screen_record_task(
        self,
        devices: List[adb_models.DeviceInfo],
        *,
        output_path: str,
        completion_callback: Optional[Callable] = None,
        progress_callback: Optional[Callable] = None,
        task_handle: Optional[TaskHandle] = None,
    ) -> Dict[str, Any]:
        return self.recording_controller._start_screen_record_task(
            devices,
            output_path=output_path,
            completion_callback=completion_callback,
            progress_callback=progress_callback,
            task_handle=task_handle,
        )

    def _on_start_screen_record_task_completed(
        self,
        payload: Dict[str, Any],
        devices: List[adb_models.DeviceInfo],
        output_path: str,
    ) -> None:
        self.recording_controller._on_start_screen_record_task_completed(payload, devices, output_path)

    def _on_start_screen_record_task_failed(self, exc: Exception) -> None:
        self.recording_controller._on_start_screen_record_task_failed(exc)

    def _enqueue_stop_screen_record(self, serials: Optional[List[str]]) -> None:
        self.recording_controller.enqueue_stop(serials)

    def _stop_screen_record_task(
        self,
        serials: Optional[Iterable[str]],
        *,
        task_handle: Optional[TaskHandle] = None,
    ) -> Dict[str, Any]:
        return self.recording_controller._stop_screen_record_task(serials, task_handle=task_handle)

    def _on_stop_screen_record_task_completed(
        self,
        payload: Dict[str, Any],
        requested_serials: Optional[Iterable[str]],
    ) -> None:
        self.recording_controller._on_stop_screen_record_task_completed(payload, requested_serials)

    def _on_stop_screen_record_task_failed(self, exc: Exception) -> None:
        self.recording_controller._on_stop_screen_record_task_failed(exc)

    def _on_recording_stopped(self, device_name, device_serial, duration, filename, output_path):
        self.recording_controller.handle_recording_stopped(device_name, device_serial, duration, filename, output_path)

    def _on_recording_state_cleared(self, device_serial):
        self.recording_controller.handle_recording_state_cleared(device_serial)

    def _on_recording_progress_event(self, event_payload: RecordingProgressEvent | Dict[str, Any]):
        self.recording_controller.handle_progress_event(event_payload)

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

        self.completion_dialog_manager.show_screenshot_summary(output_path, device_models)
        self._show_screenshot_quick_actions(output_path, device_models)

        self._update_screenshot_button_state(False)

        logger.info(f'📷 [SIGNAL] _on_screenshot_completed notification shown')
        return

    def _show_screenshot_quick_actions(self, output_path: str, device_models: List[str]) -> None:
        """Show a lightweight follow-up prompt after screenshots complete."""
        if not output_path:
            logger.debug('Screenshot quick actions skipped: empty output path')
            return

        device_summary = '\n'.join(f'• {model}' for model in device_models) if device_models else 'No device name metadata captured.'
        message = (
            f'Screenshots saved to:\n{output_path}\n\n'
            f'{device_summary}'
        )

        try:
            self.show_info('Screenshots Ready', message)
        except Exception as exc:  # pragma: no cover - UI fallback
            logger.debug('Quick actions dialog failed: %s', exc)
            self.write_to_console(f'📷 Screenshots available at {output_path}')


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
            StyleManager.apply_status_style(self.screenshot_btn, 'screenshot_processing')
        else:
            logger.info(f'🔧 [BUTTON STATE] Resetting screenshot button to default state')
            self.screenshot_btn.setText('📷 Take Screenshot')
            self.screenshot_btn.setEnabled(True)
            # Set proper default style
            StyleManager.apply_status_style(self.screenshot_btn, 'screenshot_ready')
            logger.info('📷 [BUTTON STATE] Screenshot button reset to default state successfully')

    def _on_file_generation_completed(self, operation_name, summary_text, success_metric, icon):
        """Handle file generation completed signal in main thread."""
        logger.info(f'{icon} [SIGNAL] _on_file_generation_completed executing in main thread')

        state = self.file_operations_manager.get_bug_report_progress_state()
        self._apply_progress_state_to_overlay('bug_report', state)

        self._reset_file_generation_progress()

        output_path = getattr(self.file_operations_manager, 'last_generation_output_path', '')
        summary_content = summary_text or getattr(self.file_operations_manager, 'last_generation_summary', '')

        self.completion_dialog_manager.show_file_generation_summary(
            operation_name=operation_name,
            summary_text=summary_content,
            output_path=output_path,
            success_metric=success_metric,
            icon=icon,
        )

        logger.info(f'{icon} [SIGNAL] _on_file_generation_completed dialog displayed')

        self._reset_file_generation_progress()

    def _on_file_generation_progress(self, current: int, total: int, message: str):
        """Update status bar progress for bug report generation."""
        logger.info(f'🐛 [PROGRESS] Bug report {current}/{total}: {message}')

        self.status_bar_manager.update_progress(current=current, total=total, message=message)
        state = self.file_operations_manager.get_bug_report_progress_state()
        self._apply_progress_state_to_overlay('bug_report', state)

        if total and current >= total:
            QTimer.singleShot(1500, self._reset_file_generation_progress)

    def _reset_file_generation_progress(self):
        """Hide progress indicators once generation completes."""
        self.status_bar_manager.reset_progress()

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
            state = self.app_management_manager.apk_manager.get_installation_progress_state()
            self._apply_progress_state_to_overlay('install_apk', state)

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
        try:
            state = self.app_management_manager.apk_manager.get_installation_progress_state()
            self._apply_progress_state_to_overlay('install_apk', state)
        except Exception as exc:
            logger.error(f'Error in _handle_installation_progress: {exc}')

    def _handle_installation_error(self, error_message: str):
        """處理APK安裝錯誤信號"""
        try:
            state = self.app_management_manager.apk_manager.get_installation_progress_state()
            self._apply_progress_state_to_overlay('install_apk', state)
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
        self.recording_controller.stop_screen_record()

    @ensure_devices_selected
    def enable_bluetooth(self):
        """Enable Bluetooth on selected devices."""
        def bluetooth_wrapper(serials):
            adb_tools.switch_bluetooth_enable(serials, True)
            # Trigger device list refresh to update status
            QTimer.singleShot(1000, self.device_manager.force_refresh)

        # Disable progress dialog, only show completion notification
        self._run_adb_tool_on_selected_devices(
            bluetooth_wrapper,
            'enable Bluetooth',
            show_progress=False,
            refresh_mode='connectivity',
        )

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
        self._run_adb_tool_on_selected_devices(
            bluetooth_wrapper,
            'disable Bluetooth',
            show_progress=False,
            refresh_mode='connectivity',
        )

        # Show completion notification immediately
        devices = self.get_checked_devices()
        device_count = len(devices)
        self.show_info('🔴 Disable Bluetooth Complete',
                      f'✅ Successfully disabled Bluetooth on {device_count} device(s)')

    @ensure_devices_selected
    def clear_logcat(self):
        """Clear logcat on selected devices using facade."""
        self.logcat_facade.clear_logcat_selected_devices()

    def _open_logcat_for_device(self, device: adb_models.DeviceInfo) -> None:
        """Create and show the logcat window for a device via facade."""
        self.logcat_facade._open_logcat_for_device(device)

    def show_logcat(self):
        """Show logcat viewer for the single selected device."""
        self.logcat_facade.show_logcat_for_selected()

    def view_logcat_for_device(self, device_serial: str) -> None:
        """Launch the logcat viewer for the device under the context menu pointer."""
        self.logcat_facade.view_logcat_for_device(device_serial)

    def monitor_bluetooth(self) -> None:
        """Open Bluetooth monitor for the active device selection."""
        device = self.require_single_device_selection('Bluetooth monitor')
        if device is None:
            return

        self.open_bluetooth_monitor_for_device(device.device_serial_num)

    def open_bluetooth_monitor_for_device(self, device_serial: str) -> None:
        """Open or focus the Bluetooth monitor window for a given device."""
        device = self.device_dict.get(device_serial)
        if device is None:
            self.show_error('Bluetooth Monitor', f'Device {device_serial} is no longer available.')
            return

        existing = self.bluetooth_windows.get(device_serial)
        if existing is None or not existing.isVisible():
            window = BluetoothMonitorWindow(device_serial, device, parent=self)
            window.destroyed.connect(lambda _obj=None, serial=device_serial: self.bluetooth_windows.pop(serial, None))
            self.bluetooth_windows[device_serial] = window
            existing = window

        existing.show()
        existing.raise_()
        existing.activateWindow()

    # Shell commands
    @ensure_devices_selected
    def run_shell_command(self):
        """Run shell command on selected devices using commands facade."""
        self.commands_facade.run_shell_command()

    # Enhanced command execution methods
    def add_template_command(self, command):
        """Add a template command using commands facade."""
        self.commands_facade.add_template_command(command)

    @ensure_devices_selected
    def run_single_command(self):
        """Run the currently selected/first command from batch area."""
        self.commands_facade.run_single_command()

    @ensure_devices_selected
    def run_batch_commands(self):
        """Run all commands simultaneously using commands facade."""
        self.commands_facade.run_batch_commands()


    def execute_single_command(self, command):
        """Execute a single command using commands facade."""
        self.commands_facade.execute_single_command(command)

    def log_command_results(self, command, serials, results):
        """Log command results to console with proper formatting."""
        logger.info(f'🔍 Processing results for command: {command}')

        if not results:
            logger.warning(f'❌ No results for command: {command}')
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

            if result and len(result) > 0:
                logger.info(f'📱 [{device_name}] 📋 Output ({len(result)} lines total):')

                for line_num, line in enumerate(result):
                    if line and line.strip():  # Skip empty lines
                        output_line = f'  {line.strip()}'
                        logger.info(f'📱 [{device_name}] {line_num+1:2d}▶️ {line.strip()}')

                success_msg = f'✅ [{device_name}] Completed'
                logger.info(f'📱 [{device_name}] ✅ Command completed successfully')
            else:
                error_msg = f'❌ [{device_name}] No output'
                logger.warning(f'📱 [{device_name}] ❌ No output or command failed')

        logger.info(f'🏁 Results display completed for command: {command}')
        logger.info('─' * 50)  # Separator line

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
        """Extract valid commands using commands facade."""
        return self.commands_facade.get_valid_commands()

    def add_to_history(self, command):
        """Add command to history using commands facade."""
        self.commands_facade.add_to_history(command)

    def update_history_display(self):
        """Update the history list widget using commands facade."""
        self.commands_facade.update_history_display()

    def load_from_history(self, item):
        """Load selected history item using commands facade."""
        self.commands_facade.load_from_history(item)

    def clear_command_history(self):
        """Clear command history using commands facade."""
        self.commands_facade.clear_command_history()

    def export_command_history(self):
        """Export command history using commands facade."""
        self.commands_facade.export_command_history()

    def import_command_history(self):
        """Import command history using commands facade."""
        self.commands_facade.import_command_history()

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
    def _get_file_generation_output_path(self) -> str:
        """Retrieve preferred output path for file generation workflows."""
        if hasattr(self, 'output_path_manager'):
            return self.output_path_manager.get_file_generation_output_path()

        if hasattr(self, 'file_gen_output_path_edit'):
            candidate = self.file_gen_output_path_edit.text().strip()
            if candidate:
                return candidate

        if hasattr(self, 'output_path_edit'):
            return self.output_path_edit.text().strip()

        return ''

    def _get_adb_tools_output_path(self) -> str:
        """Return the output directory configured in the ADB Tools tab."""
        if hasattr(self, 'output_path_manager'):
            return self.output_path_manager.ensure_primary_output_path()

        if hasattr(self, 'output_path_edit'):
            path = self.output_path_edit.text().strip()
            if path:
                return path
            return self._ensure_output_path_initialized()

        return ''




    def _set_device_file_status(self, message: str) -> None:
        self.device_files_facade.set_status(message)

    def refresh_device_file_browser(self, path: Optional[str] = None) -> None:
        self.device_files_facade.refresh_browser(path)

    def navigate_device_files_up(self) -> None:
        self.device_files_facade.navigate_up()

    def navigate_device_files_to_path(self) -> None:
        self.device_files_facade.navigate_to_path()

    def on_device_file_item_double_clicked(self, item: QTreeWidgetItem, column: int) -> None:
        self.device_files_facade.handle_item_double_clicked(item, column)

    def download_selected_device_files(self) -> None:
        self.device_files_facade.download_selected_files()

    def preview_selected_device_file(self, item: Optional[QTreeWidgetItem] = None) -> None:
        self.device_files_facade.preview_selected_file(item)

    def display_device_file_preview(self, local_path: str) -> None:
        self.device_files_facade.display_preview(local_path)

    def clear_device_file_preview(self) -> None:
        self.device_files_facade.clear_preview()

    def hide_preview_loading(self) -> None:
        self.device_files_facade.hide_preview_loading()

    def copy_device_file_path(self, item: Optional[QTreeWidgetItem] = None) -> None:
        self.device_files_facade.copy_path(item)

    def download_device_file_item(self, item: Optional[QTreeWidgetItem] = None) -> None:
        self.device_files_facade.download_item(item)

    def on_device_file_context_menu(self, position: QPoint) -> None:
        self.device_files_facade.show_context_menu(position)

    def ensure_preview_window(self) -> DeviceFilePreviewWindow:
        return self.device_files_facade.ensure_preview_window()

    def clear_preview_cache(self) -> None:
        self.device_files_facade.clear_preview_cache()

    def open_preview_externally(self) -> None:
        self.device_files_facade.open_preview_externally()

    def _handle_preview_cleanup(self, local_path: str) -> None:
        self.device_files_facade.handle_preview_cleanup(local_path)

    @ensure_devices_selected
    def generate_android_bug_report(self):
        """Generate Android bug report using file operations manager."""
        devices = self.get_checked_devices()
        output_path = self._get_adb_tools_output_path()
        if not output_path:
            return

        operation = 'Generate Android Bug Report'

        def handle_complete(summary: str | None = None) -> None:
            self._log_operation_complete(operation, summary or '')
            state = self.file_operations_manager.get_bug_report_progress_state()
            self._apply_progress_state_to_overlay('bug_report', state)

        def handle_failure(message: str | None = None) -> None:
            self._log_operation_failure(operation, message or 'Generation failed')
            state = self.file_operations_manager.get_bug_report_progress_state()
            self._apply_progress_state_to_overlay('bug_report', state)

        active_serials = set(self.file_operations_manager.get_active_bug_report_devices())
        current_serials = {device.device_serial_num for device in devices}
        if self.file_operations_manager.is_bug_report_in_progress() and active_serials & current_serials:
            overlapping = ', '.join(sorted(active_serials & current_serials)) or 'Unknown'
            self.show_warning(
                'Bug Report In Progress',
                'Bug report generation is already running for the following devices.\n\n'
                f'{overlapping}\n\nPlease wait for the existing run to finish or deselect these devices.'
            )
            handle_failure('Devices already generating bug report')
            return

        self._log_operation_start(operation)

        started = self.file_operations_manager.generate_android_bug_report(
            devices,
            output_path,
            on_complete=handle_complete,
            on_failure=handle_failure,
        )

        if not started:
            # Failure callback will be scheduled by file operations manager; no further action.
            return

        state = self.file_operations_manager.get_bug_report_progress_state()
        self._apply_progress_state_to_overlay('bug_report', state)

    @ensure_devices_selected
    def generate_device_discovery_file(self):
        """Generate device discovery file using file operations manager."""
        def action():
            devices = self.get_checked_devices()
            output_path = self._get_adb_tools_output_path()
            self.file_operations_manager.generate_device_discovery_file(devices, output_path)

        self._execute_with_operation_logging('Generate Device Discovery File', action)

    @ensure_devices_selected
    def pull_device_dcim_with_folder(self):
        """Pull DCIM folder from devices using file operations manager."""
        def action():
            devices = self.get_checked_devices()
            output_path = self._get_adb_tools_output_path()
            self.file_operations_manager.pull_device_dcim_folder(devices, output_path)

        self._execute_with_operation_logging('Pull Device DCIM Folder', action)

    @ensure_devices_selected
    def dump_device_hsv(self):
        """Dump device UI hierarchy using UI hierarchy manager."""
        def action():
            output_path = self._get_adb_tools_output_path()
            self.ui_hierarchy_manager.export_hierarchy(output_path)

        self._execute_with_operation_logging('Export Device UI Hierarchy', action)

    def launch_ui_inspector(self):
        """Launch the interactive UI Inspector for selected devices."""
        device = self.require_single_device_selection('UI Inspector')
        if device is None:
            return

        operation = f'Launch UI Inspector ({device.device_serial_num})'
        self._log_operation_start(operation, device.device_model)
        ready, issue_message = check_ui_inspector_prerequisites()
        if not ready:
            sanitized = ' | '.join(issue_message.splitlines())
            logger.warning('UI Inspector prerequisites failed: %s', sanitized)
            self.show_error('UI Inspector Unavailable', issue_message)
            self._log_operation_failure(operation, issue_message)
            return

        serial = device.device_serial_num
        model = device.device_model

        logger.info(f'Launching UI Inspector for device: {model} ({serial})')

        # Create and show UI Inspector window (non-modal)
        try:
            ui_inspector = UIInspectorDialog(self, serial, model)
            ui_inspector.show()
        except Exception as exc:
            self._log_operation_failure(operation, str(exc))
            raise
        else:
            self._log_operation_complete(operation, model)

    def show_about_dialog(self):
        """Show about dialog."""
        QMessageBox.about(
            self,
            'About lazy blacktea',
            'lazy blacktea - PyQt6 Version\n\n'
            'A GUI application for simplifying Android ADB and automation tasks.\n\n'
            'Converted from Tkinter to PyQt6 for enhanced user experience.'
        )

    def load_config(self, config: Optional[AppConfig] = None):
        """Load configuration from file using ConfigManager."""
        try:
            if config is None:
                config = self.config_manager.load_config()

            self.logcat_settings = config.logcat

            # Load output path from old config format for compatibility
            old_config = json_utils.read_config_json()
            if hasattr(self, 'output_path_manager'):
                self.output_path_manager.apply_legacy_paths(
                    old_config.get('output_path'),
                    old_config.get('file_gen_output_path', ''),
                )
            else:
                if old_config.get('output_path'):
                    self.output_path_edit.setText(old_config['output_path'])

                file_gen_path = old_config.get('file_gen_output_path', '').strip()
                if file_gen_path:
                    self.file_gen_output_path_edit.setText(file_gen_path)
                else:
                    main_output_path = old_config.get('output_path', '')
                    if main_output_path:
                        self.file_gen_output_path_edit.setText(main_output_path)

            # Load refresh interval from new config (set minimum 5 seconds for packaged apps)
            self.set_refresh_interval(max(5, config.device.refresh_interval))

            # Load UI scale from new config
            self.set_ui_scale(config.ui.ui_scale)

            # Apply console visibility preference
            self.set_console_panel_visibility(config.ui.show_console_panel, persist=False)

            # Load device groups from old config for compatibility
            if old_config.get('device_groups'):
                self.device_groups = old_config['device_groups']

            # Load command history from new config
            if hasattr(self, 'command_history_manager'):
                self.command_history_manager.set_history(config.command_history or [], persist=False)

            logger.info('Configuration loaded successfully')
        except Exception as e:
            logger.warning(f'Could not load config: {e}')
            self.error_handler.handle_error(ErrorCode.CONFIG_LOAD_FAILED, str(e))

    def register_theme_actions(self, actions: Dict[str, QAction]) -> None:
        """Register menu actions used for theme selection."""
        self.theme_actions = actions
        self._update_theme_actions()

    def _update_theme_actions(self) -> None:
        """Ensure theme menu reflects the currently active theme."""
        current = getattr(self, '_current_theme', 'light')
        for key, action in getattr(self, 'theme_actions', {}).items():
            action.setChecked(key == current)

    def handle_theme_selection(self, theme_key: str) -> None:
        """Handle menu-triggered theme selection."""
        self.apply_theme(theme_key, persist=True)

    def apply_theme(self, theme_name: str, persist: bool = False, initial: bool = False) -> None:
        """Apply the requested theme and refresh themed widgets."""
        resolved = self.theme_manager.set_theme(theme_name)
        self._current_theme = resolved

        StyleManager.apply_global_stylesheet(self)
        StyleManager.reapply_theme(self)

        if not initial:
            self._update_theme_actions()

        if persist:
            self.config_manager.update_ui_settings(theme=resolved)

    def save_config(self):
        """Save configuration to file using ConfigManager."""
        try:
            # Update the new config manager
            geometry = self.geometry()
            ui_payload = {
                'window_width': geometry.width(),
                'window_height': geometry.height(),
                'window_x': geometry.x(),
                'window_y': geometry.y(),
                'show_console_panel': self.show_console_panel,
            }
            if hasattr(self, 'user_scale'):
                ui_payload['ui_scale'] = self.user_scale
            self.config_manager.update_ui_settings(**ui_payload)
            self.config_manager.update_device_settings(refresh_interval=self.refresh_interval)

            # Save command history to new config
            if hasattr(self, 'command_history_manager'):
                config = self.config_manager.load_config()
                config.command_history = list(self.command_history_manager.command_history)
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

    def persist_logcat_settings(self, settings: Dict[str, int]) -> None:
        """Persist logcat performance settings through the config manager."""
        if not isinstance(settings, dict):
            return

        if self.logcat_settings is None:
            self.logcat_settings = LogcatSettings()

        update_payload: Dict[str, int] = {}
        for field in ['max_lines', 'history_multiplier', 'update_interval_ms', 'max_lines_per_update', 'max_buffer_size']:
            if field in settings:
                try:
                    value = int(settings[field])
                except (TypeError, ValueError):
                    logger.debug('Ignoring invalid logcat setting for %s: %s', field, settings[field])
                    continue
                setattr(self.logcat_settings, field, value)
                update_payload[field] = value

        if not update_payload:
            return

        try:
            self.config_manager.update_logcat_settings(**update_payload)
            logger.info('Logcat performance settings persisted: %s', update_payload)
        except Exception as exc:
            logger.error('Failed to persist logcat settings: %s', exc)

    def closeEvent(self, event):
        """Handle window close event with immediate response."""
        # Hide window immediately for better user experience
        self.hide()

        # Process any pending events to ensure UI updates
        QApplication.processEvents()

        # Optional: show a brief closing indicator while shutting down
        closing_dialog = None
        try:
            from config.constants import ApplicationConstants as _AC
            if getattr(_AC, 'SHOW_CLOSING_INDICATOR', True):
                closing_dialog = QProgressDialog('Closing Lazy Blacktea...','', 0, 0, self)
                closing_dialog.setWindowTitle('Closing')
                closing_dialog.setWindowModality(Qt.WindowModality.ApplicationModal)
                closing_dialog.setMinimumDuration(0)
                closing_dialog.setAutoClose(False)
                closing_dialog.setAutoReset(False)
                closing_dialog.setCancelButton(None)
                closing_dialog.show()
                QApplication.processEvents()
        except Exception:
            closing_dialog = None

        self.save_config()

        # Clean up timers to prevent memory leaks
        if hasattr(self, 'recording_timer'):
            self.recording_timer.stop()
        if hasattr(self, 'battery_info_manager'):
            self.battery_info_manager.stop()

        # Cancel background task handles to avoid late UI callbacks
        try:
            for handle in list(getattr(self, '_background_task_handles', [])):
                try:
                    handle.cancel()
                except Exception:
                    pass
        except Exception:
            pass

        # Clean up new modular components
        if hasattr(self, 'device_manager'):
            self.device_manager.cleanup()

        if hasattr(self, 'recording_manager'):
            # Stop any active recordings
            self.recording_manager.stop_recording()

        if hasattr(self, 'device_file_controller'):
            self.device_file_controller.shutdown()

        # Attempt to shutdown task dispatcher (bounded wait)
        try:
            if hasattr(self, '_task_dispatcher') and self._task_dispatcher is not None:
                from config.constants import ApplicationConstants as _AC
                timeout_ms = int(getattr(_AC, 'SHUTDOWN_TIMEOUT_MS', 700) or 0)
                if timeout_ms > 0:
                    self._task_dispatcher.shutdown(timeout_ms=timeout_ms)
        except Exception:
            pass

        # Dismiss closing indicator
        try:
            if closing_dialog is not None:
                closing_dialog.close()
                QApplication.processEvents()
        except Exception:
            pass

        logger.info('Application shutdown complete')
        event.accept()

    def _on_device_found_from_manager(self, serial: str, device_info):
        """處理從DeviceManager發來的新設備發現事件"""
        logger.info(f'Device found from manager: {serial} - {device_info.device_model}')
        # 更新設備字典
        self.device_dict[serial] = device_info
        # 觸發完整的UI更新（包括複選框）
        self.update_device_list(self.device_dict)
        self.battery_info_manager.refresh_serials([serial])

    def _on_device_lost_from_manager(self, serial: str):
        """處理從DeviceManager發來的設備丟失事件"""
        logger.info(f'Device lost from manager: {serial}')
        # 從設備字典中移除
        if serial in self.device_dict:
            del self.device_dict[serial]
        # 觸發完整的UI更新
        self.update_device_list(self.device_dict)
        self.battery_info_manager.remove(serial)

    def _on_device_status_updated(self, status: str):
        """處理從DeviceManager發來的狀態更新事件"""
        self.status_bar_manager.show_message(status, 2000)
