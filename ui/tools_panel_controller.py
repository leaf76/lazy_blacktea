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
    QTabWidget,
    QTextEdit,
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
        self._create_file_generation_tab(tab_widget)
        self._create_device_groups_tab(tab_widget)

        parent.addWidget(tools_widget)

    # ------------------------------------------------------------------
    # Individual tab creation helpers
    # ------------------------------------------------------------------
    def _create_adb_tools_tab(self, tab_widget: QTabWidget) -> None:
        tab = QWidget()
        layout = QVBoxLayout(tab)

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

        layout.addWidget(output_group)

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
            '📊 Android Bug Report',
            ButtonStyle.SECONDARY,
            click_handler=lambda: self.window.generate_android_bug_report(),
            tooltip='Generate Android bug report'
        )
        logcat_layout.addWidget(bug_report_btn, 0, 1)

        layout.addWidget(logcat_group)

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

        layout.addWidget(device_control_group)

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

        layout.addWidget(capture_group)
        layout.addStretch()

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

    def _create_file_generation_tab(self, tab_widget: QTabWidget) -> None:
        tab = QWidget()
        layout = QVBoxLayout(tab)

        output_group = QGroupBox(PanelText.GROUP_OUTPUT_PATH)
        output_layout = QHBoxLayout(output_group)

        self.window.file_gen_output_path_edit.setPlaceholderText(PanelText.PLACEHOLDER_OUTPUT_DIR_FILE)
        output_layout.addWidget(self.window.file_gen_output_path_edit)

        browse_btn = UIFactory.create_standard_button(
            PanelText.BUTTON_BROWSE,
            ButtonStyle.SECONDARY,
            click_handler=lambda: self.window.browse_file_generation_output_path(),
            tooltip='Select output directory for file generation'
        )
        output_layout.addWidget(browse_btn)

        layout.addWidget(output_group)

        generation_group = QGroupBox(PanelText.GROUP_FILE_GENERATION)
        generation_layout = QGridLayout(generation_group)

        for idx, (text, handler_name) in enumerate(PanelConfig.FILE_GENERATION_ACTIONS):
            handler = getattr(self.window, handler_name)
            btn = QPushButton(text)
            btn.clicked.connect(lambda checked, func=handler: func())
            self._style_button(btn, ButtonStyle.SECONDARY, height=40, min_width=220)
            row, col = divmod(idx, 2)
            generation_layout.addWidget(btn, row, col)

        layout.addWidget(generation_group)
        layout.addStretch()

        tab_widget.addTab(tab, PanelText.TAB_FILE_GENERATION)

    def _create_device_groups_tab(self, tab_widget: QTabWidget) -> None:
        tab = QWidget()
        layout = QHBoxLayout(tab)

        left_group = QGroupBox(PanelText.GROUP_CREATE_UPDATE)
        left_layout = QVBoxLayout(left_group)

        name_layout = QHBoxLayout()
        name_layout.addWidget(QLabel('Group Name:'))
        self.window.group_name_edit.setPlaceholderText(PanelText.PLACEHOLDER_GROUP_NAME)
        name_layout.addWidget(self.window.group_name_edit)
        left_layout.addLayout(name_layout)

        save_group_btn = QPushButton(PanelText.BUTTON_SAVE_GROUP)
        save_group_btn.clicked.connect(lambda: self.window.save_group())
        self._style_button(save_group_btn, ButtonStyle.PRIMARY, height=36, min_width=240)
        left_layout.addWidget(save_group_btn)

        left_layout.addStretch()
        layout.addWidget(left_group)

        right_group = QGroupBox(PanelText.GROUP_EXISTING)
        right_layout = QVBoxLayout(right_group)

        self.window.groups_listbox.itemSelectionChanged.connect(self.window.on_group_select)
        right_layout.addWidget(self.window.groups_listbox)

        group_buttons_layout = QHBoxLayout()

        select_group_btn = QPushButton(PanelText.BUTTON_SELECT_GROUP)
        select_group_btn.clicked.connect(lambda: self.window.select_devices_in_group())
        self._style_button(select_group_btn, ButtonStyle.SECONDARY, height=34, min_width=220)
        group_buttons_layout.addWidget(select_group_btn)

        delete_group_btn = QPushButton(PanelText.BUTTON_DELETE_GROUP)
        delete_group_btn.clicked.connect(lambda: self.window.delete_group())
        self._style_button(delete_group_btn, ButtonStyle.DANGER, height=34, min_width=220)
        group_buttons_layout.addWidget(delete_group_btn)

        group_buttons_layout.addStretch()
        right_layout.addLayout(group_buttons_layout)
        layout.addWidget(right_group)

        tab_widget.addTab(tab, PanelText.TAB_DEVICE_GROUPS)


__all__ = ["ToolsPanelController"]
