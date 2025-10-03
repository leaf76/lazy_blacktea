"""Helpers for updating recording status indicators in the main window."""

from __future__ import annotations

import datetime
from typing import Iterable, Set, TYPE_CHECKING

from config.constants import PanelText
from ui.style_manager import StyleManager
from utils import time_formatting

if TYPE_CHECKING:  # pragma: no cover - imported only for typing
    from lazy_blacktea_pyqt import WindowMain


def update_recording_status_view(window: "WindowMain") -> None:
    """Refresh recording labels and timers for the given window instance."""
    if not hasattr(window, "recording_status_label"):
        return

    all_statuses = window.recording_manager.get_all_recording_statuses()
    active_records_text: list[str] = []
    now = datetime.datetime.now()
    handled_serials: Set[str] = set()

    for serial, record in window.device_recordings.items():
        if not record.get("active"):
            continue

        elapsed = record.get("elapsed_before_current", 0.0)
        ongoing_start = record.get("ongoing_start")
        if ongoing_start:
            elapsed += (now - ongoing_start).total_seconds()
        elif elapsed <= 0 and serial in all_statuses and "Recording" in all_statuses[serial]:
            duration_part = all_statuses[serial].split("(")[1].rstrip(")")
            elapsed = time_formatting.parse_duration_to_seconds(duration_part)

        seconds_int = _clamp_monotonic_elapsed(record, elapsed)
        device_model = _resolve_device_model(window, serial, record)
        active_records_text.append(
            f"{device_model} ({serial[:8]}...): {time_formatting.format_seconds_to_clock(seconds_int)}"
        )
        handled_serials.add(serial)

    _collect_untracked_records(window, all_statuses, handled_serials, active_records_text)
    _apply_status_labels(window, active_records_text)


def _clamp_monotonic_elapsed(record: dict, elapsed: float) -> int:
    seconds_int = max(int(elapsed), 0)
    last_display = record.get("display_seconds", 0)
    if seconds_int < last_display:
        seconds_int = last_display
    else:
        record["display_seconds"] = seconds_int
    return seconds_int


def _resolve_device_model(window: "WindowMain", serial: str, record: dict) -> str:
    if serial in window.device_dict:
        return window.device_dict[serial].device_model
    return record.get("device_name") or "Unknown"


def _collect_untracked_records(
    window: "WindowMain",
    all_statuses: dict,
    handled_serials: Iterable[str],
    active_records_text: list[str],
) -> None:
    for serial, status in all_statuses.items():
        if "Recording" not in status or serial in handled_serials:
            continue

        device_model = window.device_dict.get(serial, None)
        if device_model is not None:
            device_model = device_model.device_model
        else:
            device_model = "Unknown"

        duration_part = status.split("(")[1].rstrip(")")
        elapsed = time_formatting.parse_duration_to_seconds(duration_part)
        seconds_int = max(int(elapsed), 0)
        active_records_text.append(
            f"{device_model} ({serial[:8]}...): {time_formatting.format_seconds_to_clock(seconds_int)}"
        )


def _apply_status_labels(window: "WindowMain", active_records_text: list[str]) -> None:
    active_count = window.recording_manager.get_active_recordings_count()
    if active_count > 0:
        status_text = PanelText.LABEL_RECORDING_PREFIX.format(count=active_count)
        window.recording_status_label.setText(status_text)
        StyleManager.apply_status_style(window.recording_status_label, "recording_active")

        StyleManager.apply_status_style(window.recording_timer_label, "recording_active")

        if len(active_records_text) > 8:
            display_recordings = active_records_text[:8] + [
                f"... and {len(active_records_text) - 8} more device(s)"
            ]
        else:
            display_recordings = active_records_text

        window.recording_timer_label.setText("\n".join(display_recordings))
    else:
        window.recording_status_label.setText(PanelText.LABEL_NO_RECORDING)
        StyleManager.apply_status_style(window.recording_status_label, "recording_inactive")
        StyleManager.apply_status_style(window.recording_timer_label, "recording_inactive")
        window.recording_timer_label.setText("")


__all__ = ["update_recording_status_view"]
