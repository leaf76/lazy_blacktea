"""System-level helper functions for clipboard and file manager actions."""

from __future__ import annotations

import platform
import subprocess
from typing import Callable, Optional, TYPE_CHECKING

from utils import common

if TYPE_CHECKING:  # pragma: no cover
    from lazy_blacktea_pyqt import WindowMain


logger = common.get_logger("system_actions")

ClipboardProvider = Callable[[], object]
SubprocessRunner = Callable[[list, bool], None]
PlatformResolver = Callable[[], str]


class SystemActionsManager:
    """Encapsulate clipboard copy and folder opening actions."""

    def __init__(
        self,
        window: "WindowMain",
        clipboard_provider: Optional[ClipboardProvider] = None,
        subprocess_runner: Optional[SubprocessRunner] = None,
        platform_resolver: Optional[PlatformResolver] = None,
    ) -> None:
        self.window = window
        self._clipboard_provider = clipboard_provider or self._default_clipboard
        self._subprocess_runner = subprocess_runner or self._default_run
        self._platform_resolver = platform_resolver or platform.system

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def copy_to_clipboard(self, text: str) -> None:
        """Copy the supplied text to the clipboard, reporting success or errors."""
        try:
            clipboard = self._clipboard_provider()
            clipboard.setText(text)
            self.window.show_info('📋 Copied!', f'Path copied to clipboard:\n{text}')
            logger.info('Copied to clipboard: %s', text)
        except Exception as error:  # pragma: no cover - defensive logging
            logger.error('Failed to copy to clipboard: %s', error)
            self.window.show_error('Error', f'Could not copy to clipboard:\n{error}')

    def open_folder(self, path: str) -> None:
        """Open the folder in the platform file manager."""
        command = self._build_open_command(path)
        try:
            self._subprocess_runner(command, check=False)
            logger.info('Opened folder via command: %s', command)
        except Exception as error:  # pragma: no cover - defensive logging
            logger.error('Failed to open folder: %s', error)
            self.window.show_error('Error', f'Could not open folder:\n{path}\n\nError: {error}')

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _build_open_command(self, path: str) -> list:
        system = self._platform_resolver()
        if system == 'Darwin':
            return ['open', path]
        if system == 'Windows':
            return ['explorer', path]
        return ['xdg-open', path]

    @staticmethod
    def _default_clipboard():
        from PyQt6.QtGui import QGuiApplication  # lazy import to avoid GUI deps in tests

        return QGuiApplication.clipboard()

    @staticmethod
    def _default_run(cmd: list, check: bool = False) -> None:
        subprocess.run(cmd)


__all__ = ["SystemActionsManager"]
