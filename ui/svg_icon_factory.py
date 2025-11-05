"""SVG Icon Factory - Professional icon generation system for ADB tools."""

from __future__ import annotations

from typing import Dict, Optional
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QColor, QIcon, QPainter, QPixmap
from PyQt6.QtSvg import QSvgRenderer


# SVG icon definitions for each tool
_SVG_ICONS: Dict[str, str] = {
    'bug_report': '''<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
        <path d="M20 8h-2.81c-.45-.78-1.07-1.45-1.82-1.96L17 4.41 15.59 3l-2.17 2.17C12.96 5.06 12.49 5 12 5s-.96.06-1.41.17L8.41 3 7 4.41l1.62 1.63C7.88 6.55 7.26 7.22 6.81 8H4v2h2.09c-.05.33-.09.66-.09 1v1H4v2h2v1c0 .34.04.67.09 1H4v2h2.81c1.04 1.79 2.97 3 5.19 3s4.15-1.21 5.19-3H20v-2h-2.09c.05-.33.09-.66.09-1v-1h2v-2h-2v-1c0-.34-.04-.67-.09-1H20V8zm-4 4v3c0 1.11-.89 2-2 2h-4c-1.11 0-2-.89-2-2v-3c0-1.11.89-2 2-2h4c1.11 0 2 .89 2 2z" fill="{color}"/>
        <circle cx="10" cy="13" r="1" fill="{color}"/>
        <circle cx="14" cy="13" r="1" fill="{color}"/>
    </svg>''',

    'reboot': '''<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
        <path d="M12 5V1L7 6l5 5V7c3.31 0 6 2.69 6 6s-2.69 6-6 6-6-2.69-6-6H4c0 4.42 3.58 8 8 8s8-3.58 8-8-3.58-8-8-8z" fill="{color}"/>
    </svg>''',

    'recovery': '''<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
        <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 15l-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9z" fill="{color}"/>
        <path d="M12 6v6l4 2" stroke="{color}" stroke-width="1.5" stroke-linecap="round"/>
    </svg>''',

    'bootloader': '''<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
        <rect x="4" y="4" width="16" height="16" rx="2" stroke="{color}" stroke-width="2" fill="none"/>
        <path d="M8 12l3 3 5-5" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
        <circle cx="12" cy="12" r="1.5" fill="{color}"/>
    </svg>''',

    'restart': '''<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
        <path d="M17.65 6.35C16.2 4.9 14.21 4 12 4c-4.42 0-7.99 3.58-7.99 8s3.57 8 7.99 8c3.73 0 6.84-2.55 7.73-6h-2.08c-.82 2.33-3.04 4-5.65 4-3.31 0-6-2.69-6-6s2.69-6 6-6c1.66 0 3.14.69 4.22 1.78L13 11h7V4l-2.35 2.35z" fill="{color}"/>
    </svg>''',

    'install_apk': '''<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
        <path d="M19 9h-4V3H9v6H5l7 7 7-7zM5 18v2h14v-2H5z" fill="{color}"/>
        <rect x="7" y="19" width="10" height="1" rx="0.5" fill="{color}"/>
    </svg>''',

    'bt_on': '''<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
        <path d="M17.71 7.71L12 2h-1v7.59L6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 11 14.41V22h1l5.71-5.71-4.3-4.29 4.3-4.29zM13 5.83l1.88 1.88L13 9.59V5.83zm1.88 10.46L13 18.17v-3.76l1.88 1.88z" fill="{color}"/>
    </svg>''',

    'bt_off': '''<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
        <path d="M13 5.83l1.88 1.88-1.6 1.6 1.41 1.41 3.02-3.02L12 2h-1v7.59l2 2V5.83zM5.41 4L4 5.41 10.59 12 5 17.59 6.41 19 11 14.41V22h1l4.29-4.29 2.3 2.29L20 18.59 5.41 4zM13 18.17v-3.76l1.88 1.88L13 18.17z" fill="{color}"/>
    </svg>''',

    'wifi_on': '''<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
        <path d="M1 9l2 2c4.97-4.97 13.03-4.97 18 0l2-2C16.93 2.93 7.08 2.93 1 9zm8 8l3 3 3-3c-1.65-1.66-4.34-1.66-6 0zm-4-4l2 2c2.76-2.76 7.24-2.76 10 0l2-2C15.14 9.14 8.87 9.14 5 13z" fill="{color}"/>
    </svg>''',

    'wifi_off': '''<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
        <path d="M21 11l2-2c-3.73-3.73-8.87-5.15-13.7-4.31l2.58 2.58c3.3-.02 6.61 1.22 9.12 3.73zm-2 2c-1.08-1.08-2.36-1.85-3.72-2.33l3.02 3.02.7-.69zM9 17l3 3 3-3c-1.65-1.66-4.34-1.66-6 0zM3.41 1.64L2 3.05 5.05 6.1C3.59 6.83 2.22 7.79 1 9l2 2c1.23-1.23 2.65-2.16 4.17-2.78l2.24 2.24C7.79 10.89 6.27 11.74 5 13l2 2c1.35-1.35 3.49-1.38 4.9-.09l5.66 5.66 1.41-1.41L3.41 1.64z" fill="{color}"/>
    </svg>''',

    'scrcpy': '''<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
        <rect x="6" y="3" width="12" height="18" rx="2" stroke="{color}" stroke-width="2" fill="none"/>
        <rect x="8" y="5" width="8" height="11" rx="1" fill="{color}" opacity="0.3"/>
        <circle cx="12" cy="18.5" r="1" fill="{color}"/>
        <path d="M10 8l4 3-4 3V8z" fill="{color}"/>
    </svg>''',

    'screenshot': '''<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
        <path d="M21 19V5c0-1.1-.9-2-2-2H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2zM8.5 13.5l2.5 3.01L14.5 12l4.5 6H5l3.5-4.5z" fill="{color}"/>
        <circle cx="9" cy="9" r="1.5" fill="{color}"/>
    </svg>''',

    'record_start': '''<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
        <circle cx="12" cy="12" r="9" stroke="{color}" stroke-width="2" fill="none"/>
        <circle cx="12" cy="12" r="5" fill="{color}"/>
    </svg>''',

    'record_stop': '''<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
        <circle cx="12" cy="12" r="9" stroke="{color}" stroke-width="2" fill="none"/>
        <rect x="8" y="8" width="8" height="8" rx="1" fill="{color}"/>
    </svg>''',

    'device_info': '''<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
        <rect x="7" y="2" width="10" height="20" rx="2" stroke="{color}" stroke-width="2" fill="none"/>
        <rect x="9" y="5" width="6" height="10" rx="1" fill="{color}" opacity="0.3"/>
        <circle cx="12" cy="18" r="1" fill="{color}"/>
    </svg>''',

    'home': '''<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
        <path d="M10 20v-6h4v6h5v-8h3L12 3 2 12h3v8h5z" fill="{color}"/>
    </svg>''',

    'inspector': '''<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
        <circle cx="11" cy="11" r="8" stroke="{color}" stroke-width="2" fill="none"/>
        <path d="M21 21l-4.35-4.35" stroke="{color}" stroke-width="2" stroke-linecap="round"/>
        <path d="M11 8v6M8 11h6" stroke="{color}" stroke-width="1.5" stroke-linecap="round"/>
    </svg>''',
}

# Color palettes for different tool types (enhanced with better contrast)
_COLOR_PALETTES: Dict[str, Dict[str, str]] = {
    'bug_report': {'light': '#dc2626', 'dark': '#f87171', 'bg_light': '#fef2f2', 'bg_dark': '#450a0a'},
    'reboot': {'light': '#1d4ed8', 'dark': '#60a5fa', 'bg_light': '#eff6ff', 'bg_dark': '#172554'},
    'recovery': {'light': '#7c3aed', 'dark': '#a78bfa', 'bg_light': '#f5f3ff', 'bg_dark': '#2e1065'},
    'bootloader': {'light': '#a21caf', 'dark': '#e879f9', 'bg_light': '#fdf4ff', 'bg_dark': '#4a044e'},
    'restart': {'light': '#d97706', 'dark': '#fbbf24', 'bg_light': '#fffbeb', 'bg_dark': '#451a03'},
    'install_apk': {'light': '#047857', 'dark': '#34d399', 'bg_light': '#f0fdf4', 'bg_dark': '#064e3b'},
    'bt_on': {'light': '#0369a1', 'dark': '#38bdf8', 'bg_light': '#f0f9ff', 'bg_dark': '#0c4a6e'},
    'bt_off': {'light': '#475569', 'dark': '#94a3b8', 'bg_light': '#f8fafc', 'bg_dark': '#1e293b'},
    'wifi_on': {'light': '#0e7490', 'dark': '#22d3ee', 'bg_light': '#ecfeff', 'bg_dark': '#164e63'},
    'wifi_off': {'light': '#475569', 'dark': '#94a3b8', 'bg_light': '#f8fafc', 'bg_dark': '#1e293b'},
    'scrcpy': {'light': '#6d28d9', 'dark': '#a78bfa', 'bg_light': '#f5f3ff', 'bg_dark': '#3b0764'},
    'screenshot': {'light': '#4338ca', 'dark': '#818cf8', 'bg_light': '#eef2ff', 'bg_dark': '#1e1b4b'},
    'record_start': {'light': '#dc2626', 'dark': '#f87171', 'bg_light': '#fef2f2', 'bg_dark': '#450a0a'},
    'record_stop': {'light': '#374151', 'dark': '#9ca3af', 'bg_light': '#f9fafb', 'bg_dark': '#1f2937'},
    'device_info': {'light': '#0d9488', 'dark': '#2dd4bf', 'bg_light': '#f0fdfa', 'bg_dark': '#134e4a'},
    'home': {'light': '#ca8a04', 'dark': '#facc15', 'bg_light': '#fefce8', 'bg_dark': '#422006'},
    'inspector': {'light': '#7c3aed', 'dark': '#a78bfa', 'bg_light': '#f5f3ff', 'bg_dark': '#2e1065'},
}

_DEFAULT_PALETTE = {
    'light': '#6b7280',
    'dark': '#9ca3af',
    'bg_light': '#f9fafb',
    'bg_dark': '#1f2937'
}

_PRIMARY_PALETTE = {
    'light': '#312e81',
    'dark': '#c7d2fe',
    'bg_light': '#e0e7ff',
    'bg_dark': '#1e1b4b'
}

_ICON_CACHE: Dict[tuple, QIcon] = {}


def _get_color_for_theme(icon_key: str, primary: bool, dark_mode: bool = False) -> tuple[str, str]:
    """Get foreground and background colors for an icon based on theme."""
    if primary:
        palette = _PRIMARY_PALETTE
    else:
        palette = _COLOR_PALETTES.get(icon_key, _DEFAULT_PALETTE)

    if dark_mode:
        fg_color = palette['dark']
        bg_color = palette['bg_dark']
    else:
        fg_color = palette['light']
        bg_color = palette['bg_light']

    return fg_color, bg_color


def _render_svg_icon(svg_content: str, color: str, size: int = 64) -> QPixmap:
    """Render SVG content to a QPixmap with the specified color."""
    # Replace color placeholder
    svg_data = svg_content.replace('{color}', color).encode('utf-8')

    # Render SVG
    renderer = QSvgRenderer(svg_data)
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    renderer.render(painter)
    painter.end()

    return pixmap


def get_svg_tool_icon(
    icon_key: str,
    label: str,
    *,
    primary: bool = False,
    size: int = 64,
    dark_mode: bool = False
) -> QIcon:
    """
    Get a professional SVG icon for the given tool.

    Args:
        icon_key: Key identifying the tool type
        label: Label text (used for fallback)
        primary: Whether this is a primary action button
        size: Icon size in pixels
        dark_mode: Whether to use dark mode colors

    Returns:
        QIcon object with the rendered SVG
    """
    cache_key = (icon_key, label, primary, size, dark_mode)
    cached = _ICON_CACHE.get(cache_key)
    if cached is not None:
        return cached

    # Get colors
    fg_color, bg_color = _get_color_for_theme(icon_key, primary, dark_mode)

    # Get SVG content
    svg_content = _SVG_ICONS.get(icon_key)

    if svg_content:
        # Render SVG on colored background
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.GlobalColor.transparent)

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Draw rounded background
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(bg_color))
        painter.drawRoundedRect(pixmap.rect().adjusted(2, 2, -2, -2), 16, 16)

        # Render SVG on top
        svg_pixmap = _render_svg_icon(svg_content, fg_color, size - 16)
        painter.drawPixmap(8, 8, svg_pixmap)
        painter.end()
    else:
        # Fallback to monogram if SVG not found
        from ui.tool_icon_factory import get_tile_tool_icon as get_fallback_icon
        return get_fallback_icon(icon_key, label, primary=primary, size=size)

    icon = QIcon(pixmap)
    _ICON_CACHE[cache_key] = icon
    return icon


def clear_icon_cache() -> None:
    """Clear the icon cache. Useful when switching themes."""
    _ICON_CACHE.clear()


__all__ = ['get_svg_tool_icon', 'clear_icon_cache']
