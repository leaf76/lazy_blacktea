"""UI panels manager for organizing different UI components."""

from typing import Dict, Optional
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QTabWidget,
    QPushButton, QLabel, QGroupBox, QScrollArea, QTextEdit,
    QCheckBox, QLineEdit, QProgressBar, QApplication,
    QTreeWidget, QStackedWidget, QSizePolicy, QToolButton, QMenu
)
from PyQt6.QtCore import Qt, pyqtSignal, QObject
from PyQt6.QtGui import QFont, QAction, QActionGroup

from utils import common
from ui.style_manager import PanelButtonVariant, StyleManager
from ui.device_table_widget import DeviceTableWidget
from ui.components.filter_bar import FilterBar
from ui.components.expandable_device_list import ExpandableDeviceList


class PanelsManager(QObject):
    """Manages creation and layout of UI panels."""

    # Signals for panel interactions
    screenshot_requested = pyqtSignal()
    recording_start_requested = pyqtSignal()
    recording_stop_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        self.logger = common.get_logger('panels_manager')
        self._default_button_height = 38

    def _style_button(self, button: QPushButton, variant: PanelButtonVariant = PanelButtonVariant.SECONDARY,
                      height: Optional[int] = None, min_width: Optional[int] = None) -> None:
        """Apply unified styling to buttons across panels."""
        final_height = height or self._default_button_height
        StyleManager.apply_panel_button_style(
            button,
            variant,
            fixed_height=final_height,
            min_width=min_width,
        )

    def create_screenshot_panel(self) -> QWidget:
        """Create screenshot panel with controls."""
        panel = QGroupBox("📷 Screenshot")
        layout = QVBoxLayout(panel)

        # Screenshot button
        screenshot_btn = QPushButton("📷 Take Screenshot")
        self._style_button(screenshot_btn, PanelButtonVariant.PRIMARY, height=44, min_width=180)
        screenshot_btn.clicked.connect(self.screenshot_requested.emit)
        layout.addWidget(screenshot_btn)

        # Output path
        path_layout = QHBoxLayout()
        path_layout.addWidget(QLabel("Output:"))

        path_edit = QLineEdit()
        path_edit.setPlaceholderText("Select output directory...")
        path_layout.addWidget(path_edit)

        browse_btn = QPushButton("Browse")
        self._style_button(browse_btn, PanelButtonVariant.NEUTRAL, height=34, min_width=90)
        browse_btn.clicked.connect(lambda: self._browse_folder(path_edit))
        path_layout.addWidget(browse_btn)

        layout.addLayout(path_layout)

        return panel

    def create_recording_panel(self) -> QWidget:
        """Create screen recording panel with controls."""
        panel = QGroupBox("🎬 Screen Recording")
        layout = QVBoxLayout(panel)

        # Recording buttons
        button_layout = QHBoxLayout()

        start_btn = QPushButton("🔴 Start Recording")
        self._style_button(start_btn, PanelButtonVariant.PRIMARY, height=44, min_width=180)
        start_btn.clicked.connect(self.recording_start_requested.emit)
        button_layout.addWidget(start_btn)

        stop_btn = QPushButton("⏹️ Stop Recording")
        self._style_button(stop_btn, PanelButtonVariant.SECONDARY, height=44, min_width=160)
        stop_btn.clicked.connect(self.recording_stop_requested.emit)
        button_layout.addWidget(stop_btn)

        layout.addLayout(button_layout)

        # Recording status
        status_label = QLabel("No active recordings")
        StyleManager.apply_hint_label(status_label)
        layout.addWidget(status_label)

        # Recording timer
        timer_label = QLabel("")
        timer_label.setWordWrap(True)
        timer_label.setMaximumHeight(100)
        layout.addWidget(timer_label)

        return panel

    def create_tools_tabs(self, parent_widget) -> QTabWidget:
        """Create tools tab widget with all tool panels."""
        tab_widget = QTabWidget()

        # ADB Tools tab
        adb_tab = self._create_adb_tools_tab()
        tab_widget.addTab(adb_tab, 'ADB Tools')

        # Shell Commands tab
        shell_tab = self._create_shell_commands_tab()
        tab_widget.addTab(shell_tab, 'Shell Commands')

        # Device Files tab
        files_tab = self._create_device_file_browser_tab()
        tab_widget.addTab(files_tab, 'Device Files')

        # Device Groups tab
        groups_tab = self._create_device_groups_tab()
        tab_widget.addTab(groups_tab, 'Device Groups')

        return tab_widget

    def _create_adb_tools_tab(self) -> QWidget:
        """Create ADB tools tab content."""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # Create tool sections
        sections = [
            ("📱 Device Control", [
                ("🔌 Reboot Device", "reboot"),
                ("🔌 Reboot to Recovery", "reboot_recovery"),
                ("🔌 Reboot to Bootloader", "reboot_bootloader"),
                ("🔄 Restart ADB", "restart_adb")
            ]),
            ("📶 Connectivity", [
                ("📶 Enable WiFi", "enable_wifi"),
                ("📶 Disable WiFi", "disable_wifi"),
                ("🔵 Enable Bluetooth", "enable_bluetooth"),
                ("🔵 Disable Bluetooth", "disable_bluetooth")
            ]),
            ("🔧 System Tools", [
                ("ℹ️ Device Info", "device_info"),
                ("🏠 Go Home", "go_home")
            ])
        ]

        for section_name, buttons in sections:
            group = QGroupBox(section_name)
            group_layout = QGridLayout(group)

            for i, (button_text, action) in enumerate(buttons):
                btn = QPushButton(button_text)
                btn.setObjectName(action)  # For identification
                self._style_button(btn, PanelButtonVariant.SECONDARY, height=36, min_width=160)
                row, col = divmod(i, 2)
                group_layout.addWidget(btn, row, col)

            layout.addWidget(group)

        layout.addStretch()
        return tab

    def _create_shell_commands_tab(self) -> QWidget:
        """Create shell commands tab content."""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # Command input section
        input_group = QGroupBox("📝 Command Input")
        input_layout = QVBoxLayout(input_group)

        command_edit = QTextEdit()
        command_edit.setPlaceholderText("Enter ADB shell commands here...\nExample: pm list packages")
        command_edit.setMaximumHeight(100)
        input_layout.addWidget(command_edit)

        button_layout = QHBoxLayout()

        run_btn = QPushButton("▶️ Run Command")
        self._style_button(run_btn, PanelButtonVariant.PRIMARY, height=36, min_width=160)
        button_layout.addWidget(run_btn)

        run_all_btn = QPushButton("⚡ Run All Commands")
        self._style_button(run_all_btn, PanelButtonVariant.SECONDARY, height=36, min_width=180)
        button_layout.addWidget(run_all_btn)

        clear_btn = QPushButton("🗑️ Clear")
        self._style_button(clear_btn, PanelButtonVariant.NEUTRAL, height=34, min_width=120)
        clear_btn.clicked.connect(command_edit.clear)
        button_layout.addWidget(clear_btn)

        input_layout.addLayout(button_layout)
        layout.addWidget(input_group)

        # Command history section
        history_group = QGroupBox("📚 Command History")
        history_layout = QVBoxLayout(history_group)

        history_list = QScrollArea()
        history_list.setMaximumHeight(150)
        history_layout.addWidget(history_list)

        layout.addWidget(history_group)

        layout.addStretch()
        return tab

    def _create_device_file_browser_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)

        info_label = QLabel('Select a device to browse its files.')
        layout.addWidget(info_label)

        path_layout = QHBoxLayout()
        path_edit = QLineEdit()
        path_edit.setPlaceholderText('/sdcard')
        path_layout.addWidget(path_edit)

        refresh_btn = QPushButton('Refresh')
        self._style_button(refresh_btn, PanelButtonVariant.SECONDARY, height=34, min_width=120)
        path_layout.addWidget(refresh_btn)

        layout.addLayout(path_layout)

        tree = QTreeWidget()
        tree.setHeaderLabels(['Name', 'Type'])
        tree.setRootIsDecorated(False)
        tree.setColumnWidth(0, 320)
        tree.setMinimumHeight(260)
        layout.addWidget(tree)

        output_layout = QHBoxLayout()
        output_path_edit = QLineEdit()
        output_path_edit.setPlaceholderText('Select download destination...')
        output_layout.addWidget(output_path_edit)

        browse_btn = QPushButton('Browse')
        self._style_button(browse_btn, PanelButtonVariant.NEUTRAL, height=34, min_width=120)
        output_layout.addWidget(browse_btn)

        download_btn = QPushButton('Download Selected')
        self._style_button(download_btn, PanelButtonVariant.PRIMARY, height=36, min_width=180)
        output_layout.addWidget(download_btn)

        layout.addLayout(output_layout)
        layout.addStretch()
        return tab

    def _create_device_groups_tab(self) -> QWidget:
        """Create device groups management tab."""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # Groups management
        groups_group = QGroupBox("👥 Device Groups")
        groups_layout = QVBoxLayout(groups_group)

        # Group list
        groups_scroll = QScrollArea()
        groups_scroll.setMaximumHeight(200)
        groups_layout.addWidget(groups_scroll)

        # Group controls
        controls_layout = QHBoxLayout()

        new_group_btn = QPushButton("➕ New Group")
        self._style_button(new_group_btn, PanelButtonVariant.PRIMARY, height=34, min_width=150)
        controls_layout.addWidget(new_group_btn)

        edit_group_btn = QPushButton("✏️ Edit Group")
        self._style_button(edit_group_btn, PanelButtonVariant.SECONDARY, height=34, min_width=150)
        controls_layout.addWidget(edit_group_btn)

        delete_group_btn = QPushButton("🗑️ Delete Group")
        self._style_button(delete_group_btn, PanelButtonVariant.DANGER, height=34, min_width=150)
        controls_layout.addWidget(delete_group_btn)

        groups_layout.addLayout(controls_layout)
        layout.addWidget(groups_group)

        layout.addStretch()
        return tab

    def _browse_folder(self, line_edit: QLineEdit):
        """Browse for folder and set path in line edit."""
        from PyQt6.QtWidgets import QFileDialog

        folder = QFileDialog.getExistingDirectory(
            self.parent,
            "Select Output Directory",
            line_edit.text() or ""
        )

        if folder:
            line_edit.setText(folder)

    def create_console_panel(self, parent_layout) -> QTextEdit:
        """Create console output panel."""
        console_group = QGroupBox("📟 Console Output")
        console_layout = QVBoxLayout(console_group)

        # Console text area
        console_text = QTextEdit()
        console_text.setReadOnly(True)
        # Allow console to expand - set minimum height but no maximum
        console_text.setMinimumHeight(150)
        console_text.setFont(QFont("Consolas", 9))
        # Set size policy to allow expansion
        from PyQt6.QtWidgets import QSizePolicy
        console_text.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        console_text.setStyleSheet(StyleManager.get_console_style())
        console_layout.addWidget(console_text)

        # Console controls
        controls_layout = QHBoxLayout()

        clear_btn = QPushButton("🗑️ Clear")
        self._style_button(clear_btn, PanelButtonVariant.NEUTRAL, height=32, min_width=120)
        clear_btn.clicked.connect(console_text.clear)
        controls_layout.addWidget(clear_btn)

        copy_btn = QPushButton("📋 Copy All")
        self._style_button(copy_btn, PanelButtonVariant.SECONDARY, height=32, min_width=120)
        copy_btn.clicked.connect(lambda: self._copy_console_text(console_text))
        controls_layout.addWidget(copy_btn)

        controls_layout.addStretch()
        console_layout.addLayout(controls_layout)

        parent_layout.addWidget(console_group)
        return console_text

    def _copy_console_text(self, console_text: QTextEdit):
        """Copy all console text to clipboard."""
        text = console_text.toPlainText()
        if text:
            clipboard = QApplication.clipboard()
            clipboard.setText(text)
            self.logger.info("Console text copied to clipboard")

    def create_status_bar_widgets(self) -> dict:
        """Create status bar widgets."""
        widgets = {}

        # Device count label
        widgets['device_count'] = QLabel("Devices: 0")
        widgets['device_count'].setStyleSheet("QLabel { margin: 2px 5px; }")

        # Recording status label
        widgets['recording_status'] = QLabel("No active recordings")
        StyleManager.apply_hint_label(widgets['recording_status'], margin='2px 5px')

        # Progress bar
        widgets['progress_bar'] = QProgressBar()
        widgets['progress_bar'].setVisible(False)
        widgets['progress_bar'].setMaximumWidth(200)

        return widgets

    def create_menu_bar(self, main_window):
        """Create the menu bar."""
        menubar = main_window.menuBar()

        # Prepare tracking dictionaries on main window
        main_window.refresh_interval_actions = {}

        # File menu
        file_menu = menubar.addMenu('File')
        exit_action = QAction('Exit', main_window)
        exit_action.triggered.connect(main_window.close)
        file_menu.addAction(exit_action)

        # Devices menu
        devices_menu = menubar.addMenu('Devices')

        refresh_now_action = QAction('Refresh Now', main_window)
        refresh_now_action.setShortcut('Ctrl+R')
        refresh_now_action.triggered.connect(main_window.refresh_device_list)
        devices_menu.addAction(refresh_now_action)

        auto_refresh_action = QAction('Auto Refresh Enabled', main_window, checkable=True)
        current_auto_state = True
        if hasattr(main_window, 'device_manager'):
            current_auto_state = main_window.device_manager.async_device_manager.auto_refresh_enabled
        auto_refresh_action.setChecked(current_auto_state)
        auto_refresh_action.triggered.connect(lambda checked: main_window.set_auto_refresh_enabled(checked))
        devices_menu.addAction(auto_refresh_action)
        main_window.auto_refresh_action = auto_refresh_action
        main_window._update_auto_refresh_action(current_auto_state)

        # ADB Server menu
        adb_menu = menubar.addMenu('ADB Server')
        start_server_action = QAction('Start Server', main_window)
        start_server_action.triggered.connect(main_window.adb_start_server)
        adb_menu.addAction(start_server_action)

        kill_server_action = QAction('Kill Server', main_window)
        kill_server_action.triggered.connect(main_window.adb_kill_server)
        adb_menu.addAction(kill_server_action)

        # Settings menu
        settings_menu = menubar.addMenu('Settings')

        theme_menu = settings_menu.addMenu('Theme')
        theme_group = QActionGroup(main_window)
        theme_group.setExclusive(True)
        theme_actions: Dict[str, QAction] = {}
        for title, key in [('Light', 'light'), ('Dark', 'dark')]:
            action = QAction(title, main_window, checkable=True)
            theme_group.addAction(action)
            action.triggered.connect(
                lambda checked, theme_key=key: main_window.handle_theme_selection(theme_key)
                if checked else None
            )
            theme_menu.addAction(action)
            theme_actions[key] = action

        if hasattr(main_window, 'register_theme_actions'):
            main_window.register_theme_actions(theme_actions)

        # UI Scale submenu
        scale_menu = settings_menu.addMenu('UI Scale')
        scale_group = QActionGroup(main_window)
        scale_group.setExclusive(True)
        scales = [('Default', 1.0), ('Large', 1.25), ('Extra Large', 1.5)]
        scale_actions = {}
        for name, scale in scales:
            action = QAction(name, main_window, checkable=True)
            scale_group.addAction(action)
            action.triggered.connect(lambda checked, s=scale: main_window.handle_ui_scale_selection(s))
            scale_menu.addAction(action)
            scale_actions[scale] = action

        if hasattr(main_window, 'register_ui_scale_actions'):
            main_window.register_ui_scale_actions(scale_actions)

        console_toggle_action = QAction('Show Console Output', main_window, checkable=True)
        console_toggle_action.setChecked(getattr(main_window, 'show_console_panel', True))
        console_toggle_action.triggered.connect(lambda checked: main_window.handle_console_panel_toggle(checked))
        settings_menu.addAction(console_toggle_action)

        if hasattr(main_window, 'register_console_panel_action'):
            main_window.register_console_panel_action(console_toggle_action)

        scrcpy_settings_action = QAction('scrcpy Settings...', main_window)
        if hasattr(main_window, 'open_scrcpy_settings_dialog'):
            scrcpy_settings_action.triggered.connect(main_window.open_scrcpy_settings_dialog)
        else:  # pragma: no cover - compatibility with legacy harnesses
            scrcpy_settings_action.setEnabled(False)
        settings_menu.addAction(scrcpy_settings_action)

        apk_install_settings_action = QAction('APK Install Settings...', main_window)
        if hasattr(main_window, 'open_apk_install_settings_dialog'):
            apk_install_settings_action.triggered.connect(main_window.open_apk_install_settings_dialog)
        else:  # pragma: no cover
            apk_install_settings_action.setEnabled(False)
        settings_menu.addAction(apk_install_settings_action)

        capture_settings_action = QAction('Capture Settings...', main_window)
        if hasattr(main_window, 'open_capture_settings_dialog'):
            capture_settings_action.triggered.connect(main_window.open_capture_settings_dialog)
        else:  # pragma: no cover
            capture_settings_action.setEnabled(False)
        settings_menu.addAction(capture_settings_action)

        output_settings_action = QAction('Output Directory...', main_window)
        if hasattr(main_window, 'open_output_settings_dialog'):
            output_settings_action.triggered.connect(main_window.open_output_settings_dialog)
        else:  # pragma: no cover
            output_settings_action.setEnabled(False)
        settings_menu.addAction(output_settings_action)

        # Refresh Interval submenu
        refresh_menu = settings_menu.addMenu('Refresh Interval')
        refresh_group = QActionGroup(main_window)
        refresh_group.setExclusive(True)
        intervals = [10, 20, 30, 60, 120]
        for interval in intervals:
            action = QAction(f'{interval} Seconds', main_window, checkable=True)
            refresh_group.addAction(action)
            refresh_menu.addAction(action)
            main_window.refresh_interval_actions[interval] = action
            action.triggered.connect(lambda checked, i=interval: main_window.set_refresh_interval(i))

        # Help menu
        help_menu = menubar.addMenu('Help')
        about_action = QAction('About', main_window)
        about_action.triggered.connect(main_window.show_about_dialog)
        help_menu.addAction(about_action)

        main_window._update_refresh_interval_actions(getattr(main_window, 'refresh_interval', 30))

    def create_device_panel(self, parent, main_window) -> dict:
        """Create the device list panel with modern UI design."""
        device_widget = QWidget()
        device_widget.setObjectName('device_panel')
        device_layout = QVBoxLayout(device_widget)
        device_layout.setContentsMargins(0, 0, 0, 0)
        device_layout.setSpacing(8)

        # ============================================================
        # Header area: Title + Icon buttons
        # ============================================================
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(8, 8, 8, 4)

        # Title and subtitle container
        title_container = QVBoxLayout()
        title_container.setSpacing(2)

        # Main title: "3 Devices • 2 Selected"
        title_label = QLabel('0 Devices')
        title_label.setObjectName('compact_header_title')
        title_label.setFont(QFont('Arial', 14, QFont.Weight.Bold))
        title_container.addWidget(title_label)

        # Subtitle: "Active: SM_G9860 (R5CN700...)"
        subtitle_label = QLabel('Active: None')
        subtitle_label.setObjectName('compact_header_subtitle')
        subtitle_label.setStyleSheet('color: #666666; font-size: 11px;')
        title_container.addWidget(subtitle_label)

        header_layout.addLayout(title_container)
        header_layout.addStretch()

        # Refresh icon button
        refresh_btn = QToolButton()
        refresh_btn.setText('\u21bb')  # Refresh symbol
        refresh_btn.setObjectName('header_refresh_btn')
        refresh_btn.setToolTip('Refresh device list')
        refresh_btn.setStyleSheet(StyleManager.get_icon_button_style())
        refresh_btn.clicked.connect(lambda: main_window.refresh_device_list())
        header_layout.addWidget(refresh_btn)

        # Expand/Collapse all button
        expand_btn = QToolButton()
        expand_btn.setText('\u2195')  # Up-down arrow symbol
        expand_btn.setObjectName('header_expand_btn')
        expand_btn.setToolTip('Expand/Collapse all devices')
        expand_btn.setStyleSheet(StyleManager.get_icon_button_style())
        header_layout.addWidget(expand_btn)

        # Selection menu button
        menu_btn = QToolButton()
        menu_btn.setText('\u2630')  # Menu symbol
        menu_btn.setObjectName('header_menu_btn')
        menu_btn.setToolTip('Selection options')
        menu_btn.setStyleSheet(StyleManager.get_icon_button_style())
        menu_btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)

        # Create selection menu
        selection_menu = QMenu(menu_btn)
        select_all_action = selection_menu.addAction('Select All')
        if hasattr(main_window, 'handle_select_all_action'):
            select_all_action.triggered.connect(main_window.handle_select_all_action)
        else:
            select_all_action.triggered.connect(main_window.select_all_devices)

        select_none_action = selection_menu.addAction('Select None')
        select_none_action.triggered.connect(main_window.select_no_devices)

        selection_menu.addSeparator()

        single_mode_action = selection_menu.addAction('Single Select Mode')
        single_mode_action.setCheckable(True)
        single_mode_action.setChecked(False)
        if hasattr(main_window, 'handle_selection_mode_toggle'):
            single_mode_action.toggled.connect(main_window.handle_selection_mode_toggle)

        menu_btn.setMenu(selection_menu)
        header_layout.addWidget(menu_btn)

        device_layout.addLayout(header_layout)

        # ============================================================
        # Search field
        # ============================================================
        search_container = QHBoxLayout()
        search_container.setContentsMargins(8, 0, 8, 0)

        search_field = QLineEdit()
        search_field.setPlaceholderText('Search devices...')
        search_field.setStyleSheet(StyleManager.get_search_input_style())
        search_field.textChanged.connect(lambda text: main_window.on_search_changed(text))
        search_container.addWidget(search_field)

        device_layout.addLayout(search_container)

        # ============================================================
        # Filter bar with chips
        # ============================================================
        filter_bar = FilterBar()
        if hasattr(main_window, 'on_filter_changed'):
            filter_bar.filter_changed.connect(main_window.on_filter_changed)
        device_layout.addWidget(filter_bar)

        # ============================================================
        # Device list (expandable)
        # ============================================================
        device_list = ExpandableDeviceList()
        device_list.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        # Connect signals
        # NOTE: selection_changed is handled by device_list_controller.set_device_list()
        # to avoid duplicate handling
        if hasattr(main_window, 'show_device_context_menu'):
            device_list.context_menu_requested.connect(
                lambda pos, serial: main_window.show_device_context_menu(pos, serial, device_list)
            )
        if hasattr(main_window, 'show_device_list_context_menu'):
            device_list.list_context_menu_requested.connect(main_window.show_device_list_context_menu)

        # Empty state label (hidden inside stack)
        no_devices_label = QLabel('No devices found')
        no_devices_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        no_devices_label.setWordWrap(True)
        no_devices_label.setObjectName('device_list_empty_state_label')
        no_devices_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        device_stack = QStackedWidget()
        device_stack.setObjectName('device_list_stack')
        device_stack.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        device_stack.addWidget(device_list)
        device_stack.addWidget(no_devices_label)
        device_stack.setCurrentWidget(device_list)

        device_layout.addWidget(device_stack)

        # Connect expand button to device list
        def on_expand_toggle():
            is_expanded = device_list.toggle_expand_all()
            # Update button icon: ⬇ when expanded (can collapse), ⬆ when collapsed (can expand)
            expand_btn.setText('\u2b07' if is_expanded else '\u2b06')
            expand_btn.setToolTip('Collapse all' if is_expanded else 'Expand all')

        expand_btn.clicked.connect(on_expand_toggle)

        parent.addWidget(device_widget)

        # ============================================================
        # Backward compatibility: Create hidden legacy components
        # ============================================================
        # Hidden checkbox for compatibility with existing code
        selection_mode_checkbox = QCheckBox('Single Select')
        selection_mode_checkbox.setVisible(False)
        selection_mode_checkbox.toggled.connect(single_mode_action.setChecked)
        single_mode_action.toggled.connect(selection_mode_checkbox.setChecked)

        # Hidden buttons for compatibility
        select_all_btn = QPushButton('Select All')
        select_all_btn.setVisible(False)
        select_none_btn = QPushButton('Select None')
        select_none_btn.setVisible(False)

        # Legacy table widget (for backward compatibility with controller)
        device_table = DeviceTableWidget()
        device_table.setVisible(False)

        # Hidden hint label for compatibility
        hint_label = QLabel('')
        hint_label.setVisible(False)

        # Return references to components
        return {
            # New components
            'title_label': title_label,
            'subtitle_label': subtitle_label,
            'filter_bar': filter_bar,
            'device_list': device_list,
            'search_field': search_field,
            'refresh_btn': refresh_btn,
            'expand_btn': expand_btn,
            'menu_btn': menu_btn,
            'single_mode_action': single_mode_action,
            # Legacy compatibility (some hidden)
            'device_table': device_table,
            'no_devices_label': no_devices_label,
            'device_panel_stack': device_stack,
            'selection_summary_label': subtitle_label,  # Reuse subtitle
            'selection_hint_label': hint_label,
            'selection_mode_checkbox': selection_mode_checkbox,
            'select_all_btn': select_all_btn,
            'select_none_btn': select_none_btn,
        }
