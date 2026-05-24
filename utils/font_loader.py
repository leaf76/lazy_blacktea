"""Application font setup.

Phase 1 of the redesign establishes the font stack contract without bundling
font files (those land in Phase 2 alongside the new shell). At startup the
loader:

1. Scans ``assets/fonts/`` for any TTF/OTF files and registers them with
   ``QFontDatabase`` so bundled fonts (Inter, JetBrains Mono) work without
   installing system-wide.
2. Resolves the preferred UI font, falling back through the system stack
   declared in ``ui.design_tokens``.
3. Applies the resolved font to ``QApplication`` so widgets inherit it.

The module is **idempotent**: ``configure_application_fonts`` may be called
multiple times safely (e.g. tests, live theme changes).
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable, List, Optional, Sequence, Tuple

from PyQt6.QtGui import QFont, QFontDatabase

from ui.design_tokens import (
    FONT_SIZE_PX,
    FONT_STACK_MONO,
    FONT_STACK_UI,
    FONT_WEIGHT,
)
from utils import common

logger = common.get_logger("font_loader")


PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent
DEFAULT_FONT_DIR: Path = PROJECT_ROOT / "assets" / "fonts"

_FONT_EXTENSIONS: Tuple[str, ...] = (".ttf", ".otf")

# Module-level cache so repeat calls are no-ops.
_LOADED_FONT_FAMILIES: List[str] = []
_CONFIGURED: bool = False


def _split_stack(stack: str) -> List[str]:
    """Split a CSS-style font-stack string into individual family names."""

    families: List[str] = []
    for raw in stack.split(","):
        family = raw.strip().strip("'\"")
        if family:
            families.append(family)
    return families


def _first_available(families: Sequence[str]) -> Optional[str]:
    available = set(QFontDatabase.families())
    for family in families:
        if family in available:
            return family
    return None


def register_bundled_fonts(font_dir: Optional[Path] = None) -> List[str]:
    """Register every TTF/OTF in ``font_dir`` with ``QFontDatabase``.

    Returns a list of unique family names that were successfully registered.
    Missing directory or empty directory is **not** an error.
    """

    target = font_dir or DEFAULT_FONT_DIR
    if not target.exists():
        return []

    registered: List[str] = []
    for path in sorted(target.iterdir()):
        if not path.is_file() or path.suffix.lower() not in _FONT_EXTENSIONS:
            continue
        font_id = QFontDatabase.addApplicationFont(str(path))
        if font_id < 0:
            logger.warning("Failed to register font: %s", path)
            continue
        for family in QFontDatabase.applicationFontFamilies(font_id):
            if family not in registered:
                registered.append(family)
    return registered


def resolve_ui_family(stack: str = FONT_STACK_UI) -> Optional[str]:
    """Return the first installed family from the UI stack, or ``None``."""

    return _first_available(_split_stack(stack))


def resolve_mono_family(stack: str = FONT_STACK_MONO) -> Optional[str]:
    """Return the first installed family from the mono stack, or ``None``."""

    return _first_available(_split_stack(stack))


def configure_application_fonts(app, *, font_dir: Optional[Path] = None) -> dict:
    """Register bundled fonts and apply the UI font to a ``QApplication``.

    Args:
        app: Active ``QApplication`` (or any object exposing
            ``setFont``).
        font_dir: Optional override for the bundled fonts directory.

    Returns:
        Dict with ``ui_family`` / ``mono_family`` actually selected, plus
        the registered families list (for diagnostics / logging).
    """

    global _CONFIGURED, _LOADED_FONT_FAMILIES

    if not _CONFIGURED:
        _LOADED_FONT_FAMILIES = register_bundled_fonts(font_dir)
        _CONFIGURED = True

    ui_family = resolve_ui_family() or QFont().defaultFamily()
    mono_family = resolve_mono_family() or "monospace"

    base = QFont(ui_family)
    base.setPixelSize(FONT_SIZE_PX["text_md"])
    base.setWeight(QFont.Weight(FONT_WEIGHT["weight_regular"]))
    try:
        app.setFont(base)
    except AttributeError:
        # Caller passed something that is not a QApplication; ignore.
        logger.debug("font_loader: object %r has no setFont; skipping", app)

    return {
        "ui_family": ui_family,
        "mono_family": mono_family,
        "registered_families": list(_LOADED_FONT_FAMILIES),
    }


def reset_for_testing() -> None:
    """Reset module-level state so tests can re-run configuration."""

    global _CONFIGURED, _LOADED_FONT_FAMILIES
    _CONFIGURED = False
    _LOADED_FONT_FAMILIES = []


__all__ = [
    "DEFAULT_FONT_DIR",
    "configure_application_fonts",
    "register_bundled_fonts",
    "reset_for_testing",
    "resolve_mono_family",
    "resolve_ui_family",
]
