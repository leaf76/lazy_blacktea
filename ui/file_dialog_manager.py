"""Wrapper around QFileDialog invocations for better testability."""

from __future__ import annotations

from typing import Callable, Optional

from PyQt6.QtWidgets import QFileDialog

DialogFn = Callable[[object, str], str]


class FileDialogManager:
    """Provide higher-level helpers around QFileDialog."""

    def __init__(self, dialog_fn: Optional[DialogFn] = None) -> None:
        self._dialog_fn = dialog_fn or QFileDialog.getExistingDirectory

    def select_directory(self, parent, title: str) -> Optional[str]:
        result = self._dialog_fn(parent, title)
        return result or None


__all__ = ["FileDialogManager"]
