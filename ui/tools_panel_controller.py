"""Controller for building the tools panel tabs."""

from __future__ import annotations

from typing import TYPE_CHECKING, Dict, List, Optional, Tuple

from PyQt6.QtWidgets import (
    QGroupBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTabWidget,
    QTextEdit,
    QTreeWidget,
    QVBoxLayout,
    QWidget,
    QToolButton,
    QProgressBar,
    QFrame,
)
from PyQt6.QtCore import Qt, QSize

from config.constants import PanelConfig, PanelText
from ui.style_manager import LabelStyle, PanelButtonVariant, StyleManager
from ui.device_overview_widget import DeviceOverviewWidget
from ui.app_list_tab import AppListTab
from ui.tool_icon_factory import get_tile_tool_icon

if TYPE_CHECKING:  # pragma: no cover
    from lazy_blacktea_pyqt import WindowMain


class ToolsPanelController:
    """Builds the tools panel and its tabs for the main window."""

    def __init__(self, main_window: "WindowMain") -> None:
        self.window = main_window
        self._default_button_height = 38

    def _style_button(
        self,
        button: QPushButton,
        variant: PanelButtonVariant = PanelButtonVariant.SECONDARY,
        *,
        height: int | None = None,
        min_width: int | None = None,
    ) -> None:
        """Apply consistent styling to buttons inside tools panel."""
        StyleManager.apply_panel_button_style(
            button,
            variant,
            fixed_height=height or self._default_button_height,
            min_width=min_width,
        )

    def create_tools_panel(self, parent) -> None:
        """Create the tabbed tools panel and attach it to the parent widget."""
        tools_widget = QWidget()
        tools_layout = QVBoxLayout(tools_widget)

        tab_widget = QTabWidget()
        tools_layout.addWidget(tab_widget)

        # Widgets reused across tabs live on the main window instance
        self.window.output_path_edit = QLineEdit()
        self.window.file_gen_output_path_edit = QLineEdit()
        self.window.groups_listbox = QListWidget()
        self.window.group_name_edit = QLineEdit()

        self._create_device_overview_tab(tab_widget)
        self._create_adb_tools_tab(tab_widget)
        self._create_shell_commands_tab(tab_widget)
        self._create_device_file_browser_tab(tab_widget)
        self._create_device_groups_tab(tab_widget)
        self._create_apps_tab(tab_widget)

        parent.addWidget(tools_widget)

    def _create_device_overview_tab(self, tab_widget: QTabWidget) -> None:
        widget = DeviceOverviewWidget(self.window)
        self.window.device_overview_widget = widget
        tab_widget.addTab(widget, PanelText.TAB_DEVICE_OVERVIEW)

    # ------------------------------------------------------------------
    # ADB Tools Tab - Reorganized by category
    # ------------------------------------------------------------------
    def _create_adb_tools_tab(self, tab_widget: QTabWidget) -> None:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(0, 0, 0, 0)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        layout.addWidget(scroll_area)

        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(8, 8, 8, 12)
        content_layout.setSpacing(10)
        scroll_area.setWidget(content_widget)

        # Monitoring Section (single device operations)
        self._create_monitoring_section(content_layout)

        # Capture Section (batch operations)
        self._create_capture_section(content_layout)

        # Control Section (batch operations)
        self._create_control_section(content_layout)

        # Utility Section
        self._create_utility_section(content_layout)

        content_layout.addStretch(1)

        tab_widget.addTab(tab, PanelText.TAB_ADB_TOOLS)

    def _create_category_header(self, text: str, hint: str = '') -> QWidget:
        """Create a styled category header with optional hint text."""
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 4, 0, 2)
        layout.setSpacing(2)

        colors = StyleManager.COLORS
        text_hint = colors.get('text_hint', '#9DA5B3')
        panel_border = colors.get('panel_border', '#3E4455')

        header = QLabel(text.upper())
        header.setStyleSheet(f"""
            QLabel {{
                font-size: 10px;
                font-weight: 700;
                letter-spacing: 1.5px;
                color: {text_hint};
                padding-bottom: 4px;
                border-bottom: 1px solid {panel_border};
            }}
        """)
        layout.addWidget(header)

        if hint:
            hint_label = QLabel(hint)
            hint_label.setStyleSheet(f"""
                QLabel {{
                    font-size: 10px;
                    color: {text_hint};
                    font-style: italic;
                }}
            """)
            layout.addWidget(hint_label)

        return container

    def _create_monitoring_section(self, parent_layout: QVBoxLayout) -> None:
        """Create the monitoring tools section (opens a window per device)."""
        parent_layout.addWidget(self._create_category_header(
            PanelText.CATEGORY_MONITORING,
            'Opens a window per device'
        ))

        grid = QGridLayout()
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(8)

        monitoring_items = []
        for label, handler_name, icon_key in PanelConfig.MONITORING_ACTIONS:
            handler = getattr(self.window, handler_name, None)
            if handler:
                monitoring_items.append({
                    'icon': icon_key,
                    'label': label,
                    'handler': handler,
                })

        self._populate_icon_grid(grid, monitoring_items, columns=3)
        parent_layout.addLayout(grid)

    def _create_capture_section(self, parent_layout: QVBoxLayout) -> None:
        """Create the capture tools section (batch operations)."""
        parent_layout.addWidget(self._create_category_header(
            PanelText.CATEGORY_CAPTURE,
            'Supports batch operations'
        ))

        grid = QGridLayout()
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(8)

        capture_items = []
        for label, handler_name, icon_key in PanelConfig.CAPTURE_ACTIONS:
            handler = getattr(self.window, handler_name, None)
            if handler:
                with_progress = icon_key == 'bug_report'
                capture_items.append({
                    'icon': icon_key,
                    'label': label,
                    'handler': handler,
                    'with_progress': with_progress,
                    'primary': icon_key == 'screenshot',
                })

        # Custom handling for capture items
        for index, item in enumerate(capture_items):
            row, column = divmod(index, 4)
            widget, button, progress_bar = self._create_icon_tool_widget(
                icon_key=str(item['icon']),
                label=str(item['label']),
                handler=item['handler'],
                primary=item.get('primary', False),
                with_progress=item.get('with_progress', False),
            )
            grid.addWidget(widget, row, column)

            # Store button references
            if item['icon'] == 'screenshot':
                self.window.screenshot_btn = button
            elif item['icon'] == 'record_start':
                self.window.start_record_btn = button
            elif item['icon'] == 'record_stop':
                self.window.stop_record_btn = button

        for col in range(4):
            grid.setColumnStretch(col, 1)

        parent_layout.addLayout(grid)

        # Recording status labels
        self.window.recording_status_label = QLabel(PanelText.LABEL_NO_RECORDING)
        StyleManager.apply_label_style(self.window.recording_status_label, LabelStyle.STATUS)
        parent_layout.addWidget(self.window.recording_status_label)

        self.window.recording_timer_label = QLabel('')
        StyleManager.apply_status_style(self.window.recording_timer_label, 'recording_active')
        parent_layout.addWidget(self.window.recording_timer_label)

    def _create_control_section(self, parent_layout: QVBoxLayout) -> None:
        """Create the device control section (batch operations)."""
        parent_layout.addWidget(self._create_category_header(
            PanelText.CATEGORY_CONTROL,
            'Supports batch operations'
        ))

        grid = QGridLayout()
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(8)

        control_items = []
        for label, handler_name, icon_key in PanelConfig.CONTROL_ACTIONS:
            handler = getattr(self.window, handler_name, None)
            if handler:
                with_progress = icon_key == 'install_apk'
                control_items.append({
                    'icon': icon_key,
                    'label': label,
                    'handler': handler,
                    'with_progress': with_progress,
                })

        # Add scrcpy if available
        if self.window.scrcpy_available:
            control_items.append({
                'icon': 'scrcpy',
                'label': 'scrcpy',
                'handler': self.window.launch_scrcpy,
            })

        self._populate_icon_grid(grid, control_items, columns=4)
        parent_layout.addLayout(grid)

    def _create_utility_section(self, parent_layout: QVBoxLayout) -> None:
        """Create the utility section."""
        parent_layout.addWidget(self._create_category_header(PanelText.CATEGORY_UTILITY))

        grid = QGridLayout()
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(8)

        utility_items = []
        for label, handler_name, icon_key in PanelConfig.UTILITY_ACTIONS:
            handler = getattr(self.window, handler_name, None)
            if handler:
                utility_items.append({
                    'icon': icon_key,
                    'label': label,
                    'handler': handler,
                })

        self._populate_icon_grid(grid, utility_items, columns=4)
        parent_layout.addLayout(grid)

    # ------------------------------------------------------------------
    # Icon button helpers
    # ------------------------------------------------------------------
    def _populate_icon_grid(
        self,
        layout: QGridLayout,
        items: List[Dict[str, object]],
        *,
        columns: int = 4,
    ) -> None:
        for index, item in enumerate(items):
            row, column = divmod(index, columns)
            icon_key = str(item['icon'])
            widget, button, progress_bar = self._create_icon_tool_widget(
                icon_key=icon_key,
                label=str(item['label']),
                handler=item['handler'],
                with_progress=item.get('with_progress', False) is True,
            )
            layout.addWidget(widget, row, column)

        for column in range(columns):
            layout.setColumnStretch(column, 1)

    def _create_icon_tool_widget(
        self,
        icon_key: str,
        label: str,
        handler,
        *,
        primary: bool = False,
        with_progress: bool = False,
    ) -> Tuple[QWidget, QToolButton, Optional[QProgressBar]]:
        container = QWidget()
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(4 if with_progress else 0)

        button = QToolButton()
        button.setObjectName('adb_tools_icon_button')
        button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        button.setIcon(get_tile_tool_icon(icon_key, label, primary=primary))
        button.setIconSize(QSize(44, 44))
        button.setText(label)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        StyleManager.apply_tile_button_style(button, primary=primary)

        progress_bar: Optional[QProgressBar] = None
        if with_progress:
            progress_bar = QProgressBar()
            progress_bar.setObjectName('adb_tools_progress_bar')
            progress_bar.setRange(0, 0)
            progress_bar.setTextVisible(False)
            progress_bar.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            progress_bar.setFixedHeight(8)
            progress_bar.hide()

        button.clicked.connect(lambda checked=False, key=icon_key: self.window.handle_tool_action(key))
        self.window.register_tool_action(icon_key, handler, button, progress_bar)

        container_layout.addWidget(button)
        if progress_bar is not None:
            container_layout.addWidget(progress_bar)

        if icon_key == 'bug_report':
            self.window.bug_report_button = button  # type: ignore[attr-defined]
        if icon_key == 'install_apk':
            self.window.install_apk_button = button  # type: ignore[attr-defined]

        return container, button, progress_bar

    def _create_shell_commands_tab(self, tab_widget: QTabWidget) -> None:
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(16, 24, 16, 24)
        content_layout.setSpacing(18)
        scroll_area.setWidget(content)

        template_group = QGroupBox(PanelText.GROUP_COMMAND_TEMPLATES)
        template_layout = QGridLayout(template_group)
        template_layout.setContentsMargins(16, 20, 16, 16)
        template_layout.setHorizontalSpacing(14)
        template_layout.setVerticalSpacing(12)

        for idx, (label, command) in enumerate(PanelConfig.SHELL_TEMPLATE_COMMANDS):
            btn = QPushButton(label)
            btn.clicked.connect(lambda checked, cmd=command: self.window.add_template_command(cmd))
            self._style_button(btn, PanelButtonVariant.SECONDARY, height=34, min_width=180)
            row, col = divmod(idx, 3)
            template_layout.addWidget(btn, row, col)

        content_layout.addWidget(template_group)

        batch_group = QGroupBox(PanelText.GROUP_BATCH_COMMANDS)
        batch_layout = QVBoxLayout(batch_group)
        batch_layout.setContentsMargins(16, 24, 16, 18)
        batch_layout.setSpacing(14)

        self.window.batch_commands_edit = QTextEdit()
        self.window.batch_commands_edit.setPlaceholderText(
            'Enter shell commands (one per line, no "adb shell" prefix needed):\n'
            'getprop ro.build.version.release\n'
            'dumpsys battery\n'
            'pm list packages -3\n\n'
            'Use # for comments'
        )
        self.window.batch_commands_edit.setMinimumHeight(180)
        self.window.batch_commands_edit.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        batch_layout.addWidget(self.window.batch_commands_edit)

        exec_buttons_layout = QHBoxLayout()

        run_single_btn = QPushButton(PanelText.BUTTON_RUN_SINGLE_COMMAND)
        run_single_btn.clicked.connect(lambda: self.window.run_single_command())
        self._style_button(run_single_btn, PanelButtonVariant.PRIMARY, height=36, min_width=200)
        exec_buttons_layout.addWidget(run_single_btn)

        run_batch_btn = QPushButton(PanelText.BUTTON_RUN_ALL_COMMANDS)
        run_batch_btn.clicked.connect(lambda: self.window.run_batch_commands())
        self._style_button(run_batch_btn, PanelButtonVariant.SECONDARY, height=36, min_width=220)
        exec_buttons_layout.addWidget(run_batch_btn)

        cancel_all_btn = QPushButton('Cancel All')
        cancel_all_btn.clicked.connect(lambda: self.window.command_execution_manager.cancel_all_commands())
        self._style_button(cancel_all_btn, PanelButtonVariant.DANGER, height=36)
        exec_buttons_layout.addWidget(cancel_all_btn)

        batch_layout.addLayout(exec_buttons_layout)

        content_layout.addWidget(batch_group)

        # Command Output Section
        output_group = QGroupBox('📤 Command Output')
        output_layout = QVBoxLayout(output_group)
        output_layout.setContentsMargins(16, 20, 16, 16)
        output_layout.setSpacing(10)

        self.window.shell_output_text = QTextEdit()
        self.window.shell_output_text.setReadOnly(True)
        self.window.shell_output_text.setPlaceholderText('Command output will appear here...')
        self.window.shell_output_text.setMinimumHeight(200)
        self.window.shell_output_text.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.window.shell_output_text.setStyleSheet(StyleManager.get_console_style())
        output_layout.addWidget(self.window.shell_output_text)

        clear_output_btn = QPushButton('Clear Output')
        clear_output_btn.clicked.connect(lambda: self.window.shell_output_text.clear())
        self._style_button(clear_output_btn, PanelButtonVariant.SECONDARY, height=32, min_width=120)
        output_layout.addWidget(clear_output_btn, alignment=Qt.AlignmentFlag.AlignRight)

        content_layout.addWidget(output_group)

        tab_widget.addTab(scroll_area, PanelText.TAB_SHELL_COMMANDS)

    def _create_device_file_browser_tab(self, tab_widget: QTabWidget) -> None:
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(16, 24, 16, 24)
        content_layout.setSpacing(16)
        scroll_area.setWidget(content)

        device_label = QLabel('Select exactly one device to browse files.')
        device_label.setObjectName('device_file_browser_device_label')
        content_layout.addWidget(device_label)
        self.window.device_file_browser_device_label = device_label

        path_group = QGroupBox(PanelText.GROUP_DEVICE_FILES)
        path_layout = QHBoxLayout(path_group)

        self.window.device_file_browser_path_edit = QLineEdit()
        self.window.device_file_browser_path_edit.setObjectName('device_file_browser_path')
        self.window.device_file_browser_path_edit.setPlaceholderText(PanelText.PLACEHOLDER_DEVICE_FILE_PATH)
        self.window.device_file_browser_path_edit.setText(PanelText.PLACEHOLDER_DEVICE_FILE_PATH)
        path_layout.addWidget(self.window.device_file_browser_path_edit)

        up_btn = QPushButton(PanelText.BUTTON_UP)
        up_btn.setToolTip('Go to parent directory')
        up_btn.clicked.connect(lambda: self.window.navigate_device_files_up())
        self._style_button(up_btn, PanelButtonVariant.SECONDARY, height=34, min_width=120)
        path_layout.addWidget(up_btn)

        refresh_btn = QPushButton(PanelText.BUTTON_REFRESH)
        refresh_btn.setToolTip('Refresh current directory')
        refresh_btn.clicked.connect(lambda: self.window.refresh_device_file_browser())
        self._style_button(refresh_btn, PanelButtonVariant.SECONDARY, height=34, min_width=120)
        path_layout.addWidget(refresh_btn)

        go_btn = QPushButton(PanelText.BUTTON_GO)
        go_btn.setToolTip('Navigate to the specified path')
        go_btn.clicked.connect(lambda: self.window.navigate_device_files_to_path())
        self._style_button(go_btn, PanelButtonVariant.PRIMARY, height=34, min_width=120)
        path_layout.addWidget(go_btn)

        content_layout.addWidget(path_group)

        self.window.device_file_tree = QTreeWidget()
        self.window.device_file_tree.setObjectName('device_file_browser_tree')
        self.window.device_file_tree.setHeaderLabels(['Name', 'Type'])
        self.window.device_file_tree.setRootIsDecorated(False)
        self.window.device_file_tree.setColumnWidth(0, 320)
        self.window.device_file_tree.setMinimumHeight(320)
        self.window.device_file_tree.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.window.device_file_tree.itemDoubleClicked.connect(
            lambda item, column: self.window.on_device_file_item_double_clicked(item, column)
        )
        self.window.device_file_tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.window.device_file_tree.customContextMenuRequested.connect(
            lambda pos: self.window.on_device_file_context_menu(pos)
        )
        content_layout.addWidget(self.window.device_file_tree)

        status_label = QLabel('Ready to browse device files.')
        status_label.setObjectName('device_file_browser_status_label')
        content_layout.addWidget(status_label)
        self.window.device_file_status_label = status_label
        self.window.device_file_controller.register_widgets(
            tree=self.window.device_file_tree,
            path_edit=self.window.device_file_browser_path_edit,
            status_label=status_label,
            device_label=device_label,
        )

        # Download action row
        action_layout = QHBoxLayout()
        action_layout.setSpacing(8)

        download_btn = QPushButton(PanelText.BUTTON_DOWNLOAD_SELECTED)
        download_btn.setToolTip('Download the checked files or folders to the configured output path')
        download_btn.clicked.connect(lambda: self.window.download_selected_device_files())
        self._style_button(download_btn, PanelButtonVariant.PRIMARY, height=34, min_width=160)
        action_layout.addWidget(download_btn)
        action_layout.addStretch()

        content_layout.addLayout(action_layout)
        content_layout.addStretch()

        tab_widget.addTab(scroll_area, PanelText.TAB_DEVICE_FILES)

    def _create_device_groups_tab(self, tab_widget: QTabWidget) -> None:
        tab = QWidget()
        layout = QHBoxLayout(tab)

        left_group = QGroupBox(PanelText.GROUP_CREATE_UPDATE)
        left_layout = QVBoxLayout(left_group)
        left_layout.setContentsMargins(16, 24, 16, 24)
        left_layout.setSpacing(14)

        helper_label = QLabel('Create a reusable device group from the current selection.')
        helper_label.setWordWrap(True)
        helper_label.setStyleSheet('color: #d8d8d8; font-size: 12px; margin-bottom: 6px;')
        left_layout.addWidget(helper_label)

        name_label = QLabel('Group Name')
        name_label.setStyleSheet('color: #f0f0f0; font-size: 11px; margin-bottom: 2px;')
        left_layout.addWidget(name_label)

        self.window.group_name_edit.setPlaceholderText(PanelText.PLACEHOLDER_GROUP_NAME)
        self.window.group_name_edit.setFixedHeight(32)
        left_layout.addWidget(self.window.group_name_edit)

        save_group_btn = QPushButton(PanelText.BUTTON_SAVE_GROUP)
        save_group_btn.setToolTip('Save the current device selection as a named group')
        save_group_btn.clicked.connect(lambda: self.window.save_group())
        self._style_button(save_group_btn, PanelButtonVariant.PRIMARY, height=34)
        save_group_btn.setMinimumHeight(34)
        left_layout.addWidget(save_group_btn)

        left_layout.addSpacing(6)

        quick_actions_layout = QHBoxLayout()
        quick_actions_layout.setSpacing(10)

        select_group_btn = QPushButton(PanelText.BUTTON_SELECT_GROUP)
        select_group_btn.setToolTip('Load and select all devices belonging to the chosen group')
        select_group_btn.clicked.connect(lambda: self.window.select_devices_in_group())
        self._style_button(select_group_btn, PanelButtonVariant.SECONDARY, height=32)
        select_group_btn.setMinimumHeight(32)
        select_group_btn.setMinimumWidth(0)
        select_group_btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        quick_actions_layout.addWidget(select_group_btn)

        delete_group_btn = QPushButton(PanelText.BUTTON_DELETE_GROUP)
        delete_group_btn.setToolTip('Remove the selected device group')
        delete_group_btn.clicked.connect(lambda: self.window.delete_group())
        self._style_button(delete_group_btn, PanelButtonVariant.DANGER, height=32)
        delete_group_btn.setMinimumHeight(32)
        delete_group_btn.setMinimumWidth(0)
        delete_group_btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        quick_actions_layout.addWidget(delete_group_btn)

        quick_actions_layout.addStretch(1)

        left_layout.addLayout(quick_actions_layout)
        left_layout.addStretch()
        layout.addWidget(left_group, stretch=2)

        right_group = QGroupBox(PanelText.GROUP_EXISTING)
        right_layout = QVBoxLayout(right_group)
        right_layout.setContentsMargins(12, 20, 12, 12)
        right_layout.setSpacing(10)

        self.window.groups_listbox.itemSelectionChanged.connect(self.window.on_group_select)
        right_layout.addWidget(self.window.groups_listbox)

        layout.addWidget(right_group, stretch=3)

        tab_widget.addTab(tab, PanelText.TAB_DEVICE_GROUPS)

    def _create_apps_tab(self, tab_widget: QTabWidget) -> None:
        """Create the Apps tab and attach it to the tab widget."""
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        content = AppListTab(self.window)
        scroll_area.setWidget(content)
        tab_widget.addTab(scroll_area, PanelText.TAB_APPS)


__all__ = ["ToolsPanelController"]
