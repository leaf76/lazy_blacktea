"""
Logcat Viewer Component - Extracted from lazy_blacktea_pyqt.py
Provides real-time logcat streaming and filtering capabilities.
"""

import logging
import os
import re
import time
from typing import Optional, Dict, List

from PyQt6.QtWidgets import (
    QWidget, QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, QSplitter, QTextEdit,
    QPushButton, QLabel, QLineEdit, QComboBox, QCheckBox, QFrame, QMessageBox,
    QInputDialog, QFormLayout, QListWidget, QListWidgetItem, QAbstractItemView,
    QSpinBox, QSizePolicy
)
from PyQt6.QtCore import (
    QProcess, QTimer, QIODevice, Qt, pyqtSignal
)
from PyQt6.QtGui import QFont, QTextCursor, QCloseEvent

try:
    from utils import adb_tools
except Exception:  # pragma: no cover - fallback when utils are unavailable
    class _AdbToolsFallback:
        """Fallback stub when adb_tools cannot be loaded."""

        @staticmethod
        def get_package_pids(*_args, **_kwargs):
            return []

    adb_tools = _AdbToolsFallback()

logger = logging.getLogger(__name__)

QT_QPROCESS = QProcess


PERFORMANCE_PRESETS = {
    'Balanced (default)': {
        'max_lines': 1000,
        'history_multiplier': 5,
        'update_interval_ms': 200,
        'lines_per_update': 50,
        'max_buffer_size': 100,
    },
    'Extended history': {
        'max_lines': 1500,
        'history_multiplier': 10,
        'update_interval_ms': 250,
        'lines_per_update': 60,
        'max_buffer_size': 120,
    },
    'Low latency streaming': {
        'max_lines': 800,
        'history_multiplier': 5,
        'update_interval_ms': 120,
        'lines_per_update': 25,
        'max_buffer_size': 60,
    },
    'Heavy throughput': {
        'max_lines': 1200,
        'history_multiplier': 6,
        'update_interval_ms': 300,
        'lines_per_update': 80,
        'max_buffer_size': 160,
    }
}


class PerformanceSettingsDialog(QDialog):
    """Performance settings dialog for Logcat viewer."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_window = parent
        self.init_ui()

    def init_ui(self):
        """Initialize the performance settings dialog UI."""
        self.setWindowTitle('Performance Settings')
        self.setFixedSize(420, 320)
        self.setModal(True)

        # Main layout
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(15)

        # Title
        title = QLabel('Performance Settings')
        title.setStyleSheet('font-size: 14px; font-weight: bold; color: #2E86C1;')
        main_layout.addWidget(title)

        # Preset selection
        preset_layout = QHBoxLayout()
        preset_label = QLabel('Preset:')
        preset_label.setFixedWidth(120)
        preset_layout.addWidget(preset_label)

        self.preset_combo = QComboBox()
        self.preset_combo.addItem('Custom')
        for preset_name in PERFORMANCE_PRESETS.keys():
            self.preset_combo.addItem(preset_name)
        preset_layout.addWidget(self.preset_combo)
        preset_layout.addStretch()
        main_layout.addLayout(preset_layout)

        # Settings section
        settings_layout = QVBoxLayout()
        settings_layout.setSpacing(10)

        # Max Lines
        max_lines_layout = QHBoxLayout()
        max_lines_label = QLabel('Max Lines:')
        max_lines_label.setFixedWidth(120)
        max_lines_layout.addWidget(max_lines_label)
        self.max_lines_spin = QSpinBox()
        self.max_lines_spin.setRange(100, 50000)
        self.max_lines_spin.setSingleStep(100)
        self.max_lines_spin.setValue(self.parent_window.max_lines if self.parent_window else 1000)
        max_lines_layout.addWidget(self.max_lines_spin)
        max_lines_layout.addStretch()
        settings_layout.addLayout(max_lines_layout)

        # History multiplier
        history_layout = QHBoxLayout()
        history_label = QLabel('History Multiplier:')
        history_label.setFixedWidth(120)
        history_layout.addWidget(history_label)
        self.history_multiplier_spin = QSpinBox()
        self.history_multiplier_spin.setRange(1, 20)
        self.history_multiplier_spin.setSingleStep(1)
        self.history_multiplier_spin.setValue(self.parent_window.history_multiplier if self.parent_window else 5)
        history_layout.addWidget(self.history_multiplier_spin)
        history_layout.addStretch()
        settings_layout.addLayout(history_layout)

        # Update Interval
        interval_layout = QHBoxLayout()
        interval_label = QLabel('Update Interval:')
        interval_label.setFixedWidth(120)
        interval_layout.addWidget(interval_label)
        self.update_interval_spin = QSpinBox()
        self.update_interval_spin.setRange(50, 2000)
        self.update_interval_spin.setSingleStep(10)
        self.update_interval_spin.setValue(self.parent_window.update_interval_ms if self.parent_window else 200)
        interval_layout.addWidget(self.update_interval_spin)
        interval_unit_label = QLabel('ms')
        interval_layout.addWidget(interval_unit_label)
        interval_layout.addStretch()
        settings_layout.addLayout(interval_layout)

        # Lines per Update
        lines_update_layout = QHBoxLayout()
        lines_update_label = QLabel('Lines per Update:')
        lines_update_label.setFixedWidth(120)
        lines_update_layout.addWidget(lines_update_label)
        self.lines_per_update_spin = QSpinBox()
        self.lines_per_update_spin.setRange(10, 500)
        self.lines_per_update_spin.setSingleStep(5)
        self.lines_per_update_spin.setValue(self.parent_window.max_lines_per_update if self.parent_window else 50)
        lines_update_layout.addWidget(self.lines_per_update_spin)
        lines_update_layout.addStretch()
        settings_layout.addLayout(lines_update_layout)

        # Buffer flush threshold
        buffer_layout = QHBoxLayout()
        buffer_label = QLabel('Flush Threshold:')
        buffer_label.setFixedWidth(120)
        buffer_layout.addWidget(buffer_label)
        self.buffer_size_spin = QSpinBox()
        self.buffer_size_spin.setRange(10, 1000)
        self.buffer_size_spin.setSingleStep(10)
        self.buffer_size_spin.setValue(self.parent_window.max_buffer_size if self.parent_window else 100)
        buffer_layout.addWidget(self.buffer_size_spin)
        buffer_layout.addWidget(QLabel('lines'))
        buffer_layout.addStretch()
        settings_layout.addLayout(buffer_layout)

        main_layout.addLayout(settings_layout)

        # Performance Tips
        tips_frame = QFrame()
        tips_frame.setStyleSheet('background-color: #f8f9fa; border: 1px solid #dee2e6; border-radius: 4px; padding: 10px;')
        tips_layout = QVBoxLayout(tips_frame)

        tips_label = QLabel('Performance Tips:')
        tips_label.setStyleSheet('font-weight: bold; color: #495057;')
        tips_layout.addWidget(tips_label)

        tips_text = QLabel(
            '• Max Lines x History Multiplier defines the retained log capacity\n'
            '• Lower Update Interval / smaller flush threshold = lower latency but higher CPU\n'
            '• Increase Lines per Update to reduce UI refresh frequency'
        )
        tips_text.setStyleSheet('color: #6c757d; font-size: 11px;')
        tips_layout.addWidget(tips_text)

        self.capacity_label = QLabel()
        self.capacity_label.setStyleSheet('font-size: 11px; color: #2E86C1;')
        tips_layout.addWidget(self.capacity_label)

        main_layout.addWidget(tips_frame)

        # Buttons
        button_layout = QHBoxLayout()
        cancel_btn = QPushButton('Cancel')
        cancel_btn.clicked.connect(self.reject)
        apply_btn = QPushButton('Apply')
        apply_btn.clicked.connect(self.apply_settings)
        apply_btn.setStyleSheet('background-color: #007bff; color: white; font-weight: bold;')

        button_layout.addStretch()
        button_layout.addWidget(cancel_btn)
        button_layout.addWidget(apply_btn)
        main_layout.addLayout(button_layout)

        self._updating_from_preset = False
        self._register_signal_handlers()
        self._update_capacity_preview()

    def apply_settings(self):
        """Apply the performance settings."""
        if not self.parent_window:
            self.accept()
            return

        try:
            # Update max lines
            max_lines = self.max_lines_spin.value()
            self.parent_window.max_lines = max_lines

            # Update interval
            interval = self.update_interval_spin.value()
            self.parent_window.update_interval_ms = interval

            # Update lines per update
            lines_per_update = self.lines_per_update_spin.value()
            self.parent_window.max_lines_per_update = lines_per_update

            # Update history multiplier
            history_multiplier = self.history_multiplier_spin.value()
            self.parent_window.history_multiplier = history_multiplier

            # Update flush threshold
            buffer_threshold = self.buffer_size_spin.value()
            self.parent_window.max_buffer_size = buffer_threshold

            if hasattr(self.parent_window, 'on_performance_settings_updated'):
                self.parent_window.on_performance_settings_updated()

            self.accept()
        except ValueError:
            QMessageBox.warning(self, 'Invalid Input', 'Please enter valid numbers for all settings.')

    def _register_signal_handlers(self):
        """Connect widget signals for preset handling and previews."""
        self.preset_combo.currentTextChanged.connect(self._handle_preset_selection)

        for spin in [
            self.max_lines_spin,
            self.history_multiplier_spin,
            self.update_interval_spin,
            self.lines_per_update_spin,
            self.buffer_size_spin,
        ]:
            spin.valueChanged.connect(self._mark_custom)
            spin.valueChanged.connect(self._update_capacity_preview)

    def _handle_preset_selection(self, preset_name: str):
        """Apply preset values when a preset is selected."""
        preset_name = preset_name.strip()
        if preset_name == 'Custom' or preset_name not in PERFORMANCE_PRESETS:
            return

        preset_values = PERFORMANCE_PRESETS[preset_name]
        self._updating_from_preset = True
        try:
            self.max_lines_spin.setValue(preset_values['max_lines'])
            self.history_multiplier_spin.setValue(preset_values['history_multiplier'])
            self.update_interval_spin.setValue(preset_values['update_interval_ms'])
            self.lines_per_update_spin.setValue(preset_values['lines_per_update'])
            self.buffer_size_spin.setValue(preset_values['max_buffer_size'])
        finally:
            self._updating_from_preset = False
            self._update_capacity_preview()

    def _mark_custom(self):
        """Switch preset selection back to custom when values change."""
        if self._updating_from_preset:
            return
        if self.preset_combo.currentText() != 'Custom':
            self.preset_combo.blockSignals(True)
            self.preset_combo.setCurrentText('Custom')
            self.preset_combo.blockSignals(False)

    def _update_capacity_preview(self):
        """Update capacity label showing the retained history size."""
        max_lines = self.max_lines_spin.value()
        history_multiplier = self.history_multiplier_spin.value()
        capacity = max_lines * history_multiplier
        self.capacity_label.setText(
            f'Capacity preview: {max_lines} visible lines × {history_multiplier} history = {capacity} stored lines'
        )


class LogcatWindow(QDialog):
    """Logcat viewer window with real-time streaming and filtering capabilities."""

    def __init__(self, device, parent=None):
        super().__init__(parent)
        self.device = device
        self.logcat_process = None
        self.is_running = False
        self.max_lines = 1000  # Performance optimization: limit log lines
        self.filters = {}  # Store named filters
        self.current_filter = None

        # Performance optimization: buffering and throttling
        self.log_buffer = []  # Buffer for incoming log lines
        self.max_buffer_size = 100  # Maximum lines to buffer before processing
        self.update_timer = QTimer()  # Timer for throttled UI updates
        self.update_timer.timeout.connect(self.process_buffered_logs)
        self.update_timer.setSingleShot(True)
        self.update_interval_ms = 200  # Update UI every 200ms max
        self._partial_line = ''  # Buffer for incomplete log lines
        self._suppress_logcat_errors = False
        self._last_rendered_mode: Optional[str] = None
        self._last_rendered_text = ''

        # Additional performance settings
        self.max_lines_per_update = 50  # Maximum lines to add to UI per update
        self.last_update_time = 0
        self.history_multiplier = 5

        # Real-time filtering
        self.log_levels_order = ['V', 'D', 'I', 'W', 'E', 'F']
        self.live_filter_pattern = None
        self.active_filters: List[Dict[str, str]] = []
        self.raw_logs: List[str] = []  # Store raw logs for unfiltered view
        self.filtered_logs: List[str] = []  # Store filtered logs for active filters

        self.init_ui()
        self.load_filters()

    def _get_status_prefix(self):
        """Get status prefix emoji based on running state."""
        return '🟢' if self.is_running else '⏸️'

    def _update_status_label(self, text):
        """Update status label with consistent formatting."""
        prefix = self._get_status_prefix()
        self.status_label.setText(f'{prefix} {text}')

    def _get_buffer_stats(self):
        """Get buffer statistics."""
        has_filters = self._has_active_filters()
        return {
            'total_logs': len(self.filtered_logs) if has_filters else len(self.raw_logs),
            'buffer_size': len(self.log_buffer),
            'filtered_count': len(self.filtered_logs) if has_filters else 0
        }

    def _manage_buffer_size(self):
        """Manage raw log buffer size based on configured history."""
        history_limit = self.max_lines * self.history_multiplier
        if len(self.raw_logs) > history_limit:
            self.raw_logs = self.raw_logs[-history_limit:]

    def _trim_filtered_logs(self):
        """Ensure filtered log history respects configured limits."""
        history_limit = self.max_lines * self.history_multiplier
        if len(self.filtered_logs) > history_limit:
            self.filtered_logs = self.filtered_logs[-history_limit:]

    def _handle_filters_changed(self):
        """Rebuild filtered history and refresh display after filter changes."""
        if self._has_active_filters():
            self.filtered_logs = self.filter_lines(self.raw_logs)
            self._trim_filtered_logs()
        else:
            self.filtered_logs.clear()

        self.refilter_display()

    def _has_active_filters(self) -> bool:
        """Return whether any filter (live or saved) is active."""
        return bool(self.live_filter_pattern) or bool(self.active_filters)

    def init_ui(self):
        """Initialize the logcat window UI."""
        self.setWindowTitle(f'Logcat Viewer - {self.device.device_model} ({self.device.device_serial_num[:8]}...)')
        self.setGeometry(100, 100, 1200, 800)

        # Main layout and splitter configuration
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        control_layout = self.create_control_panel()
        filter_panel = self.create_filter_panel()

        top_panel = QWidget()
        top_panel.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)
        top_panel.setMaximumHeight(190)
        top_layout = QVBoxLayout(top_panel)
        top_layout.setContentsMargins(0, 0, 0, 0)
        top_layout.setSpacing(6)
        top_layout.addLayout(control_layout)
        top_layout.addWidget(filter_panel)

        self.log_display = QTextEdit()
        self.log_display.setFont(QFont('Consolas', 10))
        self.log_display.setReadOnly(True)
        self.log_display.setStyleSheet(
            """
            QTextEdit {
                background-color: #1e1e1e;
                color: #ffffff;
                border: 1px solid #3e3e3e;
            }
            """
        )

        self.status_label = QLabel('Ready to start logcat...')

        log_container = QWidget()
        log_container.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        log_layout = QVBoxLayout(log_container)
        log_layout.setContentsMargins(0, 0, 0, 0)
        log_layout.setSpacing(4)
        log_layout.addWidget(self.log_display)
        log_layout.addWidget(self.status_label, alignment=Qt.AlignmentFlag.AlignLeft)

        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.addWidget(top_panel)
        splitter.addWidget(log_container)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setCollapsible(0, False)
        splitter.setCollapsible(1, False)

        layout.addWidget(splitter)

    def create_control_panel(self):
        """Create the control panel with start/stop buttons."""
        layout = QHBoxLayout()

        # Start/Stop buttons
        self.start_btn = QPushButton('▶️ Start Logcat')
        self.start_btn.clicked.connect(self.start_logcat)
        layout.addWidget(self.start_btn)

        self.stop_btn = QPushButton('⏹️ Stop')
        self.stop_btn.clicked.connect(self.stop_logcat)
        self.stop_btn.setEnabled(False)
        layout.addWidget(self.stop_btn)

        # Clear button
        clear_btn = QPushButton('🗑️ Clear')
        clear_btn.clicked.connect(self.clear_logs)
        layout.addWidget(clear_btn)

        # Performance settings button
        perf_btn = QPushButton('⚙️ Performance')
        perf_btn.clicked.connect(self.open_performance_settings)
        layout.addWidget(perf_btn)

        # Add separator
        separator = self.create_vertical_separator()
        layout.addWidget(separator)

        # Log level checkboxes
        self.log_levels = {
            'V': QCheckBox('Verbose'),
            'D': QCheckBox('Debug'),
            'I': QCheckBox('Info'),
            'W': QCheckBox('Warn'),
            'E': QCheckBox('Error'),
            'F': QCheckBox('Fatal')
        }

        for level in self.log_levels_order:
            checkbox = self.log_levels[level]
            checkbox.setChecked(True)
            checkbox.stateChanged.connect(self.update_log_levels)
            layout.addWidget(checkbox)

        # Source filter controls for tag/package filtering
        layout.addWidget(self.create_vertical_separator())

        source_label = QLabel('Source')
        source_label.setStyleSheet('font-weight: bold;')
        layout.addWidget(source_label)

        self.log_source_mode = QComboBox()
        self.log_source_mode.addItem('Tag', 'tag')
        self.log_source_mode.addItem('Package', 'package')
        self.log_source_mode.addItem('Raw', 'raw')
        self.log_source_mode.setCurrentIndex(0)
        layout.addWidget(self.log_source_mode)

        self.log_source_input = QLineEdit()
        self.log_source_input.setPlaceholderText('Tag or package filter (optional)')
        self.log_source_input.setMinimumWidth(200)
        layout.addWidget(self.log_source_input)

        layout.addStretch()
        return layout

    def create_filter_panel(self) -> QWidget:
        """Create the filter panel with real-time filtering in a compact layout."""
        panel = QWidget()
        main_layout = QVBoxLayout(panel)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(6)

        # Form-style rows for filter and saved controls
        form_widget = QWidget()
        form_layout = QGridLayout(form_widget)
        form_layout.setContentsMargins(0, 0, 0, 0)
        form_layout.setHorizontalSpacing(6)
        form_layout.setVerticalSpacing(6)

        filter_label = QLabel('Filter:')
        filter_label.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.filter_input = QLineEdit()
        self.filter_input.setPlaceholderText('Type to filter logs in real-time...')
        self.filter_input.textChanged.connect(self.apply_live_filter)
        save_filter_btn = QPushButton('Save')
        save_filter_btn.setFixedWidth(64)
        save_filter_btn.setToolTip('Save current filter pattern')
        save_filter_btn.clicked.connect(self.save_current_filter)

        form_layout.addWidget(filter_label, 0, 0, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        form_layout.addWidget(self.filter_input, 0, 1)
        form_layout.addWidget(save_filter_btn, 0, 2)

        saved_label = QLabel('Saved:')
        self.saved_filters_combo = QComboBox()
        self.saved_filters_combo.setEditable(False)
        self.saved_filters_combo.currentTextChanged.connect(self.load_saved_filter)

        apply_filter_btn = QPushButton('Apply')
        apply_filter_btn.setFixedWidth(64)
        apply_filter_btn.clicked.connect(self.apply_selected_filter)
        delete_filter_btn = QPushButton('Delete')
        delete_filter_btn.setFixedWidth(64)
        delete_filter_btn.clicked.connect(self.delete_saved_filter)

        form_layout.addWidget(saved_label, 1, 0, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        form_layout.addWidget(self.saved_filters_combo, 1, 1)
        form_layout.addWidget(apply_filter_btn, 1, 2)
        form_layout.addWidget(delete_filter_btn, 1, 3)

        main_layout.addWidget(form_widget)

        # Active filters section
        active_row = QHBoxLayout()
        active_row.setSpacing(6)
        active_label = QLabel('Active:')
        active_label.setStyleSheet('font-weight: bold;')
        active_row.addWidget(active_label, alignment=Qt.AlignmentFlag.AlignTop)

        self.active_filters_list = QListWidget()
        self.active_filters_list.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.active_filters_list.setMaximumHeight(80)
        self.active_filters_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.active_filters_list.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.active_filters_list.setWordWrap(True)
        self.update_active_filters_list()
        active_row.addWidget(self.active_filters_list)

        actions_col = QVBoxLayout()
        actions_col.setSpacing(4)
        remove_active_btn = QPushButton('Remove')
        remove_active_btn.setFixedWidth(70)
        remove_active_btn.clicked.connect(self.remove_selected_active_filters)
        actions_col.addWidget(remove_active_btn)

        clear_active_btn = QPushButton('Clear')
        clear_active_btn.setFixedWidth(70)
        clear_active_btn.clicked.connect(self.clear_active_filters)
        actions_col.addWidget(clear_active_btn)
        actions_col.addStretch()

        active_row.addLayout(actions_col)
        main_layout.addLayout(active_row)

        panel.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)
        panel.setMaximumHeight(150)
        return panel

    def save_current_filter(self):
        """Save current filter pattern."""
        if not self.filter_input.text().strip():
            QMessageBox.information(self, 'No Filter', 'Please enter a filter pattern first.')
            return

        filter_name, ok = QInputDialog.getText(self, 'Save Filter', 'Enter filter name:')
        if ok and filter_name.strip():
            self.filters[filter_name.strip()] = self.filter_input.text().strip()
            self.save_filters()
            self.update_saved_filters_combo()
            QMessageBox.information(self, 'Filter Saved', f'Filter "{filter_name}" saved successfully!')

    def delete_saved_filter(self):
        """Delete selected saved filter."""
        current_filter = self.saved_filters_combo.currentText()
        if not current_filter:
            QMessageBox.information(self, 'No Selection', 'Please select a filter to delete.')
            return

        reply = QMessageBox.question(self, 'Delete Filter',
                                   f'Are you sure you want to delete filter "{current_filter}"?',
                                   QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)

        if reply == QMessageBox.StandardButton.Yes:
            if current_filter in self.filters:
                del self.filters[current_filter]
                self.save_filters()
                self.update_saved_filters_combo()
                self.active_filters = [
                    f for f in self.active_filters if f.get('name') != current_filter
                ]
                self.update_active_filters_list()
                self._handle_filters_changed()
                QMessageBox.information(self, 'Filter Deleted', f'Filter "{current_filter}" deleted successfully!')

    def update_saved_filters_combo(self):
        """Update the saved filters combo box."""
        current_text = self.saved_filters_combo.currentText()
        self.saved_filters_combo.clear()
        self.saved_filters_combo.addItems(list(self.filters.keys()))
        # Try to restore selection
        if current_text in self.filters:
            self.saved_filters_combo.setCurrentText(current_text)

    def add_active_filter(self, name: str, pattern: str):
        """Add a saved filter to the active filters list."""
        pattern = pattern.strip()
        if not pattern:
            return

        # Avoid duplicates
        if any(
            f.get('name') == name and f.get('pattern') == pattern
            for f in self.active_filters
        ):
            return

        self.active_filters.append({'name': name, 'pattern': pattern})
        self.update_active_filters_list()
        self._handle_filters_changed()

    def update_active_filters_list(self):
        """Refresh the active filters list widget."""
        if not hasattr(self, 'active_filters_list'):
            return

        self.active_filters_list.clear()

        if not self.active_filters:
            placeholder = QListWidgetItem('No active filters')
            placeholder.setFlags(Qt.ItemFlag.NoItemFlags)
            self.active_filters_list.addItem(placeholder)
            return

        for filter_data in self.active_filters:
            name = filter_data.get('name', 'Unnamed')
            pattern = filter_data.get('pattern', '')
            item = QListWidgetItem(f'{name}: {pattern}')
            self.active_filters_list.addItem(item)

    def remove_selected_active_filters(self):
        """Remove selected entries from active filters."""
        if not hasattr(self, 'active_filters_list') or not self.active_filters:
            return

        selected_items = self.active_filters_list.selectedItems()
        if not selected_items:
            return

        rows = sorted(
            {self.active_filters_list.row(item) for item in selected_items},
            reverse=True
        )

        for row in rows:
            if 0 <= row < len(self.active_filters):
                del self.active_filters[row]

        self.update_active_filters_list()
        self._handle_filters_changed()

    def clear_active_filters(self):
        """Clear all active filters."""
        if not self.active_filters:
            return

        self.active_filters.clear()
        self.update_active_filters_list()
        self._handle_filters_changed()

    def _update_filtered_status(self):
        """Update status label when filters are active."""
        filtered_count = len(self.filtered_logs)
        capacity = self.max_lines * self.history_multiplier
        active_count = len(self.active_filters) + (1 if self.live_filter_pattern else 0)
        self._update_status_label(
            f'Filtered: {filtered_count}/{capacity} lines (active: {active_count})'
        )

    def on_performance_settings_updated(self):
        """Handle updates from the performance settings dialog."""
        self._manage_buffer_size()
        self._handle_filters_changed()

    def start_logcat(self):
        """Start the logcat streaming process."""
        if self.is_running or self.logcat_process:
            return

        selected_levels = self._get_selected_levels()

        try:
            args = self._build_logcat_arguments(selected_levels)
        except ValueError as exc:
            self.show_error(str(exc))
            return

        try:
            self._partial_line = ''
            self._suppress_logcat_errors = False

            # Create QProcess for logcat
            process = QProcess(self)
            process.readyReadStandardOutput.connect(self.read_logcat_output)
            process.finished.connect(self.on_logcat_finished)
            process.started.connect(self._handle_logcat_started)
            process.errorOccurred.connect(self._handle_logcat_error)

            self.logcat_process = process

            self.start_btn.setEnabled(False)
            self.stop_btn.setEnabled(False)
            self._update_status_label(f'Starting logcat for {self.device.device_model}...')

            # Use adb logcat with device serial
            cmd = 'adb'
            process.start(cmd, args)

        except Exception as exc:
            self.show_error(f'Error starting logcat: {exc}')
            self._cleanup_logcat_process()
            self._handle_logcat_stopped()

    def _get_selected_levels(self) -> List[str]:
        """Return selected log severity levels in configured order."""
        selected = [level for level in self.log_levels_order if self.log_levels[level].isChecked()]
        return selected or ['E']

    def _handle_logcat_started(self):
        """Update state when the logcat process reports it has started."""
        self.is_running = True
        self.stop_btn.setEnabled(True)
        self._update_status_label(f'Logcat running for {self.device.device_model}...')

    def _handle_logcat_error(self, error):
        """Handle asynchronous logcat process errors."""
        if self._suppress_logcat_errors:
            return

        error_map = {
            QT_QPROCESS.ProcessError.FailedToStart: 'Failed to start logcat process. Ensure ADB is available on PATH.',
            QT_QPROCESS.ProcessError.Crashed: 'Logcat process crashed unexpectedly.',
            QT_QPROCESS.ProcessError.Timedout: 'Timed out while starting logcat process.',
        }
        message = error_map.get(error, f'Logcat process error: {error}')
        self.show_error(message)
        self._cleanup_logcat_process()
        self._handle_logcat_stopped()

    def _build_logcat_arguments(self, selected_levels: List[str]) -> List[str]:
        """Build the adb logcat command arguments based on selected filters."""
        base_args = ['-s', self.device.device_serial_num, 'logcat', '-v', 'threadtime']
        base_args.extend(self._build_source_filters(selected_levels))
        return base_args

    def _build_source_filters(self, selected_levels: List[str]) -> List[str]:
        """Construct filter arguments for tag/package/raw modes."""
        lowest_level = self._get_lowest_level(selected_levels)

        if not hasattr(self, 'log_source_input'):
            return [f'*:{lowest_level}']

        filter_text = self.log_source_input.text().strip()
        if not filter_text:
            return [f'*:{lowest_level}']

        mode = self.log_source_mode.currentData()

        if mode == 'tag':
            tag_level = self._get_lowest_level(selected_levels)
            return [f'{filter_text}:{tag_level}', '*:S']

        if mode == 'package':
            pids = self._resolve_package_pids(filter_text)
            if not pids:
                raise ValueError(
                    f'No running process found for "{filter_text}". '
                    'Launch the app and try again.'
                )

            pid_args: List[str] = []
            for pid in pids:
                pid_args.extend(['--pid', pid])
            pid_args.append(f'*:{lowest_level}')
            return pid_args

        if mode == 'raw':
            return filter_text.split()

        return [f'*:{lowest_level}']

    def _get_lowest_level(self, selected_levels: List[str]) -> str:
        """Get the least restrictive (most verbose) level from selection."""
        priority = {level: index for index, level in enumerate(self.log_levels_order)}
        return min(selected_levels, key=lambda lvl: priority.get(lvl, len(priority)))

    def _resolve_package_pids(self, package_name: str) -> List[str]:
        """Resolve running process IDs for the provided package name."""
        try:
            pids = adb_tools.get_package_pids(self.device.device_serial_num, package_name)
            return [pid.strip() for pid in pids if pid and pid.strip()]
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.warning('PID lookup failed for %s: %s', package_name, exc)
            return []

    def read_logcat_output(self):
        """Read and buffer logcat output for processing."""
        if not self.logcat_process:
            return

        data = self.logcat_process.readAllStandardOutput()
        text = bytes(data).decode('utf-8', errors='replace')

        if not text:
            return

        normalized = text.replace('\r\n', '\n').replace('\r', '\n')
        combined = f'{self._partial_line}{normalized}' if self._partial_line else normalized

        lines = combined.split('\n')
        if combined.endswith('\n'):
            self._partial_line = ''
        else:
            self._partial_line = lines.pop() if lines else combined

        new_lines = [line for line in lines if line.strip()]

        if not new_lines:
            return

        has_filters = self._has_active_filters()

        # Capture matches before trimming raw history
        if has_filters:
            matched_lines = self.filter_lines(new_lines)
            if matched_lines:
                self.filtered_logs.extend(matched_lines)
                self._trim_filtered_logs()

        # Store raw logs for unfiltered view
        self.raw_logs.extend(new_lines)
        self._manage_buffer_size()

        # Buffer new lines for throttled updates
        self.log_buffer.extend(new_lines)

        current_time = time.time() * 1000  # Convert to milliseconds
        time_since_last_update = current_time - self.last_update_time

        should_flush = (
            time_since_last_update >= self.update_interval_ms
            or len(self.log_buffer) >= self.max_buffer_size
        )

        if should_flush:
            self.process_buffered_logs()
        elif not self.update_timer.isActive():
            remaining_time = max(1, int(self.update_interval_ms - time_since_last_update))
            self.update_timer.start(remaining_time)

    def process_buffered_logs(self):
        """Process buffered log lines and update UI."""
        if not self.log_buffer:
            return

        current_time = time.time() * 1000
        self.last_update_time = current_time

        if self._has_active_filters():
            # For active filters, rebuild the filtered view at a throttled cadence
            self.refilter_display()
            self.log_buffer.clear()
            return

        # Limit the number of lines processed per update
        lines_to_process = self.log_buffer[:self.max_lines_per_update]
        self.log_buffer = self.log_buffer[self.max_lines_per_update:]

        # Lines are already filtered in read_logcat_output, no need to filter again

        # Append new lines to the display
        if lines_to_process:
            cursor = self.log_display.textCursor()
            cursor.movePosition(QTextCursor.MoveOperation.End)
            self.log_display.setTextCursor(cursor)

            for line in lines_to_process:
                self.log_display.append(line)

            # Maintain scroll position at bottom for new content
            cursor = self.log_display.textCursor()
            cursor.movePosition(QTextCursor.MoveOperation.End)
            self.log_display.setTextCursor(cursor)

        # Limit total lines in display for performance
        self.limit_log_lines()

        # Update status with buffer info (only when no live filter is active)
        stats = self._get_buffer_stats()
        if stats['buffer_size'] > 0:
            self._update_status_label(f'Logcat running... (buffered: {stats["buffer_size"]} lines)')
        else:
            self._update_status_label(f'Logcat running... ({stats["total_logs"]} lines)')

        # Continue processing if there are more lines in buffer
        if self.log_buffer and not self.update_timer.isActive():
            self.update_timer.start(self.update_interval_ms)

    def limit_log_lines(self):
        """Limit the number of lines in the display for performance."""
        if self._has_active_filters():
            return

        document = self.log_display.document()
        extra_blocks = document.blockCount() - self.max_lines
        if extra_blocks <= 0:
            return

        cursor = QTextCursor(document)
        cursor.movePosition(QTextCursor.MoveOperation.Start)
        for _ in range(extra_blocks):
            cursor.movePosition(QTextCursor.MoveOperation.NextBlock, QTextCursor.MoveMode.KeepAnchor)
        cursor.removeSelectedText()

        # Ensure no leading empty line remains
        cleanup_cursor = QTextCursor(document)
        cleanup_cursor.movePosition(QTextCursor.MoveOperation.Start)
        if cleanup_cursor.block().text() == '':
            cleanup_cursor.deleteChar()

        self._scroll_to_bottom()

    def stop_logcat(self):
        """Stop the logcat streaming process."""
        if self.logcat_process:
            self._suppress_logcat_errors = True
        self._cleanup_logcat_process(terminate=True)
        self._handle_logcat_stopped()

    def on_logcat_finished(self):
        """Handle logcat process completion."""
        self._cleanup_logcat_process()
        self._handle_logcat_stopped()

    def _cleanup_logcat_process(self, terminate: bool = False):
        """Terminate and release the logcat QProcess."""
        process = self.logcat_process
        if not process:
            return

        # Prevent re-entrancy before invoking Qt methods that might delete the object
        self.logcat_process = None

        try:
            if terminate:
                try:
                    process.kill()
                except RuntimeError as exc:
                    logger.debug('Kill skipped (process already gone): %s', exc)
                except AttributeError:
                    pass
                try:
                    process.waitForFinished(3000)
                except RuntimeError as exc:
                    logger.debug('waitForFinished skipped (process already gone): %s', exc)
                except AttributeError:
                    pass
        except Exception as exc:
            logger.warning('Failed to terminate logcat process: %s', exc)
        finally:
            delete_later = getattr(process, 'deleteLater', None)
            if callable(delete_later):
                try:
                    delete_later()
                except RuntimeError as exc:
                    logger.debug('deleteLater skipped (process already deleted): %s', exc)

    def _handle_logcat_stopped(self):
        """Reset state and UI once logcat streaming halts."""
        self.update_timer.stop()
        self.log_buffer.clear()
        self._partial_line = ''
        self._suppress_logcat_errors = False
        self._last_rendered_mode = None
        self._last_rendered_text = ''

        self.is_running = False
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)

        if self.raw_logs:
            self.refilter_display()
        else:
            self._update_status_label('Logcat stopped.')

    def clear_logs(self):
        """Clear the log display."""
        self.log_display.clear()
        self.raw_logs.clear()
        self.filtered_logs.clear()
        self.log_buffer.clear()
        self._partial_line = ''
        self._last_rendered_mode = None
        self._last_rendered_text = ''
        self._update_status_label('Logs cleared')

    def apply_live_filter(self, pattern):
        """Apply live regex filter to logs in real-time."""
        self.live_filter_pattern = pattern.strip() if pattern.strip() else None
        self._handle_filters_changed()

    def refilter_display(self):
        """Re-filter all logs and update display."""
        if self._has_active_filters():
            self._render_filtered_logs()
        else:
            self._render_unfiltered_logs()

    def _render_filtered_logs(self):
        """Display filtered logs without truncating pre-filtered history."""
        logs_to_display = self.filtered_logs[-self.max_lines:]
        new_text = '\n'.join(logs_to_display) if logs_to_display else 'No logs match the current filter.'
        mode_changed = self._last_rendered_mode != 'filtered'

        if not mode_changed and new_text == self._last_rendered_text:
            self._update_filtered_status()
            return

        self.log_display.setPlainText(new_text)
        if logs_to_display:
            self._scroll_to_bottom()

        self._last_rendered_mode = 'filtered'
        self._last_rendered_text = new_text
        self._update_filtered_status()

    def _render_unfiltered_logs(self):
        """Display unfiltered logs from the raw buffer."""
        logs_to_display = self.raw_logs[-self.max_lines:]
        new_text = '\n'.join(logs_to_display) if logs_to_display else ''
        mode_changed = self._last_rendered_mode != 'raw'

        if not mode_changed and new_text == self._last_rendered_text:
            raw_count = len(self.raw_logs)
            capacity = self.max_lines * self.history_multiplier
            self._update_status_label(f'Total: {raw_count}/{capacity} lines')
            return

        if new_text:
            self.log_display.setPlainText(new_text)
            self._scroll_to_bottom()
        else:
            self.log_display.clear()

        self._last_rendered_mode = 'raw'
        self._last_rendered_text = new_text
        raw_count = len(self.raw_logs)
        capacity = self.max_lines * self.history_multiplier
        self._update_status_label(f'Total: {raw_count}/{capacity} lines')

    def _scroll_to_bottom(self):
        """Scroll log display to bottom."""
        scrollbar = self.log_display.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def closeEvent(self, event: QCloseEvent) -> None:  # type: ignore[override]
        """Ensure the logcat process stops when the window closes."""
        if self.logcat_process:
            self.stop_logcat()
        super().closeEvent(event)

    def filter_lines(self, lines):
        """Filter lines based on current live filter."""
        patterns = []
        if self.live_filter_pattern:
            patterns.append(self.live_filter_pattern)

        if self.active_filters:
            patterns.extend(
                filter_data['pattern']
                for filter_data in self.active_filters
                if filter_data.get('pattern')
            )

        if not patterns:
            return lines

        compiled_patterns = []
        for raw_pattern in patterns:
            try:
                compiled_patterns.append(re.compile(raw_pattern, re.IGNORECASE))
            except re.error:
                # Skip invalid regex patterns to keep UI responsive
                continue

        if not compiled_patterns:
            return lines

        filtered = []
        for line in lines:
            if any(pattern.search(line) for pattern in compiled_patterns):
                filtered.append(line)
        return filtered

    def load_saved_filter(self, filter_name):
        """Update preview when saved filter is selected."""
        if not filter_name or filter_name not in self.filters:
            return

        pattern = self.filters[filter_name]
        self.filter_input.blockSignals(True)
        self.filter_input.setText(pattern)
        self.filter_input.blockSignals(False)
        self.apply_live_filter(pattern)

    def apply_selected_filter(self):
        """Apply the selected saved filter."""
        current_filter = self.saved_filters_combo.currentText()
        if current_filter and current_filter in self.filters:
            self.add_active_filter(current_filter, self.filters[current_filter])

    def open_performance_settings(self):
        """Open performance settings dialog."""
        dialog = PerformanceSettingsDialog(self)
        dialog.exec()

    def update_log_levels(self):
        """Update logcat when log levels change (only if running)."""
        if self.is_running:
            # Restart logcat with new log levels
            self.stop_logcat()
            self.start_logcat()

    def create_vertical_separator(self):
        """Create a vertical separator line."""
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.VLine)
        separator.setFrameShadow(QFrame.Shadow.Sunken)
        return separator

    def load_filters(self):
        """Load saved filters from config file."""
        try:
            config_dir = os.path.expanduser('~')
            config_file = os.path.join(config_dir, '.lazy_blacktea_filters.json')

            if os.path.exists(config_file):
                import json
                with open(config_file, 'r', encoding='utf-8') as f:
                    self.filters = json.load(f)
                self.update_saved_filters_combo()
        except Exception as e:
            logger.warning(f'Failed to load filters: {e}')

    def save_filters(self):
        """Save filters to config file."""
        try:
            config_dir = os.path.expanduser('~')
            config_file = os.path.join(config_dir, '.lazy_blacktea_filters.json')

            import json
            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump(self.filters, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.warning(f'Failed to save filters: {e}')

    def show_error(self, message):
        """Show error message dialog."""
        from PyQt6.QtWidgets import QMessageBox
        QMessageBox.critical(self, 'Logcat Error', message)
