"""Centralised helpers for displaying Qt dialog messages."""

from __future__ import annotations

from typing import Callable, Optional, TYPE_CHECKING

from PyQt6.QtWidgets import QMessageBox

if TYPE_CHECKING:  # pragma: no cover
    from lazy_blacktea_pyqt import WindowMain


DialogCallable = Callable[["WindowMain", str, str], None]


class DialogManager:
    """Provide consistent wrappers around QMessageBox APIs."""

    def __init__(
        self,
        window: "WindowMain",
        info_fn: Optional[DialogCallable] = None,
        warning_fn: Optional[DialogCallable] = None,
        error_fn: Optional[DialogCallable] = None,
    ) -> None:
        self.window = window
        self._info_fn = info_fn or QMessageBox.information
        self._warning_fn = warning_fn or QMessageBox.warning
        self._error_fn = error_fn or QMessageBox.critical

    def show_info(self, title: str, message: str) -> None:
        self._info_fn(self.window, title, message)

    def show_warning(self, title: str, message: str) -> None:
        self._warning_fn(self.window, title, message)

    def show_error(self, title: str, message: str) -> None:
        self._error_fn(self.window, title, message)


__all__ = ["DialogManager"]
