"""Standalone UI Inspector dialog implementation."""

from __future__ import annotations

import shutil
import threading
from typing import Optional

from PyQt6.QtCore import Qt, QThread, QTimer, pyqtSignal
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import (
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


class UIInspectorWorkerThread(QThread):
    """Dedicated QThread for capturing screenshot and hierarchy data."""

    progress_updated = pyqtSignal(int, str)
    completed = pyqtSignal(dict)
    failed = pyqtSignal(str)

    def __init__(self, device_serial: str):
        super().__init__()
        self.device_serial = device_serial

    def _check_interruption(self) -> None:
        if self.isInterruptionRequested():  # pragma: no cover - defensive
            raise RuntimeError('Operation cancelled')

    def run(self) -> None:  # type: ignore[override]
        temp_dir: Optional[str] = None
        try:
            temp_dir, screenshot_path, xml_path = create_temp_files()
            logger.info(
                'UI Inspector worker started on thread %s for device %s',
                threading.get_ident(),
                self.device_serial,
            )
            logger.info(
                'UI Inspector artifacts at %s (screenshot=%s, xml=%s)',
                temp_dir,
                screenshot_path,
                xml_path,
            )
            self.progress_updated.emit(15, '📸 Capturing screenshot...')
            self._check_interruption()

            if not capture_device_screenshot(self.device_serial, screenshot_path):
                raise RuntimeError('Failed to capture screenshot')

            self.progress_updated.emit(33, '✅ Screenshot captured')
            self._check_interruption()

            self.progress_updated.emit(45, '🌳 Dumping UI hierarchy...')
            if not dump_ui_hierarchy(self.device_serial, xml_path):
                raise RuntimeError('Failed to dump UI hierarchy')

            self.progress_updated.emit(75, '🖼️ Processing screenshot...')
            self._check_interruption()

            ui_elements = parse_ui_elements_cached(xml_path)
            self.progress_updated.emit(90, '🎨 Preparing interface...')

            payload = {
                'temp_dir': temp_dir,
                'screenshot_path': screenshot_path,
                'xml_path': xml_path,
                'ui_elements': ui_elements,
            }
            self.completed.emit(payload)
            logger.info(
                'UI Inspector worker finished on thread %s for %s, elements=%d',
                threading.get_ident(),
                self.device_serial,
                len(ui_elements),
            )

        except Exception as exc:  # pragma: no cover - defensive path
            if temp_dir:
                shutil.rmtree(temp_dir, ignore_errors=True)
            if self.isInterruptionRequested():
                logger.info('UI Inspector worker interrupted for %s', self.device_serial)
                return
            logger.exception('UI Inspector worker failed for %s', self.device_serial)
            self.failed.emit(str(exc))


class UIInspectorDialog(QDialog):
    """Interactive UI Inspector dialog with screenshot and hierarchy overlay."""

    def __init__(self, parent, device_serial, device_model):
        super().__init__(parent)
        self.device_serial = device_serial
        self.device_model = device_model
        self.screenshot_data = None
        self.ui_hierarchy = None
        self.ui_elements = []
        self._progress_is_busy = False
        self._worker_start_scheduled = False

        # Initialize UI Inspector factory for creating UI components
        self.ui_inspector_factory = UIInspectorFactory(parent_dialog=self)

        self.setWindowTitle(f'📱 UI Inspector - {device_model}')
        self.setModal(True)
        self.resize(1200, 800)

        self._worker_thread: Optional[UIInspectorWorkerThread] = None
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
        self.screenshot_label.element_clicked.connect(self.on_element_clicked)
        scroll_area.setWidget(self.screenshot_label)
        scroll_area.setWidgetResizable(True)
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
        if self._worker_thread is not None:
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
        self.screenshot_label.clear()
        self.screenshot_label.setText('🔄 Loading screenshot and UI data...')
        self.screenshot_label.set_ui_elements([], 1.0)
        self.screenshot_label.set_selected_element(None)

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
        self._worker_thread = UIInspectorWorkerThread(self.device_serial)
        self._worker_thread.setObjectName(f'UIInspectorWorker-{self.device_serial}')
        self._worker_thread.progress_updated.connect(self._on_worker_progress)  # type: ignore[arg-type]
        self._worker_thread.completed.connect(self._on_worker_completed)  # type: ignore[arg-type]
        self._worker_thread.failed.connect(self._on_worker_failed)  # type: ignore[arg-type]

        self._worker_thread.start()
        logger.debug(
            'Spawning UIInspectorWorker thread name=%s object_id=%s for %s',
            self._worker_thread.objectName(),
            id(self._worker_thread),
            self.device_serial,
        )

    def _cleanup_worker(self) -> None:
        if self._worker_thread is None:
            return

        try:
            self._worker_thread.requestInterruption()
        except RuntimeError:  # pragma: no cover - thread already gone
            pass

        if not self._worker_thread.wait(5000):  # pragma: no cover - defensive timeout
            logger.warning('Timed out waiting for UIInspectorWorker thread to finish for %s', self.device_serial)
        self._worker_thread.deleteLater()

        self._worker_thread = None
        self._worker_start_scheduled = False
        logger.debug('UIInspectorWorker thread cleaned for %s', self.device_serial)

    def _on_worker_progress(self, value: int, label: str) -> None:
        self._ensure_progress_determinate()
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(value)
        self.progress_bar.setFormat(label)

    def _on_worker_completed(self, payload: dict) -> None:
        self._cleanup_worker()

        temp_dir = payload.get('temp_dir')
        screenshot_path = payload.get('screenshot_path')
        ui_elements = payload.get('ui_elements', [])

        if temp_dir:
            self._current_temp_dir = temp_dir

        pixmap = QPixmap(screenshot_path) if screenshot_path else QPixmap()
        if pixmap.isNull():
            self._on_worker_failed('Failed to load processed screenshot')
            return

        target_width = 600
        scale_factor = target_width / pixmap.width() if pixmap.width() else 1.0
        scaled_pixmap = pixmap.scaled(
            target_width,
            int(pixmap.height() * scale_factor) if pixmap.height() else target_width,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )

        self.screenshot_label.setPixmap(scaled_pixmap)
        self.screenshot_label.set_ui_elements(ui_elements, scale_factor)
        self.screenshot_data = screenshot_path
        self.ui_elements = ui_elements

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

    def _on_worker_failed(self, message: str) -> None:
        logger.error('Error refreshing UI data for %s: %s', self.device_serial, message)
        self._cleanup_worker()

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

        # Group elements by class for better organization
        class_groups = {}
        for element in self.ui_elements:
            class_name = element['class'].split('.')[-1] if element['class'] else 'Unknown'
            if class_name not in class_groups:
                class_groups[class_name] = []
            class_groups[class_name].append(element)

        for class_name, elements in class_groups.items():
            class_item = QTreeWidgetItem(self.hierarchy_tree)
            class_item.setText(0, f"{class_name} ({len(elements)})")

            for element in elements:
                element_item = QTreeWidgetItem(class_item)
                display_text = element['text'] or element['content_desc'] or element['resource_id'] or 'No text'
                if len(display_text) > 50:
                    display_text = display_text[:50] + '...'
                element_item.setText(0, display_text)
                element_item.setData(0, 32, element)  # Store element data

        self.hierarchy_tree.expandAll()

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
