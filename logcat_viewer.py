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
    QDialog, QVBoxLayout, QHBoxLayout, QTextEdit, QPushButton, QLabel,
    QLineEdit, QComboBox, QCheckBox, QFrame, QMessageBox, QInputDialog,
    QFormLayout
)
from PyQt6.QtCore import (
    QProcess, QTimer, QIODevice, Qt, pyqtSignal
)
from PyQt6.QtGui import QFont, QTextCursor

logger = logging.getLogger(__name__)


class PerformanceSettingsDialog(QDialog):
    """Performance settings dialog for Logcat viewer."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_window = parent
        self.init_ui()

    def init_ui(self):
        """Initialize the performance settings dialog UI."""
        self.setWindowTitle('Performance Settings')
        self.setFixedSize(350, 250)
        self.setModal(True)

        # Main layout
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(15)

        # Title
        title = QLabel('Performance Settings')
        title.setStyleSheet('font-size: 14px; font-weight: bold; color: #2E86C1;')
        main_layout.addWidget(title)

        # Settings section
        settings_layout = QVBoxLayout()
        settings_layout.setSpacing(10)

        # Max Lines
        max_lines_layout = QHBoxLayout()
        max_lines_label = QLabel('Max Lines:')
        max_lines_label.setFixedWidth(120)
        max_lines_layout.addWidget(max_lines_label)
        self.max_lines_spin = QLineEdit(str(self.parent_window.max_lines if self.parent_window else '1000'))
        self.max_lines_spin.setFixedWidth(80)
        max_lines_layout.addWidget(self.max_lines_spin)
        max_lines_layout.addStretch()
        settings_layout.addLayout(max_lines_layout)

        # Update Interval
        interval_layout = QHBoxLayout()
        interval_label = QLabel('Update Interval:')
        interval_label.setFixedWidth(120)
        interval_layout.addWidget(interval_label)
        self.update_interval_spin = QLineEdit(str(self.parent_window.update_interval_ms if self.parent_window else '200'))
        self.update_interval_spin.setFixedWidth(80)
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
        self.lines_per_update_spin = QLineEdit(str(self.parent_window.max_lines_per_update if self.parent_window else '50'))
        self.lines_per_update_spin.setFixedWidth(80)
        lines_update_layout.addWidget(self.lines_per_update_spin)
        lines_update_layout.addStretch()
        settings_layout.addLayout(lines_update_layout)

        main_layout.addLayout(settings_layout)

        # Performance Tips
        tips_frame = QFrame()
        tips_frame.setStyleSheet('background-color: #f8f9fa; border: 1px solid #dee2e6; border-radius: 4px; padding: 10px;')
        tips_layout = QVBoxLayout(tips_frame)

        tips_label = QLabel('Performance Tips:')
        tips_label.setStyleSheet('font-weight: bold; color: #495057;')
        tips_layout.addWidget(tips_label)

        tips_text = QLabel('• Higher Max Lines = More memory usage\n• Lower Update Interval = More responsive but higher CPU')
        tips_text.setStyleSheet('color: #6c757d; font-size: 11px;')
        tips_layout.addWidget(tips_text)

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

    def apply_settings(self):
        """Apply the performance settings."""
        if not self.parent_window:
            self.accept()
            return

        try:
            # Update max lines
            max_lines = max(100, int(self.max_lines_spin.text()))
            self.parent_window.max_lines = max_lines

            # Update interval
            interval = max(50, int(self.update_interval_spin.text()))
            self.parent_window.update_interval_ms = interval

            # Update lines per update
            lines_per_update = max(10, int(self.lines_per_update_spin.text()))
            self.parent_window.max_lines_per_update = lines_per_update

            self.accept()
        except ValueError:
            QMessageBox.warning(self, 'Invalid Input', 'Please enter valid numbers for all settings.')


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

        # Additional performance settings
        self.max_lines_per_update = 50  # Maximum lines to add to UI per update
        self.last_update_time = 0

        # Real-time filtering
        self.current_live_filter = None
        self.all_logs = []  # Store all logs for re-filtering

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
        return {
            'total_logs': len(self.all_logs),
            'buffer_size': len(self.log_buffer),
            'filtered_count': len(self.filter_lines(self.all_logs)) if self.current_live_filter else 0
        }

    def _manage_buffer_size(self):
        """Manage all_logs buffer size based on current mode."""
        if self.current_live_filter:
            # When filtering is active, keep more logs to provide richer filter results
            filter_buffer_size = self.max_lines * 5  # Keep 5x more logs for filtering
            if len(self.all_logs) > filter_buffer_size:
                self.all_logs = self.all_logs[-filter_buffer_size:]
        else:
            # When not filtering, use rolling window of max_lines for performance
            if len(self.all_logs) > self.max_lines:
                self.all_logs = self.all_logs[-self.max_lines:]

    def init_ui(self):
        """Initialize the logcat window UI."""
        self.setWindowTitle(f'Logcat Viewer - {self.device.device_model} ({self.device.device_serial_num[:8]}...)')
        self.setGeometry(100, 100, 1200, 800)

        # Main layout
        layout = QVBoxLayout(self)

        # Control panel
        control_layout = self.create_control_panel()
        layout.addLayout(control_layout)

        # Filter panel
        filter_layout = self.create_filter_panel()
        layout.addLayout(filter_layout)

        # Log display
        self.log_display = QTextEdit()
        self.log_display.setFont(QFont('Consolas', 10))
        self.log_display.setReadOnly(True)
        self.log_display.setStyleSheet("""
            QTextEdit {
                background-color: #1e1e1e;
                color: #ffffff;
                border: 1px solid #3e3e3e;
            }
        """)
        layout.addWidget(self.log_display)

        # Status bar
        self.status_label = QLabel('Ready to start logcat...')
        layout.addWidget(self.status_label)

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

        # Set default checked states (Info, Warn, Error, Fatal)
        for level, checkbox in self.log_levels.items():
            if level in ['I', 'W', 'E', 'F']:
                checkbox.setChecked(True)
            checkbox.stateChanged.connect(self.update_log_levels)
            layout.addWidget(checkbox)

        layout.addStretch()
        return layout

    def create_filter_panel(self):
        """Create the filter panel with real-time regex filtering and multiple filter support."""
        layout = QVBoxLayout()

        # Filter input section
        filter_input_layout = QHBoxLayout()

        # Live filter input - applies immediately
        self.filter_input = QLineEdit()
        self.filter_input.setPlaceholderText('Type to filter logs in real-time...')
        self.filter_input.textChanged.connect(self.apply_live_filter)  # Real-time filtering
        filter_input_layout.addWidget(QLabel('Filter:'))
        filter_input_layout.addWidget(self.filter_input)

        # Save current filter button
        save_filter_btn = QPushButton('💾 Save Filter')
        save_filter_btn.clicked.connect(self.save_current_filter)
        filter_input_layout.addWidget(save_filter_btn)

        layout.addLayout(filter_input_layout)

        # Saved filters section
        saved_filters_layout = QHBoxLayout()

        # Dropdown for saved filters
        self.saved_filters_combo = QComboBox()
        self.saved_filters_combo.setEditable(False)
        self.saved_filters_combo.currentTextChanged.connect(self.load_saved_filter)
        saved_filters_layout.addWidget(QLabel('Saved:'))
        saved_filters_layout.addWidget(self.saved_filters_combo)

        # Apply saved filter button
        apply_filter_btn = QPushButton('📋 Apply')
        apply_filter_btn.clicked.connect(self.apply_selected_filter)
        saved_filters_layout.addWidget(apply_filter_btn)

        # Delete saved filter button
        delete_filter_btn = QPushButton('🗑️ Delete')
        delete_filter_btn.clicked.connect(self.delete_saved_filter)
        saved_filters_layout.addWidget(delete_filter_btn)

        saved_filters_layout.addStretch()
        layout.addLayout(saved_filters_layout)

        return layout

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
                QMessageBox.information(self, 'Filter Deleted', f'Filter "{current_filter}" deleted successfully!')

    def update_saved_filters_combo(self):
        """Update the saved filters combo box."""
        current_text = self.saved_filters_combo.currentText()
        self.saved_filters_combo.clear()
        self.saved_filters_combo.addItems(list(self.filters.keys()))
        # Try to restore selection
        if current_text in self.filters:
            self.saved_filters_combo.setCurrentText(current_text)

    def start_logcat(self):
        """Start the logcat streaming process."""
        if self.is_running:
            return

        try:
            # Create QProcess for logcat
            self.logcat_process = QProcess()
            self.logcat_process.readyReadStandardOutput.connect(self.read_logcat_output)
            self.logcat_process.finished.connect(self.on_logcat_finished)

            # Build logcat command with selected log levels
            selected_levels = [level for level, checkbox in self.log_levels.items() if checkbox.isChecked()]
            if not selected_levels:
                selected_levels = ['E']  # Default to Error if nothing selected

            level_filter = ' '.join([f'*:{level}' for level in selected_levels])

            # Use adb logcat with device serial
            cmd = 'adb'
            args = ['-s', self.device.device_serial_num, 'logcat', '-v', 'threadtime'] + level_filter.split()

            self.logcat_process.start(cmd, args)

            if self.logcat_process.waitForStarted():
                self.is_running = True
                self.start_btn.setEnabled(False)
                self.stop_btn.setEnabled(True)
                self._update_status_label(f'Logcat running for {self.device.device_model}...')
            else:
                self.show_error('Failed to start logcat process')

        except Exception as e:
            self.show_error(f'Error starting logcat: {str(e)}')

    def read_logcat_output(self):
        """Read and buffer logcat output for processing."""
        if not self.logcat_process:
            return

        data = self.logcat_process.readAllStandardOutput()
        text = bytes(data).decode('utf-8', errors='replace')

        if not text.strip():
            return

        # Split into individual lines and process
        lines = text.strip().split('\n')
        new_lines = [line for line in lines if line.strip()]

        # Store all logs for re-filtering
        self.all_logs.extend(new_lines)

        # Manage buffer size based on current mode
        self._manage_buffer_size()

        # For live filtering, we need to update the entire display
        # instead of just appending new lines
        if self.current_live_filter:
            # Immediately re-filter and update display
            self.refilter_display()
        else:
            # Buffer new lines for performance-optimized updates
            self.log_buffer.extend(new_lines)

            # Trigger throttled update
            current_time = time.time() * 1000  # Convert to milliseconds
            time_since_last_update = current_time - self.last_update_time

            if time_since_last_update >= self.update_interval_ms or len(self.log_buffer) >= self.max_buffer_size:
                # Immediate update
                self.process_buffered_logs()
            elif not self.update_timer.isActive():
                # Schedule delayed update
                remaining_time = max(1, int(self.update_interval_ms - time_since_last_update))
                self.update_timer.start(remaining_time)

    def process_buffered_logs(self):
        """Process buffered log lines and update UI."""
        if not self.log_buffer or self.current_live_filter:
            return

        current_time = time.time() * 1000
        self.last_update_time = current_time

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
        if not self.current_live_filter:
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
        doc = self.log_display.document()
        if doc.lineCount() > self.max_lines:
            # More efficient: remove text in blocks rather than line by line
            cursor = self.log_display.textCursor()
            cursor.movePosition(QTextCursor.MoveOperation.Start)

            # Calculate how many lines to remove (remove 1/3 when limit reached)
            lines_to_remove = self.max_lines // 3

            # Move cursor to the position after lines to remove
            for _ in range(lines_to_remove):
                cursor.movePosition(QTextCursor.MoveOperation.Down)
                cursor.movePosition(QTextCursor.MoveOperation.EndOfLine)

            # Select and delete the old lines
            cursor.movePosition(QTextCursor.MoveOperation.End, QTextCursor.MoveMode.KeepAnchor)
            end_pos = cursor.position()
            cursor.setPosition(0)
            cursor.setPosition(end_pos, QTextCursor.MoveMode.KeepAnchor)

            # Only remove if we selected something
            if cursor.hasSelection():
                cursor.removeSelectedText()

    def stop_logcat(self):
        """Stop the logcat streaming process."""
        if self.logcat_process and self.is_running:
            self.logcat_process.kill()
            self.logcat_process.waitForFinished(3000)

        # Clean up performance optimization resources
        self.update_timer.stop()
        self.log_buffer.clear()

        self.is_running = False
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        # Update status to show paused state with line counts
        self.refilter_display()

    def on_logcat_finished(self):
        """Handle logcat process completion."""
        # Clean up performance optimization resources
        self.update_timer.stop()
        self.log_buffer.clear()

        self.is_running = False
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        # Update status to show paused state with line counts
        self.refilter_display()

    def clear_logs(self):
        """Clear the log display."""
        self.log_display.clear()
        self.all_logs.clear()
        self.log_buffer.clear()
        self._update_status_label('Logs cleared')

    def apply_live_filter(self, pattern):
        """Apply live regex filter to logs in real-time."""
        self.current_live_filter = pattern.strip() if pattern.strip() else None
        # Re-filter and update display immediately
        self.refilter_display()

    def refilter_display(self):
        """Re-filter all logs and update display."""
        if not self.all_logs:
            return

        self.log_display.clear()

        if self.current_live_filter:
            self._display_filtered_logs()
        else:
            self._display_unfiltered_logs()

    def _display_filtered_logs(self):
        """Display filtered logs without any max_lines limit."""
        filtered_logs = self.filter_lines(self.all_logs)
        stats = self._get_buffer_stats()

        if filtered_logs:
            # Show ALL filtered results - no truncation
            # The filter itself naturally limits the results
            all_filtered_text = '\n'.join(filtered_logs)
            self.log_display.setPlainText(all_filtered_text)
            self._scroll_to_bottom()
        else:
            # No filtered results
            self.log_display.setPlainText('No logs match the current filter.')

        # Update status for filtered mode
        self._update_status_label(f'Filtered: {stats["filtered_count"]}/{stats["total_logs"]} lines')

    def _display_unfiltered_logs(self):
        """Display unfiltered logs (buffer management already applied)."""
        logs_to_display = self.all_logs
        stats = self._get_buffer_stats()

        if logs_to_display:
            all_text = '\n'.join(logs_to_display)
            self.log_display.setPlainText(all_text)
            self._scroll_to_bottom()

        # Update status for unfiltered mode
        self._update_status_label(f'Total: {stats["total_logs"]} lines')

    def _scroll_to_bottom(self):
        """Scroll log display to bottom."""
        scrollbar = self.log_display.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def filter_lines(self, lines):
        """Filter lines based on current live filter."""
        if not self.current_live_filter:
            return lines

        try:
            pattern = re.compile(self.current_live_filter, re.IGNORECASE)
            return [line for line in lines if pattern.search(line)]
        except re.error:
            # Invalid regex, return all lines
            return lines

    def load_saved_filter(self, filter_name):
        """Update preview when saved filter is selected."""
        # Just update the selection, don't auto-apply
        pass

    def apply_selected_filter(self):
        """Apply the selected saved filter."""
        current_filter = self.saved_filters_combo.currentText()
        if current_filter and current_filter in self.filters:
            # Apply the selected filter to the input
            self.filter_input.setText(self.filters[current_filter])
            # The textChanged signal will trigger apply_live_filter automatically

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