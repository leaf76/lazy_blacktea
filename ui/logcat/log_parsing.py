"""Pure, Qt-free logcat parsing/scanning helpers.

Extracted from ``ui/logcat_viewer.py`` (a 2700+ line god-file) so this logic is
unit-testable without a ``QApplication`` and the viewer module shrinks toward a
UI-only concern (audit finding #61). ``ui.logcat_viewer`` re-exports these names,
so existing ``from ui.logcat_viewer import LogLine`` imports keep working.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Optional, Tuple

from utils.task_dispatcher import TaskCancelledError, TaskHandle


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


__all__ = [
    "LogLine",
    "_split_logcat_chunk",
    "_filter_log_lines_snapshot",
    "_scan_search_spans",
]
