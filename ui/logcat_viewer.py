"""
Logcat Viewer Component - Extracted from lazy_blacktea_pyqt.py
Provides real-time logcat streaming and filtering capabilities.
"""

import logging
import os
import re
import subprocess
import time
from collections import deque
from dataclasses import dataclass, replace
from typing import Optional, Dict, List, Any, Callable, TYPE_CHECKING, Tuple

from PyQt6.QtWidgets import (
    QWidget,
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QSplitter,
    QListView,
    QPushButton,
    QLabel,
    QLineEdit,
    QComboBox,
    QCheckBox,
    QFrame,
    QMessageBox,
    QInputDialog,
    QListWidget,
    QListWidgetItem,
    QAbstractItemView,
    QStyledItemDelegate,
    QSpinBox,
    QSizePolicy,
    QGroupBox,
    QFormLayout,
    QApplication,
    QMenu,
    QPlainTextEdit,
    QTextEdit,
)
from PyQt6.QtCore import (
    QObject,
    QProcess,
    QThread,
    QTimer,
    Qt,
    QAbstractListModel,
    QModelIndex,
    QSortFilterProxyModel,
    QSize,
    QEvent,
    QPropertyAnimation,
    QEasingCurve,
    pyqtSignal,
    pyqtSlot,
)
from PyQt6.QtGui import (
    QFont,
    QCloseEvent,
    QAction,
    QKeySequence,
    QShortcut,
    QPen,
    QColor,
    QTextCursor,
)
from PyQt6.QtWidgets import QStyle

from ui.collapsible_panel import CollapsiblePanel
from ui.logcat.filter_models import ActiveFilterState
from ui.logcat.preset_manager import PresetManager
from ui.logcat.device_watcher import DeviceWatcher
from ui.logcat.filter_panel_widget import FilterPanelWidget
from ui.logcat.search_bar_widget import SearchBarWidget
from ui.logcat.scrcpy_preview_panel import ScrcpyPreviewPanel
from ui.toast_notification import ToastNotification
from utils.task_dispatcher import TaskCancelledError, TaskContext, TaskHandle, get_task_dispatcher

if TYPE_CHECKING:
    from ui.device_manager import DeviceManager
    from config.config_manager import (
        ConfigManager,
        LogcatViewerSettings,
        LogcatViewerSettings,
    )

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
    "Balanced (default)": {
        "max_lines": 1000,
        "history_multiplier": 5,
        "update_interval_ms": 200,
        "lines_per_update": 50,
        "max_buffer_size": 100,
    },
    "Extended history": {
        "max_lines": 1500,
        "history_multiplier": 10,
        "update_interval_ms": 250,
        "lines_per_update": 60,
        "max_buffer_size": 120,
    },
    "Low latency streaming": {
        "max_lines": 800,
        "history_multiplier": 5,
        "update_interval_ms": 120,
        "lines_per_update": 25,
        "max_buffer_size": 60,
    },
    "Heavy throughput": {
        "max_lines": 1200,
        "history_multiplier": 6,
        "update_interval_ms": 300,
        "lines_per_update": 80,
        "max_buffer_size": 160,
    },
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
        r"^(?P<timestamp>\d{2}-\d{2}\s\d{2}:\d{2}:\d{2}\.\d{3})\s+"
        r"(?P<pid>\d+)\s+(?P<tid>\d+)\s+"
        r"(?P<level>[VDIWEF])\s+"
        r"(?P<tag>[^:]*):\s"
        r"(?P<message>.*)$"
    )

    @classmethod
    def from_string(cls, line: str) -> "LogLine":
        match = cls._THREADTIME_PATTERN.match(line)
        if match:
            parts = match.groupdict()
            return cls(
                timestamp=parts["timestamp"],
                pid=parts["pid"],
                tid=parts["tid"],
                level=parts["level"],
                tag=parts["tag"].strip(),
                message=parts["message"].strip(),
                raw=line,
            )
        cleaned = line.strip()
        return cls("", "", "", "I", "Logcat", cleaned, raw=line)


def _split_logcat_chunk(partial_line: str, chunk: bytes) -> Tuple[List[str], str]:
    """Split a raw stdout chunk into complete log lines and a trailing partial line."""
    if not chunk:
        return [], partial_line

    text = chunk.decode("utf-8", errors="replace")
    if not text:
        return [], partial_line

    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    combined = f"{partial_line}{normalized}" if partial_line else normalized

    parts = combined.split("\n")
    if combined.endswith("\n"):
        new_partial = ""
    else:
        new_partial = parts.pop() if parts else combined

    lines = [line for line in parts if line.strip()]
    return lines, new_partial


def _filter_log_lines_snapshot(
    logs: List[LogLine],
    patterns: List[str],
    capacity: int,
    *,
    task_handle: Optional[TaskHandle] = None,
) -> List[LogLine]:
    """Filter a snapshot of log lines and return the last `capacity` matches."""
    capacity = max(1, int(capacity))
    compiled: List[re.Pattern[str]] = []
    for raw in patterns:
        if not raw:
            continue
        try:
            compiled.append(re.compile(raw, re.IGNORECASE))
        except re.error:
            continue

    if not compiled:
        return []

    matched: List[LogLine] = []
    for idx, line in enumerate(logs):
        if task_handle is not None and idx % 256 == 0 and task_handle.is_cancelled():
            raise TaskCancelledError("Operation cancelled")
        text = line.raw
        if any(pattern.search(text) for pattern in compiled):
            matched.append(line)

    if len(matched) > capacity:
        matched = matched[-capacity:]
    return matched


def _scan_search_spans(
    lines: List[str],
    pattern: str,
    flags: int,
    max_spans: int,
    *,
    task_handle: Optional[TaskHandle] = None,
) -> Tuple[List[int], List[Tuple[int, int, int]], bool]:
    """Return (match_rows, match_spans, limited) for a list of visible lines."""
    max_spans = max(1, int(max_spans))
    compiled = re.compile(pattern, flags)

    rows: List[int] = []
    spans: List[Tuple[int, int, int]] = []
    limited = False

    for row, line in enumerate(lines):
        if task_handle is not None and row % 256 == 0 and task_handle.is_cancelled():
            raise TaskCancelledError("Operation cancelled")
        line_has_match = False
        for match in compiled.finditer(line):
            spans.append((row, match.start(), match.end()))
            line_has_match = True
            if len(spans) >= max_spans:
                limited = True
                break
        if line_has_match:
            rows.append(row)
        if limited:
            break

    return rows, spans, limited


class _LogcatStreamWorker(QObject):
    """Decode, parse and batch logcat output off the UI thread."""

    batch_ready = pyqtSignal(object, object, int)  # all_lines, matched_lines, filter_revision

    def __init__(self) -> None:
        super().__init__()
        self._timer: Optional[QTimer] = None
        self._partial_line = ""
        self._pending: List[LogLine] = []
        self._last_flush_ms = 0.0

        self._update_interval_ms = 200
        self._max_buffer_size = 100
        self._max_lines_per_update = 50

        self._compiled_patterns: List[re.Pattern[str]] = []
        self._filter_revision = 0

        self._next_line_number = 1

    @pyqtSlot()
    def initialize(self) -> None:
        """Initialize Qt timers after the worker is moved to its thread."""
        if self._timer is not None:
            return
        timer = QTimer()
        timer.setSingleShot(True)
        timer.timeout.connect(self._on_timer_timeout)
        self._timer = timer

    @pyqtSlot(int, int, int)
    def set_performance_settings(
        self, update_interval_ms: int, max_buffer_size: int, max_lines_per_update: int
    ) -> None:
        self._update_interval_ms = max(20, int(update_interval_ms))
        self._max_buffer_size = max(10, int(max_buffer_size))
        self._max_lines_per_update = max(5, int(max_lines_per_update))

    @pyqtSlot(list, int)
    def set_filter_patterns(self, patterns: List[str], revision: int) -> None:
        compiled: List[re.Pattern[str]] = []
        for raw in patterns:
            if not raw:
                continue
            try:
                compiled.append(re.compile(raw, re.IGNORECASE))
            except re.error:
                continue
        self._compiled_patterns = compiled
        self._filter_revision = int(revision)

    @pyqtSlot()
    def reset(self) -> None:
        self._partial_line = ""
        self._pending.clear()
        self._next_line_number = 1
        self._last_flush_ms = 0.0
        if self._timer is not None:
            self._timer.stop()

    @pyqtSlot(bytes)
    def feed_bytes(self, chunk: bytes) -> None:
        lines, self._partial_line = _split_logcat_chunk(self._partial_line, chunk)
        if not lines:
            return

        parsed = [LogLine.from_string(line) for line in lines]
        self._pending.extend(parsed)

        now_ms = time.monotonic() * 1000.0
        elapsed = now_ms - self._last_flush_ms
        should_flush = (
            elapsed >= self._update_interval_ms
            or len(self._pending) >= self._max_buffer_size
        )

        if should_flush:
            self._flush_once(now_ms)
            return

        if self._timer is None:
            return
        if not self._timer.isActive():
            remaining = max(1, int(self._update_interval_ms - elapsed))
            self._timer.start(remaining)

    @pyqtSlot()
    def _on_timer_timeout(self) -> None:
        if not self._pending:
            return
        self._flush_once(time.monotonic() * 1000.0)

    def _flush_once(self, now_ms: float) -> None:
        if not self._pending:
            return

        backlog = len(self._pending)
        batch_size = int(self._max_lines_per_update)
        if backlog > self._max_buffer_size * 20:
            batch_size = min(backlog, batch_size * 8)
        elif backlog > self._max_buffer_size * 10:
            batch_size = min(backlog, batch_size * 6)
        elif backlog > self._max_buffer_size * 5:
            batch_size = min(backlog, batch_size * 4)
        elif backlog > self._max_buffer_size * 2:
            batch_size = min(backlog, batch_size * 2)

        batch = self._pending[:batch_size]
        del self._pending[:batch_size]

        numbered: List[LogLine] = []
        for line in batch:
            numbered.append(replace(line, line_no=self._next_line_number))
            self._next_line_number += 1

        matched: List[LogLine] = []
        if self._compiled_patterns:
            for line in numbered:
                if any(pattern.search(line.raw) for pattern in self._compiled_patterns):
                    matched.append(line)

        self._last_flush_ms = now_ms
        self.batch_ready.emit(numbered, matched, self._filter_revision)

        if not self._pending or self._timer is None:
            return

        if self._timer.isActive():
            return

        # Catch-up scheduling: flush sooner when backlog is large.
        if len(self._pending) > self._max_buffer_size * 5:
            interval = max(10, int(self._update_interval_ms // 4))
        else:
            interval = int(self._update_interval_ms)
        self._timer.start(interval)


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
            text = (
                log.raw
                if log
                else (model.data(index, Qt.ItemDataRole.DisplayRole) or "")
            )
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
        text = (
            log.raw if log else (model.data(index, Qt.ItemDataRole.DisplayRole) or "")
        )

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
    HIGHLIGHT_BG = "#623f00"  # Yellow-orange background for matches
    HIGHLIGHT_CURRENT_BG = "#515c6a"  # Brighter for current match
    HIGHLIGHT_TEXT = "#ffffff"  # White text for visibility

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
            y_offset = (
                text_rect.top() + (text_rect.height() + fm.ascent() - fm.descent()) // 2
            )

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
                    bg_color = (
                        self.HIGHLIGHT_CURRENT_BG
                        if is_current_row
                        else self.HIGHLIGHT_BG
                    )
                    painter.fillRect(
                        x,
                        text_rect.top(),
                        seg_width,
                        text_rect.height(),
                        QColor(bg_color),
                    )

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
        self.setWindowTitle("Performance Settings")
        self.setMinimumSize(520, 360)
        self.setModal(True)

        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(14)
        main_layout.setContentsMargins(18, 18, 18, 16)

        title = QLabel("Tune Logcat Performance")
        title.setStyleSheet("font-size: 16px; font-weight: 600; color: #1b4f72;")
        main_layout.addWidget(title)

        subtitle = QLabel(
            "Balance retained history with UI responsiveness. Adjust these knobs to fit your device throughput."
        )
        subtitle.setWordWrap(True)
        subtitle.setStyleSheet("color: #5f6a6a;")
        main_layout.addWidget(subtitle)

        preset_row = QHBoxLayout()
        preset_label = QLabel("Preset")
        preset_label.setStyleSheet("font-weight: bold;")
        preset_row.addWidget(preset_label)

        self.preset_combo = QComboBox()
        self.preset_combo.addItem("Custom")
        for preset_name in PERFORMANCE_PRESETS.keys():
            self.preset_combo.addItem(preset_name)
        preset_row.addWidget(self.preset_combo, stretch=1)
        preset_row.addStretch()
        main_layout.addLayout(preset_row)

        content_grid = QGridLayout()
        content_grid.setHorizontalSpacing(18)
        content_grid.setVerticalSpacing(12)

        history_group = QGroupBox("History & Retention")
        history_form = QFormLayout(history_group)
        history_form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        history_form.setFormAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop
        )

        self.max_lines_spin = QSpinBox()
        self.max_lines_spin.setRange(100, 50000)
        self.max_lines_spin.setSingleStep(100)
        self.max_lines_spin.setValue(
            self.parent_window.max_lines if self.parent_window else 1000
        )
        history_form.addRow("Visible lines", self.max_lines_spin)

        self.history_multiplier_spin = QSpinBox()
        self.history_multiplier_spin.setRange(1, 20)
        self.history_multiplier_spin.setSingleStep(1)
        self.history_multiplier_spin.setValue(
            self.parent_window.history_multiplier if self.parent_window else 5
        )
        history_form.addRow("History multiplier", self.history_multiplier_spin)

        content_grid.addWidget(history_group, 0, 0)

        cadence_group = QGroupBox("Streaming Cadence")
        cadence_form = QFormLayout(cadence_group)
        cadence_form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        cadence_form.setFormAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop
        )

        self.update_interval_spin = QSpinBox()
        self.update_interval_spin.setRange(50, 2000)
        self.update_interval_spin.setSingleStep(10)
        self.update_interval_spin.setValue(
            self.parent_window.update_interval_ms if self.parent_window else 200
        )
        interval_row = QWidget()
        interval_layout = QHBoxLayout(interval_row)
        interval_layout.setContentsMargins(0, 0, 0, 0)
        interval_layout.setSpacing(6)
        interval_layout.addWidget(self.update_interval_spin)
        interval_layout.addWidget(QLabel("ms"))
        interval_layout.addStretch()
        cadence_form.addRow("Refresh interval", interval_row)

        self.lines_per_update_spin = QSpinBox()
        self.lines_per_update_spin.setRange(10, 500)
        self.lines_per_update_spin.setSingleStep(5)
        self.lines_per_update_spin.setValue(
            self.parent_window.max_lines_per_update if self.parent_window else 50
        )
        cadence_form.addRow("Lines per update", self.lines_per_update_spin)

        self.buffer_size_spin = QSpinBox()
        self.buffer_size_spin.setRange(10, 1000)
        self.buffer_size_spin.setSingleStep(10)
        self.buffer_size_spin.setValue(
            self.parent_window.max_buffer_size if self.parent_window else 100
        )
        buffer_row = QWidget()
        buffer_layout = QHBoxLayout(buffer_row)
        buffer_layout.setContentsMargins(0, 0, 0, 0)
        buffer_layout.setSpacing(6)
        buffer_layout.addWidget(self.buffer_size_spin)
        buffer_layout.addWidget(QLabel("lines"))
        buffer_layout.addStretch()
        cadence_form.addRow("Flush threshold", buffer_row)

        content_grid.addWidget(cadence_group, 0, 1)

        main_layout.addLayout(content_grid)

        preview_frame = QFrame()
        preview_frame.setStyleSheet(
            "background-color: #f4f6f6; border: 1px solid #d6dbdf; border-radius: 6px; padding: 10px;"
        )
        preview_layout = QVBoxLayout(preview_frame)
        preview_layout.setSpacing(4)

        preview_title = QLabel("Preview")
        preview_title.setStyleSheet("font-weight: bold; color: #34495e;")
        preview_layout.addWidget(preview_title)

        self.capacity_label = QLabel()
        self.capacity_label.setStyleSheet("color: #1f618d;")
        preview_layout.addWidget(self.capacity_label)

        self.latency_label = QLabel()
        self.latency_label.setStyleSheet("color: #616a6b;")
        preview_layout.addWidget(self.latency_label)

        tips_label = QLabel(
            "Lower intervals provide lower latency but increase CPU usage. Larger flush thresholds smooth bursty logs."
        )
        tips_label.setWordWrap(True)
        tips_label.setStyleSheet("color: #7b8793; font-size: 11px;")
        preview_layout.addWidget(tips_label)

        main_layout.addWidget(preview_frame)

        button_layout = QHBoxLayout()
        button_layout.addStretch()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)

        apply_btn = QPushButton("Apply")
        apply_btn.setStyleSheet(
            "background-color: #1f618d; color: white; font-weight: bold;"
        )
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

            if hasattr(self.parent_window, "on_performance_settings_updated"):
                self.parent_window.on_performance_settings_updated()

            self.accept()
        except ValueError:
            QMessageBox.warning(
                self, "Invalid Input", "Please enter valid numbers for all settings."
            )

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
        if preset_name == "Custom" or preset_name not in PERFORMANCE_PRESETS:
            return

        preset_values = PERFORMANCE_PRESETS[preset_name]
        self._updating_from_preset = True
        try:
            self.max_lines_spin.setValue(preset_values["max_lines"])
            self.history_multiplier_spin.setValue(preset_values["history_multiplier"])
            self.update_interval_spin.setValue(preset_values["update_interval_ms"])
            self.lines_per_update_spin.setValue(preset_values["lines_per_update"])
            self.buffer_size_spin.setValue(preset_values["max_buffer_size"])
        finally:
            self._updating_from_preset = False
            self._update_capacity_preview()

    def _mark_custom(self):
        """Switch preset selection back to custom when values change."""
        if self._updating_from_preset:
            return
        if self.preset_combo.currentText() != "Custom":
            self.preset_combo.blockSignals(True)
            self.preset_combo.setCurrentText("Custom")
            self.preset_combo.blockSignals(False)

    def _update_capacity_preview(self):
        """Update capacity label showing the retained history size."""
        max_lines = self.max_lines_spin.value()
        history_multiplier = self.history_multiplier_spin.value()
        capacity = max_lines * history_multiplier
        self.capacity_label.setText(
            f"History capacity: {capacity:,} lines ({max_lines:,} visible × {history_multiplier} history)"
        )

        interval = self.update_interval_spin.value()
        lines_per_update = self.lines_per_update_spin.value()
        flush_threshold = self.buffer_size_spin.value()
        hz = 0.0 if interval <= 0 else 1000.0 / interval
        self.latency_label.setText(
            f"UI refresh ≈ every {interval} ms ({hz:.1f} Hz), {lines_per_update} lines/batch, flush at {flush_threshold} lines."
        )


class LogcatWindow(QDialog):
    """Logcat viewer window with real-time streaming and filtering capabilities."""

    _stream_bytes = pyqtSignal(bytes)
    _stream_reset = pyqtSignal()
    _stream_perf_settings = pyqtSignal(int, int, int)  # interval_ms, buffer_size, lines_per_update
    _stream_filter_patterns = pyqtSignal(list, int)  # patterns, revision

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

        # Load viewer UI settings from config
        self._viewer_settings: Optional["LogcatViewerSettings"] = None
        if self._config_manager:
            self._viewer_settings = self._config_manager.get_logcat_viewer_settings()

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

        # Performance and streaming configuration
        self.max_buffer_size = 100
        self.update_interval_ms = 200
        self.max_lines_per_update = 50
        self.history_multiplier = 5
        self._suppress_logcat_errors = False

        # Stream worker (off-UI-thread decoding/parsing/batching)
        self._stream_thread: Optional[QThread] = None
        self._stream_worker: Optional[_LogcatStreamWorker] = None
        self._filter_revision = 0

        if self._viewer_settings:
            self._auto_scroll_enabled = self._viewer_settings.auto_scroll_enabled
        else:
            self._auto_scroll_enabled = True
        self._suppress_scroll_signal = False

        # Display/search bookkeeping (avoid scanning editor text on every update)
        self._display_revision = 0
        self._display_lines: deque[str] = deque()
        self._search_match_spans_by_row: Dict[int, List[Tuple[int, int]]] = {}
        self._search_debounce_timer = QTimer(self)
        self._search_debounce_timer.setSingleShot(True)
        self._search_debounce_timer.timeout.connect(self._run_debounced_search_scan)
        self._search_scan_inflight = False
        self._search_scan_pending = False
        self._search_task_handle = None
        self._filter_rebuild_handle = None

        self._apply_persisted_settings(settings or {})

        # Filtering state
        self.log_levels_order = ["V", "D", "I", "W", "E", "F"]
        self.live_filter_pattern: Optional[str] = None
        self.active_filters: List[str] = []

        # Search state (for highlight search feature)
        self._search_pattern: Optional[re.Pattern] = None
        self._search_match_rows: List[int] = []  # Rows with matches
        self._search_match_spans: List[Tuple[int, int, int]] = []
        self._current_match_index: int = -1  # Current match in _search_match_rows

        self._init_stream_worker()

        self.init_ui()
        self._setup_copy_features()
        self._setup_search_shortcut()
        self._setup_device_watcher()
        self._migrate_legacy_filters()
        self._apply_viewer_settings()

    def _get_status_prefix(self):
        """Get status prefix emoji based on running state."""
        return "🟢" if self.is_running else "⏸️"

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

        if "max_lines" in settings:
            self.max_lines = _coerce(settings.get("max_lines"), 100, self.max_lines)
            self.log_proxy.set_visible_limit(self.max_lines)

        if "history_multiplier" in settings:
            self.history_multiplier = _coerce(
                settings.get("history_multiplier"), 1, self.history_multiplier
            )

        if "update_interval_ms" in settings:
            self.update_interval_ms = _coerce(
                settings.get("update_interval_ms"), 50, self.update_interval_ms
            )

        if "max_lines_per_update" in settings:
            self.max_lines_per_update = _coerce(
                settings.get("max_lines_per_update"), 5, self.max_lines_per_update
            )

        if "max_buffer_size" in settings:
            self.max_buffer_size = _coerce(
                settings.get("max_buffer_size"), 10, self.max_buffer_size
            )
        # Stream worker settings are synced after worker initialization.

    def _apply_viewer_settings(self) -> None:
        if not self._viewer_settings:
            return

        if hasattr(self, "follow_latest_checkbox"):
            self.follow_latest_checkbox.setChecked(self._auto_scroll_enabled)

        if hasattr(self, "_preview_panel") and self._preview_panel:
            self._preview_panel.setVisible(self._viewer_settings.show_preview_panel)
            if hasattr(self, "preview_toggle_btn"):
                self.preview_toggle_btn.setChecked(
                    self._viewer_settings.show_preview_panel
                )

    def _save_viewer_settings(self) -> None:
        if not self._config_manager:
            return

        show_preview = False
        if hasattr(self, "_preview_panel") and self._preview_panel:
            show_preview = self._preview_panel.isVisible()

        self._config_manager.update_logcat_viewer_settings(
            auto_scroll_enabled=self._auto_scroll_enabled,
            show_preview_panel=show_preview,
        )

    def _init_stream_worker(self) -> None:
        """Start the background stream worker used for parsing/batching."""
        thread = QThread(self)
        worker = _LogcatStreamWorker()
        worker.moveToThread(thread)

        thread.started.connect(worker.initialize)
        worker.batch_ready.connect(self._on_stream_batch_ready)

        self._stream_bytes.connect(
            worker.feed_bytes, Qt.ConnectionType.QueuedConnection
        )
        self._stream_reset.connect(worker.reset, Qt.ConnectionType.QueuedConnection)
        self._stream_perf_settings.connect(
            worker.set_performance_settings, Qt.ConnectionType.QueuedConnection
        )
        self._stream_filter_patterns.connect(
            worker.set_filter_patterns, Qt.ConnectionType.QueuedConnection
        )

        thread.start()

        self._stream_thread = thread
        self._stream_worker = worker

        self._sync_stream_worker_settings()
        self._sync_stream_worker_filters()

    def _sync_stream_worker_settings(self) -> None:
        self._stream_perf_settings.emit(
            int(self.update_interval_ms),
            int(self.max_buffer_size),
            int(self.max_lines_per_update),
        )

    def _sync_stream_worker_filters(self) -> None:
        patterns: List[str] = []
        if self.live_filter_pattern:
            patterns.append(self.live_filter_pattern)
        patterns.extend(self.active_filters)
        self._stream_filter_patterns.emit(patterns, int(self._filter_revision))

    def _update_status_label(self, text):
        """Update status label with consistent formatting."""
        prefix = self._get_status_prefix()
        self.status_label.setText(f"{prefix} {text}")

    def _rebuild_log_display_from_model(self) -> None:
        """Rebuild the text display from the current model state."""
        try:
            if self._has_active_filters():
                lines = [line.raw for line in self.filtered_model.to_list()]
            else:
                # Keep only the last max_lines for display.
                capacity = max(1, int(self.max_lines))
                lines = [line.raw for line in self.log_model.to_list()][-capacity:]
            self.log_display.setPlainText("\n".join(lines))
            self._display_lines = deque(lines)
            self._display_revision += 1
            self._schedule_search_refresh()
        except Exception as exc:  # pragma: no cover - defensive
            logger.debug("Failed to rebuild log display: %s", exc)

    def _append_lines_to_log_display(self, lines: List[LogLine]) -> None:
        """Append lines to the text display respecting max_lines."""
        if not lines:
            return
        try:
            raw_lines = [line.raw for line in lines]
            doc = self.log_display.document()
            is_empty = doc.blockCount() == 1 and not doc.firstBlock().text()
            prefix = "" if is_empty else "\n"

            self.log_display.setUpdatesEnabled(False)
            try:
                cursor = QTextCursor(doc)
                cursor.movePosition(QTextCursor.MoveOperation.End)
                cursor.insertText(prefix + "\n".join(raw_lines))
            finally:
                self.log_display.setUpdatesEnabled(True)

            capacity = max(1, int(self.max_lines))
            for line in lines:
                self._display_lines.append(line.raw)
            while len(self._display_lines) > capacity:
                self._display_lines.popleft()

            self._display_revision += 1
            self._schedule_search_refresh()
        except Exception as exc:  # pragma: no cover - defensive
            logger.debug("Failed to append lines to display: %s", exc)

    def _manage_buffer_size(self):
        """Manage raw log buffer size based on configured history."""
        history_limit = self.max_lines * self.history_multiplier
        before = self.log_model.rowCount()
        self.log_model.trim(history_limit)
        if self.log_model.rowCount() != before:
            pass

    def _handle_filters_changed(self):
        """Rebuild filtered view when filters are updated."""
        self._filter_revision += 1
        current_revision = int(self._filter_revision)
        self._sync_stream_worker_filters()

        if self._filter_rebuild_handle is not None:
            try:
                self._filter_rebuild_handle.cancel()
            except Exception:
                pass
            self._filter_rebuild_handle = None

        if not self._has_active_filters():
            self.filtered_model.clear()
            self._rebuild_log_display_from_model()
            self._update_status_counts()
            self._scroll_to_bottom()
            return

        patterns: List[str] = []
        if self.live_filter_pattern:
            patterns.append(self.live_filter_pattern)
        patterns.extend(self.active_filters)

        logs_snapshot = self.log_model.to_list()
        if len(logs_snapshot) <= 600:
            matched = _filter_log_lines_snapshot(
                logs_snapshot,
                patterns,
                int(self.max_lines),
            )
            self._apply_refilter_result(matched, current_revision)
            return

        dispatcher = get_task_dispatcher()
        context = TaskContext(
            name="logcat_refilter",
            device_serial=getattr(self.device, "device_serial_num", None),
            category="logcat",
        )
        handle = dispatcher.submit(
            _filter_log_lines_snapshot,
            logs_snapshot,
            patterns,
            int(self.max_lines),
            context=context,
        )
        self._filter_rebuild_handle = handle
        handle.completed.connect(
            lambda matched: self._apply_refilter_result(matched, current_revision)
        )
        handle.failed.connect(self._on_filter_rebuild_failed)
        self._update_status_label("Applying filters...")

    def _on_filter_rebuild_failed(self, exc: Exception) -> None:
        if isinstance(exc, TaskCancelledError):
            return
        logger.debug("Filter rebuild failed: %s", exc)

    def _apply_refilter_result(self, matched: List[LogLine], revision: int) -> None:
        """Apply an async refilter result if it matches the current revision."""
        if int(revision) != int(self._filter_revision):
            return
        if not self._has_active_filters():
            return

        self.filtered_model.clear()
        if matched:
            self.filtered_model.append_lines(matched)

        self.limit_log_lines()
        self._rebuild_log_display_from_model()
        self._update_status_counts()
        self._scroll_to_bottom()

    def _has_active_filters(self) -> bool:
        """Return whether any filter (live or saved) is active."""
        return bool(self.live_filter_pattern) or bool(self.active_filters)

    def init_ui(self):
        """Initialize the logcat window UI."""
        self.setWindowTitle(
            f"Logcat Viewer - {self.device.device_model} ({self.device.device_serial_num[:8]}...)"
        )
        self.setGeometry(100, 100, 1200, 800)

        # Main layout and splitter configuration
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        control_layout = self.create_control_panel()

        # Extract levels and filters into collapsible panels for a cleaner UI.
        levels_content = self._create_levels_widget()
        levels_panel = CollapsiblePanel(
            "Levels", levels_content, collapsed=False, parent=self
        )

        filters_content = self.create_filter_panel()
        filters_panel = CollapsiblePanel(
            "Filters", filters_content, collapsed=False, parent=self
        )

        top_panel = QWidget()
        top_panel.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum
        )
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
        if hasattr(self, "levels_toggle_btn"):
            self.levels_toggle_btn.setCheckable(True)
            self.levels_toggle_btn.setChecked(not self.levels_panel.is_collapsed())
        if hasattr(self, "filters_toggle_btn"):
            self.filters_toggle_btn.setCheckable(True)
            self.filters_toggle_btn.setChecked(not self.filters_panel.is_collapsed())

        self.log_display = QPlainTextEdit()
        self.log_display.setReadOnly(True)
        self.log_display.setUndoRedoEnabled(False)
        self.log_display.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.log_display.setFont(QFont("Consolas", 10))
        self.log_display.setStyleSheet(
            """
            QPlainTextEdit {
                background-color: #1e1e1e;
                color: #ffffff;
                border: 1px solid #3e3e3e;
            }
            """
        )
        self.log_display.setMaximumBlockCount(max(1, int(self.max_lines)))
        self.log_display.verticalScrollBar().valueChanged.connect(
            self._on_log_view_scrolled
        )
        self.log_display.selectionChanged.connect(self._on_log_selection_changed)

        self.status_label = QLabel("Ready to start logcat...")

        log_container = QWidget()
        log_container.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
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
        left_panel.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
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
        self._preview_panel.setVisible(False)

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

        copy_sequence = QKeySequence(QKeySequence.StandardKey.Copy)
        select_all_sequence = QKeySequence(QKeySequence.StandardKey.SelectAll)
        copy_all_sequence = QKeySequence("Ctrl+Shift+C")

        self._copy_selected_action = QAction("Copy Selected", self)
        self._copy_selected_action.setShortcut(copy_sequence)
        self._copy_selected_action.triggered.connect(self.copy_selected_logs)

        self._copy_all_action = QAction("Copy All", self)
        self._copy_all_action.setShortcut(copy_all_sequence)
        self._copy_all_action.triggered.connect(self.copy_all_logs)

        self._select_all_action = QAction("Select All", self)
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
        if hasattr(self, "_search_bar") and self._search_bar:
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
            self._device_watcher.device_disconnected.connect(
                self._on_device_disconnected
            )
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
        has_selection = bool(self.log_display.textCursor().hasSelection())
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
        selected = self.log_display.textCursor().selectedText()
        if not selected:
            return []
        # Qt uses U+2029 paragraph separators for multi-line selections.
        normalized = selected.replace("\u2029", "\n").replace("\u2028", "\n")
        return [normalized]

    def _collect_all_visible_lines(self) -> List[str]:
        return [self.log_display.toPlainText()]

    def copy_selected_logs(self) -> str:
        """Copy the selected log rows to the clipboard and return the payload."""
        lines = self._collect_selected_lines()
        text = "\n".join(lines)
        if text:
            QApplication.clipboard().setText(text)
        return text

    def copy_all_logs(self) -> str:
        """Copy all visible log rows to the clipboard and return the payload."""
        lines = self._collect_all_visible_lines()
        text = "\n".join(lines)
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

        self.start_btn = QPushButton("▶️ Start Logcat")
        self.start_btn.clicked.connect(self.start_logcat)
        primary_row.addWidget(self.start_btn)

        self.stop_btn = QPushButton("⏹️ Stop")
        self.stop_btn.clicked.connect(self.stop_logcat)
        self.stop_btn.setEnabled(False)
        primary_row.addWidget(self.stop_btn)

        clear_btn = QPushButton("🗑️ Clear")
        clear_btn.clicked.connect(self.clear_logs)
        primary_row.addWidget(clear_btn)

        clear_buffer_btn = QPushButton("🧹 Clear Buffer")
        clear_buffer_btn.setToolTip("Clear the device logcat buffer")
        clear_buffer_btn.clicked.connect(self.confirm_clear_device_logcat_buffer)
        primary_row.addWidget(clear_buffer_btn)

        primary_row.addWidget(self.create_vertical_separator())

        self.follow_latest_checkbox = QCheckBox("Follow newest")
        self.follow_latest_checkbox.setChecked(True)
        self.follow_latest_checkbox.toggled.connect(self.set_auto_scroll_enabled)
        primary_row.addWidget(self.follow_latest_checkbox)

        jump_btn = QPushButton("Jump to latest")
        jump_btn.clicked.connect(lambda: self.set_auto_scroll_enabled(True))
        jump_btn.setToolTip("Re-enable auto-follow and scroll to newest log entries")
        primary_row.addWidget(jump_btn)

        primary_row.addWidget(self.create_vertical_separator())

        self.levels_toggle_btn = QPushButton("Levels")
        self.levels_toggle_btn.clicked.connect(self.toggle_levels_visibility)
        primary_row.addWidget(self.levels_toggle_btn)

        self.filters_toggle_btn = QPushButton("Filters")
        self.filters_toggle_btn.clicked.connect(self.toggle_filters_visibility)
        primary_row.addWidget(self.filters_toggle_btn)

        self.preview_toggle_btn = QPushButton("Preview")
        self.preview_toggle_btn.setCheckable(True)
        self.preview_toggle_btn.setChecked(False)
        self.preview_toggle_btn.setToolTip("Toggle device preview and recording panel")
        self.preview_toggle_btn.clicked.connect(self.toggle_preview_visibility)
        primary_row.addWidget(self.preview_toggle_btn)

        primary_row.addStretch(1)

        more_btn = QPushButton("⋮")
        more_btn.setFixedWidth(32)
        more_btn.setToolTip("More options")
        more_menu = QMenu(more_btn)

        self._compact_mode_action = more_menu.addAction("📦 Compact Mode")
        self._compact_mode_action.setCheckable(True)
        is_compact = (
            self._viewer_settings.compact_mode if self._viewer_settings else True
        )
        self._compact_mode_action.setChecked(is_compact)
        self._compact_mode_action.triggered.connect(self._toggle_compact_mode)

        more_menu.addSeparator()

        perf_action = more_menu.addAction("⚙️ Performance Settings")
        perf_action.triggered.connect(self.open_performance_settings)
        more_btn.setMenu(more_menu)
        primary_row.addWidget(more_btn)

        layout.addLayout(primary_row)
        return layout

    def _toggle_compact_mode(self, checked: bool) -> None:
        if hasattr(self, "levels_panel") and self.levels_panel:
            self.levels_panel.set_collapsed(checked)
        if hasattr(self, "filters_panel") and self.filters_panel:
            self.filters_panel.set_collapsed(checked)
        if self._viewer_settings:
            self._viewer_settings.compact_mode = checked

    def toggle_levels_visibility(self):
        """Toggle the visibility of the Levels panel content."""
        if hasattr(self, "levels_panel") and self.levels_panel:
            self.levels_panel.set_collapsed(not self.levels_panel.is_collapsed())
            if hasattr(self, "levels_toggle_btn"):
                self.levels_toggle_btn.setChecked(not self.levels_panel.is_collapsed())

    def toggle_filters_visibility(self):
        """Toggle the visibility of the Filters panel content."""
        if hasattr(self, "filters_panel") and self.filters_panel:
            self.filters_panel.set_collapsed(not self.filters_panel.is_collapsed())
            if hasattr(self, "filters_toggle_btn"):
                self.filters_toggle_btn.setChecked(
                    not self.filters_panel.is_collapsed()
                )

    def toggle_preview_visibility(self):
        if not hasattr(self, "_preview_panel") or not self._preview_panel:
            return

        is_visible = self._preview_panel.isVisible()
        target_visible = not is_visible

        if hasattr(self, "preview_toggle_btn"):
            self.preview_toggle_btn.setChecked(target_visible)

        if target_visible:
            self._preview_panel.setVisible(True)
            self._animate_splitter_show()
        else:
            self._animate_splitter_hide()

    def _animate_splitter_show(self) -> None:
        if not hasattr(self, "_main_splitter"):
            return

        sizes = self._main_splitter.sizes()
        total = sum(sizes)
        if total <= 0:
            return

        target_preview_width = total // 4
        target_left_width = total - target_preview_width

        self._splitter_anim = QPropertyAnimation(self, b"_splitter_sizes_anim")
        self._splitter_anim.setDuration(200)
        self._splitter_anim.setStartValue([sizes[0], 0])
        self._splitter_anim.setEndValue([target_left_width, target_preview_width])
        self._splitter_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._splitter_anim.valueChanged.connect(self._on_splitter_anim_value)
        self._splitter_anim.start()

    def _animate_splitter_hide(self) -> None:
        if not hasattr(self, "_main_splitter"):
            self._preview_panel.setVisible(False)
            return

        sizes = self._main_splitter.sizes()
        total = sum(sizes)

        self._splitter_anim = QPropertyAnimation(self, b"_splitter_sizes_anim")
        self._splitter_anim.setDuration(200)
        self._splitter_anim.setStartValue(sizes)
        self._splitter_anim.setEndValue([total, 0])
        self._splitter_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._splitter_anim.valueChanged.connect(self._on_splitter_anim_value)
        self._splitter_anim.finished.connect(self._on_splitter_hide_finished)
        self._splitter_anim.start()

    def _on_splitter_anim_value(self, value) -> None:
        if hasattr(self, "_main_splitter"):
            self._main_splitter.setSizes([int(value[0]), int(value[1])])

    def _on_splitter_hide_finished(self) -> None:
        if hasattr(self, "_preview_panel") and self._preview_panel:
            self._preview_panel.setVisible(False)

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
        levels_container.setObjectName("logcat_levels_container")
        levels_container.setStyleSheet(
            "QWidget#logcat_levels_container {"
            " background-color: #2c2c2c;"
            " border: 1px solid #3e3e3e;"
            " border-radius: 6px;"
            "}"
        )
        levels_layout = QHBoxLayout(levels_container)
        levels_layout.setContentsMargins(8, 6, 8, 6)
        levels_layout.setSpacing(8)

        self.log_levels = {
            "V": QCheckBox("Verbose"),
            "D": QCheckBox("Debug"),
            "I": QCheckBox("Info"),
            "W": QCheckBox("Warn"),
            "E": QCheckBox("Error"),
            "F": QCheckBox("Fatal"),
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

        source_label = QLabel("Source")
        source_label.setStyleSheet("font-weight: bold;")
        source_layout.addWidget(source_label)

        self.log_source_mode = QComboBox()
        self.log_source_mode.addItem("Tag", "tag")
        self.log_source_mode.addItem("Package", "package")
        self.log_source_mode.addItem("Raw", "raw")
        self.log_source_mode.setCurrentIndex(0)
        self.log_source_mode.setFixedWidth(110)
        source_layout.addWidget(self.log_source_mode)

        self.log_source_input = QLineEdit()
        self.log_source_input.setPlaceholderText("Tag or package filter (optional)")
        self.log_source_input.setMinimumWidth(220)
        source_layout.addWidget(self.log_source_input, stretch=1)

        main_layout.addWidget(source_cluster)

        # Three-level filter panel widget
        self._filter_panel_widget = FilterPanelWidget(
            parent=self,
            preset_manager=self._preset_manager,
        )
        self._filter_panel_widget.filters_changed.connect(self._on_filter_panel_changed)
        self._filter_panel_widget.live_filter_changed.connect(
            self._on_live_filter_changed
        )

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
            active_count = len(self.active_filters) + (
                1 if self.live_filter_pattern else 0
            )
            filtered_count = self.filtered_model.rowCount()
            capacity = self.max_lines
            self._update_status_label(
                f"Filtered: {filtered_count}/{capacity} lines (active: {active_count})"
            )
        else:
            capacity = self.max_lines * self.history_multiplier
            total_logs = self.log_model.rowCount()
            self._update_status_label(f"Total: {total_logs}/{capacity} lines")

    def _notify_settings_changed(self) -> None:
        """Emit persisted settings through callback if provided."""
        if callable(self._settings_callback):
            self._settings_callback(
                {
                    "max_lines": self.max_lines,
                    "history_multiplier": self.history_multiplier,
                    "update_interval_ms": self.update_interval_ms,
                    "max_lines_per_update": self.max_lines_per_update,
                    "max_buffer_size": self.max_buffer_size,
                }
            )

    def on_performance_settings_updated(self):
        """Handle updates from the performance settings dialog."""
        self.log_proxy.set_visible_limit(self.max_lines)
        self.limit_log_lines()
        self._update_status_counts()
        self._sync_stream_worker_settings()
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
            self._stream_reset.emit()
            self._suppress_logcat_errors = False
            self._sync_stream_worker_settings()
            self._sync_stream_worker_filters()

            # Create QProcess for logcat
            process = QProcess(self)
            process.readyReadStandardOutput.connect(self.read_logcat_output)
            process.finished.connect(self.on_logcat_finished)
            process.started.connect(self._handle_logcat_started)
            process.errorOccurred.connect(self._handle_logcat_error)

            self.logcat_process = process

            self.start_btn.setEnabled(False)
            self.stop_btn.setEnabled(False)
            self._update_status_label(
                f"Starting logcat for {self.device.device_model}..."
            )

            # Use adb logcat with device serial
            cmd = "adb"
            process.start(cmd, args)

        except Exception as exc:
            self.show_error(f"Error starting logcat: {exc}")
            self._cleanup_logcat_process()
            self._handle_logcat_stopped()

    def _get_selected_levels(self) -> List[str]:
        """Return selected log severity levels in configured order."""
        selected = [
            level
            for level in self.log_levels_order
            if self.log_levels[level].isChecked()
        ]
        return selected or ["E"]

    def _clear_device_logcat_buffer(self) -> None:
        """Clear the device-side logcat buffer."""
        try:
            subprocess.run(
                ["adb", "-s", self.device.device_serial_num, "logcat", "-c"],
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except FileNotFoundError:
            logger.warning("ADB executable not found when clearing logcat buffer.")
        except Exception as exc:  # pragma: no cover - defensive
            logger.debug("Clearing logcat buffer failed but continuing: %s", exc)

    def confirm_clear_device_logcat_buffer(self) -> None:
        """Ask for confirmation before clearing the device logcat buffer."""
        response = QMessageBox.question(
            self,
            "Clear Logcat Buffer",
            "Clear the device logcat buffer? This removes buffered logs on the device.",
            QMessageBox.StandardButton.Cancel | QMessageBox.StandardButton.Ok,
            QMessageBox.StandardButton.Cancel,
        )
        if response != QMessageBox.StandardButton.Ok:
            return

        self._clear_device_logcat_buffer()
        self._update_status_label("Device logcat buffer cleared.")

    def _handle_logcat_started(self):
        """Update state when the logcat process reports it has started."""
        self.is_running = True
        self.stop_btn.setEnabled(True)
        self._update_status_label(f"Logcat running for {self.device.device_model}...")

    def _handle_logcat_error(self, error):
        """Handle asynchronous logcat process errors."""
        if self._suppress_logcat_errors:
            return

        error_map = {
            QT_QPROCESS.ProcessError.FailedToStart: "Failed to start logcat process. Ensure ADB is available on PATH.",
            QT_QPROCESS.ProcessError.Crashed: "Logcat process crashed unexpectedly.",
            QT_QPROCESS.ProcessError.Timedout: "Timed out while starting logcat process.",
        }
        message = error_map.get(error, f"Logcat process error: {error}")
        self.show_error(message)
        self._cleanup_logcat_process()
        self._handle_logcat_stopped()

    def _build_logcat_arguments(self, selected_levels: List[str]) -> List[str]:
        """Build the adb logcat command arguments based on selected filters."""
        base_args = ["-s", self.device.device_serial_num, "logcat", "-v", "threadtime"]
        base_args.extend(self._build_source_filters(selected_levels))
        return base_args

    def _build_source_filters(self, selected_levels: List[str]) -> List[str]:
        """Construct filter arguments for tag/package/raw modes."""
        lowest_level = self._get_lowest_level(selected_levels)

        if not hasattr(self, "log_source_input"):
            return [f"*:{lowest_level}"]

        filter_text = self.log_source_input.text().strip()
        if not filter_text:
            return [f"*:{lowest_level}"]

        mode = self.log_source_mode.currentData()

        if mode == "tag":
            tag_level = self._get_lowest_level(selected_levels)
            return [f"{filter_text}:{tag_level}", "*:S"]

        if mode == "package":
            pids = self._resolve_package_pids(filter_text)
            if not pids:
                raise ValueError(
                    f'No running process found for "{filter_text}". '
                    "Launch the app and try again."
                )

            pid_args: List[str] = []
            for pid in pids:
                pid_args.extend(["--pid", pid])
            pid_args.append(f"*:{lowest_level}")
            return pid_args

        if mode == "raw":
            return filter_text.split()

        return [f"*:{lowest_level}"]

    def _get_lowest_level(self, selected_levels: List[str]) -> str:
        """Get the least restrictive (most verbose) level from selection."""
        priority = {level: index for index, level in enumerate(self.log_levels_order)}
        return min(selected_levels, key=lambda lvl: priority.get(lvl, len(priority)))

    def _resolve_package_pids(self, package_name: str) -> List[str]:
        """Resolve running process IDs for the provided package name."""
        try:
            pids = adb_tools.get_package_pids(
                self.device.device_serial_num, package_name
            )
            return [pid.strip() for pid in pids if pid and pid.strip()]
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.warning("PID lookup failed for %s: %s", package_name, exc)
            return []

    def read_logcat_output(self):
        """Read stdout bytes and forward to the background worker."""
        if not self.logcat_process:
            return

        data = self.logcat_process.readAllStandardOutput()
        chunk = bytes(data)
        if not chunk:
            return

        self._stream_bytes.emit(chunk)

    def _on_stream_batch_ready(
        self, all_lines: List[LogLine], matched_lines: List[LogLine], revision: int
    ) -> None:
        """Apply a parsed batch from the stream worker to models and UI."""
        if int(revision) != int(self._filter_revision):
            return

        if all_lines:
            self.log_model.append_lines(all_lines)

        if self._has_active_filters():
            if matched_lines:
                self.filtered_model.append_lines(matched_lines)
            self.limit_log_lines()
            self._append_lines_to_log_display(matched_lines)
        else:
            self._append_lines_to_log_display(all_lines)
            self.limit_log_lines()
        self._scroll_to_bottom()

        if self.is_running:
            if self._has_active_filters():
                active_count = len(self.active_filters) + (
                    1 if self.live_filter_pattern else 0
                )
                filtered_count = self.filtered_model.rowCount()
                self._update_status_label(
                    f"Logcat running... (filtered: {filtered_count}/{self.max_lines}, active: {active_count})"
                )
            else:
                capacity = self.max_lines * self.history_multiplier
                total_logs = self.log_model.rowCount()
                self._update_status_label(
                    f"Logcat running... ({total_logs}/{capacity} lines)"
                )

    def limit_log_lines(self):
        """Limit the number of lines in the display for performance."""
        try:
            self.log_display.setMaximumBlockCount(max(1, int(self.max_lines)))
        except Exception:
            pass
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
                    logger.debug("Kill skipped (process already gone): %s", exc)
                except AttributeError:
                    pass
                try:
                    process.waitForFinished(3000)
                except RuntimeError as exc:
                    logger.debug(
                        "waitForFinished skipped (process already gone): %s", exc
                    )
                except AttributeError:
                    pass
        except Exception as exc:
            logger.warning("Failed to terminate logcat process: %s", exc)
        finally:
            delete_later = getattr(process, "deleteLater", None)
            if callable(delete_later):
                try:
                    delete_later()
                except RuntimeError as exc:
                    logger.debug(
                        "deleteLater skipped (process already deleted): %s", exc
                    )

    def _handle_logcat_stopped(self):
        """Reset state and UI once logcat streaming halts."""
        self._stream_reset.emit()
        self._search_debounce_timer.stop()
        self._search_scan_inflight = False
        self._search_scan_pending = False
        if self._search_task_handle is not None:
            try:
                self._search_task_handle.cancel()
            except Exception:
                pass
        self._suppress_logcat_errors = False

        self.is_running = False
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)

        if self.log_model.rowCount():
            self.limit_log_lines()
            self._update_status_counts()
        else:
            self._update_status_label("Logcat stopped.")

    def clear_logs(self):
        """Clear the log display."""
        self.log_model.clear()
        self.filtered_model.clear()
        self._stream_reset.emit()
        self._display_lines.clear()
        self._display_revision += 1
        self._clear_search_highlight()
        self._update_status_label("Logs cleared")
        try:
            self.log_display.clear()
        except Exception:
            pass

    def set_auto_scroll_enabled(
        self, enabled: bool, *, from_scroll: bool = False
    ) -> None:
        """Enable or disable automatic scrolling to the latest log entry."""
        enabled = bool(enabled)
        if enabled == self._auto_scroll_enabled and not from_scroll:
            return

        self._auto_scroll_enabled = enabled

        if hasattr(self, "follow_latest_checkbox"):
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

    def _on_log_selection_changed(self) -> None:
        """Pause auto-follow while the user is selecting text."""
        try:
            if not self._auto_scroll_enabled:
                return
            cursor = self.log_display.textCursor()
            if cursor is not None and cursor.hasSelection():
                self.set_auto_scroll_enabled(False, from_scroll=True)
        except Exception as exc:  # pragma: no cover - defensive
            logger.debug("Selection change handling failed: %s", exc)

    def apply_live_filter(self, pattern):
        """Apply live regex filter to logs in real-time."""
        self.live_filter_pattern = pattern.strip() if pattern.strip() else None
        self._handle_filters_changed()

    def refilter_display(self):
        """Re-filter all logs and update display."""
        self._handle_filters_changed()

    def _scroll_to_bottom(self):
        """Scroll log display to bottom."""
        if not self._auto_scroll_enabled:
            return

        scroll_bar = self.log_display.verticalScrollBar()
        self._suppress_scroll_signal = True
        try:
            if scroll_bar is not None:
                scroll_bar.setValue(scroll_bar.maximum())
        finally:
            self._suppress_scroll_signal = False

    # ─────────────────────────────────────────────────────────────────────────
    # Search functionality
    # ─────────────────────────────────────────────────────────────────────────

    _SEARCH_DEBOUNCE_MS = 250
    _SYNC_SEARCH_SCAN_MAX_LINES = 600
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
        self._schedule_search_refresh(immediate=True)

    # Maximum search matches to collect for performance
    _MAX_SEARCH_MATCHES = 1000

    def _schedule_search_refresh(self, *, immediate: bool = False) -> None:
        """Throttle search scanning to keep UI responsive during heavy streaming."""
        if not self._search_pattern:
            return
        if self._search_scan_inflight:
            self._search_scan_pending = True
            return

        if immediate:
            self._search_debounce_timer.start(1)
            return

        # Avoid starving updates during constant streaming by not restarting an active timer.
        if self._search_debounce_timer.isActive():
            return
        self._search_debounce_timer.start(int(self._SEARCH_DEBOUNCE_MS))

    def _run_debounced_search_scan(self) -> None:
        """Kick off a background scan over the current visible display lines."""
        if not self._search_pattern:
            return
        if self._search_scan_inflight:
            self._search_scan_pending = True
            return

        if self._search_task_handle is not None:
            try:
                self._search_task_handle.cancel()
            except Exception:
                pass
            self._search_task_handle = None

        self._search_scan_inflight = True
        self._search_scan_pending = False

        lines_snapshot = list(self._display_lines)
        revision = int(self._display_revision)
        pattern = self._search_pattern.pattern
        flags = int(self._search_pattern.flags)

        if len(lines_snapshot) <= int(self._SYNC_SEARCH_SCAN_MAX_LINES):
            result = _scan_search_spans(
                lines_snapshot,
                pattern,
                flags,
                int(self._MAX_SEARCH_MATCHES),
            )
            self._apply_search_scan_result(result, revision, pattern, flags)
            return

        dispatcher = get_task_dispatcher()
        context = TaskContext(
            name="logcat_search_scan",
            device_serial=getattr(self.device, "device_serial_num", None),
            category="logcat",
        )
        handle = dispatcher.submit(
            _scan_search_spans,
            lines_snapshot,
            pattern,
            flags,
            int(self._MAX_SEARCH_MATCHES),
            context=context,
        )
        self._search_task_handle = handle
        handle.completed.connect(
            lambda result: self._apply_search_scan_result(
                result, revision, pattern, flags
            )
        )
        handle.failed.connect(self._on_search_scan_failed)

    def _on_search_scan_failed(self, exc: Exception) -> None:
        self._search_scan_inflight = False
        if isinstance(exc, TaskCancelledError):
            if self._search_pattern and self._search_scan_pending:
                self._schedule_search_refresh(immediate=True)
            return
        logger.debug("Search scan failed: %s", exc)
        if self._search_pattern:
            self._search_scan_pending = True
            self._schedule_search_refresh(immediate=True)

    def _apply_search_scan_result(
        self,
        result: Tuple[List[int], List[Tuple[int, int, int]], bool],
        revision: int,
        pattern: str,
        flags: int,
    ) -> None:
        """Apply a background scan result if it still matches the current view."""
        self._search_scan_inflight = False

        if (
            int(revision) != int(self._display_revision)
            or not self._search_pattern
            or self._search_pattern.pattern != pattern
            or int(self._search_pattern.flags) != int(flags)
        ):
            if self._search_pattern:
                self._search_scan_pending = True
                self._schedule_search_refresh(immediate=True)
            return

        rows, spans, limited = result
        self._search_match_rows = rows
        self._search_match_spans = spans

        spans_by_row: Dict[int, List[Tuple[int, int]]] = {}
        for row, start, end in spans:
            spans_by_row.setdefault(row, []).append((start, end))
        self._search_match_spans_by_row = spans_by_row

        if rows:
            cursor_row = self.log_display.textCursor().blockNumber()
            self._current_match_index = 0
            for i, row in enumerate(rows):
                if row >= cursor_row:
                    self._current_match_index = i
                    break
        else:
            self._current_match_index = -1

        total = len(rows)
        current = self._current_match_index + 1 if total > 0 else 0
        self._search_bar.update_match_count(current, total, limited=bool(limited))

        self._update_current_match_highlight()

        if self._search_scan_pending:
            self._search_scan_pending = False
            self._schedule_search_refresh(immediate=True)

    def _update_current_match_highlight(self) -> None:
        """Update match highlight and scroll to the current match."""
        if not self._search_match_rows or self._current_match_index < 0:
            self._apply_search_highlight(-1)
            return

        current_row = self._search_match_rows[self._current_match_index]
        self._apply_search_highlight(current_row)

        spans = self._search_match_spans_by_row.get(current_row) or []
        if not spans:
            return

        start, end = spans[0]
        document = self.log_display.document()
        block = document.findBlockByNumber(current_row)
        if not block.isValid():
            return

        cursor = QTextCursor(document)
        cursor.setPosition(block.position() + start)
        cursor.setPosition(block.position() + end, QTextCursor.MoveMode.KeepAnchor)
        self.log_display.setTextCursor(cursor)
        self.log_display.ensureCursorVisible()

    def _apply_search_highlight(self, current_row: int) -> None:
        """Highlight all matches in the text editor using extra selections."""
        if not self._search_match_spans:
            self.log_display.setExtraSelections([])
            return

        document = self.log_display.document()
        selections: List[QTextEdit.ExtraSelection] = []

        for row, start, end in self._search_match_spans:
            block = document.findBlockByNumber(row)
            if not block.isValid():
                continue
            sel = QTextEdit.ExtraSelection()
            sel_cursor = QTextCursor(document)
            sel_cursor.setPosition(block.position() + start)
            sel_cursor.setPosition(
                block.position() + end,
                QTextCursor.MoveMode.KeepAnchor,
            )
            sel.cursor = sel_cursor
            sel.format.setBackground(
                QColor(_LogListItemDelegate.HIGHLIGHT_BG)
                if row != current_row
                else QColor(_LogListItemDelegate.HIGHLIGHT_CURRENT_BG)
            )
            sel.format.setForeground(QColor(_LogListItemDelegate.HIGHLIGHT_TEXT))
            selections.append(sel)

        self.log_display.setExtraSelections(selections)

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
        if not hasattr(self, "_search_bar") or not self._search_bar:
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
            hasattr(self, "log_display")
            and watched is self.log_display
            and event.type() == QEvent.Type.Resize
        ):
            self._position_search_bar()

        return super().eventFilter(watched, event)

    def _clear_search_highlight(self) -> None:
        """Clear search pattern and refresh view."""
        self._search_debounce_timer.stop()
        self._search_scan_inflight = False
        self._search_scan_pending = False
        if self._search_task_handle is not None:
            try:
                self._search_task_handle.cancel()
            except Exception:
                pass
            self._search_task_handle = None
        self._search_pattern = None
        self._search_match_rows = []
        self._search_match_spans = []
        self._search_match_spans_by_row = {}
        self._current_match_index = -1
        self._apply_search_highlight(-1)
        if hasattr(self, "_search_bar") and self._search_bar:
            self._search_bar.update_match_count(0, 0)

    # ─────────────────────────────────────────────────────────────────────────

    def closeEvent(self, event: QCloseEvent) -> None:  # type: ignore[override]
        """Ensure the logcat process and device watcher are cleaned up."""
        self._save_viewer_settings()

        if self.logcat_process:
            self.stop_logcat()
        self._search_debounce_timer.stop()
        self._search_scan_inflight = False
        self._search_scan_pending = False
        if self._search_task_handle is not None:
            try:
                self._search_task_handle.cancel()
            except Exception:
                pass
            self._search_task_handle = None
        if self._filter_rebuild_handle is not None:
            try:
                self._filter_rebuild_handle.cancel()
            except Exception:
                pass
            self._filter_rebuild_handle = None

        if self._stream_thread is not None:
            self._stream_reset.emit()
            self._stream_thread.quit()
            self._stream_thread.wait(1500)
            self._stream_thread = None
            self._stream_worker = None

        # Cleanup device watcher to prevent memory leaks
        if self._device_watcher:
            self._device_watcher.cleanup()
            self._device_watcher = None

        # Cleanup preview panel (scrcpy and recording)
        if hasattr(self, "_preview_panel") and self._preview_panel:
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

        QMessageBox.critical(self, "Logcat Error", message)
