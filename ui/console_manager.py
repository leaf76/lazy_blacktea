"""Utilities for managing console UI interactions in the main window."""

from __future__ import annotations

import platform
from typing import Callable, Optional, TYPE_CHECKING

from PyQt6.QtCore import Qt, QPoint
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QApplication,
    QGroupBox,
    QMenu,
    QSizePolicy,
    QTextEdit,
    QVBoxLayout,
)

from utils import common
from ui.style_manager import StyleManager

if TYPE_CHECKING:  # pragma: no cover
    from lazy_blacktea_pyqt import WindowMain


logger = common.get_logger("console_manager")

ClipboardProvider = Callable[[], object]
MenuFactory = Callable[[object], QMenu]


class ConsoleManager:
    """Encapsulate console widget creation and user interactions."""

    def __init__(
        self,
        window: "WindowMain",
        clipboard_provider: Optional[ClipboardProvider] = None,
        menu_factory: Optional[MenuFactory] = None,
    ) -> None:
        self.window = window
        self._clipboard_provider = clipboard_provider
        self._menu_factory = menu_factory

    # ------------------------------------------------------------------
    # Console widget lifecycle
    # ------------------------------------------------------------------
    def create_console_panel(self, parent_layout) -> None:
        console_group = QGroupBox("Console Output")
        console_layout = QVBoxLayout(console_group)
        console_layout.setContentsMargins(16, 20, 16, 20)
        console_layout.setSpacing(12)

        console_text = QTextEdit()
        console_text.setReadOnly(True)
        console_font = QFont()
        console_font.setFamily(
            "Monaco"
            if platform.system() == "Darwin"
            else "Consolas"
            if platform.system() == "Windows"
            else "monospace"
        )
        console_font.setPointSize(9)
        console_text.setFont(console_font)
        console_text.setMinimumHeight(150)
        console_text.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        console_text.setStyleSheet(StyleManager.get_console_style())

        welcome_msg = """🍵 Console Output Ready - Logging initialized

"""
        console_text.setPlainText(welcome_msg)
        logger.info("Console widget initialized and ready")
        self.window.console_text = console_text
        self.window.console_panel = console_group
        self.window.write_to_console("✅ Console output system ready")

        console_text.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        console_text.customContextMenuRequested.connect(
            self.window.show_console_context_menu
        )

        console_layout.addWidget(console_text)
        self.window.logging_manager.initialize_logging(console_text)
        parent_layout.addWidget(console_group)

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------
    def create_console_context_menu(self) -> QMenu:
        menu = self._get_menu(self.window)
        copy_action = menu.addAction("Copy")
        copy_action.triggered.connect(self.window.copy_console_text)
        clear_action = menu.addAction("Clear Console")
        clear_action.triggered.connect(self.window.clear_console)
        return menu

    def show_console_context_menu(self, position: QPoint) -> None:
        menu = self.create_console_context_menu()
        global_pos = self.window.console_text.mapToGlobal(position)
        menu.exec(global_pos)

    def copy_console_text(self) -> None:
        cursor = self.window.console_text.textCursor()
        clipboard = self._clipboard()
        if cursor.hasSelection():
            text = cursor.selectedText()
            clipboard.setText(text)
            logger.info("Copied selected console text to clipboard")
        else:
            text = self.window.console_text.toPlainText()
            clipboard.setText(text)
            logger.info("Copied all console text to clipboard")

    def clear_console(self) -> None:
        if hasattr(self.window.console_text, "clear"):
            self.window.console_text.clear()
        else:  # pragma: no cover - fallback for injected dummies
            self.window.console_text.setPlainText("")
        logger.info("Console cleared")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _clipboard(self):
        provider = self._clipboard_provider or QApplication.clipboard
        return provider()

    def _get_menu(self, parent) -> QMenu:
        if self._menu_factory is None:
            return QMenu(parent)
        return self._menu_factory(parent)


__all__ = ["ConsoleManager"]
