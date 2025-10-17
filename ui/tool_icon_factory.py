"""Shared helpers for generating tile-style icons used across ADB tools."""

from __future__ import annotations

from typing import Dict, Tuple

from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QColor, QFont, QIcon, QPainter, QPixmap


_ICON_CACHE: Dict[Tuple[str, str, bool, int], QIcon] = {}

_PALETTE_OVERRIDES: Dict[str, Dict[str, str]] = {
    'bug_report': {'background': '#fee2e2', 'foreground': '#b91c1c'},
    'reboot': {'background': '#dbeafe', 'foreground': '#1d4ed8'},
    'recovery': {'background': '#ede9fe', 'foreground': '#5b21b6'},
    'bootloader': {'background': '#fae8ff', 'foreground': '#a21caf'},
    'restart': {'background': '#fef3c7', 'foreground': '#b45309'},
    'install_apk': {'background': '#dcfce7', 'foreground': '#047857'},
    'bt_on': {'background': '#e0f2fe', 'foreground': '#0369a1'},
    'bt_off': {'background': '#f1f5f9', 'foreground': '#475569'},
    'wifi_on': {'background': '#cffafe', 'foreground': '#0e7490'},
    'wifi_off': {'background': '#e2e8f0', 'foreground': '#334155'},
    'scrcpy': {'background': '#ede9fe', 'foreground': '#6d28d9'},
    'screenshot': {'background': '#eef2ff', 'foreground': '#3730a3'},
    'record_start': {'background': '#fee2e2', 'foreground': '#b91c1c'},
    'record_stop': {'background': '#f1f5f9', 'foreground': '#1f2937'},
    'device_info': {'background': '#e0f2f1', 'foreground': '#00695c'},
    'home': {'background': '#fef9c3', 'foreground': '#b45309'},
    'inspector': {'background': '#f3e8ff', 'foreground': '#7c3aed'},
}

_PRIMARY_DEFAULT = {'background': '#e0e7ff', 'foreground': '#312e81'}
_NEUTRAL_DEFAULT = {'background': '#f1f5f9', 'foreground': '#1f2937'}


def _extract_monogram(label: str) -> str:
    tokens = [token for token in label.split() if token]
    if not tokens:
        return '??'
    if len(tokens) == 1:
        cleaned = ''.join(ch for ch in tokens[0] if ch.isalnum())
        return cleaned[:2].upper() or tokens[0][:2].upper()
    return (tokens[0][0] + tokens[1][0]).upper()


def _resolve_palette(icon_key: str, primary: bool) -> Dict[str, str]:
    if primary:
        return dict(_PRIMARY_DEFAULT)
    palette = _PALETTE_OVERRIDES.get(icon_key)
    if palette is not None:
        return dict(palette)
    return dict(_NEUTRAL_DEFAULT)


def get_tile_tool_icon(icon_key: str, label: str, *, primary: bool = False, size: int = 64) -> QIcon:
    """Return a cached tile-style icon for the given tool."""
    cache_key = (icon_key, label, primary, size)
    cached = _ICON_CACHE.get(cache_key)
    if cached is not None:
        return cached

    palette = _resolve_palette(icon_key, primary)
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(palette['background']))
    painter.drawRoundedRect(pixmap.rect().adjusted(4, 4, -4, -4), 16, 16)

    monogram = _extract_monogram(label)
    font = QFont()
    font.setBold(True)
    font.setPointSize(18)
    painter.setFont(font)
    painter.setPen(QColor(palette['foreground']))
    painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, monogram)
    painter.end()

    icon = QIcon(pixmap)
    _ICON_CACHE[cache_key] = icon
    return icon


__all__ = ['get_tile_tool_icon']
