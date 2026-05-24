"""External QSS template loader.

Phase 1 of the redesign moves QSS templates out of ``ui.style_manager`` and
into ``ui/qss/<name>.qss`` files. Templates use ``{token_name}`` placeholders
that are resolved against the active theme palette returned by
``ui.design_tokens.get_palette``.

Why a tiny loader instead of Qt resources?
* Stays editable on disk for designers without a rebuild step.
* Plays well with the existing ``_render_css`` pipeline by speaking the same
  ``str.format_map`` placeholder convention.
* Caches parsed templates so we don't re-read files on every theme switch.

Public API
----------
* ``render(name, theme=None, *, extra=None)`` — render a stylesheet by name.
* ``available()`` — list bundled QSS template names (without extension).
* ``QSS_DIR`` — absolute path of the bundled ``ui/qss`` directory.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Iterable, List, Mapping, Optional

from ui.design_tokens import DEFAULT_THEME, get_palette

QSS_DIR: Path = Path(__file__).resolve().parent / "qss"


class QSSTemplateNotFound(FileNotFoundError):
    """Raised when a referenced QSS template file does not exist."""


def _safe_format(template: str, context: Mapping[str, str]) -> str:
    """Format a template tolerating literal ``{`` characters in CSS.

    QSS uses braces for selectors. We only substitute ``{name}`` where ``name``
    matches a Python identifier, leaving real braces alone. ``str.format_map``
    on a raw QSS string would explode on every selector ``{`` — so we run a
    pre-pass that escapes literal braces before substitution.
    """

    # Escape every brace, then re-introduce ``{name}`` placeholders for
    # known token names. This avoids touching CSS selector braces.
    escaped = template.replace("{", "{{").replace("}", "}}")
    for name in context:
        placeholder = "{{" + name + "}}"
        replacement = "{" + name + "}"
        escaped = escaped.replace(placeholder, replacement)
    return escaped.format_map({k: str(v) for k, v in context.items()})


@lru_cache(maxsize=32)
def _read_template(name: str) -> str:
    path = QSS_DIR / f"{name}.qss"
    if not path.exists():
        raise QSSTemplateNotFound(str(path))
    return path.read_text(encoding="utf-8")


def render(
    name: str,
    theme: Optional[str] = None,
    *,
    extra: Optional[Mapping[str, str]] = None,
) -> str:
    """Render a bundled QSS template against the resolved theme palette.

    Args:
        name: Template basename (without ``.qss``).
        theme: ``"light"`` / ``"dark"`` / ``None`` (defaults to light).
        extra: Optional override map merged on top of the theme palette.

    Returns:
        Rendered stylesheet text. Whitespace is preserved.
    """

    template = _read_template(name)
    context = dict(get_palette(theme or DEFAULT_THEME))
    if extra:
        context.update({k: str(v) for k, v in extra.items()})
    return _safe_format(template, context)


def available() -> List[str]:
    """Return a sorted list of bundled QSS templates (basename only)."""

    if not QSS_DIR.exists():
        return []
    return sorted(p.stem for p in QSS_DIR.glob("*.qss") if p.is_file())


def clear_cache() -> None:
    """Drop the in-memory template cache. Useful for tests and live reload."""

    _read_template.cache_clear()


def iter_templates(theme: Optional[str] = None) -> Iterable[str]:
    """Yield rendered stylesheets for every bundled template (debug helper)."""

    for name in available():
        yield render(name, theme)


__all__ = [
    "QSS_DIR",
    "QSSTemplateNotFound",
    "available",
    "clear_cache",
    "iter_templates",
    "render",
]
