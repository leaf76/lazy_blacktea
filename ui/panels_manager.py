"""UI panels manager for organizing different UI components."""

from typing import Optional
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QTabWidget,
    QPushButton, QLabel, QGroupBox, QScrollArea, QTextEdit,
    QCheckBox, QLineEdit, QProgressBar, QApplication, QComboBox
)
from PyQt6.QtCore import Qt, pyqtSignal, QObject
from PyQt6.QtGui import QFont, QAction, QActionGroup

from utils import common


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

    def create_screenshot_panel(self) -> QWidget:
        """Create screenshot panel with controls."""
        panel = QGroupBox("📷 Screenshot")
        layout = QVBoxLayout(panel)

        # Screenshot button
        screenshot_btn = QPushButton("📷 Take Screenshot")
        screenshot_btn.setMinimumHeight(40)
        screenshot_btn.clicked.connect(self.screenshot_requested.emit)
        layout.addWidget(screenshot_btn)

        # Output path
        path_layout = QHBoxLayout()
        path_layout.addWidget(QLabel("Output:"))

        path_edit = QLineEdit()
        path_edit.setPlaceholderText("Select output directory...")
        path_layout.addWidget(path_edit)

        browse_btn = QPushButton("Browse")
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
        start_btn.setMinimumHeight(40)
        start_btn.clicked.connect(self.recording_start_requested.emit)
        button_layout.addWidget(start_btn)

        stop_btn = QPushButton("⏹️ Stop Recording")
        stop_btn.setMinimumHeight(40)
        stop_btn.clicked.connect(self.recording_stop_requested.emit)
        button_layout.addWidget(stop_btn)

        layout.addLayout(button_layout)

        # Recording status
        status_label = QLabel("No active recordings")
        status_label.setStyleSheet('color: gray; font-style: italic;')
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

        # File Generation tab
        file_tab = self._create_file_generation_tab()
        tab_widget.addTab(file_tab, 'File Generation')

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
                ("🗑️ Clear Logcat", "clear_logcat"),
                ("📊 Show Logcat", "show_logcat"),
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
        run_btn.setMinimumHeight(35)
        button_layout.addWidget(run_btn)

        run_all_btn = QPushButton("⚡ Run All Commands")
        run_all_btn.setMinimumHeight(35)
        button_layout.addWidget(run_all_btn)

        clear_btn = QPushButton("🗑️ Clear")
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

    def _create_file_generation_tab(self) -> QWidget:
        """Create file generation tab content."""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # Output path section
        path_group = QGroupBox("📁 Output Settings")
        path_layout = QHBoxLayout(path_group)

        path_layout.addWidget(QLabel("Output Directory:"))

        path_edit = QLineEdit()
        path_edit.setPlaceholderText("Select output directory...")
        path_layout.addWidget(path_edit)

        browse_btn = QPushButton("Browse")
        browse_btn.clicked.connect(lambda: self._browse_folder(path_edit))
        path_layout.addWidget(browse_btn)

        layout.addWidget(path_group)

        # Generation tools section
        tools_group = QGroupBox("🛠️ Generation Tools")
        tools_layout = QGridLayout(tools_group)

        tools = [
            ("🐛 Generate Bug Report", "bug_report"),
            ("🔍 Device Discovery File", "device_discovery"),
            ("📋 Device Info Files", "device_info_files"),
            ("📊 System Report", "system_report")
        ]

        for i, (tool_text, action) in enumerate(tools):
            btn = QPushButton(tool_text)
            btn.setObjectName(action)
            btn.setMinimumHeight(40)
            row, col = divmod(i, 2)
            tools_layout.addWidget(btn, row, col)

        layout.addWidget(tools_group)
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
        controls_layout.addWidget(new_group_btn)

        edit_group_btn = QPushButton("✏️ Edit Group")
        controls_layout.addWidget(edit_group_btn)

        delete_group_btn = QPushButton("🗑️ Delete Group")
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
        console_text.setStyleSheet("""
            QTextEdit {
                background-color: #1e1e1e;
                color: #ffffff;
                border: 1px solid #404040;
                border-radius: 4px;
            }
        """)
        console_layout.addWidget(console_text)

        # Console controls
        controls_layout = QHBoxLayout()

        clear_btn = QPushButton("🗑️ Clear")
        clear_btn.clicked.connect(console_text.clear)
        controls_layout.addWidget(clear_btn)

        copy_btn = QPushButton("📋 Copy All")
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
        widgets['recording_status'].setStyleSheet("QLabel { margin: 2px 5px; color: gray; }")

        # Progress bar
        widgets['progress_bar'] = QProgressBar()
        widgets['progress_bar'].setVisible(False)
        widgets['progress_bar'].setMaximumWidth(200)

        return widgets

    def create_menu_bar(self, main_window):
        """Create the menu bar."""
        menubar = main_window.menuBar()

        # File menu
        file_menu = menubar.addMenu('File')
        exit_action = QAction('Exit', main_window)
        exit_action.triggered.connect(main_window.close)
        file_menu.addAction(exit_action)

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

        # UI Scale submenu
        scale_menu = settings_menu.addMenu('UI Scale')
        scale_group = QActionGroup(main_window)
        scales = [('Default', 1.0), ('Large', 1.25), ('Extra Large', 1.5)]
        for name, scale in scales:
            action = QAction(name, main_window, checkable=True)
            scale_group.addAction(action)
            if scale == 1.0:
                action.setChecked(True)
            action.triggered.connect(lambda checked, s=scale: main_window.set_ui_scale(s))
            scale_menu.addAction(action)

        # Refresh Interval submenu
        refresh_menu = settings_menu.addMenu('Refresh Interval')
        refresh_group = QActionGroup(main_window)
        intervals = [5, 10, 20, 30, 60]
        for interval in intervals:
            action = QAction(f'{interval} Seconds', main_window, checkable=True)
            refresh_group.addAction(action)
            if interval == 5:  # Default to 5 seconds
                action.setChecked(True)
            action.triggered.connect(lambda checked, i=interval: main_window.set_refresh_interval(i))
            refresh_menu.addAction(action)

        # Help menu
        help_menu = menubar.addMenu('Help')
        about_action = QAction('About', main_window)
        about_action.triggered.connect(main_window.show_about_dialog)
        help_menu.addAction(about_action)

    def create_device_panel(self, parent, main_window) -> dict:
        """Create the device list panel."""
        device_widget = QWidget()
        device_layout = QVBoxLayout(device_widget)

        # Title with device count
        title_label = QLabel('Connected Devices (0)')
        title_label.setFont(QFont('Arial', 12, QFont.Weight.Bold))
        device_layout.addWidget(title_label)

        # Search and sort controls
        search_layout = QHBoxLayout()

        # Search field with icon
        search_label = QLabel('🔍')
        search_layout.addWidget(search_label)

        search_field = QLineEdit()
        search_field.setPlaceholderText('Search devices (model, serial, android 13, wifi on, selected, etc.)...')
        search_field.textChanged.connect(lambda text: main_window.on_search_changed(text))
        search_layout.addWidget(search_field)

        # Sort dropdown
        sort_label = QLabel('Sort:')
        search_layout.addWidget(sort_label)

        sort_combo = QComboBox()
        sort_combo.addItems(['Name', 'Serial', 'Status', 'Selected'])
        sort_combo.currentTextChanged.connect(lambda text: main_window.on_sort_changed(text.lower()))
        search_layout.addWidget(sort_combo)

        device_layout.addLayout(search_layout)

        # Control buttons
        control_layout = QHBoxLayout()

        refresh_btn = QPushButton('Refresh')
        refresh_btn.clicked.connect(lambda checked: main_window.refresh_device_list())
        control_layout.addWidget(refresh_btn)

        select_all_btn = QPushButton('Select All')
        select_all_btn.clicked.connect(lambda checked: main_window.select_all_devices())
        control_layout.addWidget(select_all_btn)

        select_none_btn = QPushButton('Select None')
        select_none_btn.clicked.connect(lambda checked: main_window.select_no_devices())
        control_layout.addWidget(select_none_btn)

        device_layout.addLayout(control_layout)

        # Device list scroll area
        device_scroll = QScrollArea()
        device_scroll.setWidgetResizable(True)
        device_widget_inner = QWidget()
        device_layout_inner = QVBoxLayout(device_widget_inner)
        device_scroll.setWidget(device_widget_inner)

        # Enable context menu for device list
        device_scroll.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        device_scroll.customContextMenuRequested.connect(main_window.show_device_list_context_menu)

        device_layout.addWidget(device_scroll)

        # Add stretch item at the end to push devices to top
        device_layout_inner.addStretch()

        # No devices label (will be added dynamically)
        no_devices_label = QLabel('No devices found')
        no_devices_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        parent.addWidget(device_widget)

        # Return references to components that need to be accessed by main window
        return {
            'title_label': title_label,
            'device_scroll': device_scroll,
            'device_widget': device_widget_inner,
            'device_layout': device_layout_inner,
            'no_devices_label': no_devices_label
        }