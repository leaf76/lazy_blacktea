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
from PyQt6.QtCore import Qt, QSize, QEvent, QObject

from config.constants import PanelConfig, PanelText
from ui.style_manager import (
    LabelStyle,
    PanelButtonVariant,
    StyleManager,
    SPACING_SMALL,
    SPACING_MEDIUM,
    SPACING_LARGE,
)
from ui.device_overview_widget import DeviceOverviewWidget
from ui.app_list_tab import AppListTab
from ui.svg_icon_factory import get_svg_tool_icon
from ui.tool_metadata import get_tool_metadata

if TYPE_CHECKING:  # pragma: no cover
    from lazy_blacktea_pyqt import WindowMain


class ResizeEventFilter(QObject):
    """Event filter to handle resize events for responsive layout."""

    def __init__(self, controller: "ToolsPanelController") -> None:
        super().__init__()
        self.controller = controller
        self._last_width = 0

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:
        """Filter resize events and trigger grid re-layout."""
        if event.type() == QEvent.Type.Resize:
            # Get the new width
            new_width = event.size().width()  # type: ignore[attr-defined]

            # Only re-layout if width changed significantly (>50px to avoid too frequent updates)
            if abs(new_width - self._last_width) > 50:
                self._last_width = new_width
                # Trigger re-layout for all cached grids
                for grid_id in list(getattr(self.controller, '_grid_cache', {}).keys()):
                    self.controller._relayout_grid(grid_id, new_width)

        return super().eventFilter(obj, event)


class ToolsPanelController:
    """Builds the tools panel and its tabs for the main window."""

    def __init__(self, main_window: "WindowMain") -> None:
        self.window = main_window
        self._default_button_height = 38
        # Track current column count for responsive layout
        self._current_columns: Dict[str, int] = {}

    def _calculate_grid_columns(self, width: int, section: str = 'default') -> int:
        """Calculate optimal grid columns based on viewport width.

        Args:
            width: Viewport width in pixels
            section: Section identifier for tracking column changes

        Returns:
            Number of columns (2-4)
        """
        if width < 768:
            columns = 2  # Small screens (mobile, small tablets)
        elif width < 1200:
            columns = 3  # Medium screens (tablets, small desktops)
        else:
            columns = 4  # Large screens (desktops)

        self._current_columns[section] = columns
        return columns

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
    # Individual tab creation helpers
    # ------------------------------------------------------------------
    def _create_adb_tools_tab(self, tab_widget: QTabWidget) -> None:
        """Create the ADB Tools tab with enhanced layout and spacing."""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(0, 0, 0, 0)  # Remove margins for scroll area

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QScrollArea.Shape.NoFrame)  # Remove frame for cleaner look

        # Install resize event filter for responsive layout
        resize_filter = ResizeEventFilter(self)
        scroll_area.installEventFilter(resize_filter)
        # Store reference to prevent garbage collection
        if not hasattr(self, '_event_filters'):
            self._event_filters = []
        self._event_filters.append(resize_filter)

        layout.addWidget(scroll_area)

        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(12, SPACING_MEDIUM, 12, SPACING_LARGE)  # Balanced margins
        content_layout.setSpacing(SPACING_LARGE)  # Consistent group separation
        scroll_area.setWidget(content_widget)

        output_group = QGroupBox(PanelText.GROUP_OUTPUT_PATH)
        output_group.setObjectName('adb_tools_output_group')
        StyleManager.apply_panel_frame(output_group)
        output_layout = QVBoxLayout(output_group)
        output_layout.setContentsMargins(20, 20, 20, 20)  # Symmetric padding
        output_layout.setSpacing(SPACING_MEDIUM)  # Consistent vertical spacing

        output_row = QHBoxLayout()
        output_row.setSpacing(12)  # Better horizontal spacing

        self.window.output_path_edit.setPlaceholderText(PanelText.PLACEHOLDER_OUTPUT_DIR)
        output_row.addWidget(self.window.output_path_edit)

        browse_btn = QPushButton(PanelText.BUTTON_BROWSE)
        browse_btn.setToolTip('Select output directory')
        browse_btn.clicked.connect(lambda: self.window.browse_output_path())
        self._style_button(browse_btn, PanelButtonVariant.SECONDARY, min_width=140)
        output_row.addWidget(browse_btn)

        output_layout.addLayout(output_row)

        output_hint = QLabel('Screenshots, recordings, and quick exports will be saved here.')
        StyleManager.apply_label_style(output_hint, LabelStyle.STATUS)
        output_layout.addWidget(output_hint)

        output_layout.addSpacing(12)

        quick_actions_label = QLabel(PanelText.GROUP_LOGCAT)
        StyleManager.apply_label_style(quick_actions_label, LabelStyle.SUBHEADER)
        output_layout.addWidget(quick_actions_label)

        logcat_items = [
            {'icon': 'bug_report', 'label': 'Bug Report', 'handler': self.window.generate_android_bug_report},
        ]
        logcat_grid = QGridLayout()
        logcat_grid.setHorizontalSpacing(20)  # Material Design card spacing
        logcat_grid.setVerticalSpacing(20)
        logcat_grid.setContentsMargins(0, SPACING_SMALL, 0, SPACING_SMALL)
        self._populate_icon_grid(logcat_grid, logcat_items, columns=1)
        output_layout.addLayout(logcat_grid)

        output_layout.addSpacing(SPACING_LARGE)

        capture_label = QLabel(PanelText.GROUP_CAPTURE)
        StyleManager.apply_label_style(capture_label, LabelStyle.SUBHEADER)
        output_layout.addWidget(capture_label)

        capture_grid = QGridLayout()
        capture_grid.setHorizontalSpacing(20)  # Material Design card spacing
        capture_grid.setVerticalSpacing(20)  # Generous vertical spacing for cards
        capture_grid.setContentsMargins(0, SPACING_SMALL, 0, SPACING_SMALL)  # Breathing room

        screenshot_widget, screenshot_btn, _ = self._create_icon_tool_widget(
            'screenshot', 'Screenshot', self.window.take_screenshot, primary=True
        )
        self.window.screenshot_btn = screenshot_btn
        capture_grid.addWidget(screenshot_widget, 0, 0)

        start_record_widget, start_record_btn, _ = self._create_icon_tool_widget(
            'record_start', 'Start Record', self.window.start_screen_record
        )
        self.window.start_record_btn = start_record_btn
        capture_grid.addWidget(start_record_widget, 0, 1)

        stop_record_widget, stop_record_btn, _ = self._create_icon_tool_widget(
            'record_stop', 'Stop Record', self.window.stop_screen_record
        )
        self.window.stop_record_btn = stop_record_btn
        capture_grid.addWidget(stop_record_widget, 0, 2)

        capture_grid.setColumnStretch(3, 1)
        output_layout.addLayout(capture_grid)

        self.window.recording_status_label = QLabel(PanelText.LABEL_NO_RECORDING)
        StyleManager.apply_label_style(self.window.recording_status_label, LabelStyle.STATUS)
        output_layout.addWidget(self.window.recording_status_label)

        self.window.recording_timer_label = QLabel('')
        StyleManager.apply_status_style(self.window.recording_timer_label, 'recording_active')
        output_layout.addWidget(self.window.recording_timer_label)

        content_layout.addWidget(output_group)

        device_control_group = QGroupBox(PanelText.GROUP_DEVICE_CONTROL)
        device_control_group.setObjectName('adb_tools_device_control_group')
        StyleManager.apply_panel_frame(device_control_group)
        device_control_layout = QGridLayout(device_control_group)
        device_control_layout.setContentsMargins(20, 20, 20, 20)  # Symmetric padding
        device_control_layout.setHorizontalSpacing(20)  # Material Design card spacing
        device_control_layout.setVerticalSpacing(20)  # Generous vertical spacing for cards

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

        # Use responsive layout with initial 3 columns
        initial_width = self.window.width() if hasattr(self.window, 'width') else 1024
        initial_columns = self._calculate_grid_columns(initial_width, 'device_control')
        self._populate_icon_grid(
            device_control_layout,
            control_items,
            columns=initial_columns,
            store_items=True,
            grid_id='device_control'
        )

        content_layout.addWidget(device_control_group)
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
        store_items: bool = False,
        grid_id: str = '',
    ) -> None:
        """Populate a grid layout with icon tool widgets.

        Args:
            layout: The grid layout to populate
            items: List of tool items (icon, label, handler)
            columns: Number of columns (can be updated later for responsive layout)
            store_items: Whether to store items for later re-layout
            grid_id: Unique identifier for this grid (for responsive updates)
        """
        if store_items and grid_id:
            # Store grid info for responsive updates
            if not hasattr(self, '_grid_cache'):
                self._grid_cache: Dict[str, Tuple[QGridLayout, List[Dict[str, object]]]] = {}
            self._grid_cache[grid_id] = (layout, items)

        # Clear existing widgets
        while layout.count():
            item = layout.takeAt(0)
            if item and item.widget():
                item.widget().setParent(None)

        # Populate grid with current column count
        for index, item in enumerate(items):
            row, column = divmod(index, columns)
            icon_key = str(item['icon'])
            widget, button, progress_bar = self._create_icon_tool_widget(
                icon_key=icon_key,
                label=str(item['label']),
                handler=item['handler'],
                with_progress=icon_key in {'bug_report', 'install_apk'},
            )
            layout.addWidget(widget, row, column)

        # Set column stretches
        for column in range(columns):
            layout.setColumnStretch(column, 1)

    def _relayout_grid(self, grid_id: str, width: int) -> None:
        """Re-layout a grid based on viewport width.

        Args:
            grid_id: Identifier of the grid to re-layout
            width: Current viewport width
        """
        if not hasattr(self, '_grid_cache') or grid_id not in self._grid_cache:
            return

        layout, items = self._grid_cache[grid_id]
        new_columns = self._calculate_grid_columns(width, grid_id)

        # Re-populate with new column count
        self._populate_icon_grid(layout, items, columns=new_columns)

    def _create_icon_tool_widget(
        self,
        icon_key: str,
        label: str,
        handler,
        *,
        primary: bool = False,
        with_progress: bool = False,
    ) -> Tuple[QWidget, QFrame, Optional[QProgressBar]]:
        """Create a Material Design card-style tool widget.

        Returns a card with icon, title, and description following Figma/Material Design style.
        """
        # Get metadata for this tool
        metadata = get_tool_metadata(icon_key, fallback_label=label)

        # Create card frame (clickable container)
        card = QFrame()
        card.setObjectName(f'material_card_{icon_key}')
        card.setCursor(Qt.CursorShape.PointingHandCursor)
        card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        card.setMinimumHeight(150)  # Adequate size for card content
        card.setMinimumWidth(180)  # Minimum width for description readability

        # Apply Material Design card styling
        StyleManager.apply_material_card_frame_style(card, primary=primary)

        # Card layout
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(24, 24, 24, 24)  # Material Design spacing
        card_layout.setSpacing(12)
        card_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Icon container (圓形背景 + 圖示)
        icon_container = QLabel()
        icon_container.setObjectName(f'icon_container_{icon_key}')
        icon_container.setProperty('iconContainer', True)
        icon_container.setPixmap(get_svg_tool_icon(metadata.icon_key, metadata.label, primary=primary, size=56).pixmap(QSize(56, 56)))
        icon_container.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_container.setFixedSize(56, 56)
        card_layout.addWidget(icon_container, alignment=Qt.AlignmentFlag.AlignCenter)

        # Title label
        title_label = QLabel(metadata.label)
        title_label.setProperty('materialCardTitle', True)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_label.setWordWrap(False)
        card_layout.addWidget(title_label, alignment=Qt.AlignmentFlag.AlignCenter)

        # Description label
        description_label = QLabel(metadata.description)
        description_label.setProperty('materialCardDescription', True)
        description_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        description_label.setWordWrap(True)
        description_label.setMaximumWidth(160)  # Limit width for better readability
        card_layout.addWidget(description_label, alignment=Qt.AlignmentFlag.AlignCenter)

        # Enhanced tooltip with keyboard shortcut if available
        tooltip_text = metadata.tooltip
        if metadata.shortcut:
            tooltip_text = f"{metadata.tooltip}\n\nShortcut: {metadata.shortcut}"
        card.setToolTip(tooltip_text)

        # Accessibility improvements
        if metadata.accessible_name:
            card.setAccessibleName(metadata.accessible_name)
        if metadata.accessible_description:
            card.setAccessibleDescription(metadata.accessible_description)

        # Focus policy for keyboard navigation
        card.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        # Progress bar (if needed)
        progress_bar: Optional[QProgressBar] = None
        if with_progress:
            progress_bar = QProgressBar()
            progress_bar.setObjectName(f'progress_{icon_key}')
            progress_bar.setRange(0, 0)
            progress_bar.setTextVisible(False)
            progress_bar.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            progress_bar.setFixedHeight(6)  # Thinner progress bar
            progress_bar.setStyleSheet("""
                QProgressBar {
                    border: none;
                    border-radius: 3px;
                    background-color: #E9ECEF;
                }
                QProgressBar::chunk {
                    background-color: #1971C2;
                    border-radius: 3px;
                }
            """)
            progress_bar.hide()
            card_layout.addWidget(progress_bar)

        # Make entire card clickable
        card.mousePressEvent = lambda event: handler() if event.button() == Qt.MouseButton.LeftButton else None

        # Register tool action
        self.window.register_tool_action(icon_key, handler, card, progress_bar)

        # Store button references for compatibility
        if icon_key == 'bug_report':
            self.window.bug_report_button = card  # type: ignore[attr-defined]
        if icon_key == 'install_apk':
            self.window.install_apk_button = card  # type: ignore[attr-defined]

        return card, card, progress_bar

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
            'Enter multiple commands (one per line):\n'
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

        cancel_all_btn = QPushButton('❌ Cancel All')
        cancel_all_btn.clicked.connect(lambda: self.window.command_execution_manager.cancel_all_commands())
        self._style_button(cancel_all_btn, PanelButtonVariant.DANGER, height=36)
        exec_buttons_layout.addWidget(cancel_all_btn)

        batch_layout.addLayout(exec_buttons_layout)

        self.window.shell_cmd_edit = QLineEdit()
        self.window.shell_cmd_edit.setPlaceholderText(PanelText.PLACEHOLDER_SHELL_COMMAND)
        batch_layout.addWidget(self.window.shell_cmd_edit)

        run_shell_btn = QPushButton(PanelText.BUTTON_RUN_SINGLE_SHELL)
        run_shell_btn.clicked.connect(lambda: self.window.run_shell_command())
        self._style_button(run_shell_btn, PanelButtonVariant.PRIMARY, height=36, min_width=220)
        batch_layout.addWidget(run_shell_btn)

        content_layout.addWidget(batch_group)

        history_group = QGroupBox(PanelText.GROUP_COMMAND_HISTORY)
        history_layout = QVBoxLayout(history_group)
        history_layout.setContentsMargins(16, 20, 16, 20)
        history_layout.setSpacing(12)

        self.window.command_history_list = QListWidget()
        self.window.command_history_list.setMinimumHeight(200)
        self.window.command_history_list.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.window.command_history_list.itemDoubleClicked.connect(self.window.load_from_history)
        history_layout.addWidget(self.window.command_history_list)

        history_buttons_layout = QHBoxLayout()

        clear_history_btn = QPushButton(PanelText.BUTTON_CLEAR)
        clear_history_btn.setToolTip('Clear command history')
        clear_history_btn.clicked.connect(lambda: self.window.clear_command_history())
        self._style_button(clear_history_btn, PanelButtonVariant.DANGER, height=32, min_width=140)
        history_buttons_layout.addWidget(clear_history_btn)

        export_history_btn = QPushButton(PanelText.BUTTON_EXPORT)
        export_history_btn.clicked.connect(lambda: self.window.export_command_history())
        self._style_button(export_history_btn, PanelButtonVariant.SECONDARY, height=32, min_width=140)
        history_buttons_layout.addWidget(export_history_btn)

        import_history_btn = QPushButton(PanelText.BUTTON_IMPORT)
        import_history_btn.clicked.connect(lambda: self.window.import_command_history())
        self._style_button(import_history_btn, PanelButtonVariant.SECONDARY, height=32, min_width=140)
        history_buttons_layout.addWidget(import_history_btn)

        history_layout.addLayout(history_buttons_layout)
        content_layout.addWidget(history_group)

        content_layout.addStretch()
        self.window.update_history_display()

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

        output_group = QGroupBox(PanelText.GROUP_DEVICE_FILE_OUTPUT)
        output_layout = QHBoxLayout(output_group)

        self.window.file_gen_output_path_edit.setPlaceholderText(PanelText.PLACEHOLDER_DEVICE_FILE_OUTPUT)
        output_layout.addWidget(self.window.file_gen_output_path_edit)

        browse_btn = QPushButton(PanelText.BUTTON_BROWSE)
        browse_btn.setToolTip('Select local download destination')
        browse_btn.clicked.connect(lambda: self.window.browse_file_generation_output_path())
        self._style_button(browse_btn, PanelButtonVariant.SECONDARY, height=32, min_width=140)
        output_layout.addWidget(browse_btn)

        download_btn = QPushButton(PanelText.BUTTON_DOWNLOAD_SELECTED)
        download_btn.setToolTip('Download the checked files or folders')
        download_btn.clicked.connect(lambda: self.window.download_selected_device_files())
        self._style_button(download_btn, PanelButtonVariant.PRIMARY, height=34, min_width=160)
        output_layout.addWidget(download_btn)

        content_layout.addWidget(output_group)
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
