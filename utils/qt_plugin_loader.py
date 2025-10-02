"""Helpers for configuring Qt plugin search paths at runtime."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Iterable


def _candidate_plugin_roots(base_path: Path) -> Iterable[Path]:
    """Yield plausible plugin directories relative to the runtime base path."""
    internal_plugins = base_path / '_internal' / 'PyQt6' / 'Qt6' / 'plugins'
    if internal_plugins.exists():
        yield internal_plugins

    bundled_plugins = base_path / 'PyQt6' / 'Qt6' / 'plugins'
    if bundled_plugins.exists():
        yield bundled_plugins


def _resolve_plugin_directory() -> Path | None:
    """Return the first existing Qt plugin directory suited for the runtime."""
    frozen_base = getattr(sys, '_MEIPASS', None)
    if frozen_base:
        base_path = Path(frozen_base)
    else:
        base_path = Path(__file__).resolve().parents[1]

    for candidate in _candidate_plugin_roots(base_path):
        if candidate.exists():
            return candidate
    return None


def configure_qt_plugin_path() -> None:
    """Ensure Qt loads plugins from the bundled runtime when available."""
    plugin_dir = _resolve_plugin_directory()
    if plugin_dir is None:
        return

    os.environ.setdefault('QT_PLUGIN_PATH', str(plugin_dir))

    platforms_dir = plugin_dir / 'platforms'
    if platforms_dir.exists():
        os.environ.setdefault('QT_QPA_PLATFORM_PLUGIN_PATH', str(platforms_dir))


__all__ = ['configure_qt_plugin_path']
