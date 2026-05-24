"""Chip-based application status bar.

Replaces the ad-hoc Qt ``QStatusBar`` usage with a flexible widget that
displays small interactive chips (devices, tasks, trace_id, version, …).
Each chip is identified by a stable ``name`` so callers can update or
remove it without recreating the bar.

Behavioural notes
-----------------
* The bar exposes a ``chip_clicked(str)`` signal that emits the chip name
  when clicked. Callers wire this to navigation / clipboard / log actions.
* Each chip can carry an *intent* (``info``, ``success``, ``warning``,
  ``danger``) that adjusts color via design tokens. Default is ``info``.
* The bar is intentionally lightweight: no animations, no per-chip
  layouts, no theming surprises. All visuals come from
  :mod:`ui.design_tokens`.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Callable, Dict, List, Optional

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QCursor
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QToolButton,
    QWidget,
)

from ui.design_tokens import get_palette


class StatusChipIntent(str, Enum):
    """Semantic intent for chip color (mapped to accent tokens)."""

    INFO = "info"
    SUCCESS = "success"
    WARNING = "warning"
    DANGER = "danger"
    NEUTRAL = "neutral"


_INTENT_TO_TOKEN: Dict[StatusChipIntent, str] = {
    StatusChipIntent.INFO: "accent_info",
    StatusChipIntent.SUCCESS: "accent_success",
    StatusChipIntent.WARNING: "accent_warning",
    StatusChipIntent.DANGER: "accent_danger",
    StatusChipIntent.NEUTRAL: "fg_secondary",
}


@dataclass
class _Chip:
    name: str
    button: QToolButton
    intent: StatusChipIntent
    on_click: Optional[Callable[[], None]]


class AppStatusBar(QWidget):
    """Bottom status bar composed of named chips.

    Signals:
        chip_clicked(str): emitted when any chip is left-clicked.
    """

    chip_clicked = pyqtSignal(str)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("appStatusBar")
        self._chips: Dict[str, _Chip] = {}
        self._theme: str = "light"

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 4, 12, 4)
        layout.setSpacing(0)
        layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        # Two flow containers so callers can place chips on the left or right.
        self._left_frame, self._left_layout = self._make_flow()
        self._right_frame, self._right_layout = self._make_flow()
        layout.addWidget(self._left_frame, stretch=1)
        layout.addWidget(self._right_frame, stretch=0)

        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setFixedHeight(28)
        self._apply_palette()

    # ------------------------------------------------------------------ API
    def add_chip(
        self,
        name: str,
        label: str,
        *,
        intent: StatusChipIntent = StatusChipIntent.INFO,
        tooltip: Optional[str] = None,
        on_click: Optional[Callable[[], None]] = None,
        align: str = "left",
    ) -> None:
        """Add or replace a chip identified by ``name``."""

        if name in self._chips:
            self.remove_chip(name)

        button = QToolButton(self)
        button.setObjectName(f"statusChip_{name}")
        button.setAutoRaise(True)
        button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        if tooltip:
            button.setToolTip(tooltip)
        button.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
        button.setProperty("statusChipName", name)
        button.setProperty("statusChipIntent", intent.value)
        button.setProperty("statusChipLabel", label)
        self._style_button(button, intent)

        button.clicked.connect(lambda _checked=False, key=name: self._on_chip_clicked(key))

        target_layout = self._right_layout if align == "right" else self._left_layout
        # Insert before the trailing stretch so chips stay packed to the start.
        target_layout.insertWidget(target_layout.count() - 1, button)

        self._chips[name] = _Chip(name=name, button=button, intent=intent, on_click=on_click)

    def update_chip(
        self,
        name: str,
        label: Optional[str] = None,
        *,
        intent: Optional[StatusChipIntent] = None,
        tooltip: Optional[str] = None,
    ) -> bool:
        """Update an existing chip. Returns ``False`` if it doesn't exist."""

        chip = self._chips.get(name)
        if chip is None:
            return False
        if label is not None:
            chip.button.setProperty("statusChipLabel", label)
        if tooltip is not None:
            chip.button.setToolTip(tooltip)
        if intent is not None:
            chip.intent = intent
            chip.button.setProperty("statusChipIntent", intent.value)
        # Always re-render: the label / intent change requires re-styling so
        # the bullet glyph stays in sync with the new label.
        self._style_button(chip.button, chip.intent)
        return True

    def remove_chip(self, name: str) -> bool:
        """Remove a chip; returns ``False`` if it doesn't exist."""

        chip = self._chips.pop(name, None)
        if chip is None:
            return False
        chip.button.deleteLater()
        return True

    def chip_names(self) -> List[str]:
        return list(self._chips.keys())

    def has_chip(self, name: str) -> bool:
        return name in self._chips

    def set_theme(self, theme: str) -> None:
        """Re-style all chips for a theme switch."""

        self._theme = theme if theme in ("light", "dark") else "light"
        self._apply_palette()
        for chip in self._chips.values():
            self._style_button(chip.button, chip.intent)

    # --------------------------------------------------------------- helpers
    def _make_flow(self):
        frame = QFrame(self)
        frame.setObjectName("statusFlow")
        frame.setFrameShape(QFrame.Shape.NoFrame)
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        layout.addStretch(1)
        return frame, layout

    def _on_chip_clicked(self, name: str) -> None:
        chip = self._chips.get(name)
        if chip is None:
            return
        try:
            if chip.on_click is not None:
                chip.on_click()
        finally:
            self.chip_clicked.emit(name)

    def _apply_palette(self) -> None:
        palette = get_palette(self._theme)
        self.setStyleSheet(
            f"#appStatusBar {{"
            f" background-color: {palette['bg_surface_alt']};"
            f" border-top: 1px solid {palette['border_subtle']};"
            f" }}"
            f" QFrame#statusFlow {{ background: transparent; }}"
        )

    def _style_button(self, button: QToolButton, intent: StatusChipIntent) -> None:
        """Apply token-driven styling to a chip button.

        Layout: ``● label`` where the bullet is colored by the intent and
        the label takes the chip text color. ``QToolButton`` doesn't render
        rich text reliably across platforms, so we ship plain text with a
        single accent color and rely on the bullet character to convey
        intent — readable in both light and dark themes.
        """

        palette = get_palette(self._theme)
        accent_token = _INTENT_TO_TOKEN[intent]
        accent = palette.get(accent_token, palette["fg_secondary"])
        hover_bg = palette["bg_hover"]
        active_bg = palette["bg_active"]
        label = button.property("statusChipLabel") or ""
        bullet_glyph = "\u25CF"  # ●
        button.setText(f"{bullet_glyph}  {label}".strip())
        button.setStyleSheet(
            "QToolButton {"
            f" color: {accent};"
            " padding: 2px 10px;"
            " border-radius: 9999px;"
            " border: 1px solid transparent;"
            " font-size: 11px;"
            " font-weight: 500;"
            "}"
            f"QToolButton:hover {{ background-color: {hover_bg}; }}"
            f"QToolButton:pressed {{ background-color: {active_bg}; }}"
        )


__all__ = ["AppStatusBar", "StatusChipIntent"]
