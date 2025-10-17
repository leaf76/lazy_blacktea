#!/usr/bin/env python3
"""
Helper that manages a progress bar displayed directly below a button.

The indicator keeps users informed of long-running operations without
blocking the rest of the UI. It also stores the default button label and
tooltip so they can be restored when the operation completes.
"""

from __future__ import annotations

from typing import Optional

from PyQt6.QtCore import QObject, Qt
from PyQt6.QtWidgets import QAbstractButton, QProgressBar


class ButtonProgressOverlay(QObject):
    """Manage an inline progress indicator tied to a specific button."""

    def __init__(
        self,
        button: QAbstractButton | None,
        progress_bar: Optional[QProgressBar],
        *,
        cancellable: bool = True,
    ) -> None:
        super().__init__(button)
        self._button = button
        self._default_text = button.text() if button is not None else ''
        self._default_tooltip = button.toolTip() if button is not None else ''
        self._cancellable = cancellable
        self._active = False
        self._mode: str = "idle"
        self._progress_bar = progress_bar
        self._previous_enabled: Optional[bool] = None
        self._current_hint: str = ''

        if self._progress_bar is not None:
            self._progress_bar.setObjectName('tool_progress_bar')
            self._progress_bar.setTextVisible(False)
            self._progress_bar.setRange(0, 0)
            self._progress_bar.hide()
            self._progress_bar.setStyleSheet(
                """
                QProgressBar#tool_progress_bar {
                    border: 1px solid rgba(148, 163, 184, 0.35);
                    border-radius: 4px;
                    background-color: rgba(15, 23, 42, 0.6);
                    height: 10px;
                }
                QProgressBar#tool_progress_bar::chunk {
                    border-radius: 3px;
                    background-color: #60a5fa;
                }
                QProgressBar#tool_progress_bar[progressState="cancelling"]::chunk {
                    background-color: #fbbf24;
                }
                QProgressBar#tool_progress_bar[progressState="failed"]::chunk {
                    background-color: #f87171;
                }
                QProgressBar#tool_progress_bar[progressState="completed"]::chunk {
                    background-color: #34d399;
                }
                QProgressBar#tool_progress_bar[progressState="cancelled"]::chunk {
                    background-color: #9ca3af;
                }
                """
            )

    @property
    def is_active(self) -> bool:
        return self._active

    @property
    def is_cancellable(self) -> bool:
        return self._cancellable

    def set_cancellable(self, value: bool) -> None:
        self._cancellable = value

    def set_busy(self, message: str) -> None:
        """Show indeterminate progress."""
        self._activate(mode="busy")
        self._apply_tooltip(message)
        self._apply_button_hint('Working...')
        self._set_progress_range(0, 0)
        self._show_progress()

    def set_progress(self, current: int, total: int, message: str) -> None:
        """Update determinate progress."""
        self._activate(mode="progress")
        safe_total = max(1, int(total))
        clamped_value = max(0, min(int(current), safe_total))
        self._set_progress_range(0, safe_total)
        self._set_progress_value(clamped_value)
        self._apply_tooltip(message)
        self._apply_button_hint('Working...')
        self._show_progress()

    def set_cancelling(self, message: str) -> None:
        """Show cancelling state."""
        self._activate(mode="cancelling")
        self._apply_tooltip(message)
        self._apply_button_hint('Cancelling...')
        self._set_progress_range(0, 0)
        self._show_progress()

    def finish(self, message: Optional[str] = None) -> None:
        """Hide indicator after success."""
        self._set_progress_style('completed')
        self._restore_button(message or 'Operation completed')

    def fail(self, message: Optional[str] = None) -> None:
        """Hide indicator after failure while keeping tooltip feedback."""
        self._mode = 'failed'
        self._apply_tooltip(message or "Operation failed")
        self._set_progress_style('failed')
        self._set_progress_range(0, 1)
        self._set_progress_value(1)
        self._show_progress()
        self._apply_button_hint('Failed')
        self._active = False

    def reset(self) -> None:
        """Reset the overlay to its idle state."""
        self._restore_button()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _activate(self, *, mode: str) -> None:
        if self._button is not None and not self._active:
            self._set_button_property("progress-active", True)
            self._previous_enabled = self._button.isEnabled()
            self._button.setEnabled(False)
        if self._button is not None:
            self._set_button_property("progress-mode", mode)
        self._mode = mode
        self._active = True
        self._set_progress_style(mode)

    def _restore_button(self, tooltip: Optional[str] = None) -> None:
        self._deactivate()
        self._apply_button_hint(None)
        self._apply_tooltip(tooltip or self._default_tooltip)
        self._set_progress_style('idle')
        self._hide_progress()

    def _deactivate(self) -> None:
        if self._button is not None:
            self._set_button_property("progress-active", False)
            self._set_button_property("progress-mode", "idle")
            self._button.setText(self._default_text)
            if self._previous_enabled is None:
                self._button.setEnabled(True)
            else:
                self._button.setEnabled(self._previous_enabled)
            self._previous_enabled = None
        self._active = False
        self._mode = "idle"
        self._hide_progress()

    def _set_button_property(self, key: str, value) -> None:
        if self._button is None:
            return
        try:
            self._button.setProperty(key, value)
            style = self._button.style()
            if style is not None:
                style.unpolish(self._button)
                style.polish(self._button)
            self._button.update()
        except Exception:
            # Defensive: Ignore style propagation failures in headless tests.
            pass

    def _apply_tooltip(self, message: Optional[str]) -> None:
        if self._button is None:
            return
        tooltip = message or self._default_tooltip or 'Operation in progress. Please wait.'
        self._button.setToolTip(tooltip)
        self._button.setStatusTip(tooltip)
        self._button.setAccessibleDescription(tooltip)
        if self._progress_bar is not None:
            self._progress_bar.setToolTip(tooltip)

    def _apply_button_hint(self, hint: Optional[str]) -> None:
        if self._button is None:
            return
        if hint:
            if self._current_hint == hint:
                return
            self._button.setText(f'{self._default_text}\n{hint}')
            self._current_hint = hint
        else:
            if not self._current_hint:
                return
            self._button.setText(self._default_text)
            self._current_hint = ''

    def _set_progress_range(self, minimum: int, maximum: int) -> None:
        if self._progress_bar is None:
            return
        try:
            self._progress_bar.setRange(minimum, maximum)
        except Exception:
            pass

    def _set_progress_value(self, value: int) -> None:
        if self._progress_bar is None:
            return
        try:
            self._progress_bar.setValue(value)
        except Exception:
            pass

    def _show_progress(self) -> None:
        if self._progress_bar is None:
            return
        self._progress_bar.show()
        self._progress_bar.raise_()

    def _hide_progress(self) -> None:
        if self._progress_bar is None:
            return
        self._progress_bar.hide()

    def _set_progress_style(self, state: str) -> None:
        if self._progress_bar is None:
            return
        try:
            self._progress_bar.setProperty('progressState', state)
            style = self._progress_bar.style()
            if style is not None:
                style.unpolish(self._progress_bar)
                style.polish(self._progress_bar)
            self._progress_bar.update()
        except Exception:
            pass
