"""Lucide-aligned SVG icon loader.

Phase 1 deliverable for the UI/UX redesign. Replaces inline emoji usage with
themable SVG icons stored in ``ui/icons/<name>.svg``.

Design
------
* SVGs ship as plain files so designers can drop in new icons without a
  rebuild.
* Each SVG uses ``currentColor`` for stroke/fill; the loader rewrites this
  token to a concrete color (token name or hex) before rasterising.
* ``QIcon`` results are cached per (name, color, size) to avoid re-parsing
  for repeat lookups.
* The loader is **best effort**: callers receive a null ``QIcon`` if the
  icon does not exist. It never raises in production paths.

Usage
-----
.. code-block:: python

    from ui.components.icon import load_icon
    btn.setIcon(load_icon("search", color="fg_secondary"))
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Optional

from PyQt6.QtCore import QByteArray, QSize, Qt
from PyQt6.QtGui import QIcon, QPixmap
from PyQt6.QtSvg import QSvgRenderer

from ui.design_tokens import DEFAULT_THEME, get_palette

ICON_DIR: Path = Path(__file__).resolve().parent.parent / "icons"

DEFAULT_SIZE: int = 16
DEFAULT_COLOR_TOKEN: str = "fg_primary"


def _resolve_color(color: Optional[str], theme: Optional[str]) -> str:
    """Resolve a token name or literal hex/rgba string into a concrete value.

    * ``None`` → default token (``fg_primary``) under the active theme.
    * Token name → looked up in the merged palette.
    * Anything else (e.g. ``"#FF0000"``, ``"rgb(...)"``) → returned as-is.
    """

    palette = get_palette(theme or DEFAULT_THEME)
    if color is None:
        return palette.get(DEFAULT_COLOR_TOKEN, "#000000")
    if color in palette:
        return palette[color]
    return color


def available() -> list[str]:
    """Return sorted list of bundled icon names (without extension)."""

    if not ICON_DIR.exists():
        return []
    return sorted(p.stem for p in ICON_DIR.glob("*.svg") if p.is_file())


def _read_svg_template(name: str) -> Optional[str]:
    path = ICON_DIR / f"{name}.svg"
    if not path.exists():
        return None
    return path.read_text(encoding="utf-8")


@lru_cache(maxsize=256)
def _render_pixmap(name: str, color: str, size: int) -> QPixmap:
    template = _read_svg_template(name)
    if template is None:
        return QPixmap()

    payload = template.replace("currentColor", color)
    renderer = QSvgRenderer(QByteArray(payload.encode("utf-8")))
    if not renderer.isValid():
        return QPixmap()

    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    from PyQt6.QtGui import QPainter

    painter = QPainter(pixmap)
    try:
        renderer.render(painter)
    finally:
        painter.end()
    return pixmap


def load_pixmap(
    name: str,
    *,
    color: Optional[str] = None,
    size: int = DEFAULT_SIZE,
    theme: Optional[str] = None,
) -> QPixmap:
    """Render an SVG to a ``QPixmap`` at the requested size and color."""

    resolved = _resolve_color(color, theme)
    return _render_pixmap(name, resolved, int(size))


def load_icon(
    name: str,
    *,
    color: Optional[str] = None,
    size: int = DEFAULT_SIZE,
    theme: Optional[str] = None,
) -> QIcon:
    """Return a ``QIcon`` for ``name``. Falls back to an empty icon when missing.

    Args:
        name: Icon basename (without ``.svg``).
        color: Token name (e.g. ``"fg_secondary"``) or literal CSS color.
        size: Pixel size for the rasterisation; the icon will scale further
              if Qt requests bigger sizes.
        theme: Override the default theme for color resolution.
    """

    pix = load_pixmap(name, color=color, size=size, theme=theme)
    icon = QIcon()
    if not pix.isNull():
        icon.addPixmap(pix, QIcon.Mode.Normal, QIcon.State.Off)
    return icon


def clear_cache() -> None:
    """Drop the in-memory pixmap cache. Used by tests and live reloads."""

    _render_pixmap.cache_clear()


__all__ = [
    "DEFAULT_COLOR_TOKEN",
    "DEFAULT_SIZE",
    "ICON_DIR",
    "available",
    "clear_cache",
    "load_icon",
    "load_pixmap",
]
