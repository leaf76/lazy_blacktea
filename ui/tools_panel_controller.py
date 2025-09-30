"""Controller for building the tools panel tabs."""

from __future__ import annotations

from typing import TYPE_CHECKING

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
)
from PyQt6.QtCore import Qt

from config.constants import PanelConfig, PanelText
from ui.style_manager import ButtonStyle, LabelStyle, StyleManager
from ui.ui_factory import UIFactory

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

        self._create_adb_tools_tab(tab_widget)
        self._create_shell_commands_tab(tab_widget)
        self._create_device_file_browser_tab(tab_widget)
        self._create_device_groups_tab(tab_widget)

        parent.addWidget(tools_widget)

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
        content_layout.setContentsMargins(0, 0, 0, 0)
        scroll_area.setWidget(content_widget)

        output_group = QGroupBox(PanelText.GROUP_OUTPUT_PATH)
        output_layout = QHBoxLayout(output_group)

        self.window.output_path_edit.setPlaceholderText(PanelText.PLACEHOLDER_OUTPUT_DIR)
        output_layout.addWidget(self.window.output_path_edit)

        browse_btn = UIFactory.create_standard_button(
            PanelText.BUTTON_BROWSE,
            ButtonStyle.SECONDARY,
            click_handler=lambda: self.window.browse_output_path(),
            tooltip='Select output directory'
        )
        output_layout.addWidget(browse_btn)

        content_layout.addWidget(output_group)

        logcat_group = QGroupBox(PanelText.GROUP_LOGCAT)
        logcat_layout = QGridLayout(logcat_group)

        clear_logcat_btn = UIFactory.create_standard_button(
            '🗑️ Clear Logcat',
            ButtonStyle.DANGER,
            click_handler=lambda: self.window.clear_logcat(),
            tooltip='Clear logcat on selected devices'
        )
        logcat_layout.addWidget(clear_logcat_btn, 0, 0)

        bug_report_btn = UIFactory.create_standard_button(
            PanelText.BUTTON_GENERATE_BUG_REPORT,
            ButtonStyle.SECONDARY,
            click_handler=lambda: self.window.generate_android_bug_report(),
            tooltip='Generate Android bug report using current selection'
        )
        logcat_layout.addWidget(bug_report_btn, 0, 1)
        content_layout.addWidget(logcat_group)

        device_control_group = QGroupBox(PanelText.GROUP_DEVICE_CONTROL)
        device_control_layout = QGridLayout(device_control_group)

        device_actions = list(PanelConfig.DEVICE_ACTIONS)
        if self.window.scrcpy_available:
            device_actions.append(('🖥️ Mirror Device (scrcpy)', 'launch_scrcpy'))

        for idx, (text, handler_name) in enumerate(device_actions):
            handler = getattr(self.window, handler_name)
            btn = QPushButton(text)
            btn.clicked.connect(lambda checked, func=handler: func())
            style = ButtonStyle.PRIMARY if 'reboot' in handler_name else ButtonStyle.SECONDARY
            self._style_button(btn, style, height=36, min_width=180)
            row, col = divmod(idx, 2)
            device_control_layout.addWidget(btn, row, col)

        content_layout.addWidget(device_control_group)

        capture_group = QGroupBox(PanelText.GROUP_CAPTURE)
        capture_layout = QGridLayout(capture_group)

        self.window.screenshot_btn = QPushButton('📷 Take Screenshot')
        self.window.screenshot_btn.clicked.connect(lambda: self.window.take_screenshot())
        self._style_button(self.window.screenshot_btn, ButtonStyle.PRIMARY, height=44, min_width=220)
        capture_layout.addWidget(self.window.screenshot_btn, 0, 0)

        self.window.start_record_btn = QPushButton('🎥 Start Screen Record')
        self.window.start_record_btn.clicked.connect(lambda: self.window.start_screen_record())
        self._style_button(self.window.start_record_btn, ButtonStyle.SECONDARY, height=40, min_width=220)
        capture_layout.addWidget(self.window.start_record_btn, 1, 0)

        self.window.stop_record_btn = QPushButton('⏹️ Stop Screen Record')
        self.window.stop_record_btn.clicked.connect(lambda: self.window.stop_screen_record())
        self._style_button(self.window.stop_record_btn, ButtonStyle.NEUTRAL, height=40, min_width=220)
        capture_layout.addWidget(self.window.stop_record_btn, 1, 1)

        self.window.recording_status_label = QLabel(PanelText.LABEL_NO_RECORDING)
        StyleManager.apply_label_style(self.window.recording_status_label, LabelStyle.STATUS)
        capture_layout.addWidget(self.window.recording_status_label, 2, 0, 1, 2)

        self.window.recording_timer_label = QLabel('')
        self.window.recording_timer_label.setStyleSheet(
            StyleManager.get_status_styles()['recording_active']
        )
        capture_layout.addWidget(self.window.recording_timer_label, 3, 0, 1, 2)

        content_layout.addWidget(capture_group)

        content_layout.addStretch(1)

        tab_widget.addTab(tab, PanelText.TAB_ADB_TOOLS)

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
