"""
Logcat Viewer Component - Extracted from lazy_blacktea_pyqt.py
Provides real-time logcat streaming and filtering capabilities.
"""

import logging
import os
import re
import subprocess
import time
from dataclasses import dataclass, replace
from typing import Optional, Dict, List, Any, Callable

from PyQt6.QtWidgets import (
    QWidget, QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, QSplitter, QListView,
    QPushButton, QLabel, QLineEdit, QComboBox, QCheckBox, QFrame, QMessageBox,
    QInputDialog, QListWidget, QListWidgetItem, QAbstractItemView,
    QSpinBox, QSizePolicy, QGroupBox, QFormLayout, QApplication, QMenu
)
from PyQt6.QtCore import (
    QObject, QProcess, QTimer, Qt, QAbstractListModel, QModelIndex, QSortFilterProxyModel
)
from PyQt6.QtGui import QFont, QCloseEvent, QAction, QKeySequence, QShortcut

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


class CollapsiblePanel(QWidget):
    """A simple collapsible panel controlled by a header button.

    - The header is a button with a disclosure indicator.
    - Clicking toggles the visibility of the content widget.
    """

    def __init__(self, title: str, content: Optional[QWidget] = None, *, collapsed: bool = False, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._collapsed = collapsed
        self._content_widget: Optional[QWidget] = None

        self._root = QVBoxLayout(self)
        self._root.setContentsMargins(0, 0, 0, 0)
        self._root.setSpacing(4)

        self._toggle_btn = QPushButton(self._title_text(title))
        self._toggle_btn.setCheckable(True)
        self._toggle_btn.setChecked(not collapsed)
        self._toggle_btn.setFlat(True)
        self._toggle_btn.clicked.connect(self._on_toggled)
        self._toggle_btn.setStyleSheet(
            """
            QPushButton {
                text-align: left;
                padding: 6px 8px;
                color: #d0d3d4;
                background-color: #2b2f33;
                border: 1px solid #3e444a;
                border-radius: 6px;
                font-weight: 600;
            }
            QPushButton:pressed {
                background-color: #25323a;
            }
            """
        )
        self._root.addWidget(self._toggle_btn)

        self._content_container = QWidget()
        self._content_container.setObjectName('collapsible_content')
        self._content_container.setStyleSheet(
            """
            QWidget#collapsible_content {
                background-color: #2c2c2c;
                border: 1px solid #3e3e3e;
                border-radius: 6px;
            }
            """
        )
        self._content_layout = QVBoxLayout(self._content_container)
        self._content_layout.setContentsMargins(8, 8, 8, 8)
        self._content_layout.setSpacing(6)
        self._root.addWidget(self._content_container)

        if content is not None:
            self.set_content(content)

        self._apply_collapsed_state()

    def _title_text(self, title: str) -> str:
        return ('▾ ' if not self._collapsed else '▸ ') + title

    def _on_toggled(self):
        self._collapsed = not self._toggle_btn.isChecked()
        self._apply_collapsed_state()

    def _apply_collapsed_state(self):
        self._content_container.setVisible(not self._collapsed)
        # Update disclosure indicator
        text = self._toggle_btn.text()
        plain = text[2:] if len(text) > 2 else text
        self._toggle_btn.setText(self._title_text(plain))

    def set_content(self, widget: QWidget) -> None:
        # Clear previous
        while self._content_layout.count():
            item = self._content_layout.takeAt(0)
            if (w := item.widget()) is not None:
                w.setParent(None)
        self._content_widget = widget
        self._content_layout.addWidget(widget)
        self._apply_collapsed_state()

    def set_collapsed(self, collapsed: bool) -> None:
        self._collapsed = bool(collapsed)
        self._toggle_btn.setChecked(not self._collapsed)
        self._apply_collapsed_state()

    def is_collapsed(self) -> bool:
        return self._collapsed


@dataclass(frozen=True)
class LogLine:
    """Represents a parsed logcat line with convenient accessors."""

    timestamp: str
    pid: str
    tid: str
    level: str
    tag: str
    message: str
    raw: str
    line_no: int = 0

    _THREADTIME_PATTERN = re.compile(
        r'^(?P<timestamp>\d{2}-\d{2}\s\d{2}:\d{2}:\d{2}\.\d{3})\s+'
        r'(?P<pid>\d+)\s+(?P<tid>\d+)\s+'
        r'(?P<level>[VDIWEF])\s+'
        r'(?P<tag>[^:]*):\s'
        r'(?P<message>.*)$'
    )

    @classmethod
    def from_string(cls, line: str) -> "LogLine":
        match = cls._THREADTIME_PATTERN.match(line)
        if match:
            parts = match.groupdict()
            return cls(
                timestamp=parts['timestamp'],
                pid=parts['pid'],
                tid=parts['tid'],
                level=parts['level'],
                tag=parts['tag'].strip(),
                message=parts['message'].strip(),
                raw=line,
            )
        cleaned = line.strip()
        return cls('', '', '', 'I', 'Logcat', cleaned, raw=line)


class LogcatListModel(QAbstractListModel):
    """List model holding log lines for QListView rendering."""

    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._logs: List[LogLine] = []

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:  # type: ignore[override]
        if parent.isValid():
            return 0
        return len(self._logs)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:  # type: ignore[override]
        if not index.isValid() or not (0 <= index.row() < len(self._logs)):
            return None
        log = self._logs[index.row()]
        if role == Qt.ItemDataRole.DisplayRole:
            return log.raw
        if role == Qt.ItemDataRole.UserRole:
            return log
        return None

    def append_lines(self, lines: List[LogLine]) -> None:
        if not lines:
            return
        start = len(self._logs)
        end = start + len(lines) - 1
        self.beginInsertRows(QModelIndex(), start, end)
        self._logs.extend(lines)
        self.endInsertRows()

    def clear(self) -> None:
        if not self._logs:
            return
        self.beginResetModel()
        self._logs.clear()
        self.endResetModel()

    def trim(self, max_size: int) -> None:
        if max_size <= 0 or len(self._logs) <= max_size:
            return
        remove_count = len(self._logs) - max_size
        self.remove_first(remove_count)

    def get_line(self, row: int) -> Optional[LogLine]:
        if 0 <= row < len(self._logs):
            return self._logs[row]
        return None

    def to_list(self) -> List[LogLine]:
        return list(self._logs)

    def remove_first(self, count: int) -> None:
        if count <= 0 or not self._logs:
            return
        actual = min(count, len(self._logs))
        self.beginRemoveRows(QModelIndex(), 0, actual - 1)
        del self._logs[:actual]
        self.endRemoveRows()


class LogcatFilterProxyModel(QSortFilterProxyModel):
    """Proxy model applying regex filters and visible limits."""

    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._live_pattern: Optional[str] = None
        self._saved_patterns: List[str] = []
        self._compiled_patterns: List[re.Pattern[str]] = []
        self._visible_limit = 0
        self._limit_cache: Optional[set[int]] = None

    def set_live_pattern(self, pattern: Optional[str]) -> None:
        normalized = pattern.strip() if pattern and pattern.strip() else None
        if normalized == self._live_pattern:
            return
        self._live_pattern = normalized
        self._limit_cache = None
        self._rebuild_patterns()

    def set_saved_patterns(self, patterns: List[str]) -> None:
        normalized = [p.strip() for p in patterns if p and p.strip()]
        if normalized == self._saved_patterns:
            return
        self._saved_patterns = normalized
        self._limit_cache = None
        self._rebuild_patterns()

    def set_visible_limit(self, limit: int) -> None:
        limit = max(0, int(limit))
        if limit == self._visible_limit:
            return
        self._visible_limit = limit
        self._limit_cache = None
        self.invalidateFilter()

    def _rebuild_patterns(self) -> None:
        compiled: List[re.Pattern[str]] = []
        for pattern in [self._live_pattern, *self._saved_patterns]:
            if not pattern:
                continue
            try:
                compiled.append(re.compile(pattern, re.IGNORECASE))
            except re.error:
                continue
        self._compiled_patterns = compiled
        self.invalidateFilter()

    def _matches(self, text: str) -> bool:
        if not self._compiled_patterns:
            return True
        return any(pattern.search(text) for pattern in self._compiled_patterns)

    def reset_limit_cache(self) -> None:
        """Clear cached limit computation so next filter pass recomputes it."""
        self._limit_cache = None

    def _ensure_limit_cache(self) -> Optional[set[int]]:
        if self._visible_limit <= 0:
            return None
        if self._limit_cache is not None:
            return self._limit_cache

        model = self.sourceModel()
        if model is None:
            self._limit_cache = set()
            return self._limit_cache

        cache: set[int] = set()
        remaining = self._visible_limit
        for row in range(model.rowCount() - 1, -1, -1):
            index = model.index(row, 0)
            log: Optional[LogLine] = model.data(index, Qt.ItemDataRole.UserRole)
            text = log.raw if log else (model.data(index, Qt.ItemDataRole.DisplayRole) or '')
            if self._matches(str(text)):
                cache.add(row)
                remaining -= 1
                if remaining <= 0:
                    break

        self._limit_cache = cache
        return cache

    def filterAcceptsRow(self, source_row: int, source_parent: QModelIndex) -> bool:  # type: ignore[override]
        model = self.sourceModel()
        if model is None:
            return False

        index = model.index(source_row, 0, source_parent)
        log: Optional[LogLine] = model.data(index, Qt.ItemDataRole.UserRole)
        text = log.raw if log else (model.data(index, Qt.ItemDataRole.DisplayRole) or '')

        if not self._matches(str(text)):
            return False

        cache = self._ensure_limit_cache()
        if cache is None:
            return True
        return source_row in cache

class PerformanceSettingsDialog(QDialog):
    """Performance settings dialog for Logcat viewer."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_window = parent
        self.init_ui()

    def init_ui(self):
        """Initialize the performance settings dialog UI."""
        self.setWindowTitle('Performance Settings')
        self.setMinimumSize(520, 360)
        self.setModal(True)

        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(14)
        main_layout.setContentsMargins(18, 18, 18, 16)

        title = QLabel('Tune Logcat Performance')
        title.setStyleSheet('font-size: 16px; font-weight: 600; color: #1b4f72;')
        main_layout.addWidget(title)

        subtitle = QLabel('Balance retained history with UI responsiveness. Adjust these knobs to fit your device throughput.')
        subtitle.setWordWrap(True)
        subtitle.setStyleSheet('color: #5f6a6a;')
        main_layout.addWidget(subtitle)

        preset_row = QHBoxLayout()
        preset_label = QLabel('Preset')
        preset_label.setStyleSheet('font-weight: bold;')
        preset_row.addWidget(preset_label)

        self.preset_combo = QComboBox()
        self.preset_combo.addItem('Custom')
        for preset_name in PERFORMANCE_PRESETS.keys():
            self.preset_combo.addItem(preset_name)
        preset_row.addWidget(self.preset_combo, stretch=1)
        preset_row.addStretch()
        main_layout.addLayout(preset_row)

        content_grid = QGridLayout()
        content_grid.setHorizontalSpacing(18)
        content_grid.setVerticalSpacing(12)

        history_group = QGroupBox('History & Retention')
        history_form = QFormLayout(history_group)
        history_form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        history_form.setFormAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)

        self.max_lines_spin = QSpinBox()
        self.max_lines_spin.setRange(100, 50000)
        self.max_lines_spin.setSingleStep(100)
        self.max_lines_spin.setValue(self.parent_window.max_lines if self.parent_window else 1000)
        history_form.addRow('Visible lines', self.max_lines_spin)

        self.history_multiplier_spin = QSpinBox()
        self.history_multiplier_spin.setRange(1, 20)
        self.history_multiplier_spin.setSingleStep(1)
        self.history_multiplier_spin.setValue(self.parent_window.history_multiplier if self.parent_window else 5)
        history_form.addRow('History multiplier', self.history_multiplier_spin)

        content_grid.addWidget(history_group, 0, 0)

        cadence_group = QGroupBox('Streaming Cadence')
        cadence_form = QFormLayout(cadence_group)
        cadence_form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        cadence_form.setFormAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)

        self.update_interval_spin = QSpinBox()
        self.update_interval_spin.setRange(50, 2000)
        self.update_interval_spin.setSingleStep(10)
        self.update_interval_spin.setValue(self.parent_window.update_interval_ms if self.parent_window else 200)
        interval_row = QWidget()
        interval_layout = QHBoxLayout(interval_row)
        interval_layout.setContentsMargins(0, 0, 0, 0)
        interval_layout.setSpacing(6)
        interval_layout.addWidget(self.update_interval_spin)
        interval_layout.addWidget(QLabel('ms'))
        interval_layout.addStretch()
        cadence_form.addRow('Refresh interval', interval_row)

        self.lines_per_update_spin = QSpinBox()
        self.lines_per_update_spin.setRange(10, 500)
        self.lines_per_update_spin.setSingleStep(5)
        self.lines_per_update_spin.setValue(self.parent_window.max_lines_per_update if self.parent_window else 50)
        cadence_form.addRow('Lines per update', self.lines_per_update_spin)

        self.buffer_size_spin = QSpinBox()
        self.buffer_size_spin.setRange(10, 1000)
        self.buffer_size_spin.setSingleStep(10)
        self.buffer_size_spin.setValue(self.parent_window.max_buffer_size if self.parent_window else 100)
        buffer_row = QWidget()
        buffer_layout = QHBoxLayout(buffer_row)
        buffer_layout.setContentsMargins(0, 0, 0, 0)
        buffer_layout.setSpacing(6)
        buffer_layout.addWidget(self.buffer_size_spin)
        buffer_layout.addWidget(QLabel('lines'))
        buffer_layout.addStretch()
        cadence_form.addRow('Flush threshold', buffer_row)

        content_grid.addWidget(cadence_group, 0, 1)

        main_layout.addLayout(content_grid)

        preview_frame = QFrame()
        preview_frame.setStyleSheet('background-color: #f4f6f6; border: 1px solid #d6dbdf; border-radius: 6px; padding: 10px;')
        preview_layout = QVBoxLayout(preview_frame)
        preview_layout.setSpacing(4)

        preview_title = QLabel('Preview')
        preview_title.setStyleSheet('font-weight: bold; color: #34495e;')
        preview_layout.addWidget(preview_title)

        self.capacity_label = QLabel()
        self.capacity_label.setStyleSheet('color: #1f618d;')
        preview_layout.addWidget(self.capacity_label)

        self.latency_label = QLabel()
        self.latency_label.setStyleSheet('color: #616a6b;')
        preview_layout.addWidget(self.latency_label)

        tips_label = QLabel('Lower intervals provide lower latency but increase CPU usage. Larger flush thresholds smooth bursty logs.')
        tips_label.setWordWrap(True)
        tips_label.setStyleSheet('color: #7b8793; font-size: 11px;')
        preview_layout.addWidget(tips_label)

        main_layout.addWidget(preview_frame)

        button_layout = QHBoxLayout()
        button_layout.addStretch()
        cancel_btn = QPushButton('Cancel')
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)

        apply_btn = QPushButton('Apply')
        apply_btn.setStyleSheet('background-color: #1f618d; color: white; font-weight: bold;')
        apply_btn.clicked.connect(self.apply_settings)
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
            f'History capacity: {capacity:,} lines ({max_lines:,} visible × {history_multiplier} history)'
        )

        interval = self.update_interval_spin.value()
        lines_per_update = self.lines_per_update_spin.value()
        flush_threshold = self.buffer_size_spin.value()
        hz = 0.0 if interval <= 0 else 1000.0 / interval
        self.latency_label.setText(
            f'UI refresh ≈ every {interval} ms ({hz:.1f} Hz), {lines_per_update} lines/batch, flush at {flush_threshold} lines.'
        )


class LogcatWindow(QDialog):
    """Logcat viewer window with real-time streaming and filtering capabilities."""

    def __init__(
        self,
        device,
        parent=None,
        *,
        settings: Optional[Dict[str, int]] = None,
        on_settings_changed: Optional[Callable[[Dict[str, int]], None]] = None,
    ):
        super().__init__(parent)
        self.setWindowFlag(Qt.WindowType.WindowContextHelpButtonHint, False)
        self.setWindowFlag(Qt.WindowType.WindowMinMaxButtonsHint, True)
        self.setWindowFlag(Qt.WindowType.WindowMaximizeButtonHint, True)
        self.setSizeGripEnabled(True)

        self.device = device
        self.logcat_process = None
        self.is_running = False
        self.max_lines = 1000
        self.filters: Dict[str, str] = {}
        self.current_filter = None
        self._settings_callback = on_settings_changed

        # Data model and filtering pipeline
        self.log_model = LogcatListModel(self)
        self.log_proxy = LogcatFilterProxyModel(self)
        self.log_proxy.setSourceModel(self.log_model)
        self.log_proxy.set_visible_limit(self.max_lines)
        self.filtered_model = LogcatListModel(self)
        self._compiled_filter_patterns: List[re.Pattern[str]] = []

        # Performance and buffering configuration
        self.log_buffer: List[LogLine] = []
        self.max_buffer_size = 100
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.process_buffered_logs)
        self.update_timer.setSingleShot(True)
        self.update_interval_ms = 200
        self._partial_line = ''
        self._suppress_logcat_errors = False

        self.max_lines_per_update = 50
        self.last_update_time = 0
        self.history_multiplier = 5

        # Auto scroll state
        self._auto_scroll_enabled = True
        self._suppress_scroll_signal = False

        # Line numbering for log display
        self._next_line_number = 1

        self._apply_persisted_settings(settings or {})

        # Filtering state
        self.log_levels_order = ['V', 'D', 'I', 'W', 'E', 'F']
        self.live_filter_pattern: Optional[str] = None
        self.active_filters: List[Dict[str, str]] = []

        self.init_ui()
        self._setup_copy_features()
        self.load_filters()

    def _get_status_prefix(self):
        """Get status prefix emoji based on running state."""
        return '🟢' if self.is_running else '⏸️'

    def _apply_persisted_settings(self, settings: Dict[str, int]) -> None:
        """Apply persisted performance settings with basic validation."""
        if not settings:
            return

        def _coerce(value, minimum, default):
            try:
                numeric = int(value)
            except (TypeError, ValueError):
                return default
            if numeric < minimum:
                return minimum
            return numeric

        if 'max_lines' in settings:
            self.max_lines = _coerce(settings.get('max_lines'), 100, self.max_lines)
            self.log_proxy.set_visible_limit(self.max_lines)

        if 'history_multiplier' in settings:
            self.history_multiplier = _coerce(settings.get('history_multiplier'), 1, self.history_multiplier)

        if 'update_interval_ms' in settings:
            self.update_interval_ms = _coerce(settings.get('update_interval_ms'), 50, self.update_interval_ms)

        if 'max_lines_per_update' in settings:
            self.max_lines_per_update = _coerce(settings.get('max_lines_per_update'), 5, self.max_lines_per_update)

        if 'max_buffer_size' in settings:
            self.max_buffer_size = _coerce(settings.get('max_buffer_size'), 10, self.max_buffer_size)

        self.update_timer.setInterval(self.update_interval_ms)

    def _update_status_label(self, text):
        """Update status label with consistent formatting."""
        prefix = self._get_status_prefix()
        self.status_label.setText(f'{prefix} {text}')

    def _get_buffer_stats(self):
        """Get buffer statistics."""
        if self._has_active_filters():
            total_logs = self.filtered_model.rowCount()
            filtered_count = total_logs
        else:
            total_logs = self.log_model.rowCount()
            filtered_count = 0
        return {
            'total_logs': total_logs,
            'buffer_size': len(self.log_buffer),
            'filtered_count': filtered_count,
        }

    def _manage_buffer_size(self):
        """Manage raw log buffer size based on configured history."""
        history_limit = self.max_lines * self.history_multiplier
        before = self.log_model.rowCount()
        self.log_model.trim(history_limit)
        if self.log_model.rowCount() != before:
            self.log_proxy.reset_limit_cache()
            self.log_proxy.invalidateFilter()

    def _handle_filters_changed(self):
        """Rebuild filtered view when filters are updated."""
        # Ensure the raw view remains unfiltered.
        self.log_proxy.set_saved_patterns([])
        self.log_proxy.set_live_pattern(None)

        self._compiled_filter_patterns = self._compile_filter_patterns()

        if self._has_active_filters():
            self._rebuild_filtered_model()
            if self.log_display.model() is not self.filtered_model:
                self.log_display.setModel(self.filtered_model)
        else:
            if self.log_display.model() is not self.log_proxy:
                self.log_display.setModel(self.log_proxy)
            self.filtered_model.clear()

        self.limit_log_lines()
        self._update_status_counts()
        self._scroll_to_bottom()

    def _has_active_filters(self) -> bool:
        """Return whether any filter (live or saved) is active."""
        return bool(self.live_filter_pattern) or bool(self.active_filters)

    def _compile_filter_patterns(self) -> List[re.Pattern[str]]:
        patterns = []
        if self.live_filter_pattern:
            patterns.append(self.live_filter_pattern)

        for filter_data in self.active_filters:
            pattern = filter_data.get('pattern')
            if pattern:
                patterns.append(pattern)

        compiled: List[re.Pattern[str]] = []
        for raw_pattern in patterns:
            try:
                compiled.append(re.compile(raw_pattern, re.IGNORECASE))
            except re.error:
                continue
        return compiled

    def _line_matches_filters(self, line: LogLine) -> bool:
        if not self._compiled_filter_patterns:
            return False
        return any(pattern.search(line.raw) for pattern in self._compiled_filter_patterns)

    def _rebuild_filtered_model(self) -> None:
        self.filtered_model.clear()
        if not self._compiled_filter_patterns:
            return

        matched = [
            line
            for line in self.log_model.to_list()
            if self._line_matches_filters(line)
        ]

        capacity = max(1, self.max_lines)
        if len(matched) > capacity:
            matched = matched[-capacity:]
        self.filtered_model.append_lines(matched)

    def _append_filtered_lines(self, lines: List[LogLine]) -> None:
        if not lines or not self._compiled_filter_patterns:
            return

        matched = [line for line in lines if self._line_matches_filters(line)]
        if not matched:
            return

        self.filtered_model.append_lines(matched)
        capacity = max(1, self.max_lines)
        overflow = self.filtered_model.rowCount() - capacity
        if overflow > 0:
            self.filtered_model.remove_first(overflow)

    def init_ui(self):
        """Initialize the logcat window UI."""
        self.setWindowTitle(f'Logcat Viewer - {self.device.device_model} ({self.device.device_serial_num[:8]}...)')
        self.setGeometry(100, 100, 1200, 800)

        # Main layout and splitter configuration
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        control_layout = self.create_control_panel()

        # Extract levels and filters into collapsible panels for a cleaner UI.
        levels_content = self._create_levels_widget()
        levels_panel = CollapsiblePanel('Levels', levels_content, collapsed=False, parent=self)

        filters_content = self.create_filter_panel()
        filters_panel = CollapsiblePanel('Filters', filters_content, collapsed=False, parent=self)

        top_panel = QWidget()
        top_panel.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)
        top_layout = QVBoxLayout(top_panel)
        top_layout.setContentsMargins(0, 0, 0, 0)
        top_layout.setSpacing(2)
        top_layout.addLayout(control_layout)
        top_layout.addWidget(levels_panel)
        top_layout.addWidget(filters_panel)

        # Place Levels/Filters toggles next to Start Logcat; hide panel headers to avoid duplication
        self.levels_panel = levels_panel
        self.filters_panel = filters_panel
        # Collapse by default to keep top area compact; user can expand via buttons
        self.levels_panel.set_collapsed(True)
        self.filters_panel.set_collapsed(True)
        # Hide the internal header buttons; external toolbar buttons control visibility
        try:
            self.levels_panel._toggle_btn.setVisible(False)
            self.filters_panel._toggle_btn.setVisible(False)
        except Exception:
            pass

        # If toolbar toggle buttons exist, ensure they reflect and control panel state
        if hasattr(self, 'levels_toggle_btn'):
            self.levels_toggle_btn.setCheckable(True)
            self.levels_toggle_btn.setChecked(not self.levels_panel.is_collapsed())
        if hasattr(self, 'filters_toggle_btn'):
            self.filters_toggle_btn.setCheckable(True)
            self.filters_toggle_btn.setChecked(not self.filters_panel.is_collapsed())

        self.log_display = QListView()
        self.log_display.setModel(self.log_proxy)
        self.log_display.setFont(QFont('Consolas', 10))
        self.log_display.setUniformItemSizes(True)
        self.log_display.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.log_display.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.log_display.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.log_display.setStyleSheet(
            """
            QListView {
                background-color: #1e1e1e;
                color: #ffffff;
                border: 1px solid #3e3e3e;
            }
            """
        )
        self.log_display.verticalScrollBar().valueChanged.connect(self._on_log_view_scrolled)

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

    def _setup_copy_features(self) -> None:
        """Enable context menu and keyboard shortcuts for copying logs."""
        self.log_display.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.log_display.customContextMenuRequested.connect(self._show_log_context_menu)
        self.log_display.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)

        copy_sequence = QKeySequence(QKeySequence.StandardKey.Copy)
        select_all_sequence = QKeySequence(QKeySequence.StandardKey.SelectAll)
        copy_all_sequence = QKeySequence('Ctrl+Shift+C')

        self._copy_selected_action = QAction('Copy Selected', self)
        self._copy_selected_action.setShortcut(copy_sequence)
        self._copy_selected_action.triggered.connect(self.copy_selected_logs)

        self._copy_all_action = QAction('Copy All', self)
        self._copy_all_action.setShortcut(copy_all_sequence)
        self._copy_all_action.triggered.connect(self.copy_all_logs)

        self._select_all_action = QAction('Select All', self)
        self._select_all_action.setShortcut(select_all_sequence)
        self._select_all_action.triggered.connect(self.select_all_logs)

        self._copy_shortcut = QShortcut(copy_sequence, self.log_display)
        self._copy_shortcut.activated.connect(self.copy_selected_logs)

        self._select_all_shortcut = QShortcut(select_all_sequence, self.log_display)
        self._select_all_shortcut.activated.connect(self.select_all_logs)

        self._copy_all_shortcut = QShortcut(copy_all_sequence, self.log_display)
        self._copy_all_shortcut.activated.connect(self.copy_all_logs)

    def _build_log_context_menu(self) -> QMenu:
        """Create the context menu used by the log view."""
        has_selection = bool(self.log_display.selectionModel() and self.log_display.selectionModel().hasSelection())
        self._copy_selected_action.setEnabled(has_selection)

        menu = QMenu(self)
        menu.addAction(self._copy_selected_action)
        menu.addAction(self._copy_all_action)
        menu.addSeparator()
        menu.addAction(self._select_all_action)
        return menu

    def _show_log_context_menu(self, position) -> None:
        """Display the context menu at the requested viewport position."""
        menu = self._build_log_context_menu()
        global_position = self.log_display.viewport().mapToGlobal(position)
        menu.exec(global_position)

    def _collect_selected_lines(self) -> List[str]:
        selection_model = self.log_display.selectionModel()
        model = self.log_display.model()
        if not selection_model or model is None:
            return []

        rows = sorted(selection_model.selectedRows(), key=lambda idx: idx.row())
        lines: List[str] = []
        for index in rows:
            if not index.isValid():
                continue
            text = model.data(index, Qt.ItemDataRole.DisplayRole)
            if text is None:
                continue
            lines.append(str(text))
        return lines

    def _collect_all_visible_lines(self) -> List[str]:
        model = self.log_display.model()
        if model is None:
            return []

        lines: List[str] = []
        for row in range(model.rowCount()):
            index = model.index(row, 0)
            text = model.data(index, Qt.ItemDataRole.DisplayRole)
            if text is None:
                continue
            lines.append(str(text))
        return lines

    def copy_selected_logs(self) -> str:
        """Copy the selected log rows to the clipboard and return the payload."""
        lines = self._collect_selected_lines()
        text = '\n'.join(lines)
        if text:
            QApplication.clipboard().setText(text)
        return text

    def copy_all_logs(self) -> str:
        """Copy all visible log rows to the clipboard and return the payload."""
        lines = self._collect_all_visible_lines()
        text = '\n'.join(lines)
        if text:
            QApplication.clipboard().setText(text)
        return text

    def select_all_logs(self) -> None:
        """Select every row in the log display for convenience."""
        self.log_display.selectAll()

    def create_control_panel(self):
        """Create the primary control toolbar (start/stop, performance, follow)."""
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        primary_row = QHBoxLayout()
        primary_row.setContentsMargins(0, 0, 0, 0)
        primary_row.setSpacing(8)

        # Start/Stop buttons
        self.start_btn = QPushButton('▶️ Start Logcat')
        self.start_btn.clicked.connect(self.start_logcat)
        primary_row.addWidget(self.start_btn)

        self.stop_btn = QPushButton('⏹️ Stop')
        self.stop_btn.clicked.connect(self.stop_logcat)
        self.stop_btn.setEnabled(False)
        primary_row.addWidget(self.stop_btn)

        clear_btn = QPushButton('🗑️ Clear')
        clear_btn.clicked.connect(self.clear_logs)
        primary_row.addWidget(clear_btn)

        perf_btn = QPushButton('⚙️ Performance')
        perf_btn.clicked.connect(self.open_performance_settings)
        primary_row.addWidget(perf_btn)

        primary_row.addWidget(self.create_vertical_separator())

        self.follow_latest_checkbox = QCheckBox('Follow newest')
        self.follow_latest_checkbox.setChecked(True)
        self.follow_latest_checkbox.toggled.connect(self.set_auto_scroll_enabled)
        primary_row.addWidget(self.follow_latest_checkbox)

        jump_btn = QPushButton('Jump to latest')
        jump_btn.clicked.connect(lambda: self.set_auto_scroll_enabled(True))
        jump_btn.setToolTip('Re-enable auto-follow and scroll to newest log entries')
        primary_row.addWidget(jump_btn)

        # Inline toggles to expand/collapse Levels and Filters panels just below
        primary_row.addWidget(self.create_vertical_separator())

        self.levels_toggle_btn = QPushButton('Levels')
        self.levels_toggle_btn.clicked.connect(self.toggle_levels_visibility)
        primary_row.addWidget(self.levels_toggle_btn)

        self.filters_toggle_btn = QPushButton('Filters')
        self.filters_toggle_btn.clicked.connect(self.toggle_filters_visibility)
        primary_row.addWidget(self.filters_toggle_btn)

        primary_row.addStretch(1)
        layout.addLayout(primary_row)
        return layout

    def toggle_levels_visibility(self):
        """Toggle the visibility of the Levels panel content."""
        if hasattr(self, 'levels_panel') and self.levels_panel:
            self.levels_panel.set_collapsed(not self.levels_panel.is_collapsed())
            if hasattr(self, 'levels_toggle_btn'):
                self.levels_toggle_btn.setChecked(not self.levels_panel.is_collapsed())

    def toggle_filters_visibility(self):
        """Toggle the visibility of the Filters panel content."""
        if hasattr(self, 'filters_panel') and self.filters_panel:
            self.filters_panel.set_collapsed(not self.filters_panel.is_collapsed())
            if hasattr(self, 'filters_toggle_btn'):
                self.filters_toggle_btn.setChecked(not self.filters_panel.is_collapsed())

    def _create_levels_widget(self) -> QWidget:
        """Create content widget for log levels checkboxes."""
        levels_container = QWidget()
        levels_container.setObjectName('logcat_levels_container')
        levels_container.setStyleSheet(
            'QWidget#logcat_levels_container {'
            ' background-color: #2c2c2c;'
            ' border: 1px solid #3e3e3e;'
            ' border-radius: 6px;'
            '}'
        )
        levels_layout = QHBoxLayout(levels_container)
        levels_layout.setContentsMargins(8, 6, 8, 6)
        levels_layout.setSpacing(8)

        self.log_levels = {
            'V': QCheckBox('Verbose'),
            'D': QCheckBox('Debug'),
            'I': QCheckBox('Info'),
            'W': QCheckBox('Warn'),
            'E': QCheckBox('Error'),
            'F': QCheckBox('Fatal'),
        }

        for level in self.log_levels_order:
            checkbox = self.log_levels[level]
            checkbox.setChecked(True)
            checkbox.stateChanged.connect(self.update_log_levels)
            levels_layout.addWidget(checkbox)

        levels_layout.addStretch(1)
        return levels_container

    def create_filter_panel(self) -> QWidget:
        """Create the filter panel (source + live/saved filters)."""
        panel = QWidget()
        main_layout = QVBoxLayout(panel)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(8)

        # Source (Tag/Package/Raw) row
        source_cluster = QWidget()
        source_layout = QHBoxLayout(source_cluster)
        source_layout.setContentsMargins(0, 0, 0, 0)
        source_layout.setSpacing(8)

        source_label = QLabel('Source')
        source_label.setStyleSheet('font-weight: bold;')
        source_layout.addWidget(source_label)

        self.log_source_mode = QComboBox()
        self.log_source_mode.addItem('Tag', 'tag')
        self.log_source_mode.addItem('Package', 'package')
        self.log_source_mode.addItem('Raw', 'raw')
        self.log_source_mode.setCurrentIndex(0)
        self.log_source_mode.setFixedWidth(110)
        source_layout.addWidget(self.log_source_mode)

        self.log_source_input = QLineEdit()
        self.log_source_input.setPlaceholderText('Tag or package filter (optional)')
        self.log_source_input.setMinimumWidth(220)
        source_layout.addWidget(self.log_source_input, stretch=1)

        main_layout.addWidget(source_cluster)

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
        self.saved_filters_combo.currentIndexChanged.connect(self.load_saved_filter)

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
            normalized_name = filter_name.strip()
            self.filters[normalized_name] = self.filter_input.text().strip()
            self.save_filters()
            self.update_saved_filters_combo()
            new_index = self.saved_filters_combo.findData(normalized_name, role=Qt.ItemDataRole.UserRole)
            if new_index != -1:
                self.saved_filters_combo.setCurrentIndex(new_index)
            QMessageBox.information(self, 'Filter Saved', f'Filter "{filter_name}" saved successfully!')

    def delete_saved_filter(self):
        """Delete selected saved filter."""
        index = self.saved_filters_combo.currentIndex()
        if index < 0:
            QMessageBox.information(self, 'No Selection', 'Please select a filter to delete.')
            return

        filter_name = self.saved_filters_combo.itemData(index, Qt.ItemDataRole.UserRole)
        if not filter_name:
            QMessageBox.information(self, 'No Selection', 'Please select a filter to delete.')
            return

        display_name = self.saved_filters_combo.itemText(index)

        reply = QMessageBox.question(
            self,
            'Delete Filter',
            f'Are you sure you want to delete filter "{display_name}"?',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            if filter_name in self.filters:
                del self.filters[filter_name]
                self.save_filters()
                self.update_saved_filters_combo()
                self.active_filters = [
                    f for f in self.active_filters if f.get('name') != filter_name
                ]
                self.update_active_filters_list()
                self._handle_filters_changed()
                QMessageBox.information(
                    self,
                    'Filter Deleted',
                    f'Filter "{display_name}" deleted successfully!'
                )

    def update_saved_filters_combo(self):
        """Update the saved filters combo box."""
        if not hasattr(self, 'saved_filters_combo'):
            return

        current_name = self.saved_filters_combo.currentData(Qt.ItemDataRole.UserRole)

        self.saved_filters_combo.blockSignals(True)
        self.saved_filters_combo.clear()

        for name, pattern in self.filters.items():
            display = f'{name}: {pattern}'
            self.saved_filters_combo.addItem(display, name)
            index = self.saved_filters_combo.count() - 1
            self.saved_filters_combo.setItemData(index, pattern, Qt.ItemDataRole.ToolTipRole)

        target_index = -1
        if current_name:
            target_index = self.saved_filters_combo.findData(current_name, role=Qt.ItemDataRole.UserRole)

        if target_index == -1 and self.saved_filters_combo.count() > 0:
            target_index = 0

        if target_index != -1:
            self.saved_filters_combo.setCurrentIndex(target_index)

        self.saved_filters_combo.blockSignals(False)

        if self.saved_filters_combo.count() > 0:
            self.load_saved_filter(self.saved_filters_combo.currentIndex())

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

    def _update_status_counts(self) -> None:
        """Update the status label based on current filter state."""
        if self._has_active_filters():
            active_count = len(self.active_filters) + (1 if self.live_filter_pattern else 0)
            filtered_count = self.filtered_model.rowCount()
            capacity = self.max_lines
            self._update_status_label(
                f'Filtered: {filtered_count}/{capacity} lines (active: {active_count})'
            )
        else:
            capacity = self.max_lines * self.history_multiplier
            total_logs = self.log_model.rowCount()
            self._update_status_label(f'Total: {total_logs}/{capacity} lines')

    def _notify_settings_changed(self) -> None:
        """Emit persisted settings through callback if provided."""
        if callable(self._settings_callback):
            self._settings_callback(
                {
                    'max_lines': self.max_lines,
                    'history_multiplier': self.history_multiplier,
                    'update_interval_ms': self.update_interval_ms,
                    'max_lines_per_update': self.max_lines_per_update,
                    'max_buffer_size': self.max_buffer_size,
                }
            )

    def on_performance_settings_updated(self):
        """Handle updates from the performance settings dialog."""
        self.limit_log_lines()
        self._update_status_counts()
        self.update_timer.setInterval(self.update_interval_ms)
        self._notify_settings_changed()

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
            self._clear_device_logcat_buffer()
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

    def _clear_device_logcat_buffer(self) -> None:
        """Clear device-side logcat buffer so streaming starts from current time."""
        try:
            subprocess.run(
                ['adb', '-s', self.device.device_serial_num, 'logcat', '-c'],
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except FileNotFoundError:
            logger.warning('ADB executable not found when clearing logcat buffer.')
        except Exception as exc:  # pragma: no cover - defensive
            logger.debug('Clearing logcat buffer failed but continuing: %s', exc)

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

        new_log_lines = [LogLine.from_string(line) for line in new_lines]

        # Buffer new lines for throttled updates
        self.log_buffer.extend(new_log_lines)

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

        lines_to_process = self.log_buffer[:self.max_lines_per_update]
        self.log_buffer = self.log_buffer[self.max_lines_per_update:]

        if not lines_to_process:
            if self.log_buffer and not self.update_timer.isActive():
                self.update_timer.start(self.update_interval_ms)
            return

        numbered_lines = self._assign_line_numbers(lines_to_process)

        if numbered_lines:
            self.log_model.append_lines(numbered_lines)
            self.log_proxy.reset_limit_cache()
            if self._has_active_filters():
                self._append_filtered_lines(numbered_lines)
            self._manage_buffer_size()
            self.limit_log_lines()
            self._scroll_to_bottom()

        if self.is_running:
            stats = self._get_buffer_stats()
            if stats['buffer_size'] > 0:
                self._update_status_label(f'Logcat running... (buffered: {stats["buffer_size"]} lines)')
            else:
                suffix = 'visible lines' if self._has_active_filters() else 'lines'
                self._update_status_label(f'Logcat running... ({stats["total_logs"]} {suffix})')

        if self.log_buffer and not self.update_timer.isActive():
            self.update_timer.start(self.update_interval_ms)

    def _assign_line_numbers(self, lines: List[LogLine]) -> List[LogLine]:
        if not lines:
            return []

        numbered: List[LogLine] = []
        for line in lines:
            numbered.append(replace(line, line_no=self._next_line_number))
            self._next_line_number += 1
        return numbered

    def limit_log_lines(self):
        """Limit the number of lines in the display for performance."""
        self.log_proxy.set_visible_limit(self.max_lines)
        self._manage_buffer_size()
        if self._has_active_filters():
            capacity = max(1, self.max_lines)
            overflow = self.filtered_model.rowCount() - capacity
            if overflow > 0:
                self.filtered_model.remove_first(overflow)

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

        self.is_running = False
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)

        if self.log_model.rowCount():
            self.limit_log_lines()
            self._update_status_counts()
        else:
            self._update_status_label('Logcat stopped.')

    def clear_logs(self):
        """Clear the log display."""
        self.log_model.clear()
        self.filtered_model.clear()
        self.log_buffer.clear()
        self._partial_line = ''
        self.log_proxy.reset_limit_cache()
        if self._has_active_filters():
            self._handle_filters_changed()
        else:
            self._update_status_label('Logs cleared')
        self._next_line_number = 1

    def set_auto_scroll_enabled(self, enabled: bool, *, from_scroll: bool = False) -> None:
        """Enable or disable automatic scrolling to the latest log entry."""
        enabled = bool(enabled)
        if enabled == self._auto_scroll_enabled and not from_scroll:
            return

        self._auto_scroll_enabled = enabled

        if hasattr(self, 'follow_latest_checkbox'):
            self.follow_latest_checkbox.blockSignals(True)
            self.follow_latest_checkbox.setChecked(enabled)
            self.follow_latest_checkbox.blockSignals(False)

        if enabled:
            self._scroll_to_bottom()

    def _on_log_view_scrolled(self, value: int) -> None:
        """Handle user scrolling to pause or resume auto-follow."""
        if self._suppress_scroll_signal:
            return

        scroll_bar = self.log_display.verticalScrollBar()
        if scroll_bar is None:
            return

        distance_to_bottom = scroll_bar.maximum() - value
        threshold = max(2, scroll_bar.pageStep() // 4)

        if distance_to_bottom <= threshold:
            if not self._auto_scroll_enabled:
                self.set_auto_scroll_enabled(True, from_scroll=True)
        else:
            if self._auto_scroll_enabled:
                self.set_auto_scroll_enabled(False, from_scroll=True)

    def apply_live_filter(self, pattern):
        """Apply live regex filter to logs in real-time."""
        self.live_filter_pattern = pattern.strip() if pattern.strip() else None
        self._handle_filters_changed()

    def refilter_display(self):
        """Re-filter all logs and update display."""
        self.log_proxy.invalidateFilter()
        self.limit_log_lines()
        self._update_status_counts()

    def _scroll_to_bottom(self):
        """Scroll log display to bottom."""
        if not self._auto_scroll_enabled:
            return

        model = self.log_display.model()
        if model is None or model.rowCount() == 0:
            return
        last_index = model.index(model.rowCount() - 1, 0)
        scroll_bar = self.log_display.verticalScrollBar()
        self._suppress_scroll_signal = True
        try:
            if scroll_bar is not None:
                scroll_bar.setValue(scroll_bar.maximum())
            self.log_display.scrollTo(last_index, QAbstractItemView.ScrollHint.PositionAtBottom)
        finally:
            self._suppress_scroll_signal = False

    def closeEvent(self, event: QCloseEvent) -> None:  # type: ignore[override]
        """Ensure the logcat process stops when the window closes."""
        if self.logcat_process:
            self.stop_logcat()
        super().closeEvent(event)

    def load_saved_filter(self, filter_name):
        """Update preview when saved filter is selected."""
        if not hasattr(self, 'saved_filters_combo'):
            return

        index = filter_name if isinstance(filter_name, int) else self.saved_filters_combo.currentIndex()
        if index < 0:
            return

        actual_name = self.saved_filters_combo.itemData(index, Qt.ItemDataRole.UserRole)
        if not actual_name:
            return

        pattern = self.filters.get(actual_name)
        if pattern is None:
            return

        self.saved_filters_combo.setToolTip(f'{actual_name}: {pattern}')

    def apply_selected_filter(self):
        """Apply the selected saved filter."""
        index = self.saved_filters_combo.currentIndex()
        if index < 0:
            return

        filter_name = self.saved_filters_combo.itemData(index, Qt.ItemDataRole.UserRole)
        if filter_name and filter_name in self.filters:
            self.add_active_filter(filter_name, self.filters[filter_name])

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
