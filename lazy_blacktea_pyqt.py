"""A PyQt6 GUI application for simplifying Android ADB and automation tasks."""

import datetime
import glob
import logging
import os
import platform
import shutil
import subprocess
import sys
import threading
import webbrowser
from typing import Dict, List
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QGridLayout, QSplitter, QTabWidget, QScrollArea, QTextEdit,
    QCheckBox, QPushButton, QLabel,
    QLineEdit, QGroupBox, QFileDialog, QComboBox,
    QMessageBox, QMenu, QStatusBar, QProgressBar,
    QInputDialog, QListWidget, QDialog, QTreeWidget, QTreeWidgetItem
)
from PyQt6.QtCore import (
    Qt, QTimer, pyqtSignal, QMutex, QMutexLocker, QPoint
)
from PyQt6.QtGui import (
    QFont, QTextCursor, QAction, QIcon, QGuiApplication,
    QPainter, QPen, QColor, QBrush, QPixmap, QCursor
)
from PyQt6.QtWidgets import QToolTip

from utils import adb_models
from utils import adb_tools
from utils import common
from utils import dump_device_ui
from utils import json_utils
from utils.ui_inspector_utils import (
    capture_device_screenshot, dump_ui_hierarchy, parse_ui_elements_cached,
    find_elements_at_position, elements_match, create_temp_files
)
from utils.ui_widgets import (
    create_welcome_widget, create_loading_widget, create_success_widget,
    create_error_widget, create_element_header, create_content_section,
    create_position_section, create_interaction_section, create_technical_section,
    create_automation_section
)

# Import configuration and constants
from config.config_manager import ConfigManager
from config.constants import (
    UIConstants, PathConstants, ADBConstants, MessageConstants,
    LoggingConstants, ApplicationConstants
)

# Import new modular components
from ui.error_handler import ErrorHandler, ErrorCode, global_error_handler, setup_exception_hook
from ui.command_executor import CommandExecutor, ensure_devices_selected
from ui.device_manager import DeviceManager
from ui.panels_manager import PanelsManager

# Import new utils modules
from utils.screenshot_utils import take_screenshots_batch, validate_screenshot_path
from utils.recording_utils import RecordingManager, validate_recording_path
from utils.file_generation_utils import (
    generate_bug_report_batch, generate_device_discovery_file,
    validate_file_output_path
)
from utils.debounced_refresh import (
    DeviceListDebouncedRefresh, BatchedUIUpdater, PerformanceOptimizedRefresh
)

logger = common.get_logger('lazy_blacktea')


class ConsoleHandler(logging.Handler):
    """A logging handler that outputs to a QTextEdit widget."""

    def __init__(self, text_widget, parent):
        super().__init__()
        self.text_widget = text_widget
        self.parent = parent
        self.mutex = QMutex()

    def _update_widget(self, msg, levelname):
        """Updates the QTextEdit widget on the main thread."""
        try:
            with QMutexLocker(self.mutex):
                cursor = self.text_widget.textCursor()
                cursor.movePosition(QTextCursor.MoveOperation.End)

                # Use a bright, noticeable color to make sure text is visible
                if levelname == 'WARNING':
                    self.text_widget.setTextColor(Qt.GlobalColor.magenta)  # More visible
                elif levelname == 'ERROR':
                    self.text_widget.setTextColor(Qt.GlobalColor.red)
                elif levelname == 'CRITICAL':
                    font = QFont()
                    font.setBold(True)
                    self.text_widget.setCurrentFont(font)
                    self.text_widget.setTextColor(Qt.GlobalColor.red)
                else:
                    # Use blue for INFO messages to make them clearly visible
                    self.text_widget.setTextColor(Qt.GlobalColor.blue)

                cursor.insertText(msg + '\n')
                self.text_widget.setTextCursor(cursor)
                self.text_widget.ensureCursorVisible()

                # Make sure the text widget updates immediately
                self.text_widget.update()
                self.text_widget.repaint()

        except Exception:
            pass

    def emit(self, record):
        msg = self.format(record)
        # Use QTimer to ensure thread safety
        QTimer.singleShot(0, lambda: self._update_widget(msg, record.levelname))



class ClickableScreenshotLabel(QLabel):
    """A QLabel that emits signals when clicked, for interactive screenshot."""
    element_clicked = pyqtSignal(int, int)

    def __init__(self):
        super().__init__()
        self.ui_elements = []
        self.selected_element = None
        self.scale_factor = 1.0

    def set_ui_elements(self, elements, scale_factor=1.0):
        """Set UI elements for overlay drawing."""
        self.ui_elements = elements
        self.scale_factor = scale_factor
        self.update()

    def set_selected_element(self, element):
        """Highlight a selected element."""
        self.selected_element = element
        self.update()

    def _rectangles_overlap(self, rect1, rect2, overlap_threshold=0.8):
        """Check if two rectangles overlap significantly."""
        x1, y1, w1, h1 = rect1
        x2, y2, w2, h2 = rect2

        # Calculate intersection
        left = max(x1, x2)
        top = max(y1, y2)
        right = min(x1 + w1, x2 + w2)
        bottom = min(y1 + h1, y2 + h2)

        if left >= right or top >= bottom:
            return False  # No intersection

        # Calculate intersection area
        intersection_area = (right - left) * (bottom - top)

        # Calculate areas of both rectangles
        area1 = w1 * h1
        area2 = w2 * h2
        smaller_area = min(area1, area2)

        # Check if overlap is significant (>= threshold of smaller rectangle)
        return intersection_area / smaller_area >= overlap_threshold

    def mousePressEvent(self, event):
        if event.button() == 1:  # Left mouse button
            x = int(event.position().x() / self.scale_factor)
            y = int(event.position().y() / self.scale_factor)
            self.element_clicked.emit(x, y)
        super().mousePressEvent(event)

    def paintEvent(self, event):
        """Override paint event to draw enhanced element overlays with labels."""
        super().paintEvent(event)

        if not self.ui_elements:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setFont(QFont("Arial", 8, QFont.Weight.Bold))

        # Process and draw elements
        processed_elements = self._process_elements()
        if not processed_elements:
            return

        element_count = self._draw_ui_elements(painter, processed_elements)
        self._draw_selected_element(painter)
        self._draw_element_count(painter, element_count)

    def _process_elements(self):
        """Process and filter UI elements for drawing."""
        # Sort elements by importance once
        sorted_elements = sorted(self.ui_elements, key=lambda e: (
            not e.get('clickable', False),
            not bool(e.get('text', '').strip()),
            not bool(e.get('resource_id')),
            not bool(e.get('content_desc'))
        ))

        processed_elements = []
        drawn_bounds = []

        for element in sorted_elements:
            # Calculate scaled bounds once
            bounds = element['bounds']
            scaled_rect = self._calculate_scaled_rect(bounds)
            if not scaled_rect:
                continue

            x1, y1, width, height = scaled_rect

            # Skip if overlaps with existing elements
            if self._check_overlap(scaled_rect, drawn_bounds):
                continue

            # Get element styling
            styling = self._get_element_styling(element, width, height)
            if not styling:
                continue

            processed_elements.append({
                'rect': scaled_rect,
                'styling': styling,
                'element': element
            })
            drawn_bounds.append(scaled_rect)

        return processed_elements

    def _calculate_scaled_rect(self, bounds):
        """Calculate scaled rectangle from bounds."""
        x1 = int(bounds[0] * self.scale_factor)
        y1 = int(bounds[1] * self.scale_factor)
        x2 = int(bounds[2] * self.scale_factor)
        y2 = int(bounds[3] * self.scale_factor)

        width = x2 - x1
        height = y2 - y1

        # Skip very small elements
        if width < 5 or height < 5:
            return None

        return (x1, y1, width, height)

    def _check_overlap(self, current_rect, drawn_bounds):
        """Check if rectangle overlaps with existing bounds."""
        for drawn_rect in drawn_bounds:
            if self._rectangles_overlap(current_rect, drawn_rect, overlap_threshold=0.8):
                return True
        return False

    def _get_element_styling(self, element, width, height):
        """Get styling for an element based on its properties."""
        if element.get('clickable', False):
            if element.get('text'):
                return {
                    'pen_color': QColor(0, 200, 255, 180),
                    'brush_color': QColor(0, 200, 255, 30),
                    'label_bg_color': QColor(0, 150, 255, 200),
                    'label': "🔵"
                }
            return {
                'pen_color': QColor(0, 255, 0, 180),
                'brush_color': QColor(0, 255, 0, 30),
                'label_bg_color': QColor(0, 200, 0, 200),
                'label': "🖱️"
            }
        elif element.get('text') and element['text'].strip():
            return {
                'pen_color': QColor(0, 100, 255, 150),
                'brush_color': QColor(0, 100, 255, 20),
                'label_bg_color': QColor(0, 100, 255, 180),
                'label': "📝"
            }
        elif element.get('resource_id'):
            return {
                'pen_color': QColor(150, 0, 255, 150),
                'brush_color': QColor(150, 0, 255, 20),
                'label_bg_color': QColor(150, 0, 255, 180),
                'label': "🆔"
            }
        elif element.get('content_desc'):
            return {
                'pen_color': QColor(255, 165, 0, 150),
                'brush_color': QColor(255, 165, 0, 20),
                'label_bg_color': QColor(255, 165, 0, 180),
                'label': "💬"
            }
        elif width >= 20 and height >= 20:
            return {
                'pen_color': QColor(128, 128, 128, 100),
                'brush_color': QColor(128, 128, 128, 15),
                'label_bg_color': QColor(128, 128, 128, 150),
                'label': "📦"
            }
        return None

    def _draw_ui_elements(self, painter, processed_elements):
        """Draw UI elements efficiently."""
        element_count = 0

        for item in processed_elements:
            x1, y1, width, height = item['rect']
            styling = item['styling']

            # Draw element background
            painter.setPen(QPen(styling['pen_color'], 1, Qt.PenStyle.SolidLine))
            painter.setBrush(QBrush(styling['brush_color']))
            painter.drawRect(x1, y1, width, height)

            # Draw label for larger elements
            if width > 25 and height > 15:
                self._draw_element_label(painter, x1, y1, styling)

            element_count += 1

        return element_count

    def _draw_element_label(self, painter, x1, y1, styling):
        """Draw label for an element."""
        label_x, label_y, label_size = x1 + 2, y1 + 2, 12

        painter.setPen(QPen(Qt.GlobalColor.transparent))
        painter.setBrush(QBrush(styling['label_bg_color']))
        painter.drawRect(label_x, label_y, label_size, label_size)

        painter.setPen(QPen(Qt.GlobalColor.white))
        painter.drawText(label_x + 1, label_y + 10, styling['label'])

    def _draw_selected_element(self, painter):
        """Draw selected element highlighting."""
        if not self.selected_element:
            return

        scaled_rect = self._calculate_scaled_rect(self.selected_element['bounds'])
        if not scaled_rect:
            return

        x1, y1, width, height = scaled_rect

        # Draw selection highlight
        painter.setPen(QPen(QColor(255, 0, 0, 255), 3, Qt.PenStyle.SolidLine))
        painter.setBrush(QBrush(QColor(255, 0, 0, 50)))
        painter.drawRect(x1, y1, width, height)

        # Draw selection label
        painter.setPen(QPen(Qt.GlobalColor.white))
        painter.setBrush(QBrush(QColor(255, 0, 0, 220)))
        painter.drawRect(x1, y1 - 20, 80, 18)
        painter.drawText(x1 + 5, y1 - 6, "🎯 SELECTED")

    def _draw_element_count(self, painter, element_count):
        """Draw element count indicator."""
        if element_count <= 0:
            return

        painter.setPen(QPen(Qt.GlobalColor.white))
        painter.setBrush(QBrush(QColor(0, 0, 0, 180)))
        text_width = 120
        painter.drawRect(self.width() - text_width - 10, 10, text_width, 20)
        painter.drawText(self.width() - text_width - 5, 25, f"📱 {element_count} elements")


# Logcat classes moved to logcat_viewer.py
from logcat_viewer import LogcatWindow


class UIInspectorDialog(QDialog):
    """Interactive UI Inspector dialog with screenshot and hierarchy overlay."""

    def __init__(self, parent, device_serial, device_model):
        super().__init__(parent)
        self.device_serial = device_serial
        self.device_model = device_model
        self.screenshot_data = None
        self.ui_hierarchy = None
        self.ui_elements = []

        self.setWindowTitle(f'📱 UI Inspector - {device_model}')
        self.setModal(True)
        self.resize(1200, 800)

        self.setup_ui()
        self.refresh_ui_data()

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
        device_info.setStyleSheet('''
            QLabel {
                font-size: 14px;
                font-weight: bold;
                padding: 8px 12px;
                border: 1px solid palette(mid);
                border-radius: 6px;
            }
        ''')
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
        button.setFixedHeight(36)
        button.setStyleSheet('''
            QPushButton {
                padding: 0px 16px;
                font-weight: bold;
                font-size: 12px;
                min-width: 80px;
            }
        ''')
        return button

    def create_screenshot_panel(self):
        """Create the screenshot panel with system styling."""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        # Screenshot header with system styling
        header = QLabel('📸 Device Screenshot')
        header.setStyleSheet('''
            QLabel {
                font-size: 14px;
                font-weight: bold;
                padding: 8px 0px;
                border-bottom: 1px solid palette(mid);
                margin-bottom: 8px;
            }
        ''')
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
        header.setStyleSheet('''
            QLabel {
                font-size: 14px;
                font-weight: bold;
                padding: 8px 0px;
                border-bottom: 1px solid palette(mid);
                margin-bottom: 8px;
            }
        ''')
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
        search_label.setStyleSheet('''
            QLabel {
                font-size: 14px;
                color: #666666;
                padding: 4px;
            }
        ''')
        search_layout.addWidget(search_label)

        self.hierarchy_search = QLineEdit()
        self.hierarchy_search.setPlaceholderText('Search elements...')
        self.hierarchy_search.setStyleSheet('''
            QLineEdit {
                padding: 6px 8px;
                font-size: 12px;
            }
        ''')
        search_layout.addWidget(self.hierarchy_search)

        layout.addWidget(search_widget)

        # Hierarchy tree with system styling
        self.hierarchy_tree = QTreeWidget()
        self.hierarchy_tree.setHeaderLabel('UI Elements')
        self.hierarchy_tree.itemClicked.connect(self.on_tree_item_clicked)
        self.hierarchy_tree.itemActivated.connect(self.on_tree_item_activated)
        self.hierarchy_tree.setStyleSheet('''
            QTreeWidget {
                font-size: 11px;
            }
            QTreeWidget::item {
                padding: 4px;
            }
        ''')

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

    def refresh_ui_data(self):
        """Refresh both screenshot and UI hierarchy data with progress indication."""

        try:
            # Show progress and disable refresh button
            self.progress_bar.setVisible(True)
            self.progress_bar.setValue(0)
            self.progress_bar.setFormat("🔄 Initializing...")
            self.refresh_btn.setEnabled(False)
            self.refresh_btn.setText('🔄 Loading...')

            # Show loading message
            self.screenshot_label.setText('🔄 Loading screenshot and UI data...')
            self.show_loading_message()

            # Create temporary files using optimized utility
            _, screenshot_path, xml_path = create_temp_files()

            # Step 1: Capture screenshot (33% progress)
            self.progress_bar.setValue(15)
            self.progress_bar.setFormat("📸 Capturing screenshot...")

            if not capture_device_screenshot(self.device_serial, screenshot_path):
                raise Exception("Failed to capture screenshot")

            self.progress_bar.setValue(33)
            self.progress_bar.setFormat("✅ Screenshot captured")

            # Step 2: Dump UI hierarchy (66% progress)
            self.progress_bar.setValue(45)
            self.progress_bar.setFormat("🌳 Dumping UI hierarchy...")

            if not dump_ui_hierarchy(self.device_serial, xml_path):
                raise Exception("Failed to dump UI hierarchy")

            self.progress_bar.setValue(75)
            self.progress_bar.setFormat("🖼️ Processing screenshot...")

            # Load screenshot
            pixmap = QPixmap(screenshot_path)
            if not pixmap.isNull():
                # Scale screenshot to fit display
                target_width = 600
                scale_factor = target_width / pixmap.width()
                scaled_pixmap = pixmap.scaled(target_width, int(pixmap.height() * scale_factor), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                self.screenshot_label.setPixmap(scaled_pixmap)
                self.screenshot_data = screenshot_path

                self.progress_bar.setValue(85)
                self.progress_bar.setFormat("🌳 Parsing UI hierarchy...")

                # Parse UI hierarchy using optimized cached function
                self.ui_elements = parse_ui_elements_cached(xml_path)

                self.progress_bar.setValue(95)
                self.progress_bar.setFormat("🎨 Building interface...")

                # Set UI elements for overlay drawing
                self.screenshot_label.set_ui_elements(self.ui_elements, scale_factor)

                # Update tree view
                self.update_hierarchy_tree()

                # Complete progress
                self.progress_bar.setValue(100)
                self.progress_bar.setFormat("✅ Complete!")

                element_count = len(self.ui_elements)
                self.show_success_message(element_count)

                # Hide progress bar after a short delay
                QTimer.singleShot(1500, lambda: self.progress_bar.setVisible(False))

            logger.info(f'UI Inspector data refreshed for device: {self.device_serial} - Found {len(self.ui_elements)} elements')

        except Exception as e:
            logger.error(f'Error refreshing UI data: {e}')
            self.progress_bar.setValue(0)
            self.progress_bar.setFormat("❌ Error occurred")
            self.progress_bar.setVisible(False)

            self.screenshot_label.setText(f'❌ Error loading data from {self.device_model}:\n{str(e)}\n\n🔄 Click Refresh to try again')
            self.show_error_message(str(e))

        finally:
            # Re-enable refresh button
            self.refresh_btn.setEnabled(True)
            self.refresh_btn.setText('🔄 Refresh')


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
        spacer.setStyleSheet('QWidget { background-color: transparent; }')
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


class WindowMain(QMainWindow):
    """Main PyQt6 application window."""

    # Define custom signals for thread-safe UI updates
    recording_stopped_signal = pyqtSignal(str, str, str, str, str)  # device_name, device_serial, duration, filename, output_path
    recording_state_cleared_signal = pyqtSignal(str)  # device_serial
    screenshot_completed_signal = pyqtSignal(str, int, list)  # output_path, device_count, device_models
    file_generation_completed_signal = pyqtSignal(str, str, int, str)  # operation_name, output_path, device_count, icon
    console_output_signal = pyqtSignal(str)  # message

    def __init__(self):
        super().__init__()

        # Initialize new modular components
        self.config_manager = ConfigManager()
        self.error_handler = ErrorHandler(self)
        self.command_executor = CommandExecutor(self)
        self.device_manager = DeviceManager(self)
        self.recording_manager = RecordingManager()
        self.panels_manager = PanelsManager(self)

        # Connect device manager refresh signal to main UI update
        self.device_manager.refresh_thread.devices_updated.connect(self.update_device_list)

        # Setup global error handler and exception hook
        global_error_handler.parent = self
        setup_exception_hook()

        # Initialize variables (keeping some for compatibility)
        self.device_dict: Dict[str, adb_models.DeviceInfo] = {}
        self.check_devices: Dict[str, QCheckBox] = {}
        self.device_groups: Dict[str, List[str]] = {}
        self.refresh_interval = 10
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
        self.screenshot_completed_signal.connect(self._on_screenshot_completed)
        self.file_generation_completed_signal.connect(self._on_file_generation_completed)
        self.console_output_signal.connect(self._on_console_output)

        # Connect panels_manager signals
        self.panels_manager.screenshot_requested.connect(self.take_screenshot)
        self.panels_manager.recording_start_requested.connect(self.start_screen_record)
        self.panels_manager.recording_stop_requested.connect(self.stop_screen_record)

        self.user_scale = 1.0
        self.scrcpy_available = self._check_scrcpy_available()  # Check if scrcpy is installed

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
        self.load_config()

        # Initialize groups list (now that UI is created)
        self.update_groups_listbox()

        # Start device refresh with delay to avoid GUI blocking
        QTimer.singleShot(250, self.device_manager.start_device_refresh)

    def init_ui(self):
        """Initialize the user interface."""
        logger.info('[INIT] init_ui method started')
        self.setWindowTitle(f'🍵 {ApplicationConstants.APP_NAME}')
        self.setGeometry(100, 100, UIConstants.WINDOW_WIDTH, UIConstants.WINDOW_HEIGHT)


        # Set application icon
        self.set_app_icon()

        # Set global tooltip styling for better positioning and appearance
        self.setStyleSheet(self.styleSheet() + '''
            QToolTip {
                background-color: rgba(45, 45, 45, 0.95);
                color: white;
                border: 1px solid rgba(255, 255, 255, 0.2);
                border-radius: 6px;
                padding: 6px;
                font-size: 11px;
                font-family: 'Segoe UI', Arial, sans-serif;
                max-width: 350px;
            }
        ''')

        # Remove the problematic attribute setting as it's not needed for tooltip positioning

        # Create central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # Create main layout
        main_layout = QVBoxLayout(central_widget)

        # Create menu bar
        self.panels_manager.create_menu_bar(self)

        # Create main splitter
        main_splitter = QSplitter(Qt.Orientation.Horizontal)
        main_layout.addWidget(main_splitter)

        # Create device list panel
        # Create device panel using panels_manager
        device_components = self.panels_manager.create_device_panel(main_splitter, self)
        self.title_label = device_components['title_label']
        self.device_scroll = device_components['device_scroll']
        self.device_widget = device_components['device_widget']
        self.device_layout = device_components['device_layout']
        self.no_devices_label = device_components['no_devices_label']

        # Create tools panel
        self.create_tools_panel(main_splitter)

        # Set splitter proportions
        main_splitter.setSizes([400, 800])

        # Create console panel at bottom
        self.create_console_panel(main_layout)

        # Create status bar
        self.create_status_bar()

    def set_app_icon(self):
        """Set the application icon."""

        # Try different icon formats based on the platform
        icon_paths = [
            'assets/icons/icon_128x128.png',  # Default for cross-platform
            'assets/icons/AppIcon.icns',      # macOS format
            'assets/icons/app_icon.ico'       # Windows format
        ]

        for icon_path in icon_paths:
            if os.path.exists(icon_path):
                try:
                    # Set window icon
                    self.setWindowIcon(QIcon(icon_path))
                    # Set application icon (for taskbar/dock)
                    QApplication.instance().setWindowIcon(QIcon(icon_path))
                    logger.debug(f"Successfully loaded app icon from {icon_path}")
                    break
                except Exception as e:
                    logger.warning(f"Failed to load icon from {icon_path}: {e}")
                    continue
        else:
            logger.warning("No suitable app icon found")



    def create_tools_panel(self, parent):
        """Create the tools panel with tabs."""
        tools_widget = QWidget()
        tools_layout = QVBoxLayout(tools_widget)

        # Create tab widget
        tab_widget = QTabWidget()
        tools_layout.addWidget(tab_widget)

        # Initialize critical UI elements first to prevent attribute errors
        self.output_path_edit = QLineEdit()
        self.file_gen_output_path_edit = QLineEdit()  # Restore text field for File Generation
        self.groups_listbox = QListWidget()
        self.group_name_edit = QLineEdit()

        # Create all tabs immediately to ensure proper initialization
        # (Lazy loading caused attribute errors with configuration loading)
        self.create_adb_tools_tab(tab_widget)
        self.create_shell_commands_tab(tab_widget)
        self.create_file_generation_tab(tab_widget)
        self.create_device_groups_tab(tab_widget)

        parent.addWidget(tools_widget)


    def create_adb_tools_tab(self, tab_widget):
        """Create the ADB tools tab with categorized functions."""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # Output path section
        output_group = QGroupBox('Output Path')
        output_layout = QHBoxLayout(output_group)

        self.output_path_edit.setPlaceholderText('Select output directory...')
        output_layout.addWidget(self.output_path_edit)

        browse_btn = QPushButton('Browse')
        browse_btn.clicked.connect(lambda: self.browse_output_path())
        output_layout.addWidget(browse_btn)

        layout.addWidget(output_group)

        # Logcat section
        logcat_group = QGroupBox('📄 Logcat')
        logcat_layout = QGridLayout(logcat_group)

        # Clear logcat button
        clear_logcat_btn = QPushButton('🗑️ Clear Logcat')
        clear_logcat_btn.clicked.connect(lambda: self.clear_logcat())
        logcat_layout.addWidget(clear_logcat_btn, 0, 0)

        # Android Bug Report button
        bug_report_btn = QPushButton('📊 Android Bug Report')
        bug_report_btn.clicked.connect(lambda: self.generate_android_bug_report())
        logcat_layout.addWidget(bug_report_btn, 0, 1)

        # View Logcat button
        view_logcat_btn = QPushButton('👁️ View Logcat')
        view_logcat_btn.clicked.connect(lambda: self.show_logcat())
        logcat_layout.addWidget(view_logcat_btn, 1, 0)

        layout.addWidget(logcat_group)

        # Device Control section
        device_control_group = QGroupBox('📱 Device Control')
        device_control_layout = QGridLayout(device_control_group)

        device_actions = [
            ('🔄 Reboot Device', self.reboot_device),
            ('📦 Install APK', self.install_apk),
            ('🔵 Enable Bluetooth', self.enable_bluetooth),
            ('🔴 Disable Bluetooth', self.disable_bluetooth),
        ]

        # Add scrcpy action if available
        if self.scrcpy_available:
            device_actions.append(('🖥️ Mirror Device (scrcpy)', self.launch_scrcpy))

        for i, (text, func) in enumerate(device_actions):
            btn = QPushButton(text)
            btn.clicked.connect(lambda checked, f=func: f())
            row, col = divmod(i, 2)
            device_control_layout.addWidget(btn, row, col)

        layout.addWidget(device_control_group)

        # Screen Capture & Recording section (combined)
        capture_group = QGroupBox('📱 Screen Capture & Recording')
        capture_layout = QGridLayout(capture_group)

        # Screenshot button
        self.screenshot_btn = QPushButton('📷 Take Screenshot')
        self.screenshot_btn.clicked.connect(lambda: self.take_screenshot())
        # Set initial default style
        self.screenshot_btn.setStyleSheet('''
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                padding: 8px 12px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:pressed {
                background-color: #3d8b40;
            }
        ''')
        capture_layout.addWidget(self.screenshot_btn, 0, 0)

        # Recording buttons
        self.start_record_btn = QPushButton('🎥 Start Screen Record')
        self.start_record_btn.clicked.connect(lambda: self.start_screen_record())
        capture_layout.addWidget(self.start_record_btn, 1, 0)

        self.stop_record_btn = QPushButton('⏹️ Stop Screen Record')
        self.stop_record_btn.clicked.connect(lambda: self.stop_screen_record())
        capture_layout.addWidget(self.stop_record_btn, 1, 1)

        # Recording status display
        self.recording_status_label = QLabel('No active recordings')
        self.recording_status_label.setStyleSheet('color: gray; font-style: italic;')
        capture_layout.addWidget(self.recording_status_label, 2, 0, 1, 2)

        # Recording timer display
        self.recording_timer_label = QLabel('')
        self.recording_timer_label.setStyleSheet('color: red; font-weight: bold;')
        capture_layout.addWidget(self.recording_timer_label, 3, 0, 1, 2)

        layout.addWidget(capture_group)

        layout.addStretch()
        tab_widget.addTab(tab, 'ADB Tools')

    def update_recording_status(self):
        """Update recording status display using new recording manager."""
        if not hasattr(self, 'recording_status_label'):
            return

        # Get all recording statuses from new manager
        all_statuses = self.recording_manager.get_all_recording_statuses()
        active_recordings = []

        for serial, status in all_statuses.items():
            if 'Recording' in status:
                # Get device model for display
                device_model = 'Unknown'
                if serial in self.device_dict:
                    device_model = self.device_dict[serial].device_model

                # Extract duration from status (format: "Recording (MM:SS)")
                duration_part = status.split('(')[1].rstrip(')')
                active_recordings.append(f"{device_model} ({serial[:8]}...): {duration_part}")

        active_count = self.recording_manager.get_active_recordings_count()

        if active_count > 0:
            status_text = f"🔴 Recording: {active_count} device(s)"
            self.recording_status_label.setText(status_text)
            self.recording_status_label.setStyleSheet('color: red; font-weight: bold;')

            # Limit display to first 8 recordings to prevent UI overflow
            if len(active_recordings) > 8:
                display_recordings = active_recordings[:8] + [f"... and {len(active_recordings) - 8} more device(s)"]
            else:
                display_recordings = active_recordings

            self.recording_timer_label.setText('\n'.join(display_recordings))
        else:
            self.recording_status_label.setText('No active recordings')
            self.recording_status_label.setStyleSheet('color: gray; font-style: italic;')
            self.recording_timer_label.setText('')

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

    def create_shell_commands_tab(self, tab_widget):
        """Create the enhanced shell commands tab with batch execution and history."""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # Command Templates section
        template_group = QGroupBox('📋 Command Templates')
        template_layout = QGridLayout(template_group)

        template_commands = [
            ('📱 Device Info', 'getprop ro.build.version.release'),
            ('🔋 Battery Info', 'dumpsys battery'),
            ('📊 Memory Info', 'dumpsys meminfo'),
            ('🌐 Network Info', 'dumpsys connectivity'),
            ('📱 App List', 'pm list packages -3'),
            ('🗑️ Clear Cache', 'pm trim-caches 1000000000'),
        ]

        for i, (name, command) in enumerate(template_commands):
            btn = QPushButton(name)
            btn.clicked.connect(lambda checked, cmd=command: self.add_template_command(cmd))
            row, col = divmod(i, 3)
            template_layout.addWidget(btn, row, col)

        layout.addWidget(template_group)

        # Batch Commands section
        batch_group = QGroupBox('📝 Batch Commands')
        batch_layout = QVBoxLayout(batch_group)

        # Commands text area
        self.batch_commands_edit = QTextEdit()
        self.batch_commands_edit.setPlaceholderText(
            'Enter multiple commands (one per line):\n'
            'getprop ro.build.version.release\n'
            'dumpsys battery\n'
            'pm list packages -3\n\n'
            'Use # for comments'
        )
        self.batch_commands_edit.setMaximumHeight(120)
        batch_layout.addWidget(self.batch_commands_edit)

        # Execution buttons
        exec_buttons_layout = QHBoxLayout()

        run_single_btn = QPushButton('▶️ Run Single Command')
        run_single_btn.clicked.connect(lambda: self.run_single_command())
        exec_buttons_layout.addWidget(run_single_btn)

        run_batch_btn = QPushButton('🚀 Run All Commands')
        run_batch_btn.clicked.connect(lambda: self.run_batch_commands())
        exec_buttons_layout.addWidget(run_batch_btn)


        batch_layout.addLayout(exec_buttons_layout)
        layout.addWidget(batch_group)

        # Command History section
        history_group = QGroupBox('📜 Command History')
        history_layout = QVBoxLayout(history_group)

        self.command_history_list = QListWidget()
        self.command_history_list.setMaximumHeight(100)
        self.command_history_list.itemDoubleClicked.connect(self.load_from_history)
        history_layout.addWidget(self.command_history_list)

        history_buttons_layout = QHBoxLayout()

        clear_history_btn = QPushButton('🗑️ Clear')
        clear_history_btn.clicked.connect(lambda: self.clear_command_history())
        history_buttons_layout.addWidget(clear_history_btn)

        export_history_btn = QPushButton('📤 Export')
        export_history_btn.clicked.connect(lambda: self.export_command_history())
        history_buttons_layout.addWidget(export_history_btn)

        import_history_btn = QPushButton('📥 Import')
        import_history_btn.clicked.connect(lambda: self.import_command_history())
        history_buttons_layout.addWidget(import_history_btn)

        history_layout.addLayout(history_buttons_layout)
        layout.addWidget(history_group)

        layout.addStretch()

        # Initialize command history
        self.command_history = []
        self.load_command_history_from_config()

        tab_widget.addTab(tab, 'Shell Commands')


    def create_file_generation_tab(self, tab_widget):
        """Create the file generation tab with independent output path."""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # Output path section (matching ADB Tools format)
        output_group = QGroupBox('Output Path')
        output_layout = QHBoxLayout(output_group)

        self.file_gen_output_path_edit.setPlaceholderText('Select output directory...')
        output_layout.addWidget(self.file_gen_output_path_edit)

        browse_btn = QPushButton('Browse')
        browse_btn.clicked.connect(lambda: self.browse_file_generation_output_path())
        output_layout.addWidget(browse_btn)

        layout.addWidget(output_group)

        # File Generation Tools section
        generation_group = QGroupBox('🛠️ File Generation Tools')
        generation_layout = QGridLayout(generation_group)

        generation_actions = [
            ('🔍 Device Discovery', self.generate_device_discovery_file),
            ('📷 Device DCIM Pull', self.pull_device_dcim_with_folder),
            ('📱 UI Inspector', self.launch_ui_inspector),
            ('📁 Export UI Hierarchy', self.dump_device_hsv),
        ]

        for i, (text, func) in enumerate(generation_actions):
            btn = QPushButton(text)
            btn.clicked.connect(lambda checked, f=func: f())
            row, col = divmod(i, 2)
            generation_layout.addWidget(btn, row, col)

        layout.addWidget(generation_group)
        layout.addStretch()

        tab_widget.addTab(tab, 'File Generation')

    def create_device_groups_tab(self, tab_widget):
        """Create the device groups management tab."""
        tab = QWidget()
        layout = QHBoxLayout(tab)

        # Left side: Create/Edit Group
        left_group = QGroupBox('Create/Update Group')
        left_layout = QVBoxLayout(left_group)

        # Group name input
        name_layout = QHBoxLayout()
        name_layout.addWidget(QLabel('Group Name:'))
        self.group_name_edit.setPlaceholderText('Enter group name...')
        name_layout.addWidget(self.group_name_edit)
        left_layout.addLayout(name_layout)

        # Save group button
        save_group_btn = QPushButton('Save Current Selection as Group')
        save_group_btn.clicked.connect(lambda: self.save_group())
        left_layout.addWidget(save_group_btn)

        left_layout.addStretch()
        layout.addWidget(left_group)

        # Right side: Group List
        right_group = QGroupBox('Existing Groups')
        right_layout = QVBoxLayout(right_group)

        # Groups list (using pre-initialized widget)
        self.groups_listbox.itemSelectionChanged.connect(self.on_group_select)
        right_layout.addWidget(self.groups_listbox)

        # Group action buttons
        group_buttons_layout = QHBoxLayout()

        select_group_btn = QPushButton('Select Devices in Group')
        select_group_btn.clicked.connect(lambda: self.select_devices_in_group())
        group_buttons_layout.addWidget(select_group_btn)

        delete_group_btn = QPushButton('Delete Selected Group')
        delete_group_btn.clicked.connect(lambda: self.delete_group())
        group_buttons_layout.addWidget(delete_group_btn)

        right_layout.addLayout(group_buttons_layout)
        layout.addWidget(right_group)

        tab_widget.addTab(tab, 'Device Groups')

    def create_console_panel(self, parent_layout):
        """Create the console output panel."""
        console_group = QGroupBox('Console Output')
        console_layout = QVBoxLayout(console_group)

        self.console_text = QTextEdit()
        self.console_text.setReadOnly(True)
        # Use system monospace font instead of specific 'Courier' to avoid font lookup delays
        console_font = QFont()
        console_font.setFamily('Monaco' if platform.system() == 'Darwin' else 'Consolas' if platform.system() == 'Windows' else 'monospace')
        console_font.setPointSize(9)
        self.console_text.setFont(console_font)
        self.console_text.setMaximumHeight(200)

        # Ensure console is visible with clear styling
        self.console_text.setStyleSheet("""
            QTextEdit {
                background-color: white;
                color: black;
                border: 2px solid #cccccc;
                padding: 5px;
            }
        """)

        # Add a welcome message to verify the console is working
        welcome_msg = """🍵 Console Output Ready - Logging initialized

"""
        self.console_text.setPlainText(welcome_msg)
        logger.info('Console widget initialized and ready')
        self.write_to_console("✅ Console output system ready")

        # Enable context menu for console
        self.console_text.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.console_text.customContextMenuRequested.connect(self.show_console_context_menu)

        console_layout.addWidget(self.console_text)

        # Setup console handler for all loggers
        console_handler = ConsoleHandler(self.console_text, self)
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(
            logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        )


        # Replace existing StreamHandler with our ConsoleHandler
        # Remove any existing StreamHandler from common.py
        for handler in logger.handlers[:]:
            if isinstance(handler, logging.StreamHandler) and not isinstance(handler, ConsoleHandler):
                logger.removeHandler(handler)

        # Add our custom ConsoleHandler
        if not any(isinstance(h, ConsoleHandler) for h in logger.handlers):
            logger.addHandler(console_handler)
        else:
            pass

        logger.setLevel(logging.INFO)

        # For other module loggers, just ensure they propagate to main logger
        related_loggers = ['adb_tools', 'common', 'ui_inspector_utils', 'dump_device_ui']
        for logger_name in related_loggers:
            module_logger = logging.getLogger(logger_name)
            module_logger.setLevel(logging.INFO)
            # Make sure they propagate to main logger (which has our ConsoleHandler)
            module_logger.propagate = True

        parent_layout.addWidget(console_group)


    def create_status_bar(self):
        """Create the status bar."""
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)

        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.status_bar.addPermanentWidget(self.progress_bar)

        self.status_bar.showMessage('Ready')

    def get_checked_devices(self) -> List[adb_models.DeviceInfo]:
        """Get list of checked devices."""
        checked_devices = []
        for serial, checkbox in self.check_devices.items():
            if checkbox.isChecked() and serial in self.device_dict:
                checked_devices.append(self.device_dict[serial])
        return checked_devices

    def show_info(self, title: str, message: str):
        """Show info message box."""
        QMessageBox.information(self, title, message)

    def show_warning(self, title: str, message: str):
        """Show warning message box."""
        QMessageBox.warning(self, title, message)

    def show_error(self, title: str, message: str):
        """Show error message box."""
        QMessageBox.critical(self, title, message)

    def set_ui_scale(self, scale: float):
        """Set UI scale factor."""
        self.user_scale = scale
        font = self.font()
        font.setPointSize(int(10 * scale))
        self.setFont(font)
        logger.debug(f'UI scale set to {scale}')

    def set_refresh_interval(self, interval: int):
        """Set device refresh interval."""
        self.refresh_interval = interval
        if hasattr(self, 'device_refresh_thread'):
            self.device_refresh_thread.set_refresh_interval(interval)
        logger.debug(f'Refresh interval set to {interval} seconds')

    def update_device_list(self, device_dict: Dict[str, adb_models.DeviceInfo]):
        """Update the device list display without rebuilding UI."""
        self.device_dict = device_dict

        # Batch UI updates for better performance
        self.device_scroll.setUpdatesEnabled(False)

        # Get currently checked devices to preserve state
        checked_serials = set()
        for serial, checkbox in self.check_devices.items():
            if checkbox.isChecked():
                checked_serials.add(serial)

        # Find devices to add and remove
        current_serials = set(self.check_devices.keys())
        new_serials = set(device_dict.keys())

        # Remove devices that are no longer connected
        for serial in current_serials - new_serials:
            if serial in self.check_devices:
                checkbox = self.check_devices[serial]
                checkbox.setParent(None)
                checkbox.deleteLater()  # Proper memory cleanup
                del self.check_devices[serial]

        # Add new devices
        for serial in new_serials - current_serials:
            if serial in device_dict:
                device = device_dict[serial]

                # Create enhanced device display with operation status
                operation_status = self._get_device_operation_status(serial)
                recording_status = self._get_device_recording_status(serial)

                # Format GMS version for display
                gms_display = device.gms_version if device.gms_version and device.gms_version != 'N/A' else 'N/A'

                device_text = (
                    f'{operation_status}{recording_status}📱 {device.device_model:<20} | '
                    f'🆔 {device.device_serial_num:<20} | '
                    f'🤖 Android {device.android_ver:<2} (API {device.android_api_level:<2}) | '
                    f'🎯 GMS: {gms_display:<12} | '
                    f'📶 WiFi: {self._get_on_off_status(device.wifi_is_on):<3} | '
                    f'🔵 BT: {self._get_on_off_status(device.bt_is_on)}'
                )
                checkbox = QCheckBox(device_text)
                checkbox.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
                checkbox.customContextMenuRequested.connect(lambda pos, serial=serial, cb=checkbox: self.show_device_context_menu(pos, serial, cb))

                # Get enhanced tooltip using unified method
                tooltip_text = self._create_device_tooltip(device, serial)

                # Use custom tooltip positioning instead of default
                checkbox.setToolTip("")  # Clear default tooltip
                checkbox.enterEvent = lambda event, txt=tooltip_text, cb=checkbox: self._show_custom_tooltip(cb, txt, event)
                checkbox.leaveEvent = lambda event: QToolTip.hideText()

                checkbox.setFont(QFont('Segoe UI', 10))  # Modern font for better readability

                # Add visual selection indicator styling
                self._apply_device_checkbox_style(checkbox)

                # Restore checked state if it was previously checked
                if serial in checked_serials:
                    checkbox.setChecked(True)

                # Connect to update selection count and visual feedback
                checkbox.stateChanged.connect(self.update_selection_count)
                checkbox.stateChanged.connect(lambda state, cb=checkbox: self._update_checkbox_visual_state(cb, state))

                self.check_devices[serial] = checkbox
                # Insert before the stretch item (which is always the last item)
                insert_index = self.device_layout.count() - 1
                self.device_layout.insertWidget(insert_index, checkbox)

        # Update existing device info (tooltip) without recreating checkbox
        for serial in new_serials & current_serials:
            if serial in self.check_devices and serial in device_dict:
                device = device_dict[serial]
                checkbox = self.check_devices[serial]
                # Update text with enhanced formatting and operation status
                operation_status = self._get_device_operation_status(serial)
                recording_status = self._get_device_recording_status(serial)

                # Format GMS version for display
                gms_display = device.gms_version if device.gms_version and device.gms_version != 'N/A' else 'N/A'

                device_text = (
                    f'{operation_status}{recording_status}📱 {device.device_model:<15} | '
                    f'🆔 {device.device_serial_num:<15} | '
                    f'🤖 Android {device.android_ver:<2} (API {device.android_api_level:<2}) | '
                    f'🎯 GMS: {gms_display:<12} | '
                    f'📶 WiFi: {self._get_on_off_status(device.wifi_is_on):<3} | '
                    f'🔵 BT: {self._get_on_off_status(device.bt_is_on)}'
                )
                checkbox.setText(device_text)

                # Update tooltip using unified method
                tooltip_text = self._create_device_tooltip(device, serial)

                # Update custom tooltip positioning for existing checkboxes
                checkbox.setToolTip("")  # Clear default tooltip
                checkbox.enterEvent = lambda event, txt=tooltip_text, cb=checkbox: self._show_custom_tooltip(cb, txt, event)
                checkbox.leaveEvent = lambda event: QToolTip.hideText()

                # Apply visual styling to existing checkboxes
                self._apply_device_checkbox_style(checkbox)

        # Update title with device count
        device_count = len(device_dict)
        selected_count = len(checked_serials & new_serials)
        self.title_label.setText(f'Connected Devices ({device_count}) - Selected: {selected_count}')

        # Re-enable UI updates after batch operations
        self.device_scroll.setUpdatesEnabled(True)

        # Handle no devices case
        if not device_dict:
            if not hasattr(self, 'no_devices_label') or not self.no_devices_label.parent():
                self.no_devices_label = QLabel('No devices found')
                self.no_devices_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                insert_index = self.device_layout.count() - 1
                self.device_layout.insertWidget(insert_index, self.no_devices_label)
        else:
            # Remove no devices label if devices are present
            if hasattr(self, 'no_devices_label') and self.no_devices_label.parent():
                self.no_devices_label.setParent(None)

    def refresh_device_list(self):
        """Manually refresh device list."""
        try:
            devices = adb_tools.get_devices_list()
            device_dict = {device.device_serial_num: device for device in devices}
            self.update_device_list(device_dict)
            logger.info('Device list refreshed manually')
        except Exception as e:
            logger.error(f'Error refreshing device list: {e}')
            self.show_error('Error', f'Failed to refresh device list: {e}')

    def select_all_devices(self):
        """Select all connected devices."""
        for checkbox in self.check_devices.values():
            checkbox.setChecked(True)
        logger.info(f'Selected all {len(self.check_devices)} devices')

    def select_no_devices(self):
        """Deselect all devices."""
        for checkbox in self.check_devices.values():
            checkbox.setChecked(False)
        logger.info('Deselected all devices')

    # Device Groups functionality
    def save_group(self):
        """Save the currently selected devices as a group."""
        group_name = self.group_name_edit.text().strip()
        if not group_name:
            self.show_error('Error', 'Group name cannot be empty.')
            return

        checked_devices = self.get_checked_devices()
        if not checked_devices:
            self.show_error('Warning', 'No devices selected to save in the group.')
            return

        # Check if group already exists
        if group_name in self.device_groups:
            reply = QMessageBox.question(
                self,
                'Confirm',
                f"Group '{group_name}' already exists. Do you want to overwrite it?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply != QMessageBox.StandardButton.Yes:
                return

        serial_numbers = [device.device_serial_num for device in checked_devices]
        self.device_groups[group_name] = serial_numbers

        self.show_info(
            'Success',
            f"Group '{group_name}' saved with {len(serial_numbers)} devices."
        )
        self.update_groups_listbox()
        logger.info(f"Saved group '{group_name}' with devices: {serial_numbers}")

    def delete_group(self):
        """Delete the selected group."""
        current_item = self.groups_listbox.currentItem()
        if not current_item:
            self.show_error('Error', 'No group selected to delete.')
            return

        group_name = current_item.text()
        reply = QMessageBox.question(
            self,
            'Confirm',
            f"Are you sure you want to delete group '{group_name}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            if group_name in self.device_groups:
                del self.device_groups[group_name]
                logger.info(f"Group '{group_name}' deleted.")
                self.update_groups_listbox()
                self.group_name_edit.clear()

    def select_devices_in_group(self):
        """Select devices in the phone list that belong to the selected group."""
        current_item = self.groups_listbox.currentItem()
        if not current_item:
            self.show_error('Error', 'No group selected.')
            return

        group_name = current_item.text()
        self.select_devices_in_group_by_name(group_name)

    def select_devices_in_group_by_name(self, group_name: str):
        """Select devices in the phone list that belong to the given group name."""
        serials_in_group = self.device_groups.get(group_name, [])
        if not serials_in_group:
            logger.info(f"Group '{group_name}' is empty.")
            return

        # First, clear all selections
        self.select_no_devices()

        # Select devices that are in the group and currently connected
        connected_devices = 0
        missing_devices = []

        for serial in serials_in_group:
            if serial in self.check_devices:
                self.check_devices[serial].setChecked(True)
                connected_devices += 1
            else:
                missing_devices.append(serial)

        if missing_devices:
            self.show_info(
                'Info',
                f"The following devices from group '{group_name}' are not currently connected:\n" +
                '\n'.join(missing_devices)
            )

        logger.info(f"Selected {connected_devices} devices in group '{group_name}'.")

    def update_groups_listbox(self):
        """Update the listbox with current group names."""
        self.groups_listbox.clear()
        for group_name in sorted(self.device_groups.keys()):
            self.groups_listbox.addItem(group_name)

    def on_group_select(self):
        """Handle selection of a group in the listbox."""
        current_item = self.groups_listbox.currentItem()
        if current_item:
            group_name = current_item.text()
            self.group_name_edit.setText(group_name)

    # Context Menu functionality
    def show_device_list_context_menu(self, position):
        """Show context menu for device list."""
        context_menu = QMenu(self)

        # Basic actions
        refresh_action = context_menu.addAction('Refresh')
        refresh_action.triggered.connect(lambda: self.refresh_device_list())

        select_all_action = context_menu.addAction('Select All')
        select_all_action.triggered.connect(lambda: self.select_all_devices())

        clear_all_action = context_menu.addAction('Clear All')
        clear_all_action.triggered.connect(lambda: self.select_no_devices())

        copy_info_action = context_menu.addAction('Copy Selected Device Info')
        copy_info_action.triggered.connect(lambda: self.copy_selected_device_info())

        context_menu.addSeparator()

        # Group selection submenu
        if self.device_groups:
            group_menu = context_menu.addMenu('Select Group')
            for group_name in sorted(self.device_groups.keys()):
                group_action = group_menu.addAction(group_name)
                group_action.triggered.connect(
                    lambda checked, g=group_name: self.select_devices_in_group_by_name(g)
                )
        else:
            group_action = context_menu.addAction('Select Group')
            group_action.setEnabled(False)
            group_action.setText('No groups available')

        context_menu.addSeparator()

        # Device-specific actions (if devices are selected)
        checked_devices = self.get_checked_devices()
        if checked_devices:
            reboot_action = context_menu.addAction('Reboot Selected')
            reboot_action.triggered.connect(lambda: self.reboot_device())

            enable_bt_action = context_menu.addAction('Enable Bluetooth')
            enable_bt_action.triggered.connect(lambda: self.enable_bluetooth())

            disable_bt_action = context_menu.addAction('Disable Bluetooth')
            disable_bt_action.triggered.connect(lambda: self.disable_bluetooth())

        # Show menu at the cursor position
        global_pos = self.device_scroll.mapToGlobal(position)
        context_menu.exec(global_pos)

    def copy_selected_device_info(self):
        """Copy selected device information to clipboard with comprehensive details."""
        checked_devices = self.get_checked_devices()
        if not checked_devices:
            self.show_info('Info', 'No devices selected.')
            return

        device_info_sections = []

        for i, device in enumerate(checked_devices):
            # Generate comprehensive device information in plain text
            device_info = []
            device_info.append(f"Device #{i+1}")
            device_info.append("=" * 50)

            # Basic Information
            device_info.append("BASIC INFORMATION:")
            device_info.append(f"Model: {device.device_model}")
            device_info.append(f"Serial Number: {device.device_serial_num}")
            device_info.append(f"Product: {device.device_prod}")
            device_info.append(f"USB: {device.device_usb}")
            device_info.append("")

            # System Information
            device_info.append("SYSTEM INFORMATION:")
            device_info.append(f"Android Version: {device.android_ver}")
            device_info.append(f"API Level: {device.android_api_level}")
            device_info.append(f"GMS Version: {device.gms_version}")
            device_info.append(f"Build Fingerprint: {device.build_fingerprint}")
            device_info.append("")

            # Connectivity
            device_info.append("CONNECTIVITY:")
            device_info.append(f"WiFi Status: {self._get_on_off_status(device.wifi_is_on)}")
            device_info.append(f"Bluetooth Status: {self._get_on_off_status(device.bt_is_on)}")
            device_info.append("")

            # Try to get additional hardware information
            try:
                additional_info = self._get_additional_device_info(device.device_serial_num)
                device_info.append("HARDWARE INFORMATION:")
                device_info.append(f"Screen Size: {additional_info.get('screen_size', 'Unknown')}")
                device_info.append(f"Screen Density: {additional_info.get('screen_density', 'Unknown')}")
                device_info.append(f"CPU Architecture: {additional_info.get('cpu_arch', 'Unknown')}")
                device_info.append("")
                device_info.append("BATTERY INFORMATION:")
                device_info.append(f"Battery Level: {additional_info.get('battery_level', 'Unknown')}")
                device_info.append(f"Battery Capacity: {additional_info.get('battery_capacity_mah', 'Unknown')}")
                device_info.append(f"Battery mAs: {additional_info.get('battery_mas', 'Unknown')}")
                device_info.append(f"Estimated DOU: {additional_info.get('battery_dou_hours', 'Unknown')}")
            except Exception as e:
                device_info.append("HARDWARE INFORMATION:")
                device_info.append("Hardware information unavailable")
                logger.warning(f"Could not get additional info for {device.device_serial_num}: {e}")

            device_info_sections.append('\n'.join(device_info))

        # Combine all device information
        header = f"ANDROID DEVICE INFORMATION REPORT\nGenerated: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\nTotal Devices: {len(checked_devices)}\n\n"
        footer = "\n" + "=" * 50 + "\nReport generated by lazy blacktea PyQt6 version"

        full_info_text = header + '\n\n'.join(device_info_sections) + footer

        # Copy to clipboard
        clipboard = QApplication.clipboard()
        clipboard.setText(full_info_text)

        self.show_info('Success', f'Copied comprehensive information for {len(checked_devices)} device(s) to clipboard.\n\nInformation includes:\n• Basic device details\n• System information\n• Connectivity status\n• Hardware specifications')
        logger.info(f'Copied comprehensive device info to clipboard: {len(checked_devices)} devices')

    def show_console_context_menu(self, position):
        """Show context menu for console."""
        context_menu = QMenu(self)

        # Copy action
        copy_action = context_menu.addAction('Copy')
        copy_action.triggered.connect(lambda: self.copy_console_text())

        # Clear action
        clear_action = context_menu.addAction('Clear Console')
        clear_action.triggered.connect(lambda: self.clear_console())

        # Show menu at the cursor position
        global_pos = self.console_text.mapToGlobal(position)
        context_menu.exec(global_pos)

    def copy_console_text(self):
        """Copy selected console text to clipboard."""
        cursor = self.console_text.textCursor()
        if cursor.hasSelection():
            selected_text = cursor.selectedText()
            clipboard = QApplication.clipboard()
            clipboard.setText(selected_text)
            logger.info('Copied selected console text to clipboard')
        else:
            # If no selection, copy all console text
            all_text = self.console_text.toPlainText()
            clipboard = QApplication.clipboard()
            clipboard.setText(all_text)
            logger.info('Copied all console text to clipboard')

    def clear_console(self):
        """Clear the console output."""
        self.console_text.clear()
        logger.info('Console cleared')

    def _get_on_off_status(self, status):
        """Convert boolean status to On/Off string, similar to original Tkinter version."""
        if status is None or status == 'None':
            return 'Unknown'
        return 'On' if status else 'Off'

    def _get_device_operation_status(self, serial: str) -> str:
        """Get operation status indicator for device."""
        if serial in self.device_operations:
            operation = self.device_operations[serial]
            return f'⚙️ {operation.upper()} | '
        return ''

    def _get_device_recording_status(self, serial: str) -> str:
        """Get recording status indicator for device."""
        if (serial in self.device_recordings and
            self.device_recordings[serial] and
            self.device_recordings[serial].get('active', False)):
            return '🔴 REC | '
        return ''

    def _create_device_tooltip(self, device, serial):
        """Create enhanced tooltip with device information - unified method."""
        base_tooltip = (
            f'📱 Device Information\n'
            f'━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n'
            f'Model: {device.device_model}\n'
            f'Serial: {device.device_serial_num}\n'
            f'Android: {device.android_ver} (API Level {device.android_api_level})\n'
            f'GMS Version: {device.gms_version}\n'
            f'Product: {device.device_prod}\n'
            f'USB: {device.device_usb}\n'
            f'━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n'
            f'📡 Connectivity\n'
            f'WiFi: {self._get_on_off_status(device.wifi_is_on)}\n'
            f'Bluetooth: {self._get_on_off_status(device.bt_is_on)}\n'
            f'━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n'
            f'🔧 Build Information\n'
            f'Build Fingerprint: {device.build_fingerprint[:50]}...'
        )

        # Try to get additional info, but don't block UI for it
        try:
            additional_info = self._get_additional_device_info(serial)
            extended_tooltip = base_tooltip + (
                f'\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n'
                f'🖥️ Hardware Information\n'
                f'Screen Size: {additional_info.get("screen_size", "Unknown")}\n'
                f'Screen Density: {additional_info.get("screen_density", "Unknown")}\n'
                f'CPU Architecture: {additional_info.get("cpu_arch", "Unknown")}\n'
                f'━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n'
                f'🔋 Battery Information\n'
                f'Battery Level: {additional_info.get("battery_level", "Unknown")}\n'
                f'Battery Capacity: {additional_info.get("battery_capacity_mah", "Unknown")}\n'
                f'Battery mAs: {additional_info.get("battery_mas", "Unknown")}\n'
                f'Estimated DOU: {additional_info.get("battery_dou_hours", "Unknown")}'
            )
            return extended_tooltip
        except:
            return base_tooltip

    def _get_additional_device_info(self, serial_num):
        """Get additional device information for enhanced display."""
        try:
            # Use utils functions where possible
            return adb_tools.get_additional_device_info(serial_num)
        except Exception as e:
            logger.error(f'Error getting additional device info for {serial_num}: {e}')
            return {
                'screen_density': 'Unknown',
                'screen_size': 'Unknown',
                'battery_level': 'Unknown',
                'battery_capacity_mah': 'Unknown',
                'battery_mas': 'Unknown',
                'battery_dou_hours': 'Unknown',
                'cpu_arch': 'Unknown'
            }

    def _apply_device_checkbox_style(self, checkbox):
        """Apply visual styling to device checkbox for better selection feedback."""
        checkbox.setStyleSheet('''
            QCheckBox {
                padding: 8px;
                border: 2px solid transparent;
                border-radius: 6px;
                background-color: rgba(240, 240, 240, 0.3);
                margin: 2px;
            }
            QCheckBox:hover {
                background-color: rgba(200, 220, 255, 0.5);
                border: 2px solid rgba(100, 150, 255, 0.3);
            }
            QCheckBox:checked {
                background-color: rgba(100, 200, 100, 0.2);
                border: 2px solid rgba(50, 150, 50, 0.6);
                font-weight: bold;
            }
            QCheckBox:checked:hover {
                background-color: rgba(100, 200, 100, 0.3);
                border: 2px solid rgba(50, 150, 50, 0.8);
            }
            QCheckBox::indicator {
                width: 16px;
                height: 16px;
                border-radius: 3px;
                border: 2px solid #666;
                background-color: white;
            }
            QCheckBox::indicator:checked {
                background-color: #4CAF50;
                border: 2px solid #4CAF50;
                image: url(data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMTAiIGhlaWdodD0iNyIgdmlld0JveD0iMCAwIDEwIDciIGZpbGw9Im5vbmUiIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyI+CjxwYXRoIGQ9Ik04LjUgMUwzLjUgNkwxLjUgNCIgc3Ryb2tlPSJ3aGl0ZSIgc3Ryb2tlLXdpZHRoPSIyIiBzdHJva2UtbGluZWNhcD0icm91bmQiIHN0cm9rZS1saW5lam9pbj0icm91bmQiLz4KPHN2Zz4K);
            }
            QCheckBox::indicator:hover {
                border: 2px solid #2196F3;
            }
        ''')

    def _update_checkbox_visual_state(self, checkbox, state):
        """Update visual state of checkbox when selection changes."""
        # The styling is handled by CSS, but we can add additional visual feedback here if needed
        if state == 2:  # Checked state
            # Add selected visual indicator (handled by CSS)
            pass
        else:  # Unchecked state
            # Remove selected visual indicator (handled by CSS)
            pass

    def _create_custom_tooltip_checkbox(self, device_text, tooltip_text):
        """Create a checkbox with custom tooltip positioning."""
        checkbox = QCheckBox(device_text)

        # Remove default tooltip and add custom event handling
        checkbox.setToolTip("")  # Clear default tooltip
        checkbox.enterEvent = lambda event: self._show_custom_tooltip(checkbox, tooltip_text, event)
        checkbox.leaveEvent = lambda event: QToolTip.hideText()

        return checkbox

    def _show_custom_tooltip(self, widget, tooltip_text, event):
        """Show custom positioned tooltip near cursor."""
        # Get global cursor position
        cursor_pos = QCursor.pos()

        # Offset tooltip very close to cursor (5px right, 5px down)
        tooltip_pos = QPoint(cursor_pos.x() + 5, cursor_pos.y() + 5)

        # Show tooltip at custom position
        QToolTip.showText(tooltip_pos, tooltip_text, widget)

    def _check_scrcpy_available(self):
        """Check if scrcpy is available in the system and get version info."""

        is_available, version_output = adb_tools.check_tool_availability('scrcpy')

        if is_available:
            logger.info(f'scrcpy is available: {version_output}')

            # Extract version number for compatibility checks
            if 'scrcpy' in version_output:
                # Parse version like "scrcpy 3.3.2"
                try:
                    version_line = version_output.split('\n')[0]
                    version_str = version_line.split()[1]
                    major_version = int(version_str.split('.')[0])
                    self.scrcpy_major_version = major_version
                    logger.info(f'Detected scrcpy major version: {major_version}')
                except (IndexError, ValueError):
                    self.scrcpy_major_version = 2  # Default to older version
                    logger.warning('Could not parse scrcpy version, assuming v2.x')
            else:
                self.scrcpy_major_version = 2

            return True
        else:
            logger.info('scrcpy is not available')
            self.scrcpy_major_version = None
            return False

    def update_selection_count(self):
        """Update the title to show current selection count."""
        device_count = len(self.device_dict)
        selected_count = len(self.get_checked_devices())
        self.title_label.setText(f'Connected Devices ({device_count}) - Selected: {selected_count}')

    def show_device_context_menu(self, position, device_serial, checkbox_widget):
        """Show context menu for individual device."""
        if device_serial not in self.device_dict:
            return

        device = self.device_dict[device_serial]
        context_menu = QMenu(self)
        # Use system default styling for context menu
        context_menu.setStyleSheet('''
            QMenu::item:disabled {
                font-weight: bold;
            }
            QMenu::separator {
                height: 1px;
                background-color: #E0E0E0;
                margin: 4px 0px;
            }
        ''')

        # Device info header
        device_name = f'📱 {device.device_model} ({device_serial[:8]}...)'
        header_action = context_menu.addAction(device_name)
        header_action.setEnabled(False)
        # Note: QAction doesn't support setStyleSheet, styling is handled by QMenu
        context_menu.addSeparator()

        # Quick selection actions
        select_only_action = context_menu.addAction('✅ Select Only This Device')
        select_only_action.triggered.connect(lambda: self.select_only_device(device_serial))

        deselect_action = context_menu.addAction('❌ Deselect This Device')
        deselect_action.triggered.connect(lambda: self.deselect_device(device_serial))

        context_menu.addSeparator()

        # UI Inspector action (only if this device is selected)
        if checkbox_widget.isChecked():
            ui_inspector_action = context_menu.addAction('🔍 Launch UI Inspector')
            ui_inspector_action.triggered.connect(lambda: self.launch_ui_inspector_for_device(device_serial))
            context_menu.addSeparator()

        # Device-specific actions
        reboot_action = context_menu.addAction('🔄 Reboot Device')
        reboot_action.triggered.connect(lambda: self.reboot_single_device(device_serial))

        screenshot_action = context_menu.addAction('📷 Take Screenshot')
        screenshot_action.triggered.connect(lambda: self.take_screenshot_single_device(device_serial))

        scrcpy_action = context_menu.addAction('🖥️ Mirror Device (scrcpy)')
        scrcpy_action.triggered.connect(lambda: self.launch_scrcpy_single_device(device_serial))

        context_menu.addSeparator()

        # Copy device info
        copy_info_action = context_menu.addAction('📋 Copy Device Info')
        copy_info_action.triggered.connect(lambda: self.copy_single_device_info(device_serial))

        # Show context menu
        global_pos = checkbox_widget.mapToGlobal(position)
        context_menu.exec(global_pos)

    def select_only_device(self, target_serial):
        """Select only the specified device, deselect all others."""
        for serial, checkbox in self.check_devices.items():
            checkbox.setChecked(serial == target_serial)

    def deselect_device(self, target_serial):
        """Deselect the specified device."""
        if target_serial in self.check_devices:
            self.check_devices[target_serial].setChecked(False)

    def launch_ui_inspector_for_device(self, device_serial):
        """Launch UI Inspector for a specific device."""
        if device_serial in self.device_dict:
            device = self.device_dict[device_serial]
            logger.info(f'Launching UI Inspector for device: {device.device_model} ({device_serial})')
            ui_inspector = UIInspectorDialog(self, device_serial, device.device_model)
            ui_inspector.exec()

    def reboot_single_device(self, device_serial):
        """Reboot a single device."""
        self.run_in_thread(adb_tools.run_reboot_devices, [device_serial])
        logger.info(f'Rebooting device: {device_serial}')

    def take_screenshot_single_device(self, device_serial):
        """Take screenshot for a single device."""
        if device_serial in self.device_dict:
            device = self.device_dict[device_serial]

            # Use the configured output path
            output_path = self.output_path_edit.text().strip()
            if not output_path or not common.check_exists_dir(output_path):
                output_path = common.get_full_path('~/Desktop')

            self.run_in_thread(adb_tools.run_take_screenshots, [device_serial], [device.device_model], output_path)
            logger.info(f'Taking screenshot for device: {device.device_model} ({device_serial})')

    def launch_scrcpy_single_device(self, device_serial):
        """Launch scrcpy for a single device."""
        self.run_in_thread(adb_tools.run_setup_scrcpy, [device_serial])
        logger.info(f'Launching scrcpy for device: {device_serial}')

    def copy_single_device_info(self, device_serial):
        """Copy information for a single device."""
        if device_serial in self.device_dict:
            device = self.device_dict[device_serial]
            device_info = f'''Device Information:
Model: {device.device_model}
Serial: {device.device_serial_num}
Android Version: {device.android_ver} (API Level {device.android_api_level})
GMS Version: {device.gms_version}
Product: {device.device_prod}
USB: {device.device_usb}
WiFi Status: {self._get_on_off_status(device.wifi_is_on)}
Bluetooth Status: {self._get_on_off_status(device.bt_is_on)}
Build Fingerprint: {device.build_fingerprint}'''

            try:
                clipboard = QGuiApplication.clipboard()
                clipboard.setText(device_info)
                self.show_info('📋 Copied!', f'Device information copied to clipboard for:\n{device.device_model}')
                logger.info(f'📋 Copied device info to clipboard: {device_serial}')
            except Exception as e:
                logger.error(f'❌ Failed to copy device info to clipboard: {e}')
                self.show_error('Error', f'Could not copy to clipboard:\n{e}')

    def browse_output_path(self):
        """Browse for output directory."""
        directory = QFileDialog.getExistingDirectory(self, 'Select Output Directory')
        if directory:
            # Use common.py to ensure proper path handling
            normalized_path = common.make_gen_dir_path(directory)
            self.output_path_edit.setText(normalized_path)

    def browse_file_generation_output_path(self):
        """Browse and select file generation output directory."""
        directory = QFileDialog.getExistingDirectory(self, 'Select File Generation Output Directory')
        if directory:
            # Use common.py to ensure proper path handling
            normalized_path = common.make_gen_dir_path(directory)
            self.file_gen_output_path_edit.setText(normalized_path)
            logger.info(f'Selected file generation output directory: {normalized_path}')


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

    def _run_adb_tool_on_selected_devices(self, tool_func, description: str, *args, show_progress=True, **kwargs):
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

        # Trigger device list refresh to show operation status
        QTimer.singleShot(100, self.refresh_device_list)

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
                # Clear operation status for all devices
                QTimer.singleShot(0, lambda: self._clear_device_operations(serials))

        self.run_in_thread(wrapper)

    def _clear_device_operations(self, serials):
        """Clear operation status for specified devices."""
        for serial in serials:
            if serial in self.device_operations:
                del self.device_operations[serial]
        # Refresh device list to update display
        self.refresh_device_list()

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
        """Install APK on selected devices with enhanced progress display."""
        apk_file, _ = QFileDialog.getOpenFileName(self, 'Select APK File', '', 'APK Files (*.apk)')
        if apk_file:
            devices = self.get_checked_devices()
            apk_name = os.path.basename(apk_file)

            # Show enhanced progress notification
            self.error_handler.show_info('📦 APK Installation',
                                       f'Installing {apk_name} to {len(devices)} device(s)...\n\n'
                                       f'📱 Devices: {len(devices)} selected\n'
                                       f'📄 APK: {apk_name}\n\n'
                                       f'Please wait, installation in progress...')

            # Install with progress tracking
            def install_with_progress():
                try:
                    self._install_apk_with_progress(devices, apk_file, apk_name)
                except Exception as e:
                    logger.error(f'APK installation failed: {e}')
                    self.error_handler.handle_error(ErrorCode.COMMAND_EXECUTION_FAILED, str(e))

            # Run in background thread
            import threading
            thread = threading.Thread(target=install_with_progress)
            thread.daemon = True
            thread.start()

            logger.info(f'Installing APK {apk_file} to {len(devices)} devices')

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
        self.refresh_device_list()

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
                self.refresh_device_list()
            except Exception as signal_error:
                logger.error(f'🔧 [CALLBACK RECEIVED] Signal emission failed: {signal_error}')
                import traceback
                logger.error(f'🔧 [CALLBACK RECEIVED] Traceback: {traceback.format_exc()}')

        take_screenshots_batch(devices, validated_path, screenshot_callback)

    @ensure_devices_selected
    def start_screen_record(self):
        """Start screen recording using new recording manager."""
        output_path = self.output_path_edit.text().strip()

        # Validate output path using utils
        validated_path = validate_recording_path(output_path)
        if not validated_path:
            self.error_handler.handle_error(ErrorCode.FILE_NOT_FOUND,
                                           'Please select a valid output directory first.')
            return

        devices = self.get_checked_devices()

        # Check if any devices are already recording
        already_recording = []
        for device in devices:
            if self.recording_manager.is_recording(device.device_serial_num):
                already_recording.append(f"{device.device_model} ({device.device_serial_num[:8]}...)")

        if already_recording:
            self.error_handler.show_warning(
                'Devices Already Recording',
                f'The following devices are already recording:\n\n'
                f'{chr(10).join(already_recording)}\n\n'
                f'Please stop these recordings first or select different devices.'
            )
            return

        device_count = len(devices)

        # Show info about recording
        self.error_handler.show_info(
            'Screen Recording Started',
            f'Starting recording on {device_count} device(s)...\n\n'
            f'📍 Important Notes:\n'
            f'• ADB has a 3-minute recording limit per session\n'
            f'• Each device records independently\n'
            f'• You can stop recording manually or it will auto-stop\n\n'
            f'Files will be saved to: {validated_path}'
        )

        # Use new recording manager with callback
        def recording_callback(device_name, device_serial, duration, filename, output_path):
            self.recording_stopped_signal.emit(device_name, device_serial, duration, filename, output_path)

        success = self.recording_manager.start_recording(devices, validated_path, recording_callback)
        if not success:
            self.error_handler.handle_error(ErrorCode.COMMAND_FAILED, 'Failed to start recording')

    def _on_recording_stopped(self, device_name, device_serial, duration, filename, output_path):
        """Handle recording stopped signal in main thread."""
        logger.info(f'🔴 [SIGNAL] _on_recording_stopped executing in main thread for {device_serial}')
        self.show_info(
            'Recording Stopped',
            f'Recording stopped for {device_name}\n'
            f'Duration: {duration}\n'
            f'File: {filename}.mp4\n'
            f'Location: {output_path}'
        )
        logger.info(f'🔴 [SIGNAL] _on_recording_stopped completed for {device_serial}')

    def _on_recording_state_cleared(self, device_serial):
        """Handle recording state cleared signal in main thread."""
        logger.info(f'🔄 [SIGNAL] _on_recording_state_cleared executing in main thread for {device_serial}')
        if device_serial in self.device_recordings:
            logger.info(f'🔄 [SIGNAL] Setting active=False for {device_serial}')
            self.device_recordings[device_serial]['active'] = False
        if device_serial in self.device_operations:
            logger.info(f'🔄 [SIGNAL] Removing operation for {device_serial}')
            del self.device_operations[device_serial]
        logger.info(f'🔄 [SIGNAL] Triggering UI refresh for {device_serial}')
        self.refresh_device_list()
        self.update_recording_status()
        logger.info(f'🔄 [SIGNAL] _on_recording_state_cleared completed for {device_serial}')

    def _on_screenshot_completed(self, output_path, device_count, device_models):
        """Handle screenshot completed signal in main thread."""
        logger.info(f'📷 [SIGNAL] _on_screenshot_completed executing in main thread')

        # Create enhanced success message
        device_list = ', '.join(device_models[:3])
        if len(device_models) > 3:
            device_list += f' and {len(device_models) - 3} more'

        # Show a simple success notification instead of modal dialog
        self.show_info('📷 Screenshots Completed',
                      f'✅ Successfully captured {device_count} screenshot(s)\n'
                      f'📱 Devices: {device_list}\n'
                      f'📁 Location: {output_path}')

        # Restore screenshot button state
        self._update_screenshot_button_state(False)

        logger.info(f'📷 [SIGNAL] _on_screenshot_completed notification shown')
        return  # Skip the dialog creation


    def _open_folder(self, path):
        """Open the specified folder in system file manager."""

        try:
            if platform.system() == 'Darwin':  # macOS
                subprocess.run(['open', path])
            elif platform.system() == 'Windows':  # Windows
                subprocess.run(['explorer', path])
            else:  # Linux
                subprocess.run(['xdg-open', path])
            logger.info(f'📁 Opened folder: {path}')
        except Exception as e:
            logger.error(f'❌ Failed to open folder: {e}')
            self.show_error('Error', f'Could not open folder:\n{path}\n\nError: {e}')

    def _show_screenshot_quick_actions(self, output_path, device_models):
        """Show quick actions menu for screenshots."""

        dialog = QDialog(self)
        dialog.setWindowTitle('⚡ Screenshot Quick Actions')
        dialog.setModal(True)
        dialog.resize(350, 250)

        layout = QVBoxLayout(dialog)

        # Title
        title_label = QLabel('⚡ Quick Actions for Screenshots')
        title_label.setStyleSheet('font-weight: bold; font-size: 14px; color: #1976D2; margin-bottom: 10px;')
        layout.addWidget(title_label)

        # Find screenshot files
        screenshot_files = []
        try:
            # Look for common screenshot file patterns
            patterns = ['*.png', '*.jpg', '*.jpeg']
            for pattern in patterns:
                screenshot_files.extend(glob.glob(os.path.join(output_path, pattern)))
            screenshot_files = sorted(screenshot_files, key=os.path.getmtime, reverse=True)
        except Exception as e:
            logger.error(f'Error finding screenshots: {e}')

        # Info label
        info_label = QLabel(f'📱 Screenshots from: {", ".join(device_models[:2])}{"..." if len(device_models) > 2 else ""}')
        info_label.setStyleSheet('color: #424242; margin-bottom: 15px;')
        layout.addWidget(info_label)

        # Action buttons
        button_style = '''
            QPushButton {
                background-color: #F5F5F5;
                border: 1px solid #E0E0E0;
                padding: 10px;
                border-radius: 5px;
                text-align: left;
                margin: 2px;
            }
            QPushButton:hover {
                background-color: #E3F2FD;
                border-color: #1976D2;
            }
        '''

        # Take another screenshot
        another_screenshot_btn = QPushButton('📷 Take Another Screenshot')
        another_screenshot_btn.setStyleSheet(button_style)
        another_screenshot_btn.clicked.connect(lambda: (dialog.accept(), self.take_screenshot()))
        layout.addWidget(another_screenshot_btn)

        # Start recording
        start_recording_btn = QPushButton('🎥 Start Recording Same Devices')
        start_recording_btn.setStyleSheet(button_style)
        start_recording_btn.clicked.connect(lambda: (dialog.accept(), self.start_screen_record()))
        layout.addWidget(start_recording_btn)

        # Copy path to clipboard
        copy_path_btn = QPushButton('📋 Copy Folder Path')
        copy_path_btn.setStyleSheet(button_style)
        copy_path_btn.clicked.connect(lambda: self._copy_to_clipboard(output_path))
        layout.addWidget(copy_path_btn)

        # Show file count if available
        if screenshot_files:
            file_count_label = QLabel(f'📁 Found {len(screenshot_files)} screenshot file(s)')
            file_count_label.setStyleSheet('color: #666; font-size: 12px; margin-top: 10px;')
            layout.addWidget(file_count_label)

        # Close button
        close_btn = QPushButton('Close')
        close_btn.setStyleSheet('''
            QPushButton {
                background-color: #757575;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                margin-top: 10px;
            }
            QPushButton:hover {
                background-color: #616161;
            }
        ''')
        close_btn.clicked.connect(dialog.accept)
        layout.addWidget(close_btn)

        dialog.exec()

    def _copy_to_clipboard(self, text):
        """Copy text to system clipboard."""
        try:
            clipboard = QGuiApplication.clipboard()
            clipboard.setText(text)
            self.show_info('📋 Copied!', f'Path copied to clipboard:\n{text}')
            logger.info(f'📋 Copied to clipboard: {text}')
        except Exception as e:
            logger.error(f'❌ Failed to copy to clipboard: {e}')
            self.show_error('Error', f'Could not copy to clipboard:\n{e}')

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
        self.refresh_device_list()
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
            self.screenshot_btn.setStyleSheet('''
                QPushButton {
                    background-color: #FF9800;
                    color: white;
                    border: none;
                    padding: 8px 12px;
                    border-radius: 4px;
                    font-weight: bold;
                }
            ''')
        else:
            logger.info(f'🔧 [BUTTON STATE] Resetting screenshot button to default state')
            self.screenshot_btn.setText('📷 Take Screenshot')
            self.screenshot_btn.setEnabled(True)
            # Set proper default style
            self.screenshot_btn.setStyleSheet('''
                QPushButton {
                    background-color: #4CAF50;
                    color: white;
                    border: none;
                    padding: 8px 12px;
                    border-radius: 4px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #45a049;
                }
                QPushButton:pressed {
                    background-color: #3d8b40;
                }
            ''')
            logger.info('📷 [BUTTON STATE] Screenshot button reset to default state successfully')

    def _on_file_generation_completed(self, operation_name, output_path, device_count, icon):
        """Handle file generation completed signal in main thread."""
        logger.info(f'{icon} [SIGNAL] _on_file_generation_completed executing in main thread')

        # Create enhanced success dialog similar to screenshot completion
        dialog = QDialog(self)
        dialog.setWindowTitle(f'{icon} {operation_name} Completed')
        dialog.setModal(True)
        dialog.resize(450, 200)

        layout = QVBoxLayout(dialog)

        # Success message
        success_label = QLabel(f'✅ Successfully completed {operation_name.lower()}')
        success_label.setStyleSheet('font-weight: bold; color: #2E7D32; font-size: 14px;')
        layout.addWidget(success_label)

        # Device info
        device_label = QLabel(f'📱 Processed: {device_count} device(s)')
        device_label.setStyleSheet('color: #424242; margin: 10px 0px;')
        layout.addWidget(device_label)

        # Path info
        path_label = QLabel(f'📁 Location: {output_path}')
        path_label.setStyleSheet('color: #424242; word-wrap: break-word;')
        path_label.setWordWrap(True)
        layout.addWidget(path_label)

        # Button layout
        button_layout = QHBoxLayout()

        # Open folder button
        open_folder_btn = QPushButton('🗂️ Open Folder')
        open_folder_btn.setStyleSheet('''
            QPushButton {
                background-color: #1976D2;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #1565C0;
            }
        ''')
        open_folder_btn.clicked.connect(lambda: self._open_folder(output_path))
        button_layout.addWidget(open_folder_btn)

        # Close button
        close_btn = QPushButton('Close')
        close_btn.setStyleSheet('''
            QPushButton {
                background-color: #757575;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #616161;
            }
        ''')
        close_btn.clicked.connect(dialog.accept)
        button_layout.addWidget(close_btn)

        layout.addWidget(QLabel())  # Spacer
        layout.addLayout(button_layout)

        dialog.exec()
        logger.info(f'{icon} [SIGNAL] _on_file_generation_completed dialog closed')

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
            print(f'Error in _on_console_output: {e}')

    def _clear_device_recording(self, serial):
        """Clear recording state for a specific device."""
        if serial in self.device_recordings:
            self.device_recordings[serial]['active'] = False
            # Also remove from device operations if it exists
            if serial in self.device_operations and self.device_operations[serial] == 'Recording':
                del self.device_operations[serial]
            # Force refresh device list to update display
            self.refresh_device_list()
            # Update recording status panel
            self.update_recording_status()
        else:
            pass

    def stop_screen_record(self):
        """Stop screen recording using new recording manager."""
        # Check if there are any active recordings
        if self.recording_manager.get_active_recordings_count() == 0:
            self.error_handler.show_warning('No Active Recordings',
                                           'No active recordings found.\n\n'
                                           'Please start recording first, or the recordings may have already stopped automatically.')
            return

        # Get selected devices to determine which recordings to stop
        selected_devices = self.get_checked_devices()

        if selected_devices:
            # Stop recording only on selected devices
            devices_to_stop = []
            for device in selected_devices:
                if self.recording_manager.is_recording(device.device_serial_num):
                    devices_to_stop.append(device.device_serial_num)

            if not devices_to_stop:
                # Show which devices are currently recording
                all_statuses = self.recording_manager.get_all_recording_statuses()
                recording_list = []
                for serial, status in all_statuses.items():
                    if 'Recording' in status and serial in self.device_dict:
                        device_name = self.device_dict[serial].device_model
                        recording_list.append(f"{device_name} ({serial[:8]}...)")

                self.error_handler.show_warning(
                    'No Selected Devices Recording',
                    f'None of the selected devices are currently recording.\n\n'
                    f'Currently recording devices:\n{chr(10).join(recording_list)}\n\n'
                    f'Please select the devices you want to stop recording.'
                )
                return

            # Stop recording on specific devices
            for serial in devices_to_stop:
                self.recording_manager.stop_recording(serial)
                logger.info(f'Stopped recording for device: {serial}')
        else:
            # Stop all recordings if no devices are selected
            stopped_devices = self.recording_manager.stop_recording()
            logger.info(f'Stopped all recordings on {len(stopped_devices)} devices')

    @ensure_devices_selected
    def enable_bluetooth(self):
        """Enable Bluetooth on selected devices."""
        def bluetooth_wrapper(serials):
            adb_tools.switch_bluetooth_enable(serials, True)
            # Trigger device list refresh to update status
            QTimer.singleShot(1000, self.refresh_device_list)

        # Disable progress dialog, only show completion notification
        self._run_adb_tool_on_selected_devices(bluetooth_wrapper, 'enable Bluetooth', show_progress=False)

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
            QTimer.singleShot(1000, self.refresh_device_list)

        # Disable progress dialog, only show completion notification
        self._run_adb_tool_on_selected_devices(bluetooth_wrapper, 'disable Bluetooth', show_progress=False)

        # Show completion notification immediately
        devices = self.get_checked_devices()
        device_count = len(devices)
        self.show_info('🔴 Disable Bluetooth Complete',
                      f'✅ Successfully disabled Bluetooth on {device_count} device(s)')

    @ensure_devices_selected
    def clear_logcat(self):
        """Clear logcat on selected devices."""
        def logcat_wrapper(serials):
            for serial in serials:
                adb_tools.clear_device_logcat(serial)

        self._run_adb_tool_on_selected_devices(logcat_wrapper, 'clear logcat')

    @ensure_devices_selected
    def show_logcat(self):
        """Show logcat viewer for selected device."""
        selected_devices = self.get_checked_devices()
        if not selected_devices:
            self.show_error('Error', 'Please select a device.')
            return

        # For now, only support single device
        if len(selected_devices) > 1:
            self.show_error('Error', 'Please select only one device for logcat viewing.')
            return

        device = selected_devices[0]
        # Create and show logcat window
        self.logcat_window = LogcatWindow(device, self)
        self.logcat_window.show()

    # Shell commands
    @ensure_devices_selected
    def run_shell_command(self):
        """Run shell command on selected devices."""
        command = self.shell_cmd_edit.text().strip()
        if not command:
            self.show_error('Error', 'Please enter a command.')
            return

        devices = self.get_checked_devices()
        if not devices:
            self.show_error('Error', 'No devices selected.')
            return

        serials = [d.device_serial_num for d in devices]
        device_count = len(devices)

        logger.info(f'Running shell command "{command}" on {device_count} device(s): {serials}')
        self.show_info('Shell Command', f'Running command on {device_count} device(s):\n"{command}"\n\nCheck console output for results.')

        def shell_wrapper():
            try:
                # The function expects a list of serials, not individual serials
                adb_tools.run_adb_shell_command(serials, command)
                QTimer.singleShot(0, lambda: logger.info(f'Shell command "{command}" completed on all devices'))
            except Exception as e:
                raise e  # Re-raise to be handled by run_in_thread

        self.run_in_thread(shell_wrapper)

    # Enhanced command execution methods
    def add_template_command(self, command):
        """Add a template command to the batch commands area."""
        current_text = self.batch_commands_edit.toPlainText()
        if current_text:
            new_text = current_text + '\n' + command
        else:
            new_text = command
        self.batch_commands_edit.setPlainText(new_text)

    @ensure_devices_selected
    def run_single_command(self):
        """Run the currently selected/first command from batch area."""
        text = self.batch_commands_edit.toPlainText().strip()
        if not text:
            self.show_error('Error', 'Please enter commands in the batch area.')
            return

        # Get cursor position to determine which line to execute
        cursor = self.batch_commands_edit.textCursor()
        current_line = cursor.blockNumber()

        lines = text.split('\n')
        if current_line < len(lines):
            command = lines[current_line].strip()
        else:
            command = lines[0].strip()  # Default to first line

        # Skip comments and empty lines
        if not command or command.startswith('#'):
            self.show_error('Error', 'Selected line is empty or a comment.')
            return

        self.execute_single_command(command)

    @ensure_devices_selected
    def run_batch_commands(self):
        """Run all commands simultaneously."""
        commands = self.get_valid_commands()
        if not commands:
            self.show_error('Error', 'No valid commands found. Please enter commands in the Batch Commands area.')
            return

        devices = self.get_checked_devices()
        serials = [d.device_serial_num for d in devices]
        device_count = len(devices)

        self.show_info('Batch Commands',
                      f'Running {len(commands)} commands simultaneously on {device_count} device(s):\n\n' +
                      '\n'.join(f'• {cmd}' for cmd in commands[:5]) +
                      (f'\n... and {len(commands)-5} more' if len(commands) > 5 else ''))

        for command in commands:
            self.add_to_history(command)
            def shell_wrapper(cmd=command):
                try:
                    def log_results(results):
                        # Direct console output using signal system
                        self.write_to_console(f'🚀 Executing: {cmd}')
                        # Direct call to result logging
                        self.log_command_results(cmd, serials, results)

                    adb_tools.run_adb_shell_command(serials, cmd, callback=log_results)
                except Exception as e:
                    QTimer.singleShot(0, lambda c=cmd: logger.warning(f'Command failed: {c} - {e}'))

            self.run_in_thread(shell_wrapper)


    def execute_single_command(self, command):
        """Execute a single command and add to history."""
        devices = self.get_checked_devices()
        serials = [d.device_serial_num for d in devices]
        device_count = len(devices)

        logger.info(f'🚀 Starting command execution: "{command}" on {device_count} device(s)')
        self.show_info('Single Command', f'Running command on {device_count} device(s):\n"{command}"\n\nCheck console output for results.')

        self.add_to_history(command)

        def shell_wrapper():
            try:
                # Use callback to ensure results are logged to console
                def log_results(results):
                    # Direct console output using signal system
                    self.write_to_console('📨 Callback received, processing results...')
                    # Direct call to result logging - no timer needed
                    self.log_command_results(command, serials, results)

                logger.info(f'📞 Calling adb_tools.run_adb_shell_command with callback')
                adb_tools.run_adb_shell_command(serials, command, callback=log_results)
                QTimer.singleShot(0, lambda: logger.info(f'✅ Single command "{command}" execution completed'))
            except Exception as e:
                logger.error(f'❌ Command execution failed: {e}')
                raise e

        self.run_in_thread(shell_wrapper)

    def log_command_results(self, command, serials, results):
        """Log command results to console with proper formatting."""
        logger.info(f'🔍 Processing results for command: {command}')

        if not results:
            logger.warning(f'❌ No results for command: {command}')
            self.write_to_console(f'❌ No results: {command}')
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
            self.write_to_console(f'📱 [{device_name}] {command}')

            if result and len(result) > 0:
                # Show first few lines of output
                max_lines = 10  # Reduced for cleaner display
                output_lines = result[:max_lines] if len(result) > max_lines else result

                logger.info(f'📱 [{device_name}] 📋 Output ({len(result)} lines total):')
                self.write_to_console(f'📋 {len(result)} lines output:')

                for line_num, line in enumerate(output_lines):
                    if line and line.strip():  # Skip empty lines
                        output_line = f'  {line.strip()}'  # Simplified format
                        logger.info(f'📱 [{device_name}] {line_num+1:2d}▶️ {line.strip()}')
                        self.write_to_console(output_line)

                if len(result) > max_lines:
                    truncated_msg = f'  ... {len(result) - max_lines} more lines'
                    logger.info(f'📱 [{device_name}] ... and {len(result) - max_lines} more lines (truncated)')
                    self.write_to_console(truncated_msg)

                success_msg = f'✅ [{device_name}] Completed'
                logger.info(f'📱 [{device_name}] ✅ Command completed successfully')
                self.write_to_console(success_msg)
            else:
                error_msg = f'❌ [{device_name}] No output'
                logger.warning(f'📱 [{device_name}] ❌ No output or command failed')
                self.write_to_console(error_msg)

        logger.info(f'🏁 Results display completed for command: {command}')
        logger.info('─' * 50)  # Separator line
        self.write_to_console('─' * 30)  # Shorter separator line

    def write_to_console(self, message):
        """Write message to console widget using signal."""
        try:
            # Use signal for thread-safe console output
            self.console_output_signal.emit(message)
        except Exception as e:
            print(f'Error emitting console signal: {e}')

    def _write_to_console_safe(self, message):
        """Thread-safe method to write to console."""
        try:
            cursor = self.console_text.textCursor()
            cursor.movePosition(QTextCursor.MoveOperation.End)
            cursor.insertText(f'{message}\n')
            self.console_text.setTextCursor(cursor)
            self.console_text.ensureCursorVisible()
        except Exception as e:
            print(f'Error in _write_to_console_safe: {e}')


    def get_valid_commands(self):
        """Extract valid commands from batch text area."""
        text = self.batch_commands_edit.toPlainText().strip()
        if not text:
            return []

        lines = text.split('\n')
        commands = []

        for line in lines:
            line = line.strip()
            if line and not line.startswith('#'):
                commands.append(line)

        return commands

    def add_to_history(self, command):
        """Add command to history."""
        if command not in self.command_history:
            self.command_history.append(command)
            # Keep only last 50 commands
            if len(self.command_history) > 50:
                self.command_history = self.command_history[-50:]
            self.update_history_display()
            # Auto-save to config
            logger.info(f'Adding command to history: {command}')
            self.save_command_history_to_config()
        else:
            logger.info(f'Command already in history: {command}')

    def update_history_display(self):
        """Update the history list widget."""
        self.command_history_list.clear()
        for command in reversed(self.command_history):  # Show most recent first
            self.command_history_list.addItem(command)

    def load_from_history(self, item):
        """Load selected history item to batch commands area."""
        command = item.text()
        current_text = self.batch_commands_edit.toPlainText()
        if current_text:
            new_text = current_text + '\n' + command
        else:
            new_text = command
        self.batch_commands_edit.setPlainText(new_text)

    def clear_command_history(self):
        """Clear command history."""
        self.command_history.clear()
        self.update_history_display()
        # Auto-save to config after clearing
        self.save_command_history_to_config()

    def export_command_history(self):
        """Export command history to file."""
        if not self.command_history:
            self.show_info('Export History', 'No commands in history to export.')
            return

        filename, _ = QFileDialog.getSaveFileName(
            self, 'Export Command History',
            f'adb_commands_{common.current_format_time_utc()}.txt',
            'Text Files (*.txt);;All Files (*)'
        )

        if filename:
            try:
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write('# ADB Command History\n')
                    f.write(f'# Generated: {common.timestamp_time()}\n\n')
                    for command in self.command_history:
                        f.write(f'{command}\n')

                self.show_info('Export History', f'Command history exported to:\n{filename}')
            except Exception as e:
                self.show_error('Export Error', f'Failed to export history:\n{e}')

    def import_command_history(self):
        """Import command history from file."""
        filename, _ = QFileDialog.getOpenFileName(
            self, 'Import Command History', '',
            'Text Files (*.txt);;All Files (*)'
        )

        if filename:
            try:
                with open(filename, 'r', encoding='utf-8') as f:
                    lines = f.readlines()

                loaded_commands = []
                for line in lines:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        loaded_commands.append(line)

                if loaded_commands:
                    self.command_history.extend(loaded_commands)
                    # Remove duplicates while preserving order
                    seen = set()
                    self.command_history = [x for x in self.command_history if not (x in seen or seen.add(x))]
                    # Keep only last 50 commands
                    if len(self.command_history) > 50:
                        self.command_history = self.command_history[-50:]

                    self.update_history_display()
                    # Auto-save to config after importing
                    self.save_command_history_to_config()
                    self.show_info('Import History', f'Imported {len(loaded_commands)} commands from:\n{filename}')
                else:
                    self.show_info('Import History', 'No valid commands found in file.')

            except Exception as e:
                self.show_error('Import Error', f'Failed to import history:\n{e}')

    def load_command_history_from_config(self):
        """Load command history from config file."""
        try:
            config_data = json_utils.read_config_json()
            if 'command_history' in config_data:
                self.command_history = config_data['command_history'][-50:]  # Keep only last 50
                self.update_history_display()
        except Exception:
            self.command_history = []

    def save_command_history_to_config(self):
        """Save command history to config file."""
        try:
            config_data = json_utils.read_config_json()
            config_data['command_history'] = self.command_history
            json_utils.save_config_json(config_data)
            logger.info(f'Command history auto-saved ({len(self.command_history)} commands)')
        except Exception as e:
            logger.warning(f'Failed to save command history to config: {e}')

    # scrcpy functionality
    @ensure_devices_selected
    def launch_scrcpy(self):
        """Launch scrcpy for selected devices."""
        if not self.scrcpy_available:
            self.show_scrcpy_installation_guide()
            return

        devices = self.get_checked_devices()
        if not devices:
            self.show_error('Error', 'No devices selected.')
            return

        if len(devices) > 1:
            # Multiple devices - ask user to choose one
            device_choices = [f"{d.device_model} ({d.device_serial_num})" for d in devices]
            choice, ok = QInputDialog.getItem(
                self,
                'Select Device for Mirroring',
                'scrcpy can only mirror one device at a time.\nPlease select which device to mirror:',
                device_choices,
                0,
                False
            )
            if not ok:
                return

            # Find the selected device
            selected_index = device_choices.index(choice)
            selected_device = devices[selected_index]
        else:
            selected_device = devices[0]

        serial = selected_device.device_serial_num
        device_model = selected_device.device_model

        logger.info(f'Launching scrcpy for device: {device_model} ({serial})')
        self.show_info('scrcpy', f'Launching device mirroring for:\n{device_model} ({serial})\n\nscrcpy window will open shortly...')

        def scrcpy_wrapper():
            try:

                # Get the correct scrcpy command path
                scrcpy_cmd = adb_tools.get_scrcpy_command()
                cmd = [scrcpy_cmd, '-s', serial]

                # Add version-compatible options
                cmd.extend([
                    '--max-size', '1024',  # Limit resolution for better performance
                    '--max-fps', '30',     # Limit FPS for better performance
                    '--stay-awake',        # Keep device awake while mirroring
                ])

                # Add bit rate option based on scrcpy version
                if hasattr(self, 'scrcpy_major_version') and self.scrcpy_major_version >= 3:
                    # scrcpy 3.x+ uses --video-bit-rate
                    cmd.extend(['--video-bit-rate', '8M'])
                else:
                    # scrcpy 2.x and earlier use --bit-rate
                    cmd.extend(['--bit-rate', '8M'])

                logger.info(f'Executing scrcpy command: {" ".join(cmd)}')

                # Launch scrcpy in background
                if sys.platform.startswith('win'):
                    # Windows
                    subprocess.Popen(cmd, creationflags=subprocess.CREATE_NEW_CONSOLE)
                else:
                    # macOS/Linux
                    subprocess.Popen(cmd)

                QTimer.singleShot(0, lambda: logger.info(f'scrcpy launched successfully for {device_model}'))

            except subprocess.CalledProcessError as e:
                error_msg = f'Failed to launch scrcpy: {e}'
                logger.error(error_msg)
                QTimer.singleShot(0, lambda: self.show_error('scrcpy Error', error_msg))
            except Exception as e:
                error_msg = f'Error launching scrcpy: {str(e)}'
                logger.error(error_msg)
                QTimer.singleShot(0, lambda: self.show_error('scrcpy Error', error_msg))

        self.run_in_thread(scrcpy_wrapper)

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
    @ensure_devices_selected
    def generate_android_bug_report(self):
        """Generate Android bug report using utils."""
        output_path = self.file_gen_output_path_edit.text().strip()

        # Validate output path using utils
        validated_path = validate_file_output_path(output_path)
        if not validated_path:
            self.error_handler.handle_error(ErrorCode.FILE_NOT_FOUND,
                                           'Please select a valid file generation output directory first.')
            return

        devices = self.get_checked_devices()

        # Show progress notification
        self.error_handler.show_info('📊 Generating Bug Reports',
                                   f'Generating Android bug reports for {len(devices)} device(s)...\n\n'
                                   f'📁 Saving to: {validated_path}\n\n'
                                   f'Please wait, this may take a while...')

        # Enhanced callback with error handling for Samsung and other device issues
        def bug_report_callback(operation_name, output_path, device_count, icon):
            self.file_generation_completed_signal.emit(operation_name, output_path, device_count, icon)

        # Enhanced error-aware generation
        def generation_wrapper():
            try:
                generate_bug_report_batch(devices, validated_path, bug_report_callback)
            except Exception as e:
                # Handle Samsung and other device-specific failures
                QTimer.singleShot(0, lambda: self.show_error(
                    '🐛 Bug Report Generation Failed',
                    f'Failed to generate bug reports for some devices.\n\n'
                    f'Error: {str(e)}\n\n'
                    f'Common causes:\n'
                    f'• Samsung devices may require special permissions\n'
                    f'• Device may not support bug report generation\n'
                    f'• Insufficient storage space on device\n'
                    f'• Device disconnected during process\n'
                    f'• Root access required for some devices\n\n'
                    f'Please check:\n'
                    f'1. Enable "USB debugging (Security settings)"\n'
                    f'2. Grant all requested permissions\n'
                    f'3. Ensure device has sufficient storage\n'
                    f'4. Try with individual devices if multiple selected'
                ))

        # Run in background thread with error handling
        threading.Thread(target=generation_wrapper, daemon=True).start()

    @ensure_devices_selected
    def generate_device_discovery_file(self):
        """Generate device discovery file using utils."""
        output_path = self.file_gen_output_path_edit.text().strip()

        # Validate output path using utils
        validated_path = validate_file_output_path(output_path)
        if not validated_path:
            self.error_handler.handle_error(ErrorCode.FILE_NOT_FOUND,
                                           'Please select a valid file generation output directory first.')
            return

        devices = self.get_checked_devices()

        # Show progress notification
        self.error_handler.show_info('🔍 Generating Discovery File',
                                   f'Extracting device discovery information for {len(devices)} device(s)...\n\n'
                                   f'📁 Saving to: {validated_path}\n\n'
                                   f'Please wait...')

        # Use file generation utils with callback
        def discovery_callback(operation_name, output_path, device_count, icon):
            self.file_generation_completed_signal.emit(operation_name, output_path, device_count, icon)

        generate_device_discovery_file(devices, validated_path, discovery_callback)

    @ensure_devices_selected
    def pull_device_dcim_with_folder(self):
        """Pull DCIM folder from devices."""
        output_path = self.file_gen_output_path_edit.text().strip()
        if not output_path:
            self.show_error('Error', 'Please select a file generation output directory first.')
            return

        # Validate and normalize output path using common.py
        if not common.check_exists_dir(output_path):
            normalized_path = common.make_gen_dir_path(output_path)
            if not normalized_path:
                self.show_error('Error', 'Invalid file generation output directory path.')
                return
            output_path = normalized_path

        devices = self.get_checked_devices()
        serials = [d.device_serial_num for d in devices]
        device_count = len(devices)

        # Show progress notification
        self.show_info('📷 Pulling DCIM Folders',
                      f'Pulling DCIM folders from {device_count} device(s)...\n\n'
                      f'📁 Saving to: {output_path}\n\n'
                      f'This may take some time depending on the number of photos and videos...')

        def dcim_wrapper():
            try:
                adb_tools.pull_device_dcim(serials, output_path)
                # Emit completion signal
                self.file_generation_completed_signal.emit('DCIM Pull', output_path, device_count, '📷')
            except Exception as e:
                raise e  # Re-raise to be handled by run_in_thread

        self.run_in_thread(dcim_wrapper)
        logger.info(f'Pulling DCIM folders from {device_count} devices: {serials}')

    @ensure_devices_selected
    def dump_device_hsv(self):
        """Dump device UI hierarchy."""
        output_path = self.file_gen_output_path_edit.text().strip()
        if not output_path:
            self.show_error('Error', 'Please select a file generation output directory first.')
            return

        # Validate and normalize output path using common.py
        if not common.check_exists_dir(output_path):
            normalized_path = common.make_gen_dir_path(output_path)
            if not normalized_path:
                self.show_error('Error', 'Invalid file generation output directory path.')
                return
            output_path = normalized_path

        devices = self.get_checked_devices()
        serials = [d.device_serial_num for d in devices]
        device_count = len(devices)

        # Show progress notification
        self.show_info('📱 Dumping UI Hierarchy',
                      f'Dumping UI hierarchy for {device_count} device(s)...\n\n'
                      f'📁 Saving to: {output_path}\n\n'
                      f'Please wait...')

        def hsv_wrapper():
            try:
                adb_tools.pull_devices_hsv(serials, output_path)
                # Emit completion signal
                self.file_generation_completed_signal.emit('UI Hierarchy Dump', output_path, device_count, '📱')
            except Exception as e:
                raise e  # Re-raise to be handled by run_in_thread

        self.run_in_thread(hsv_wrapper)
        logger.info(f'Dumping UI hierarchy for {device_count} devices: {serials}')

    @ensure_devices_selected
    def launch_ui_inspector(self):
        """Launch the interactive UI Inspector for selected devices."""
        devices = self.get_checked_devices()
        if len(devices) != 1:
            self.show_warning('Single Device Required',
                            'UI Inspector requires exactly one device to be selected.\n\n'
                            'Please select only one device and try again.')
            return

        device = devices[0]
        serial = device.device_serial_num
        model = device.device_model

        logger.info(f'Launching UI Inspector for device: {model} ({serial})')

        # Create and show UI Inspector dialog
        ui_inspector = UIInspectorDialog(self, serial, model)
        ui_inspector.exec()

    def show_about_dialog(self):
        """Show about dialog."""
        QMessageBox.about(
            self,
            'About lazy blacktea',
            'lazy blacktea - PyQt6 Version\n\n'
            'A GUI application for simplifying Android ADB and automation tasks.\n\n'
            'Converted from Tkinter to PyQt6 for enhanced user experience.'
        )

    def load_config(self):
        """Load configuration from file using ConfigManager."""
        try:
            config = self.config_manager.load_config()

            # Load output path from old config format for compatibility
            old_config = json_utils.read_config_json()
            if old_config.get('output_path'):
                self.output_path_edit.setText(old_config['output_path'])

            # Load file generation output path
            file_gen_path = old_config.get('file_gen_output_path', '').strip()
            if file_gen_path:
                self.file_gen_output_path_edit.setText(file_gen_path)
            else:
                # Use main output path as default for file generation
                main_output_path = old_config.get('output_path', '')
                if main_output_path:
                    self.file_gen_output_path_edit.setText(main_output_path)

            # Load refresh interval from new config (set minimum 10 seconds for packaged apps)
            self.refresh_interval = max(10, config.device.refresh_interval)
            self.device_manager.refresh_thread.set_refresh_interval(self.refresh_interval)

            # Load UI scale from new config
            self.set_ui_scale(config.ui.ui_scale)

            # Load device groups from old config for compatibility
            if old_config.get('device_groups'):
                self.device_groups = old_config['device_groups']

            # Load command history from new config
            if config.command_history:
                self.command_executor.set_command_history(config.command_history)

            logger.info('Configuration loaded successfully')
        except Exception as e:
            logger.warning(f'Could not load config: {e}')
            self.error_handler.handle_error(ErrorCode.CONFIG_LOAD_FAILED, str(e))

    def save_config(self):
        """Save configuration to file using ConfigManager."""
        try:
            # Update the new config manager
            self.config_manager.update_ui_settings(ui_scale=self.user_scale)
            self.config_manager.update_device_settings(refresh_interval=self.refresh_interval)

            # Save command history to new config
            if hasattr(self, 'command_executor'):
                config = self.config_manager.load_config()
                config.command_history = self.command_executor.get_command_history()
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

    def closeEvent(self, event):
        """Handle window close event with immediate response."""
        # Hide window immediately for better user experience
        self.hide()

        # Process any pending events to ensure UI updates
        QApplication.processEvents()

        self.save_config()

        # Clean up timers to prevent memory leaks
        if hasattr(self, 'recording_timer'):
            self.recording_timer.stop()

        # Clean up new modular components
        if hasattr(self, 'device_manager'):
            self.device_manager.cleanup()

        if hasattr(self, 'recording_manager'):
            # Stop any active recordings
            self.recording_manager.stop_recording()

        # Clean up old threads aggressively for immediate shutdown
        if hasattr(self, 'device_refresh_thread'):
            self.device_refresh_thread.stop()
            # Use very short timeout for immediate shutdown experience
            if not self.device_refresh_thread.wait(300):  # 300ms timeout for immediate feel
                logger.debug('Device refresh thread terminated immediately for fast shutdown')
                self.device_refresh_thread.terminate()

        logger.info('Application shutdown complete')
        event.accept()


def main():
    """Main application entry point."""
    app = QApplication(sys.argv)
    app.setApplicationName('lazy blacktea')
    app.setApplicationVersion('0.0.1')

    window = WindowMain()
    window.show()

    sys.exit(app.exec())


if __name__ == '__main__':
    main()