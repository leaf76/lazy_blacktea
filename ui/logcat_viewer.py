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
from typing import Optional, Dict, List, Any, Callable, TYPE_CHECKING

from PyQt6.QtWidgets import (
    QWidget, QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, QSplitter, QListView,
    QPushButton, QLabel, QLineEdit, QComboBox, QCheckBox, QFrame, QMessageBox,
    QInputDialog, QListWidget, QListWidgetItem, QAbstractItemView, QStyledItemDelegate,
    QSpinBox, QSizePolicy, QGroupBox, QFormLayout, QApplication, QMenu
)
from PyQt6.QtCore import (
    QObject, QProcess, QTimer, Qt, QAbstractListModel, QModelIndex, QSortFilterProxyModel, QSize,
    QEvent
)
from PyQt6.QtGui import QFont, QCloseEvent, QAction, QKeySequence, QShortcut, QPen, QColor
from PyQt6.QtWidgets import QStyle

from ui.collapsible_panel import CollapsiblePanel
from ui.logcat.filter_models import ActiveFilterState
from ui.logcat.preset_manager import PresetManager
from ui.logcat.device_watcher import DeviceWatcher
from ui.logcat.filter_panel_widget import FilterPanelWidget
from ui.logcat.search_bar_widget import SearchBarWidget
from ui.logcat.scrcpy_preview_panel import ScrcpyPreviewPanel
from ui.toast_notification import ToastNotification

if TYPE_CHECKING:
    from ui.device_manager import DeviceManager
    from config.config_manager import ConfigManager

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


class _LogListItemDelegate(QStyledItemDelegate):
    """Custom delegate ensuring long lines expand width for horizontal scrolling.

    - Disables implicit eliding by providing a wider size hint based on text width.
    - Keeps height from base delegate for consistent row height.
    - Supports search highlighting with configurable match patterns.
    """

    # Highlight colors
    HIGHLIGHT_BG = '#623f00'         # Yellow-orange background for matches
    HIGHLIGHT_CURRENT_BG = '#515c6a'  # Brighter for current match
    HIGHLIGHT_TEXT = '#ffffff'       # White text for visibility

    def __init__(self, parent=None):
        super().__init__(parent)
        self._search_pattern: Optional[re.Pattern] = None
        self._current_match_row: int = -1

    def set_search_pattern(self, pattern: Optional[re.Pattern]) -> None:
        """Set the search pattern for highlighting."""
        self._search_pattern = pattern

    def set_current_match_row(self, row: int) -> None:
        """Set the current match row for brighter highlight."""
        self._current_match_row = row

    def sizeHint(self, option, index):  # type: ignore[override]
        base = super().sizeHint(option, index)
        text = index.data(Qt.ItemDataRole.DisplayRole)
        if text is None:
            return base
        fm = option.fontMetrics
        # Add small padding to avoid clipping of last character
        width = fm.horizontalAdvance(str(text)) + 12
        height = base.height()
        return QSize(width, height)

    def paint(self, painter, option, index):  # type: ignore[override]
        """Paint the item with optional search highlighting."""
        text = index.data(Qt.ItemDataRole.DisplayRole)
        if text is None or not self._search_pattern:
            super().paint(painter, option, index)
            return

        text = str(text)

        # Find all matches in this text
        matches = list(self._search_pattern.finditer(text))
        if not matches:
            super().paint(painter, option, index)
            return

        # Draw background (handle selection state)
        painter.save()
        try:
            # Fill background based on selection state
            is_selected = bool(option.state & QStyle.StateFlag.State_Selected)
            if is_selected:
                painter.fillRect(option.rect, option.palette.highlight())
            else:
                painter.fillRect(option.rect, option.palette.base().color())

            # Set up font and metrics
            font = option.font
            painter.setFont(font)
            fm = option.fontMetrics

            # Calculate text position
            text_rect = option.rect.adjusted(4, 0, -4, 0)
            y_offset = text_rect.top() + (text_rect.height() + fm.ascent() - fm.descent()) // 2

            # Determine if this is the current match row
            is_current_row = index.row() == self._current_match_row

            # Draw text character by character with highlighting
            x = text_rect.left()
            match_idx = 0
            i = 0

            while i < len(text):
                # Check if we're at a match start
                in_match = False
                match_end = i

                while match_idx < len(matches):
                    match = matches[match_idx]
                    if i >= match.end():
                        match_idx += 1
                        continue
                    if i >= match.start():
                        in_match = True
                        match_end = match.end()
                    break

                if in_match:
                    # Draw highlighted segment
                    segment = text[i:match_end]
                    seg_width = fm.horizontalAdvance(segment)

                    # Draw highlight background
                    bg_color = self.HIGHLIGHT_CURRENT_BG if is_current_row else self.HIGHLIGHT_BG
                    painter.fillRect(x, text_rect.top(), seg_width, text_rect.height(), QColor(bg_color))

                    # Draw text
                    painter.setPen(QColor(self.HIGHLIGHT_TEXT))
                    painter.drawText(x, y_offset, segment)

                    x += seg_width
                    i = match_end
                else:
                    # Find where next match starts (or end of string)
                    next_match_start = len(text)
                    if match_idx < len(matches):
                        next_match_start = matches[match_idx].start()

                    # Draw normal segment
                    segment = text[i:next_match_start]
                    seg_width = fm.horizontalAdvance(segment)

                    # Normal text color
                    if is_selected:
                        painter.setPen(option.palette.highlightedText().color())
                    else:
                        painter.setPen(option.palette.text().color())

                    painter.drawText(x, y_offset, segment)

                    x += seg_width
                    i = next_match_start

        finally:
            painter.restore()


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
        device_manager: Optional["DeviceManager"] = None,
        config_manager: Optional["ConfigManager"] = None,
    ):
        super().__init__(parent)
        # Configure as a normal resizable window (not always-on-top of parent)
        self.setWindowFlag(Qt.WindowType.WindowContextHelpButtonHint, False)
        self.setWindowFlag(Qt.WindowType.Window, True)
        self.setWindowFlag(Qt.WindowType.Dialog, False)
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, False)
        self.setWindowFlag(Qt.WindowType.WindowMinMaxButtonsHint, True)
        self.setWindowFlag(Qt.WindowType.WindowMaximizeButtonHint, True)
        self.setWindowFlag(Qt.WindowType.WindowMinimizeButtonHint, True)
        self.setWindowModality(Qt.WindowModality.NonModal)
        self.setSizeGripEnabled(True)

        self.device = device
        self.logcat_process = None
        self.is_running = False
        self.max_lines = 1000
        self._settings_callback = on_settings_changed
        self._config_manager = config_manager

        # Device monitoring for graceful disconnection handling
        self._device_manager = device_manager
        self._device_watcher: Optional[DeviceWatcher] = None
        self._toast: Optional[ToastNotification] = None

        # Preset manager for three-level filter architecture
        self._preset_manager = PresetManager()

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
        self.active_filters: List[str] = []

        # Search state (for highlight search feature)
        self._search_pattern: Optional[re.Pattern] = None
        self._search_match_rows: List[int] = []  # Rows with matches
        self._current_match_index: int = -1      # Current match in _search_match_rows
        self._log_delegate: Optional[_LogListItemDelegate] = None

        self.init_ui()
        self._setup_copy_features()
        self._setup_search_shortcut()
        self._setup_device_watcher()
        self._migrate_legacy_filters()

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
        """Compile all active filter patterns into regex objects."""
        patterns: List[str] = []
        if self.live_filter_pattern:
            patterns.append(self.live_filter_pattern)
        patterns.extend(self.active_filters)

        compiled: List[re.Pattern[str]] = []
        for raw_pattern in patterns:
            if not raw_pattern:
                continue
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
        # Enable correct width calculation for long lines and allow horizontal scroll
        self.log_display.setUniformItemSizes(False)
        self.log_display.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.log_display.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.log_display.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.log_display.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.log_display.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.log_display.setWordWrap(False)
        try:
            # Avoid eliding long log lines; show full width with horizontal scroll
            from PyQt6.QtCore import Qt as _Qt
            self.log_display.setTextElideMode(_Qt.TextElideMode.ElideNone)
        except Exception:
            pass
        # Use custom delegate so the view knows the actual width per row
        try:
            self._log_delegate = _LogListItemDelegate(self.log_display)
            self.log_display.setItemDelegate(self._log_delegate)
        except Exception:
            pass
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

        # Create floating search bar as overlay on log_display (VS Code style)
        self._search_bar = SearchBarWidget(self.log_display)
        self._search_bar.search_changed.connect(self._on_search_changed)
        self._search_bar.navigate_next.connect(self._navigate_to_next_match)
        self._search_bar.navigate_prev.connect(self._navigate_to_prev_match)
        self._search_bar.closed.connect(self._on_search_closed)
        # Install event filter on log_display to handle resize events
        self.log_display.installEventFilter(self)

        # Create vertical splitter for logcat area (top controls + log display)
        vertical_splitter = QSplitter(Qt.Orientation.Vertical)
        vertical_splitter.addWidget(top_panel)
        vertical_splitter.addWidget(log_container)
        vertical_splitter.setStretchFactor(0, 0)
        vertical_splitter.setStretchFactor(1, 1)
        vertical_splitter.setCollapsible(0, False)
        vertical_splitter.setCollapsible(1, False)

        # Create left panel container for logcat content
        left_panel = QWidget()
        left_panel.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.addWidget(vertical_splitter)

        # Create scrcpy preview panel on the right
        self._preview_panel = ScrcpyPreviewPanel(
            device=self.device,
            log_model=self.log_model,
            config_manager=self._config_manager,
            parent=self,
        )
        self._preview_panel.error_occurred.connect(self._on_preview_error)
        self._preview_panel.recording_stopped.connect(self._on_recording_stopped)

        # Create horizontal splitter for main layout (logcat | preview)
        main_splitter = QSplitter(Qt.Orientation.Horizontal)
        main_splitter.addWidget(left_panel)
        main_splitter.addWidget(self._preview_panel)
        main_splitter.setStretchFactor(0, 3)  # Logcat takes more space
        main_splitter.setStretchFactor(1, 1)  # Preview panel smaller
        main_splitter.setCollapsible(0, False)
        main_splitter.setCollapsible(1, True)  # Preview can be collapsed

        # Store splitter reference for state persistence
        self._main_splitter = main_splitter

        layout.addWidget(main_splitter)

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

    def _setup_search_shortcut(self) -> None:
        """Register keyboard shortcuts for search functionality."""
        # Ctrl+F to open search bar
        find_sequence = QKeySequence(QKeySequence.StandardKey.Find)
        self._find_shortcut = QShortcut(find_sequence, self)
        self._find_shortcut.setContext(Qt.ShortcutContext.WindowShortcut)
        self._find_shortcut.activated.connect(self._handle_find_shortcut)
        self._find_shortcut.activatedAmbiguously.connect(self._handle_find_shortcut)

        # F3 for next match
        self._next_match_shortcut = QShortcut(QKeySequence(Qt.Key.Key_F3), self)
        self._next_match_shortcut.setContext(Qt.ShortcutContext.WindowShortcut)
        self._next_match_shortcut.activated.connect(self._navigate_to_next_match)

        # Shift+F3 for previous match
        self._prev_match_shortcut = QShortcut(
            QKeySequence(Qt.KeyboardModifier.ShiftModifier | Qt.Key.Key_F3), self
        )
        self._prev_match_shortcut.setContext(Qt.ShortcutContext.WindowShortcut)
        self._prev_match_shortcut.activated.connect(self._navigate_to_prev_match)

    def _handle_find_shortcut(self) -> None:
        """Show the floating search bar and focus it."""
        if hasattr(self, '_search_bar') and self._search_bar:
            self._position_search_bar()
            self._search_bar.show_search()
            self._search_bar.raise_()  # Ensure it's on top
            if not self.isActiveWindow():
                self.activateWindow()

    def _setup_device_watcher(self) -> None:
        """Initialize device state monitoring for graceful disconnection handling."""
        if self._device_manager is None:
            return

        try:
            self._device_watcher = DeviceWatcher(
                self.device.device_serial_num,
                self._device_manager,
                parent=self,
            )
            self._device_watcher.device_disconnected.connect(self._on_device_disconnected)
        except Exception as exc:
            logger.warning("Failed to setup device watcher: %s", exc)

        # Create toast notification widget
        self._toast = ToastNotification(parent=self)

    def _on_device_disconnected(self, serial: str) -> None:
        """Handle device disconnection gracefully."""
        if serial != self.device.device_serial_num:
            return

        logger.info("Device disconnected during logcat: %s", serial)

        # Stop logcat if running
        if self.is_running:
            self._suppress_logcat_errors = True
            self.stop_logcat()

        # Show non-blocking toast notification
        self._show_disconnect_toast()

    def _show_disconnect_toast(self) -> None:
        """Show non-blocking notification about device disconnection."""
        if self._toast:
            self._toast.show_toast(
                "Device disconnected. Logcat stopped.",
                style=ToastNotification.STYLE_WARNING,
                duration_ms=4000,
            )

        # Also update status label
        self._update_status_label("Device disconnected")

    def _migrate_legacy_filters(self) -> None:
        """Migrate legacy filters to new preset format on first run."""
        try:
            migrated = self._preset_manager.migrate_legacy_filters()
            if migrated > 0:
                logger.info("Migrated %d legacy filters to preset format", migrated)
        except Exception as exc:
            logger.warning("Legacy filter migration failed: %s", exc)

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

        self.preview_toggle_btn = QPushButton('Preview')
        self.preview_toggle_btn.setCheckable(True)
        self.preview_toggle_btn.setChecked(True)
        self.preview_toggle_btn.setToolTip('Toggle device preview and recording panel')
        self.preview_toggle_btn.clicked.connect(self.toggle_preview_visibility)
        primary_row.addWidget(self.preview_toggle_btn)

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

    def toggle_preview_visibility(self):
        """Toggle the visibility of the preview panel."""
        if hasattr(self, '_preview_panel') and self._preview_panel:
            is_visible = self._preview_panel.isVisible()
            self._preview_panel.setVisible(not is_visible)
            if hasattr(self, 'preview_toggle_btn'):
                self.preview_toggle_btn.setChecked(not is_visible)

    def _on_preview_error(self, message: str) -> None:
        """Handle errors from the preview panel."""
        if self._toast:
            self._toast.show_toast(
                message,
                style=ToastNotification.STYLE_ERROR,
                duration_ms=4000,
            )

    def _on_recording_stopped(self, video_path: str) -> None:
        """Handle recording completion notification."""
        if self._toast and video_path:
            self._toast.show_toast(
                f"Recording saved: {os.path.basename(video_path)}",
                style=ToastNotification.STYLE_SUCCESS,
                duration_ms=5000,
            )

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
        """Create the filter panel with three-level architecture.

        Level 1: Live filter (real-time input)
        Level 2: Active filters (currently applied)
        Level 3: Saved presets (persistent combinations)
        """
        panel = QWidget()
        main_layout = QVBoxLayout(panel)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(8)

        # Source (Tag/Package/Raw) row - kept for ADB filtering
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

        # Three-level filter panel widget
        self._filter_panel_widget = FilterPanelWidget(
            parent=self,
            preset_manager=self._preset_manager,
        )
        self._filter_panel_widget.filters_changed.connect(self._on_filter_panel_changed)
        self._filter_panel_widget.live_filter_changed.connect(self._on_live_filter_changed)

        main_layout.addWidget(self._filter_panel_widget)

        panel.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)
        return panel

    def _on_filter_panel_changed(self) -> None:
        """Handle filter changes from the FilterPanelWidget."""
        filter_state = self._filter_panel_widget.get_filter_state()
        self.live_filter_pattern = filter_state.live_pattern
        self.active_filters = filter_state.active_patterns
        self._handle_filters_changed()

    def _on_live_filter_changed(self, pattern: str) -> None:
        """Handle live filter text changes from the panel."""
        self.live_filter_pattern = pattern.strip() if pattern.strip() else None
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

    # ─────────────────────────────────────────────────────────────────────────
    # Search functionality
    # ─────────────────────────────────────────────────────────────────────────

    def _on_search_changed(self, pattern: str) -> None:
        """Handle search pattern changes from the search bar."""
        if not pattern:
            self._clear_search_highlight()
            return

        # Compile the pattern from the search bar
        compiled = self._search_bar.compile_pattern()
        if compiled is None:
            self._clear_search_highlight()
            self._search_bar.update_match_count(0, 0)
            return

        self._search_pattern = compiled
        self._update_search_matches()

    # Maximum search matches to collect for performance
    _MAX_SEARCH_MATCHES = 1000

    def _update_search_matches(self) -> None:
        """Scan visible logs and build list of matching row indices.

        Limits results to _MAX_SEARCH_MATCHES for performance with large logs.
        """
        if not self._search_pattern:
            self._search_match_rows = []
            self._current_match_index = -1
            self._search_bar.update_match_count(0, 0)
            return

        model = self.log_display.model()
        if model is None:
            return

        # Find rows with matches (limited for performance)
        match_rows = []
        for row in range(model.rowCount()):
            index = model.index(row, 0)
            text = model.data(index, Qt.ItemDataRole.DisplayRole)
            if text and self._search_pattern.search(str(text)):
                match_rows.append(row)
                if len(match_rows) >= self._MAX_SEARCH_MATCHES:
                    break

        self._search_match_rows = match_rows

        if match_rows:
            # Set current match to the first visible or first overall
            visible_rect = self.log_display.viewport().rect()
            first_visible = self.log_display.indexAt(visible_rect.topLeft())
            last_visible = self.log_display.indexAt(visible_rect.bottomLeft())

            # Find a match that's visible, or default to first
            self._current_match_index = 0
            if first_visible.isValid() and last_visible.isValid():
                for i, row in enumerate(match_rows):
                    if first_visible.row() <= row <= last_visible.row():
                        self._current_match_index = i
                        break

            self._update_current_match_highlight()
        else:
            self._current_match_index = -1
            self._update_delegate_highlight(None, -1)

        total = len(match_rows)
        current = self._current_match_index + 1 if total > 0 else 0
        limited = total >= self._MAX_SEARCH_MATCHES
        self._search_bar.update_match_count(current, total, limited=limited)

    def _update_current_match_highlight(self) -> None:
        """Update the delegate with current match info and refresh view."""
        if not self._search_match_rows or self._current_match_index < 0:
            self._update_delegate_highlight(self._search_pattern, -1)
            return

        current_row = self._search_match_rows[self._current_match_index]
        self._update_delegate_highlight(self._search_pattern, current_row)

        # Scroll to the current match
        model = self.log_display.model()
        if model:
            index = model.index(current_row, 0)
            self.log_display.scrollTo(index, QAbstractItemView.ScrollHint.EnsureVisible)

    def _update_delegate_highlight(
        self, pattern: Optional[re.Pattern], current_row: int
    ) -> None:
        """Update the delegate with search pattern and refresh the view."""
        if self._log_delegate:
            self._log_delegate.set_search_pattern(pattern)
            self._log_delegate.set_current_match_row(current_row)

        # Force repaint of the visible area
        self.log_display.viewport().update()

    def _navigate_to_next_match(self) -> None:
        """Navigate to the next search match."""
        if not self._search_match_rows:
            return

        total = len(self._search_match_rows)
        self._current_match_index = (self._current_match_index + 1) % total
        self._update_current_match_highlight()
        self._search_bar.update_match_count(self._current_match_index + 1, total)

    def _navigate_to_prev_match(self) -> None:
        """Navigate to the previous search match."""
        if not self._search_match_rows:
            return

        total = len(self._search_match_rows)
        self._current_match_index = (self._current_match_index - 1) % total
        self._update_current_match_highlight()
        self._search_bar.update_match_count(self._current_match_index + 1, total)

    def _on_search_closed(self) -> None:
        """Handle search bar close - clear all highlights."""
        self._clear_search_highlight()

    def _position_search_bar(self) -> None:
        """Position the search bar in the top-right corner of the log display."""
        if not hasattr(self, '_search_bar') or not self._search_bar:
            return

        parent = self._search_bar.parentWidget()
        if parent is None:
            return

        # Get parent (log_display) dimensions
        parent_width = parent.width()
        search_bar_width = self._search_bar.sizeHint().width()
        search_bar_height = self._search_bar.height()

        # Position in top-right corner with some padding
        margin_right = 20
        margin_top = 10

        x = parent_width - search_bar_width - margin_right
        y = margin_top

        # Ensure it doesn't go off the left edge
        x = max(margin_right, x)

        self._search_bar.move(x, y)

    def eventFilter(self, watched: QObject, event) -> bool:
        """Handle resize events to reposition the search bar."""
        if (
            hasattr(self, 'log_display')
            and watched is self.log_display
            and event.type() == QEvent.Type.Resize
        ):
            self._position_search_bar()

        return super().eventFilter(watched, event)

    def _clear_search_highlight(self) -> None:
        """Clear search pattern and refresh view."""
        self._search_pattern = None
        self._search_match_rows = []
        self._current_match_index = -1
        self._update_delegate_highlight(None, -1)

    # ─────────────────────────────────────────────────────────────────────────

    def closeEvent(self, event: QCloseEvent) -> None:  # type: ignore[override]
        """Ensure the logcat process and device watcher are cleaned up."""
        if self.logcat_process:
            self.stop_logcat()

        # Cleanup device watcher to prevent memory leaks
        if self._device_watcher:
            self._device_watcher.cleanup()
            self._device_watcher = None

        # Cleanup preview panel (scrcpy and recording)
        if hasattr(self, '_preview_panel') and self._preview_panel:
            self._preview_panel.cleanup()

        super().closeEvent(event)

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

    def show_error(self, message):
        """Show error message dialog."""
        from PyQt6.QtWidgets import QMessageBox
        QMessageBox.critical(self, 'Logcat Error', message)
