"""Design tokens — single source of truth for theme palettes.

Phase 1 deliverable for the UI/UX redesign (see ``docs/design/tokens.md``).

Design goals
------------
* Provide a **spec namespace** (e.g. ``bg_canvas``, ``accent_primary``) that
  matches ``docs/design/tokens.md`` so future widgets can use stable names.
* Preserve every legacy key currently consumed by ``ui/style_manager.py`` and
  the rest of the UI (e.g. ``primary``, ``text_primary``, ``tile_bg``).
  Phase 1 must produce **zero visual regression**; spec values that differ
  from today are deferred to Phase 3 when individual widgets migrate.
* Be technology-neutral: the same dict can be consumed by PyQt6 today and any
  future Rust / QML port.

Public API
----------
* ``LIGHT_TOKENS`` / ``DARK_TOKENS`` — spec namespace.
* ``LIGHT_LEGACY`` / ``DARK_LEGACY`` — legacy key namespace (current values).
* ``THEME_ALIASES`` — keeps ``"default"`` -> ``"light"`` working.
* ``get_palette(theme)`` — merged dict (legacy keys + spec keys), used by
  ``StyleManager._THEME_PRESETS`` to keep current callers happy.
* ``get_tokens(theme)`` — only the spec namespace; for new code.

The module is intentionally pure data; it must not import Qt so that tests can
import it under any platform without ``QApplication``.
"""

from __future__ import annotations

from typing import Dict, Mapping

# ---------------------------------------------------------------------------
# 1. Legacy palette (verbatim copy of the original ``_THEME_PRESETS``)
#
# Do not change a single value here without coordinated widget updates.
# Phase 3 / 4 may shift values widget-by-widget; until then these are the
# guaranteed-current colors that downstream tests rely on.
# ---------------------------------------------------------------------------

LIGHT_LEGACY: Dict[str, str] = {
    "primary": "#4CAF50",
    "primary_hover": "#45A049",
    "secondary": "#1976D2",
    "secondary_hover": "#1565C0",
    "warning": "#FF9800",
    "warning_hover": "#F57C00",
    "danger": "#F44336",
    "danger_hover": "#D32F2F",
    "neutral": "#757575",
    "neutral_hover": "#616161",
    "success": "#2E7D32",
    "success_background": "rgba(46, 125, 50, 0.1)",
    "error": "#C62828",
    "error_background": "rgba(198, 40, 40, 0.1)",
    "info": "#1976D2",
    "text_primary": "#212121",
    "text_secondary": "#424242",
    "text_hint": "#666666",
    "border": "#D7DCE6",
    "background": "#F3F4F6",
    "background_hover": "rgba(200, 220, 255, 0.45)",
    "panel_background": "#FFFFFF",
    "panel_border": "#D7DCE6",
    "tile_primary_bg": "#EEF2FF",
    "tile_primary_border": "#A5B4FC",
    "tile_primary_hover": "#E1E7FF",
    "tile_bg": "#F8FAFC",
    "tile_border": "#D0D7E2",
    "tile_hover": "#EEF2F7",
    "tile_text": "#1F2937",
    "tile_primary_text": "#111827",
    "status_text_on_dark": "#FFFFFF",
    "status_disabled_bg": "#EBEBEB",
    "status_disabled_text": "#9A9A9A",
    "status_disabled_border": "#D1D1D1",
    "tooltip_background": "rgba(45, 45, 45, 0.95)",
    "tooltip_text": "#FFFFFF",
    "tooltip_border": "rgba(255, 255, 255, 0.2)",
    "input_background": "#FFFFFF",
    "input_border": "#CCCCCC",
    "console_background": "#FFFFFF",
    "console_text": "#000000",
    "console_border": "#B0B8C2",
    "terminal_background": "#1a1a2e",
    "terminal_text": "#e0e0e0",
    "terminal_border": "#2a2a4a",
    "terminal_input_bg": "#16213e",
    "terminal_input_border": "#3a3a5a",
    "terminal_prompt": "#00d9ff",
    "terminal_success": "#00ff88",
    "terminal_error": "#ff6b6b",
    "terminal_device_header": "#7c3aed",
    "tile_processing_bg": "#444444",
    "tile_processing_border": "#2F2F2F",
    "tile_processing_hover": "#3A3A3A",
    "tile_ready_bg": "#111111",
    "tile_ready_border": "#000000",
    "tile_ready_hover": "#000000",
}

DARK_LEGACY: Dict[str, str] = {
    "primary": "#66BB6A",
    "primary_hover": "#57A65B",
    "secondary": "#64B5F6",
    "secondary_hover": "#4A9DE0",
    "warning": "#FFB74D",
    "warning_hover": "#FFA726",
    "danger": "#EF5350",
    "danger_hover": "#E53935",
    "neutral": "#9E9E9E",
    "neutral_hover": "#BDBDBD",
    "success": "#81C784",
    "success_background": "rgba(129, 199, 132, 0.15)",
    "error": "#E57373",
    "error_background": "rgba(229, 115, 115, 0.15)",
    "info": "#64B5F6",
    "text_primary": "#EAEAEA",
    "text_secondary": "#C8C8C8",
    "text_hint": "#9DA5B3",
    "border": "#3F4657",
    "background": "#1B1E26",
    "background_hover": "rgba(120, 160, 255, 0.25)",
    "panel_background": "#252A37",
    "panel_border": "#3E4455",
    "tile_primary_bg": "#333A56",
    "tile_primary_border": "#55608C",
    "tile_primary_hover": "#3F4566",
    "tile_bg": "#2E3449",
    "tile_border": "#454C63",
    "tile_hover": "#3A4159",
    "tile_text": "#E6EAF7",
    "tile_primary_text": "#F5F7FF",
    "status_text_on_dark": "#FFFFFF",
    "status_disabled_bg": "#2C3143",
    "status_disabled_text": "#8088A0",
    "status_disabled_border": "#3F465A",
    "tooltip_background": "rgba(240, 240, 240, 0.95)",
    "tooltip_text": "#111111",
    "tooltip_border": "rgba(0, 0, 0, 0.35)",
    "input_background": "#2D3142",
    "input_border": "#4A5168",
    "console_background": "#1C2030",
    "console_text": "#E0E6F3",
    "console_border": "#3A4052",
    "terminal_background": "#0d1117",
    "terminal_text": "#c9d1d9",
    "terminal_border": "#30363d",
    "terminal_input_bg": "#161b22",
    "terminal_input_border": "#30363d",
    "terminal_prompt": "#58a6ff",
    "terminal_success": "#3fb950",
    "terminal_error": "#f85149",
    "terminal_device_header": "#a371f7",
    "tile_processing_bg": "#5A6076",
    "tile_processing_border": "#707791",
    "tile_processing_hover": "#666D86",
    "tile_ready_bg": "#66BB6A",
    "tile_ready_border": "#4A9B4E",
    "tile_ready_hover": "#57A65B",
}


# ---------------------------------------------------------------------------
# 2. Spec namespace (Phase 1 = current values, mapped to spec names)
#
# These keys mirror ``docs/design/tokens.md``. Values that have a clear legacy
# counterpart reuse the legacy color so the rendered UI does not change. Keys
# that are new (``bg_active``, ``bg_scrim``, ``border_strong``, ``tint_*``)
# get conservative defaults that pass the WCAG contrast targets defined in
# ``docs/design/tokens.md§1.7``.
# ---------------------------------------------------------------------------

LIGHT_TOKENS: Dict[str, str] = {
    # Surfaces
    "bg_canvas": LIGHT_LEGACY["background"],
    "bg_surface": LIGHT_LEGACY["panel_background"],
    "bg_surface_alt": LIGHT_LEGACY["tile_bg"],
    "bg_elevated": LIGHT_LEGACY["panel_background"],
    "bg_hover": "rgba(15, 23, 42, 0.04)",
    "bg_active": "rgba(15, 23, 42, 0.08)",
    "bg_scrim": "rgba(15, 23, 42, 0.45)",

    # Borders
    "border_subtle": LIGHT_LEGACY["panel_border"],
    "border_default": LIGHT_LEGACY["border"],
    "border_strong": LIGHT_LEGACY["tile_border"],
    "border_focus": LIGHT_LEGACY["secondary"],

    # Foreground
    "fg_primary": LIGHT_LEGACY["text_primary"],
    "fg_secondary": LIGHT_LEGACY["text_secondary"],
    "fg_muted": LIGHT_LEGACY["text_hint"],
    "fg_inverse": LIGHT_LEGACY["status_text_on_dark"],
    "fg_link": LIGHT_LEGACY["secondary"],

    # Accents
    # Blue brand CTA per docs/design/tokens.md §1.4 (WCAG 6.0:1 target). The
    # legacy "primary" key stays green so existing legacy-styled buttons are
    # unaffected; only spec-token consumers adopt the blue (#28).
    "accent_primary": "#2D6CDF",
    "accent_primary_hover": "#245AC0",
    "accent_primary_press": "#1D4DA3",
    "accent_secondary": LIGHT_LEGACY["secondary"],
    "accent_secondary_hover": LIGHT_LEGACY["secondary_hover"],
    "accent_success": LIGHT_LEGACY["success"],
    "accent_warning": LIGHT_LEGACY["warning"],
    "accent_danger": LIGHT_LEGACY["danger"],
    "accent_info": LIGHT_LEGACY["info"],

    # Tints (12 % alpha overlays; mirror ``success_background`` / ``error_background``)
    "tint_primary": "rgba(45, 108, 223, 0.10)",
    "tint_success": LIGHT_LEGACY["success_background"],
    "tint_warning": "rgba(255, 152, 0, 0.10)",
    "tint_danger": LIGHT_LEGACY["error_background"],
    "tint_info": "rgba(25, 118, 210, 0.10)",
}

DARK_TOKENS: Dict[str, str] = {
    # Surfaces
    "bg_canvas": DARK_LEGACY["background"],
    "bg_surface": DARK_LEGACY["panel_background"],
    "bg_surface_alt": DARK_LEGACY["tile_bg"],
    "bg_elevated": DARK_LEGACY["tile_primary_bg"],
    "bg_hover": "rgba(255, 255, 255, 0.06)",
    "bg_active": "rgba(255, 255, 255, 0.10)",
    "bg_scrim": "rgba(0, 0, 0, 0.55)",

    # Borders
    "border_subtle": DARK_LEGACY["panel_border"],
    "border_default": DARK_LEGACY["border"],
    "border_strong": DARK_LEGACY["tile_border"],
    "border_focus": DARK_LEGACY["secondary"],

    # Foreground
    "fg_primary": DARK_LEGACY["text_primary"],
    "fg_secondary": DARK_LEGACY["text_secondary"],
    "fg_muted": DARK_LEGACY["text_hint"],
    "fg_inverse": DARK_LEGACY["background"],
    "fg_link": DARK_LEGACY["secondary"],

    # Accents (blue brand CTA per docs/design/tokens.md §1.4; see light note)
    "accent_primary": "#5B9DFF",
    "accent_primary_hover": "#7AB1FF",
    "accent_primary_press": "#3F86E8",
    "accent_secondary": DARK_LEGACY["secondary"],
    "accent_secondary_hover": DARK_LEGACY["secondary_hover"],
    "accent_success": DARK_LEGACY["success"],
    "accent_warning": DARK_LEGACY["warning"],
    "accent_danger": DARK_LEGACY["danger"],
    "accent_info": DARK_LEGACY["info"],

    # Tints
    "tint_primary": "rgba(91, 157, 255, 0.16)",
    "tint_success": DARK_LEGACY["success_background"],
    "tint_warning": "rgba(255, 183, 77, 0.18)",
    "tint_danger": DARK_LEGACY["error_background"],
    "tint_info": "rgba(100, 181, 246, 0.16)",
}


# ---------------------------------------------------------------------------
# 3. Spacing / radius / motion / typography
#
# Plain Python constants so widgets can read them without parsing strings.
# Density defaults to ``cozy``; ``compact`` and ``comfortable`` are exposed
# for Preferences (Phase 4).
# ---------------------------------------------------------------------------

SPACING: Dict[str, int] = {
    "space_0": 0,
    "space_1": 2,
    "space_2": 4,
    "space_3": 8,
    "space_4": 12,
    "space_5": 16,
    "space_6": 24,
    "space_7": 32,
    "space_8": 48,
}

RADIUS: Dict[str, int] = {
    "radius_none": 0,
    "radius_xs": 4,
    "radius_sm": 6,
    "radius_md": 8,
    "radius_lg": 12,
    "radius_full": 999,
}

MOTION_MS: Dict[str, int] = {
    "motion_instant": 0,
    "motion_fast": 80,
    "motion_normal": 160,
    "motion_slow": 240,
}

DENSITY_MULTIPLIER: Dict[str, float] = {
    "compact": 0.75,
    "cozy": 1.0,
    "comfortable": 1.25,
}

FONT_STACK_UI = "Inter, 'SF Pro Text', 'Segoe UI', 'Noto Sans TC', sans-serif"
FONT_STACK_MONO = (
    "'JetBrains Mono', 'SF Mono', 'Cascadia Mono', Consolas, monospace"
)

FONT_SIZE_PX: Dict[str, int] = {
    "text_xs": 11,
    "text_sm": 12,
    "text_md": 13,
    "text_lg": 14,
    "text_xl": 16,
    "text_2xl": 20,
    "text_3xl": 24,
}

FONT_WEIGHT: Dict[str, int] = {
    "weight_regular": 400,
    "weight_medium": 500,
    "weight_semibold": 600,
    "weight_bold": 700,
}


# ---------------------------------------------------------------------------
# 4. Theme aliases & accessors
# ---------------------------------------------------------------------------

THEME_ALIASES: Dict[str, str] = {"default": "light"}
SUPPORTED_THEMES: tuple = ("light", "dark")
DEFAULT_THEME: str = "light"


def _resolve_theme(theme: str | None) -> str:
    key = (theme or "").lower()
    key = THEME_ALIASES.get(key, key)
    if key not in SUPPORTED_THEMES:
        return DEFAULT_THEME
    return key


def get_legacy_palette(theme: str | None) -> Dict[str, str]:
    """Return the legacy-keys-only palette for a theme.

    Equivalent to the historic ``_THEME_PRESETS[theme]``.
    """

    resolved = _resolve_theme(theme)
    base = LIGHT_LEGACY if resolved == "light" else DARK_LEGACY
    return dict(base)


def get_tokens(theme: str | None) -> Dict[str, str]:
    """Return the spec-namespace-only token dict for a theme."""

    resolved = _resolve_theme(theme)
    base = LIGHT_TOKENS if resolved == "light" else DARK_TOKENS
    return dict(base)


def get_palette(theme: str | None) -> Dict[str, str]:
    """Return a merged palette: legacy keys first, then spec namespace.

    The merge order guarantees that legacy keys keep their historic values
    even when a future spec key shares the same logical color.
    """

    resolved = _resolve_theme(theme)
    legacy = get_legacy_palette(resolved)
    tokens = get_tokens(resolved)
    merged: Dict[str, str] = {}
    merged.update(legacy)
    merged.update(tokens)
    return merged


def get_typography() -> Mapping[str, object]:
    """Convenience accessor for typography scale + font stacks."""

    return {
        "font_ui": FONT_STACK_UI,
        "font_mono": FONT_STACK_MONO,
        "size_px": dict(FONT_SIZE_PX),
        "weight": dict(FONT_WEIGHT),
    }


__all__ = [
    "DARK_LEGACY",
    "DARK_TOKENS",
    "DEFAULT_THEME",
    "DENSITY_MULTIPLIER",
    "FONT_SIZE_PX",
    "FONT_STACK_MONO",
    "FONT_STACK_UI",
    "FONT_WEIGHT",
    "LIGHT_LEGACY",
    "LIGHT_TOKENS",
    "MOTION_MS",
    "RADIUS",
    "SPACING",
    "SUPPORTED_THEMES",
    "THEME_ALIASES",
    "get_legacy_palette",
    "get_palette",
    "get_tokens",
    "get_typography",
]
