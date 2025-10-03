"""Controller for building the tools panel tabs."""

from __future__ import annotations

from typing import TYPE_CHECKING, Dict, List

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
)
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QColor, QFont, QFontDatabase, QIcon, QPainter, QPixmap

from config.constants import PanelConfig, PanelText
from ui.style_manager import ButtonStyle, LabelStyle, StyleManager
from ui.ui_factory import UIFactory
from ui.device_overview_widget import DeviceOverviewWidget

if TYPE_CHECKING:  # pragma: no cover
    from lazy_blacktea_pyqt import WindowMain


class ToolsPanelController:
    """Builds the tools panel and its tabs for the main window."""

    def __init__(self, main_window: "WindowMain") -> None:
        self.window = main_window
        self._default_button_height = 38
        self._icon_cache: Dict[str, QIcon] = {}

    def _style_button(
        self,
        button: QPushButton,
        style: ButtonStyle = ButtonStyle.SECONDARY,
        *,
        height: int | None = None,
        min_width: int | None = None,
    ) -> None:
        """Apply consistent styling to buttons inside tools panel."""
        StyleManager.apply_button_style(button, style, fixed_height=height or self._default_button_height)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        if min_width:
            button.setMinimumWidth(min_width)

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

        parent.addWidget(tools_widget)

    def _create_device_overview_tab(self, tab_widget: QTabWidget) -> None:
        widget = DeviceOverviewWidget(self.window)
        self.window.device_overview_widget = widget
        tab_widget.addTab(widget, PanelText.TAB_DEVICE_OVERVIEW)

    # ------------------------------------------------------------------
    # Individual tab creation helpers
    # ------------------------------------------------------------------
    def _create_adb_tools_tab(self, tab_widget: QTabWidget) -> None:
        tab = QWidget()
        layout = QVBoxLayout(tab)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        layout.addWidget(scroll_area)

        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(4, 8, 4, 16)
        content_layout.setSpacing(20)
        scroll_area.setWidget(content_widget)

        output_group = QGroupBox(PanelText.GROUP_OUTPUT_PATH)
        output_group.setObjectName('adb_tools_output_group')
        StyleManager.apply_panel_frame(output_group)
        output_layout = QVBoxLayout(output_group)
        output_layout.setSpacing(10)

        output_row = QHBoxLayout()
        output_row.setSpacing(10)

        self.window.output_path_edit.setPlaceholderText(PanelText.PLACEHOLDER_OUTPUT_DIR)
        output_row.addWidget(self.window.output_path_edit)

        browse_btn = UIFactory.create_standard_button(
            PanelText.BUTTON_BROWSE,
            ButtonStyle.SECONDARY,
            click_handler=lambda: self.window.browse_output_path(),
            tooltip='Select output directory'
        )
        output_row.addWidget(browse_btn)

        output_layout.addLayout(output_row)

        output_hint = QLabel('Screenshots, recordings, and quick exports will be saved here.')
        StyleManager.apply_label_style(output_hint, LabelStyle.STATUS)
        output_layout.addWidget(output_hint)

        reports_group = QGroupBox(PanelText.GROUP_FILE_OPERATIONS)
        reports_group.setObjectName('adb_tools_reports_group')
        StyleManager.apply_panel_frame(reports_group)
        reports_layout = QVBoxLayout(reports_group)
        reports_layout.setSpacing(10)

        reports_row = QHBoxLayout()
        reports_row.setSpacing(10)

        self.window.file_gen_output_path_edit.setPlaceholderText(PanelText.PLACEHOLDER_DEVICE_FILE_OUTPUT)
        reports_row.addWidget(self.window.file_gen_output_path_edit)

        reports_browse_btn = UIFactory.create_standard_button(
            PanelText.BUTTON_BROWSE,
            ButtonStyle.SECONDARY,
            click_handler=lambda: self.window.browse_file_generation_output_path(),
            tooltip='Select reports output directory'
        )
        reports_row.addWidget(reports_browse_btn)

        reports_layout.addLayout(reports_row)

        reports_hint = QLabel('Bug reports, discovery exports, and batch pulls will write to this path.')
        StyleManager.apply_label_style(reports_hint, LabelStyle.STATUS)
        reports_layout.addWidget(reports_hint)

        content_layout.addWidget(output_group)
        content_layout.addWidget(reports_group)
        content_layout.addSpacing(8)

        logcat_group = QGroupBox(PanelText.GROUP_LOGCAT)
        logcat_group.setObjectName('adb_tools_logcat_group')
        StyleManager.apply_panel_frame(logcat_group)
        logcat_layout = QVBoxLayout(logcat_group)
        logcat_layout.setSpacing(10)

        logcat_items = [
            {'icon': 'clear_logcat', 'label': 'Clear Logcat', 'handler': self.window.clear_logcat},
            {'icon': 'bug_report', 'label': 'Bug Report', 'handler': self.window.generate_android_bug_report},
        ]
        logcat_grid = QGridLayout()
        logcat_grid.setHorizontalSpacing(16)
        logcat_grid.setVerticalSpacing(12)
        self._populate_icon_grid(logcat_grid, logcat_items, columns=2)
        logcat_layout.addLayout(logcat_grid)

        content_layout.addWidget(logcat_group)
        content_layout.addSpacing(8)
        device_control_group = QGroupBox(PanelText.GROUP_DEVICE_CONTROL)
        device_control_group.setObjectName('adb_tools_device_control_group')
        StyleManager.apply_panel_frame(device_control_group)
        device_control_layout = QGridLayout(device_control_group)
        device_control_layout.setHorizontalSpacing(16)
        device_control_layout.setVerticalSpacing(12)

        device_actions = list(PanelConfig.DEVICE_ACTIONS)
        if self.window.scrcpy_available:
            device_actions.append(('Mirror Device (scrcpy)', 'launch_scrcpy'))

        device_icon_map = {
            'reboot_device': ('reboot', 'Reboot'),
            'install_apk': ('install_apk', 'Install APK'),
            'enable_bluetooth': ('bt_on', 'BT On'),
            'disable_bluetooth': ('bt_off', 'BT Off'),
            'launch_scrcpy': ('scrcpy', 'scrcpy'),
        }

        control_items: List[Dict[str, object]] = []
        for text, handler_name in device_actions:
            handler = getattr(self.window, handler_name)
            icon, label = device_icon_map.get(
                handler_name,
                (handler_name, text),
            )
            control_items.append({'icon': icon, 'label': label, 'handler': handler})

        self._populate_icon_grid(device_control_layout, control_items, columns=3)

        content_layout.addWidget(device_control_group)
        content_layout.addSpacing(8)

        capture_group = QGroupBox(PanelText.GROUP_CAPTURE)
        capture_group.setObjectName('adb_tools_capture_group')
        StyleManager.apply_panel_frame(capture_group)
        capture_layout = QVBoxLayout(capture_group)
        capture_layout.setSpacing(10)

        capture_grid = QGridLayout()
        capture_grid.setHorizontalSpacing(16)
        capture_grid.setVerticalSpacing(12)

        screenshot_btn = self._create_icon_tool_button('screenshot', 'Screenshot', self.window.take_screenshot, primary=True)
        self.window.screenshot_btn = screenshot_btn
        capture_grid.addWidget(screenshot_btn, 0, 0)

        start_record_btn = self._create_icon_tool_button('record_start', 'Start Record', self.window.start_screen_record)
        self.window.start_record_btn = start_record_btn
        capture_grid.addWidget(start_record_btn, 0, 1)

        stop_record_btn = self._create_icon_tool_button('record_stop', 'Stop Record', self.window.stop_screen_record)
        self.window.stop_record_btn = stop_record_btn
        capture_grid.addWidget(stop_record_btn, 0, 2)

        capture_layout.addLayout(capture_grid)

        self.window.recording_status_label = QLabel(PanelText.LABEL_NO_RECORDING)
        StyleManager.apply_label_style(self.window.recording_status_label, LabelStyle.STATUS)
        capture_layout.addWidget(self.window.recording_status_label)

        self.window.recording_timer_label = QLabel('')
        self.window.recording_timer_label.setStyleSheet(
            StyleManager.get_status_styles()['recording_active']
        )
        capture_layout.addWidget(self.window.recording_timer_label)
        content_layout.addWidget(capture_group)
        content_layout.addSpacing(8)

        content_layout.addStretch(1)

        tab_widget.addTab(tab, PanelText.TAB_ADB_TOOLS)

    # ------------------------------------------------------------------
    # Icon button helpers
    # ------------------------------------------------------------------
    def _populate_icon_grid(
        self,
        layout: QGridLayout,
        items: List[Dict[str, object]],
        *,
        columns: int = 3,
    ) -> None:
        for index, item in enumerate(items):
            row, column = divmod(index, columns)
            button = self._create_icon_tool_button(
                icon_key=str(item['icon']),
                label=str(item['label']),
                handler=item['handler'],
            )
            layout.addWidget(button, row, column)

        for column in range(columns):
            layout.setColumnStretch(column, 1)

    def _create_icon_tool_button(
        self,
        icon_key: str,
        label: str,
        handler,
        *,
        primary: bool = False,
    ) -> QToolButton:
        button = QToolButton()
        button.setObjectName('adb_tools_icon_button')
        button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        button.setIcon(self._get_tool_icon(icon_key, label, primary=primary))
        button.setIconSize(QSize(48, 48))
        button.setText(label)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        bg_color = '#eef2ff' if primary else '#f8fafc'
        border_color = '#a5b4fc' if primary else '#d0d7e2'

        button.setStyleSheet(
            f"""
            QToolButton#adb_tools_icon_button {{
                background-color: {bg_color};
                border: 1px solid {border_color};
                border-radius: 14px;
                padding: 10px 12px;
                color: #1c2a3f;
                font-weight: 600;
            }}
            QToolButton#adb_tools_icon_button:hover {{
                background-color: #e0e7ff;
                border-color: #94a3f8;
            }}
            QToolButton#adb_tools_icon_button:pressed {{
                background-color: #c7d2fe;
                border-color: #818cf8;
            }}
            QToolButton#adb_tools_icon_button:disabled {{
                color: #9ca3af;
                border-color: #e5e7eb;
                background-color: #f8fafc;
            }}
            """
        )

        button.clicked.connect(lambda checked=False, func=handler: func())
        return button

    def _get_tool_icon(self, icon_key: str, label: str, *, primary: bool = False) -> QIcon:
        cache_key = f"{icon_key}|{primary}"
        cached = self._icon_cache.get(cache_key)
        if cached is not None:
            return cached

        size = 64
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.GlobalColor.transparent)

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        palette = self._resolve_icon_palette(icon_key, primary)

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(palette['background']))
        painter.drawRoundedRect(pixmap.rect().adjusted(4, 4, -4, -4), 16, 16)

        monogram = self._extract_monogram(label)
        font = QFont()
        font.setBold(True)
        font.setPointSize(18)
        painter.setFont(font)
        painter.setPen(QColor(palette['foreground']))
        painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, monogram)
        painter.end()

        icon = QIcon(pixmap)
        self._icon_cache[cache_key] = icon
        return icon

    @staticmethod
    def _extract_monogram(label: str) -> str:
        tokens = [token for token in label.split() if token]
        if not tokens:
            return '??'
        if len(tokens) == 1:
            cleaned = ''.join(ch for ch in tokens[0] if ch.isalnum())
            return cleaned[:2].upper() or tokens[0][:2].upper()
        return (tokens[0][0] + tokens[1][0]).upper()

    @staticmethod
    def _resolve_icon_palette(icon_key: str, primary: bool) -> Dict[str, str]:
        base_palettes: Dict[str, Dict[str, str]] = {
            'clear_logcat': {'background': '#fef3c7', 'foreground': '#92400e'},
            'bug_report': {'background': '#fee2e2', 'foreground': '#b91c1c'},
            'reboot': {'background': '#dbeafe', 'foreground': '#1d4ed8'},
            'install_apk': {'background': '#dcfce7', 'foreground': '#047857'},
            'bt_on': {'background': '#e0f2fe', 'foreground': '#0369a1'},
            'bt_off': {'background': '#f1f5f9', 'foreground': '#475569'},
            'scrcpy': {'background': '#ede9fe', 'foreground': '#6d28d9'},
            'screenshot': {'background': '#eef2ff', 'foreground': '#3730a3'},
            'record_start': {'background': '#fee2e2', 'foreground': '#b91c1c'},
            'record_stop': {'background': '#f1f5f9', 'foreground': '#1f2937'},
        }

        palette = base_palettes.get(icon_key, None)
        if palette is None:
            palette = {'background': '#f1f5f9', 'foreground': '#1f2937'}

        if primary:
            palette = {
                'background': '#e0e7ff',
                'foreground': '#312e81',
            }

        return palette

    def _create_shell_commands_tab(self, tab_widget: QTabWidget) -> None:
        tab = QWidget()
        layout = QVBoxLayout(tab)

        template_group = QGroupBox(PanelText.GROUP_COMMAND_TEMPLATES)
        template_layout = QGridLayout(template_group)

        for idx, (label, command) in enumerate(PanelConfig.SHELL_TEMPLATE_COMMANDS):
            btn = QPushButton(label)
            btn.clicked.connect(lambda checked, cmd=command: self.window.add_template_command(cmd))
            self._style_button(btn, ButtonStyle.SECONDARY, height=34, min_width=180)
            row, col = divmod(idx, 3)
            template_layout.addWidget(btn, row, col)

        layout.addWidget(template_group)

        batch_group = QGroupBox(PanelText.GROUP_BATCH_COMMANDS)
        batch_layout = QVBoxLayout(batch_group)

        self.window.batch_commands_edit = QTextEdit()
        self.window.batch_commands_edit.setPlaceholderText(
            'Enter multiple commands (one per line):\n'
            'getprop ro.build.version.release\n'
            'dumpsys battery\n'
            'pm list packages -3\n\n'
            'Use # for comments'
        )
        self.window.batch_commands_edit.setMaximumHeight(120)
        batch_layout.addWidget(self.window.batch_commands_edit)

        exec_buttons_layout = QHBoxLayout()

        run_single_btn = QPushButton(PanelText.BUTTON_RUN_SINGLE_COMMAND)
        run_single_btn.clicked.connect(lambda: self.window.run_single_command())
        self._style_button(run_single_btn, ButtonStyle.PRIMARY, height=36, min_width=200)
        exec_buttons_layout.addWidget(run_single_btn)

        run_batch_btn = QPushButton(PanelText.BUTTON_RUN_ALL_COMMANDS)
        run_batch_btn.clicked.connect(lambda: self.window.run_batch_commands())
        self._style_button(run_batch_btn, ButtonStyle.SECONDARY, height=36, min_width=220)
        exec_buttons_layout.addWidget(run_batch_btn)

        cancel_all_btn = QPushButton('❌ Cancel All')
        cancel_all_btn.clicked.connect(lambda: self.window.command_execution_manager.cancel_all_commands())
        self._style_button(cancel_all_btn, ButtonStyle.DANGER, height=36)
        exec_buttons_layout.addWidget(cancel_all_btn)

        batch_layout.addLayout(exec_buttons_layout)

        self.window.shell_cmd_edit = QLineEdit()
        self.window.shell_cmd_edit.setPlaceholderText(PanelText.PLACEHOLDER_SHELL_COMMAND)
        batch_layout.addWidget(self.window.shell_cmd_edit)

        run_shell_btn = QPushButton(PanelText.BUTTON_RUN_SINGLE_SHELL)
        run_shell_btn.clicked.connect(lambda: self.window.run_shell_command())
        self._style_button(run_shell_btn, ButtonStyle.PRIMARY, height=36, min_width=220)
        batch_layout.addWidget(run_shell_btn)

        layout.addWidget(batch_group)

        history_group = QGroupBox(PanelText.GROUP_COMMAND_HISTORY)
        history_layout = QVBoxLayout(history_group)

        self.window.command_history_list = QListWidget()
        self.window.command_history_list.setMaximumHeight(100)
        self.window.command_history_list.itemDoubleClicked.connect(self.window.load_from_history)
        history_layout.addWidget(self.window.command_history_list)

        history_buttons_layout = QHBoxLayout()

        clear_history_btn = UIFactory.create_standard_button(
            PanelText.BUTTON_CLEAR,
            ButtonStyle.DANGER,
            click_handler=lambda: self.window.clear_command_history(),
            tooltip='Clear command history'
        )
        history_buttons_layout.addWidget(clear_history_btn)

        export_history_btn = QPushButton(PanelText.BUTTON_EXPORT)
        export_history_btn.clicked.connect(lambda: self.window.export_command_history())
        self._style_button(export_history_btn, ButtonStyle.SECONDARY, height=32, min_width=140)
        history_buttons_layout.addWidget(export_history_btn)

        import_history_btn = QPushButton(PanelText.BUTTON_IMPORT)
        import_history_btn.clicked.connect(lambda: self.window.import_command_history())
        self._style_button(import_history_btn, ButtonStyle.SECONDARY, height=32, min_width=140)
        history_buttons_layout.addWidget(import_history_btn)

        history_layout.addLayout(history_buttons_layout)
        layout.addWidget(history_group)

        layout.addStretch()
        self.window.update_history_display()

        tab_widget.addTab(tab, PanelText.TAB_SHELL_COMMANDS)

    def _create_device_file_browser_tab(self, tab_widget: QTabWidget) -> None:
        tab = QWidget()
        layout = QVBoxLayout(tab)

        device_label = QLabel('Select exactly one device to browse files.')
        device_label.setObjectName('device_file_browser_device_label')
        layout.addWidget(device_label)
        self.window.device_file_browser_device_label = device_label

        path_group = QGroupBox(PanelText.GROUP_DEVICE_FILES)
        path_layout = QHBoxLayout(path_group)

        self.window.device_file_browser_path_edit = QLineEdit()
        self.window.device_file_browser_path_edit.setObjectName('device_file_browser_path')
        self.window.device_file_browser_path_edit.setPlaceholderText(PanelText.PLACEHOLDER_DEVICE_FILE_PATH)
        self.window.device_file_browser_path_edit.setText(PanelText.PLACEHOLDER_DEVICE_FILE_PATH)
        path_layout.addWidget(self.window.device_file_browser_path_edit)

        up_btn = UIFactory.create_standard_button(
            PanelText.BUTTON_UP,
            ButtonStyle.SECONDARY,
            click_handler=lambda: self.window.navigate_device_files_up(),
            tooltip='Go to parent directory'
        )
        path_layout.addWidget(up_btn)

        refresh_btn = UIFactory.create_standard_button(
            PanelText.BUTTON_REFRESH,
            ButtonStyle.SECONDARY,
            click_handler=lambda: self.window.refresh_device_file_browser(),
            tooltip='Refresh current directory'
        )
        path_layout.addWidget(refresh_btn)

        go_btn = UIFactory.create_standard_button(
            PanelText.BUTTON_GO,
            ButtonStyle.PRIMARY,
            click_handler=lambda: self.window.navigate_device_files_to_path(),
            tooltip='Navigate to the specified path'
        )
        path_layout.addWidget(go_btn)

        layout.addWidget(path_group)

        self.window.device_file_tree = QTreeWidget()
        self.window.device_file_tree.setObjectName('device_file_browser_tree')
        self.window.device_file_tree.setHeaderLabels(['Name', 'Type'])
        self.window.device_file_tree.setRootIsDecorated(False)
        self.window.device_file_tree.setColumnWidth(0, 320)
        self.window.device_file_tree.setMinimumHeight(260)
        self.window.device_file_tree.itemDoubleClicked.connect(
            lambda item, column: self.window.on_device_file_item_double_clicked(item, column)
        )
        self.window.device_file_tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.window.device_file_tree.customContextMenuRequested.connect(
            lambda pos: self.window.on_device_file_context_menu(pos)
        )
        layout.addWidget(self.window.device_file_tree)

        status_label = QLabel('Ready to browse device files.')
        status_label.setObjectName('device_file_browser_status_label')
        layout.addWidget(status_label)
        self.window.device_file_status_label = status_label

        output_group = QGroupBox(PanelText.GROUP_DEVICE_FILE_OUTPUT)
        output_layout = QHBoxLayout(output_group)

        self.window.file_gen_output_path_edit.setPlaceholderText(PanelText.PLACEHOLDER_DEVICE_FILE_OUTPUT)
        output_layout.addWidget(self.window.file_gen_output_path_edit)

        browse_btn = UIFactory.create_standard_button(
            PanelText.BUTTON_BROWSE,
            ButtonStyle.SECONDARY,
            click_handler=lambda: self.window.browse_file_generation_output_path(),
            tooltip='Select local download destination'
        )
        output_layout.addWidget(browse_btn)

        download_btn = UIFactory.create_standard_button(
            PanelText.BUTTON_DOWNLOAD_SELECTED,
            ButtonStyle.PRIMARY,
            click_handler=lambda: self.window.download_selected_device_files(),
            tooltip='Download the checked files or folders'
        )
        output_layout.addWidget(download_btn)

        layout.addWidget(output_group)
        layout.addStretch()

        tab_widget.addTab(tab, PanelText.TAB_DEVICE_FILES)

    def _create_device_groups_tab(self, tab_widget: QTabWidget) -> None:
        tab = QWidget()
        layout = QHBoxLayout(tab)

        left_group = QGroupBox(PanelText.GROUP_CREATE_UPDATE)
        left_layout = QVBoxLayout(left_group)
        left_layout.setContentsMargins(12, 12, 12, 12)
        left_layout.setSpacing(10)

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
        self._style_button(save_group_btn, ButtonStyle.PRIMARY, height=34)
        save_group_btn.setMinimumHeight(34)
        left_layout.addWidget(save_group_btn)

        left_layout.addSpacing(6)

        quick_actions_layout = QHBoxLayout()
        quick_actions_layout.setSpacing(10)

        select_group_btn = QPushButton(PanelText.BUTTON_SELECT_GROUP)
        select_group_btn.setToolTip('Load and select all devices belonging to the chosen group')
        select_group_btn.clicked.connect(lambda: self.window.select_devices_in_group())
        self._style_button(select_group_btn, ButtonStyle.SECONDARY, height=32)
        select_group_btn.setMinimumHeight(32)
        select_group_btn.setMinimumWidth(0)
        select_group_btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        quick_actions_layout.addWidget(select_group_btn)

        delete_group_btn = QPushButton(PanelText.BUTTON_DELETE_GROUP)
        delete_group_btn.setToolTip('Remove the selected device group')
        delete_group_btn.clicked.connect(lambda: self.window.delete_group())
        self._style_button(delete_group_btn, ButtonStyle.DANGER, height=32)
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

        self.window.groups_listbox.itemSelectionChanged.connect(self.window.on_group_select)
        right_layout.addWidget(self.window.groups_listbox)

        layout.addWidget(right_group, stretch=3)

        tab_widget.addTab(tab, PanelText.TAB_DEVICE_GROUPS)


__all__ = ["ToolsPanelController"]
