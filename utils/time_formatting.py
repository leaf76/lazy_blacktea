"""Reusable helpers for formatting and parsing time durations."""

from __future__ import annotations

from typing import Union

from utils import common

logger = common.get_logger("time_formatting")

Number = Union[int, float]


def format_seconds_to_clock(seconds: Number) -> str:
    """Return a zero-padded ``HH:MM:SS`` string for the given seconds value."""
    try:
        total_seconds = max(int(seconds), 0)
    except (TypeError, ValueError):  # pragma: no cover - defensive fallback
        logger.debug("Invalid seconds value for formatting: %r", seconds)
        total_seconds = 0

    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    secs = total_seconds % 60
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def parse_duration_to_seconds(duration_str: str) -> float:
    """Convert ``HH:MM:SS`` strings to seconds; return ``0.0`` for bad input."""
    if not duration_str:
        return 0.0

    try:
        parts = duration_str.split(":")
        if len(parts) == 3:
            hours, minutes, seconds = (int(part) for part in parts)
            return float(hours * 3600 + minutes * 60 + seconds)
    except (ValueError, TypeError):  # pragma: no cover - defensive parsing
        logger.debug("Unable to parse duration string: %s", duration_str)
    return 0.0


__all__ = ["format_seconds_to_clock", "parse_duration_to_seconds"]
