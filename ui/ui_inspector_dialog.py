"""Standalone UI Inspector dialog implementation."""

from __future__ import annotations

import shutil
from typing import Callable, Optional

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QFileDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QProgressBar,
    QScrollArea,
    QSplitter,
    QTabWidget,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QHBoxLayout,
    QWidget,
)

from utils import common, dump_device_ui
from utils.task_dispatcher import TaskContext, TaskHandle, TaskCancelledError, get_task_dispatcher
from utils.ui_inspector_utils import (
    capture_device_screenshot,
    create_temp_files,
    dump_ui_hierarchy,
    elements_match,
    find_elements_at_position,
    parse_ui_elements_cached,
)
from utils.ui_widgets import (
    create_automation_section,
    create_content_section,
    create_element_header,
    create_error_widget,
    create_interaction_section,
    create_loading_widget,
    create_position_section,
    create_success_widget,
    create_welcome_widget,
    create_technical_section,
)
from ui.screenshot_widget import ClickableScreenshotLabel
from ui.style_manager import ButtonStyle, LabelStyle, StyleManager
from ui.ui_factory import UIInspectorFactory


logger = common.get_logger('lazy_blacktea')


def _execute_ui_inspector_task(
    device_serial: str,
    *,
    progress_callback: Optional[Callable[[int, str], None]] = None,
    task_handle: Optional[TaskHandle] = None,
) -> dict:
    """Capture screenshot and hierarchy data for UI Inspector."""

    def _report(value: int, label: str) -> None:
        if progress_callback:
            progress_callback(value, label)

    def _check_cancelled() -> None:
        if task_handle and task_handle.is_cancelled():  # pragma: no cover - defensive
            raise TaskCancelledError('Operation cancelled')

    temp_dir: Optional[str] = None
    try:
        temp_dir, screenshot_path, xml_path = create_temp_files()
        logger.info('UI Inspector artifacts at %s (screenshot=%s, xml=%s)', temp_dir, screenshot_path, xml_path)

        _report(15, '📸 Capturing screenshot...')
        _check_cancelled()

        if not capture_device_screenshot(device_serial, screenshot_path):
            raise RuntimeError('Failed to capture screenshot')

        _report(33, '✅ Screenshot captured')
        _check_cancelled()

        _report(45, '🌳 Dumping UI hierarchy...')
        if not dump_ui_hierarchy(device_serial, xml_path):
            raise RuntimeError('Failed to dump UI hierarchy')

        _report(75, '🖼️ Processing screenshot...')
        _check_cancelled()

        ui_elements = parse_ui_elements_cached(xml_path)
        _report(90, '🎨 Preparing interface...')

        payload = {
            'temp_dir': temp_dir,
            'screenshot_path': screenshot_path,
            'xml_path': xml_path,
            'ui_elements': ui_elements,
        }
        logger.info('UI Inspector background task completed for %s', device_serial)
        return payload

    except Exception:
        if temp_dir:
            shutil.rmtree(temp_dir, ignore_errors=True)
        raise


class UIInspectorDialog(QDialog):
    """Interactive UI Inspector dialog with screenshot and hierarchy overlay."""

    def __init__(self, parent, device_serial, device_model):
        super().__init__(parent)
        self.device_serial = device_serial
        self.device_model = device_model
        self.screenshot_data = None
        self.ui_hierarchy = None
        self.ui_elements = []
        self._hierarchy_filter_text: str = ''
        self._progress_is_busy = False
        self._worker_start_scheduled = False
        self._base_pixmap: Optional[QPixmap] = None
        self._base_scale: float = 1.0
        self._zoom_multiplier: float = 1.0
        self._zoom_options = (
            (0.3, '30%'),
            (0.4, '40%'),
            (0.5, '50%'),
            (0.67, '67%'),
            (0.8, '80%'),
            (1.0, '100%'),
        )
        self.zoom_combo: Optional[QComboBox] = None

        # Initialize UI Inspector factory for creating UI components
        self.ui_inspector_factory = UIInspectorFactory(parent_dialog=self)

        self.setWindowTitle(f'📱 UI Inspector - {device_model}')
        self.setModal(True)
        self.resize(1200, 800)

        self._task_handle: Optional[TaskHandle] = None
        self._current_temp_dir: Optional[str] = None

        self.setup_ui()
        QTimer.singleShot(0, self.refresh_ui_data)

    def setup_ui(self):
        """Setup the redesigned UI Inspector interface."""
        # Main layout - vertical splitter for better responsiveness
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(8)

        # Top toolbar with modern design
        self.create_modern_toolbar(main_layout)

        # Main content area with horizontal splitter
        content_splitter = QSplitter(Qt.Orientation.Horizontal)
        content_splitter.setChildrenCollapsible(False)

        # Left panel - Screenshot with modern styling
        left_panel = self.create_screenshot_panel()
        content_splitter.addWidget(left_panel)

        # Right panel - Element details and hierarchy with tabs
        right_panel = self.create_inspector_panel()
        content_splitter.addWidget(right_panel)

        # Set splitter proportions (60% screenshot, 40% inspector)
        content_splitter.setSizes([600, 400])
        content_splitter.setStretchFactor(0, 3)
        content_splitter.setStretchFactor(1, 2)

        main_layout.addWidget(content_splitter)

    def create_modern_toolbar(self, parent_layout):
        """Create a toolbar with system colors."""
        toolbar_widget = QWidget()
        toolbar_widget.setFixedHeight(60)
        # Use system default background
        toolbar_widget.setAutoFillBackground(True)

        toolbar = QHBoxLayout(toolbar_widget)
        toolbar.setContentsMargins(16, 12, 16, 12)
        toolbar.setSpacing(12)

        # Device info section with system styling
        device_info = QLabel(f'📱 {self.device_model}')
        device_info.setStyleSheet(StyleManager.get_device_info_style())
        toolbar.addWidget(device_info)

        toolbar.addStretch()

        # Action buttons with system styling
        self.refresh_btn = self.create_system_button('🔄 Refresh')
        self.refresh_btn.clicked.connect(self.refresh_ui_data)
        toolbar.addWidget(self.refresh_btn)

        zoom_label = QLabel('🔎 Zoom')
        StyleManager.apply_label_style(zoom_label, LabelStyle.SUBHEADER)
        toolbar.addWidget(zoom_label)

        zoom_combo = QComboBox()
        zoom_combo.setFixedHeight(36)
        for factor, label in self._zoom_options:
            zoom_combo.addItem(label, factor)
        zoom_combo.setCurrentIndex(len(self._zoom_options) - 1)
        zoom_combo.currentIndexChanged.connect(self._on_zoom_combo_changed)
        zoom_combo.setEnabled(False)
        self.zoom_combo = zoom_combo
        toolbar.addWidget(zoom_combo)

        # Progress bar with system styling
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setFixedSize(200, 28)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setRange(0, 100)
        toolbar.addWidget(self.progress_bar)

        save_btn = self.create_system_button('💾 Save')
        save_btn.clicked.connect(self.save_screenshot)
        toolbar.addWidget(save_btn)

        export_btn = self.create_system_button('📁 Export')
        export_btn.clicked.connect(self.export_hierarchy)
        toolbar.addWidget(export_btn)

        parent_layout.addWidget(toolbar_widget)

    def create_system_button(self, text):
        """Create a button with system styling."""
        button = QPushButton(text)
        StyleManager.apply_button_style(button, ButtonStyle.SYSTEM, 36)
        return button

    def create_screenshot_panel(self):
        """Create the screenshot panel with system styling."""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        # Screenshot header with system styling
        header = QLabel('📸 Device Screenshot')
        StyleManager.apply_label_style(header, LabelStyle.HEADER)
        layout.addWidget(header)

        # Screenshot display with system scroll area
        scroll_area = QScrollArea()
        scroll_area.setFrameStyle(QScrollArea.Shape.StyledPanel)

        self.screenshot_label = ClickableScreenshotLabel()
        self.screenshot_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        self.screenshot_label.element_clicked.connect(self.on_element_clicked)
        scroll_area.setWidget(self.screenshot_label)
        scroll_area.setWidgetResizable(True)
        scroll_area.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        layout.addWidget(scroll_area)

        return panel

    def create_inspector_panel(self):
        """Create the inspector panel with system styling."""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        # Inspector header with system styling
        header = QLabel('🔍 Element Inspector')
        StyleManager.apply_label_style(header, LabelStyle.HEADER)
        layout.addWidget(header)

        # Create tabbed interface with system styling
        tab_widget = QTabWidget()

        # Element Details Tab
        details_tab = self.create_element_details_tab()
        tab_widget.addTab(details_tab, '📋 Details')

        # UI Hierarchy Tab
        hierarchy_tab = self.create_hierarchy_tab()
        tab_widget.addTab(hierarchy_tab, '🌳 Hierarchy')

        layout.addWidget(tab_widget)
        return panel

    def create_element_details_tab(self):
        """Create the element details tab with modern design."""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        # Create scrollable area for element details with system styling
        details_scroll = QScrollArea()
        details_scroll.setWidgetResizable(True)
        details_scroll.setFrameStyle(QScrollArea.Shape.NoFrame)

        # Element details container with programmatic spacing
        self.element_details_widget = QWidget()
        self.element_details_layout = QVBoxLayout(self.element_details_widget)
        self.element_details_layout.setContentsMargins(8, 8, 8, 8)
        self.element_details_layout.setSpacing(12)

        # Ensure proper alignment and add stretch at bottom
        self.element_details_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        # Initialize with welcome message
        self.show_welcome_message()

        details_scroll.setWidget(self.element_details_widget)
        layout.addWidget(details_scroll)

        return tab

    def create_hierarchy_tab(self):
        """Create the hierarchy tab with enhanced tree view."""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        # Search bar for hierarchy
        search_widget = QWidget()
        search_layout = QHBoxLayout(search_widget)
        search_layout.setContentsMargins(0, 0, 0, 0)

        search_label = QLabel('🔍')
        search_label.setStyleSheet(StyleManager.get_search_label_style())
        search_layout.addWidget(search_label)

        self.hierarchy_search = QLineEdit()
        self.hierarchy_search.setPlaceholderText('Search elements...')
        self.hierarchy_search.setStyleSheet(StyleManager.get_search_input_style())
        self.hierarchy_search.textChanged.connect(self.on_hierarchy_search_changed)
        search_layout.addWidget(self.hierarchy_search)

        layout.addWidget(search_widget)

        # Hierarchy tree with system styling
        self.hierarchy_tree = QTreeWidget()
        self.hierarchy_tree.setHeaderLabel('UI Elements')
        self.hierarchy_tree.itemClicked.connect(self.on_tree_item_clicked)
        self.hierarchy_tree.itemActivated.connect(self.on_tree_item_activated)
        self.hierarchy_tree.setStyleSheet(StyleManager.get_tree_style())

        # Install event filter for optimized Enter key handling
        self.hierarchy_tree.installEventFilter(self)

        layout.addWidget(self.hierarchy_tree)
        return tab

    def show_welcome_message(self):
        """Show the initial welcome message in element details."""
        self.clear_element_details()
        welcome_widget = create_welcome_widget()
        self.element_details_layout.addWidget(welcome_widget)
        self._add_section_spacer()

    def clear_element_details(self):
        """Clear all widgets from element details layout."""
        while self.element_details_layout.count():
            child = self.element_details_layout.takeAt(0)
            if child.widget():
                widget = child.widget()
                widget.setParent(None)
                widget.deleteLater()

        # Force layout update
        self.element_details_layout.update()
        self.element_details_widget.update()


    def show_loading_message(self):
        """Show loading message with progress info."""
        self.clear_element_details()
        loading_widget = create_loading_widget(self.device_model, self.device_serial)
        self.element_details_layout.addWidget(loading_widget)
        self._add_section_spacer()

    def show_success_message(self, element_count):
        """Show success message after loading."""
        self.clear_element_details()
        success_widget = create_success_widget(self.device_model, element_count)
        self.element_details_layout.addWidget(success_widget)
        self._add_section_spacer()

    def show_error_message(self, error_msg):
        """Show error message with troubleshooting tips."""
        self.clear_element_details()
        error_widget = create_error_widget(self.device_model, self.device_serial, error_msg)
        self.element_details_layout.addWidget(error_widget)
        self._add_section_spacer()

    def closeEvent(self, event) -> None:  # type: ignore[override]
        self._cleanup_worker()
        self._cleanup_temp_dir()
        super().closeEvent(event)

    def refresh_ui_data(self):
        """Trigger an asynchronous refresh of screenshot and hierarchy data."""
        if self._task_handle is not None:
            logger.info('UI Inspector refresh already running for %s', self.device_serial)
            return

        if self._worker_start_scheduled:
            logger.info('UI Inspector refresh already scheduled for %s', self.device_serial)
            return

        self._worker_start_scheduled = True
        self._prepare_loading_state()
        QTimer.singleShot(0, self._start_worker)

    # ------------------------------------------------------------------
    # Worker lifecycle helpers
    # ------------------------------------------------------------------
    def _prepare_loading_state(self) -> None:
        self._cleanup_temp_dir()
        self.screenshot_data = None
        self.ui_elements = []
        self._base_pixmap = None
        self._base_scale = 1.0
        self._zoom_multiplier = 1.0
        self.screenshot_label.clear()
        self.screenshot_label.setText('🔄 Loading screenshot and UI data...')
        self.screenshot_label.set_ui_elements([], 1.0)
        self.screenshot_label.set_selected_element(None)
        if self.zoom_combo:
            self.zoom_combo.blockSignals(True)
            try:
                default_index = self.zoom_combo.findData(1.0)
                if default_index != -1:
                    self.zoom_combo.setCurrentIndex(default_index)
            finally:
                self.zoom_combo.blockSignals(False)
            self.zoom_combo.setEnabled(False)

        self._set_progress_busy_mode()
        self.progress_bar.setVisible(True)
        self.progress_bar.setFormat('🔄 Initializing...')

        self.refresh_btn.setEnabled(False)
        self.refresh_btn.setText('🔄 Loading...')

        self.show_loading_message()

    def _set_progress_busy_mode(self) -> None:
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setValue(0)
        self._progress_is_busy = True

    def _ensure_progress_determinate(self) -> None:
        if self._progress_is_busy:
            self.progress_bar.setRange(0, 100)
            self._progress_is_busy = False

    def _start_worker(self) -> None:
        self._worker_start_scheduled = False
        context = TaskContext(
            name='ui_inspector_refresh',
            device_serial=self.device_serial,
            category='ui_inspector',
        )
        handle = get_task_dispatcher().submit(
            _execute_ui_inspector_task,
            self.device_serial,
            context=context,
        )
        handle.progress.connect(self._on_worker_progress)
        handle.completed.connect(self._on_worker_completed)
        handle.failed.connect(self._on_worker_failed)
        handle.finished.connect(self._on_worker_finished)
        self._task_handle = handle
        logger.debug('Dispatched UI Inspector task for %s', self.device_serial)

    def _cleanup_worker(self) -> None:
        if self._task_handle is None:
            return

        self._task_handle.cancel()
        self._task_handle = None
        self._worker_start_scheduled = False
        logger.debug('UIInspector task cancelled for %s', self.device_serial)

    def _on_worker_progress(self, value: int, label: str) -> None:
        self._ensure_progress_determinate()
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(value)
        self.progress_bar.setFormat(label)

    def _on_worker_completed(self, payload: dict) -> None:
        temp_dir = payload.get('temp_dir')
        screenshot_path = payload.get('screenshot_path')
        ui_elements = payload.get('ui_elements', [])

        if temp_dir:
            self._current_temp_dir = temp_dir

        pixmap = QPixmap(screenshot_path) if screenshot_path else QPixmap()
        if pixmap.isNull():
            self._on_worker_failed('Failed to load processed screenshot')
            return

        self._base_pixmap = pixmap
        self._base_scale = (600 / pixmap.width()) if pixmap.width() else 1.0
        self._zoom_multiplier = 1.0
        self.ui_elements = ui_elements
        self.screenshot_data = screenshot_path

        if self.zoom_combo:
            self.zoom_combo.blockSignals(True)
            try:
                default_index = self.zoom_combo.findData(1.0)
                if default_index != -1:
                    self.zoom_combo.setCurrentIndex(default_index)
            finally:
                self.zoom_combo.blockSignals(False)
            self.zoom_combo.setEnabled(True)

        self._apply_scaled_pixmap()

        self.update_hierarchy_tree()
        self.show_success_message(len(ui_elements))

        logger.debug('UI Inspector temp dir active: %s', self._current_temp_dir)

        self._ensure_progress_determinate()
        self.progress_bar.setValue(100)
        self.progress_bar.setFormat('✅ Complete!')
        QTimer.singleShot(1500, lambda: self.progress_bar.setVisible(False))

        self.refresh_btn.setEnabled(True)
        self.refresh_btn.setText('🔄 Refresh')

        logger.info('UI Inspector data refreshed for device: %s - Found %s elements', self.device_serial, len(ui_elements))

    def _on_worker_failed(self, error: Exception) -> None:
        # Treat cancellation as a normal outcome without surfacing an error UI
        if isinstance(error, TaskCancelledError) or str(error).strip() == 'Operation cancelled':
            logger.info('UI Inspector task cancelled for %s', self.device_serial)
            self.refresh_btn.setEnabled(True)
            self.refresh_btn.setText('🔄 Refresh')
            return

        message = str(error)
        logger.error('Error refreshing UI data for %s: %s', self.device_serial, message)

        self._ensure_progress_determinate()
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat('❌ Error occurred')
        self.progress_bar.setVisible(False)

        self.screenshot_label.setText(
            f'❌ Error loading data from {self.device_model}:\n{message}\n\n🔄 Click Refresh to try again'
        )
        self.show_error_message(message)

        self.refresh_btn.setEnabled(True)
        self.refresh_btn.setText('🔄 Refresh')

    def _on_worker_finished(self) -> None:
        self._task_handle = None
        self._worker_start_scheduled = False

    def _cleanup_temp_dir(self) -> None:
        if not self._current_temp_dir:
            return
        try:
            logger.debug('UI Inspector temp dir cleanup start: %s', self._current_temp_dir)
            shutil.rmtree(self._current_temp_dir, ignore_errors=True)
        finally:
            self._current_temp_dir = None
            logger.debug('UI Inspector temp dir cleanup done')


    def update_hierarchy_tree(self):
        """Update the hierarchy tree widget."""
        self.hierarchy_tree.clear()

        if not self.ui_elements:
            return

        filter_key = self._hierarchy_filter_text.casefold()
        if filter_key:
            filtered_elements = [
                element for element in self.ui_elements
                if self._element_matches_filter(element, filter_key)
            ]
        else:
            filtered_elements = list(self.ui_elements)

        if not filtered_elements:
            placeholder = QTreeWidgetItem(self.hierarchy_tree)
            placeholder.setText(0, 'No matching elements')
            placeholder.setFlags(Qt.ItemFlag.NoItemFlags)
            self.hierarchy_tree.expandAll()
            return

        class_groups: dict[str, list[dict]] = {}
        for element in filtered_elements:
            class_name = element.get('class', '').split('.')[-1] if element.get('class') else 'Unknown'
            class_groups.setdefault(class_name, []).append(element)

        for class_name, elements in class_groups.items():
            class_item = QTreeWidgetItem(self.hierarchy_tree)
            class_item.setText(0, f"{class_name} ({len(elements)})")

            for element in elements:
                element_item = QTreeWidgetItem(class_item)
                element_item.setText(0, self._build_element_display_text(element))
                element_item.setData(0, 32, element)  # Store element data

        self.hierarchy_tree.expandAll()

    def on_hierarchy_search_changed(self, raw_text: str) -> None:
        """Filter hierarchy tree items based on search input."""
        normalized = raw_text.strip()
        if normalized == self._hierarchy_filter_text:
            return
        self._hierarchy_filter_text = normalized
        self.update_hierarchy_tree()

    def _build_element_display_text(self, element: dict) -> str:
        """Build display text for hierarchy entries with truncation."""
        display_text = (
            element.get('text')
            or element.get('content_desc')
            or element.get('resource_id')
            or 'No text'
        )

        if len(display_text) > 50:
            return display_text[:50] + '...'
        return display_text

    def _element_matches_filter(self, element: dict, filter_key: str) -> bool:
        """Return True when the element contains the filter token in searchable fields."""
        if not filter_key:
            return True

        searchable_values = [
            element.get('text', ''),
            element.get('content_desc', ''),
            element.get('resource_id', ''),
            element.get('class', ''),
            element.get('package', ''),
        ]

        for value in searchable_values:
            if value and filter_key in value.casefold():
                return True

        bounds = element.get('bounds')
        if bounds and filter_key in str(bounds).casefold():
            return True

        return False

    def on_element_clicked(self, x, y):
        """Handle click on screenshot to select UI element and highlight in tree."""
        # Use optimized utility function to find elements at position
        candidates = find_elements_at_position(self.ui_elements, x, y)

        if candidates:
            # Take the most precise match (smallest element)
            selected_element = candidates[0]

            # Update element details and screenshot highlight
            self.show_element_details(selected_element)
            self.screenshot_label.set_selected_element(selected_element)

            # Find and select the corresponding item in the hierarchy tree
            self.select_element_in_tree(selected_element)

    def select_element_in_tree(self, target_element):
        """Find and select the corresponding element in the hierarchy tree."""
        if not target_element:
            return

        # Clear current selection
        self.hierarchy_tree.clearSelection()

        # Search through all items in the tree
        root = self.hierarchy_tree.invisibleRootItem()
        for i in range(root.childCount()):
            class_item = root.child(i)

            # Search through elements in this class group
            for j in range(class_item.childCount()):
                element_item = class_item.child(j)
                stored_element = element_item.data(0, 32)

                if stored_element and elements_match(stored_element, target_element):
                    # Expand the parent class item
                    class_item.setExpanded(True)

                    # Select and scroll to the element item
                    element_item.setSelected(True)
                    self.hierarchy_tree.scrollToItem(element_item)

                    # Set as current item to give it focus
                    self.hierarchy_tree.setCurrentItem(element_item)

                    logger.info(f'Selected element in tree: {target_element.get("class", "Unknown")}')
                    return

        logger.warning('Could not find matching element in hierarchy tree')


    def on_tree_item_clicked(self, item, column):
        """Handle click on hierarchy tree item."""
        element = item.data(0, 32)
        if element:
            self.show_element_details(element)
            self.screenshot_label.set_selected_element(element)

    # ------------------------------------------------------------------
    # Screenshot zoom helpers
    # ------------------------------------------------------------------
    def _apply_scaled_pixmap(self) -> None:
        if not self._base_pixmap or self._base_pixmap.isNull():
            return

        final_scale = self._base_scale * self._zoom_multiplier
        if final_scale <= 0:
            return

        width = max(1, int(self._base_pixmap.width() * final_scale))
        height = max(1, int(self._base_pixmap.height() * final_scale))
        scaled_pixmap = self._base_pixmap.scaled(
            width,
            height,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )

        self.screenshot_label.setPixmap(scaled_pixmap)
        self.screenshot_label.set_ui_elements(self.ui_elements, final_scale)

    def _on_zoom_combo_changed(self, index: int) -> None:
        if not self.zoom_combo:
            return
        factor = self.zoom_combo.itemData(index)
        if not factor:
            return
        self.set_screenshot_zoom(float(factor))

    def set_screenshot_zoom(self, multiplier: float) -> None:
        """Adjust screenshot zoom while keeping overlays aligned."""
        if multiplier <= 0:
            logger.warning('Ignored invalid zoom multiplier: %s', multiplier)
            return

        self._zoom_multiplier = multiplier

        if self.zoom_combo:
            index = self.zoom_combo.findData(multiplier)
            if index != -1 and self.zoom_combo.currentIndex() != index:
                self.zoom_combo.blockSignals(True)
                try:
                    self.zoom_combo.setCurrentIndex(index)
                finally:
                    self.zoom_combo.blockSignals(False)

        self._apply_scaled_pixmap()

    def on_tree_item_activated(self, item, column):
        """Handle activation (Enter key, double-click) on hierarchy tree item."""
        # Use the same logic as clicking but prevent multiple rapid calls
        self.on_tree_item_clicked(item, column)

    def eventFilter(self, source, event):
        """Filter events to optimize tree widget performance."""
        if source == self.hierarchy_tree:
            # Handle key press events
            if event.type() == event.Type.KeyPress:
                key = event.key()

                # Handle Enter/Return key more efficiently
                if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                    current_item = self.hierarchy_tree.currentItem()
                    if current_item:
                        # Process immediately without waiting for default behavior
                        self.on_tree_item_activated(current_item, 0)
                        return True  # Event handled, don't propagate

                # Handle Space key for expand/collapse
                elif key == Qt.Key.Key_Space:
                    current_item = self.hierarchy_tree.currentItem()
                    if current_item and current_item.childCount() > 0:
                        current_item.setExpanded(not current_item.isExpanded())
                        return True

        # Pass event to parent for default handling
        return super().eventFilter(source, event)

    def show_element_details(self, element):
        """Display comprehensive details of the selected element with enhanced UI."""
        self.clear_element_details()

        # Element header
        class_name = element['class'].split('.')[-1] if element['class'] else 'Unknown'
        header_label = create_element_header(class_name)
        self.element_details_layout.addWidget(header_label)
        self._add_section_spacer()

        # Content section
        content_section = create_content_section(element)
        if content_section:
            self.element_details_layout.addWidget(content_section)
            self._add_section_spacer()

        # Position & Size section
        position_section = create_position_section(element)
        self.element_details_layout.addWidget(position_section)
        self._add_section_spacer()

        # Interaction properties section
        interaction_section = create_interaction_section(element)
        self.element_details_layout.addWidget(interaction_section)
        self._add_section_spacer()

        # Technical details section
        technical_section = create_technical_section(element)
        self.element_details_layout.addWidget(technical_section)
        self._add_section_spacer()

        # Automation tips section
        automation_section = create_automation_section(element)
        self.element_details_layout.addWidget(automation_section)
        self._add_section_spacer()

        # Add stretch to push everything to the top
        self.element_details_layout.addStretch()

    def _add_section_spacer(self):
        """Add a spacer between sections to prevent overlap."""
        spacer = QWidget()
        spacer.setFixedHeight(16)  # Increased spacer height
        # Spacer styling handled by parent layout
        self.element_details_layout.addWidget(spacer)

    def save_screenshot(self):
        """Save the current screenshot."""
        if self.screenshot_data:

            filename, _ = QFileDialog.getSaveFileName(
                self,
                'Save Screenshot',
                f'ui_inspector_{self.device_model}_{common.current_format_time_utc()}.png',
                'PNG files (*.png)'
            )

            if filename:
                shutil.copy2(self.screenshot_data, filename)
                logger.info(f'Screenshot saved to: {filename}')

    def export_hierarchy(self):
        """Export the UI hierarchy to files."""
        if hasattr(self.parent(), 'file_gen_output_path_edit'):
            output_path = self.parent().file_gen_output_path_edit.text().strip()
            if output_path and common.check_exists_dir(output_path):
                # Use the existing dump_device_ui functionality
                dump_device_ui.generate_process(self.device_serial, output_path)

                QMessageBox.information(
                    self,
                    '📁 Export Complete',
                    f'UI hierarchy exported successfully!\n\nLocation: {output_path}'
                )
                return

        # Fallback to file dialog
        directory = QFileDialog.getExistingDirectory(self, 'Select Export Directory')
        if directory:
            dump_device_ui.generate_process(self.device_serial, directory)

            QMessageBox.information(
                self,
                '📁 Export Complete',
                f'UI hierarchy exported successfully!\n\nLocation: {directory}'
            )



__all__ = ["UIInspectorDialog"]
