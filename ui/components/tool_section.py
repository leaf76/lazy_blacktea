from __future__ import annotations

from typing import List, Optional, Tuple

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QGridLayout,
    QPushButton,
    QLabel,
)

from config.constants import PanelText
from ui.collapsible_panel import CollapsiblePanel
from ui.style_manager import StyleManager


ActionTuple = Tuple[str, str, str, str]


class ToolButton(QPushButton):
    def __init__(
        self,
        label: str,
        action_key: str,
        icon_key: str,
        emoji: str,
        *,
        hero: bool = False,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._label = label
        self._action_key = action_key
        self._icon_key = icon_key
        self._emoji = emoji
        self._hero = hero
        self._loading = False
        self._original_text = ""

        self._setup_ui()

    def _setup_ui(self) -> None:
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        if self._hero:
            self._original_text = f"{self._emoji}\n{self._label}"
            self.setText(self._original_text)
            self.setFixedSize(100, 72)
        else:
            self._original_text = f"{self._emoji} {self._label}"
            self.setText(self._original_text)
            self.setMinimumHeight(36)

        self._apply_style()

    def _apply_style(self) -> None:
        colors = StyleManager.COLORS
        bg = colors.get("tile_bg", "#2E3449")
        bg_hover = colors.get("tile_hover", "#3A4159")
        bg_pressed = colors.get("tile_pressed", "#2A2F3D")
        border = colors.get("tile_border", "#454C63")
        text = colors.get("text_primary", "#EAEAEA")

        if self._hero:
            self.setStyleSheet(f"""
                QPushButton {{
                    background-color: {bg};
                    border: 1px solid {border};
                    border-radius: 10px;
                    color: {text};
                    font-size: 12px;
                    font-weight: 500;
                    padding: 8px;
                }}
                QPushButton:hover {{
                    background-color: {bg_hover};
                    border-color: {colors.get("accent", "#5C9DFF")};
                }}
                QPushButton:pressed {{
                    background-color: {bg_pressed};
                }}
                QPushButton:disabled {{
                    background-color: {colors.get("disabled_bg", "#1E222B")};
                    color: {colors.get("text_disabled", "#666")};
                }}
            """)
        else:
            self.setStyleSheet(f"""
                QPushButton {{
                    background-color: {bg};
                    border: 1px solid {border};
                    border-radius: 6px;
                    color: {text};
                    font-size: 11px;
                    padding: 6px 12px;
                    text-align: left;
                }}
                QPushButton:hover {{
                    background-color: {bg_hover};
                }}
                QPushButton:pressed {{
                    background-color: {bg_pressed};
                }}
                QPushButton:disabled {{
                    background-color: {colors.get("disabled_bg", "#1E222B")};
                    color: {colors.get("text_disabled", "#666")};
                }}
            """)

    @property
    def action_key(self) -> str:
        return self._action_key

    def set_loading(self, loading: bool) -> None:
        self._loading = loading
        self.setEnabled(not loading)
        if loading:
            if self._hero:
                self.setText(f"⏳\n{PanelText.BUTTON_LOADING.split(' ', 1)[1]}")
            else:
                self.setText(PanelText.BUTTON_LOADING)
        else:
            self.setText(self._original_text)

    def is_loading(self) -> bool:
        return self._loading


class QuickActionsSection(QWidget):
    action_triggered = pyqtSignal(str)

    def __init__(
        self,
        actions: List[ActionTuple],
        *,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._actions = actions
        self._buttons: dict[str, ToolButton] = {}

        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        header = QLabel(PanelText.SECTION_QUICK_ACTIONS)
        header.setObjectName("section_header")
        self._apply_header_style(header)
        layout.addWidget(header)

        buttons_container = QWidget()
        grid = QGridLayout(buttons_container)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(12)

        for i, (label, action_key, icon_key, emoji) in enumerate(self._actions):
            btn = ToolButton(label, action_key, icon_key, emoji, hero=True)
            btn.clicked.connect(
                lambda checked, k=action_key: self.action_triggered.emit(k)
            )
            self._buttons[action_key] = btn
            row, col = divmod(i, 4)
            grid.addWidget(btn, row, col)

        layout.addWidget(buttons_container)

    def _apply_header_style(self, label: QLabel) -> None:
        colors = StyleManager.COLORS
        label.setStyleSheet(f"""
            QLabel#section_header {{
                color: {colors.get("text_primary", "#EAEAEA")};
                font-size: 13px;
                font-weight: 600;
                padding: 4px 0;
                background: transparent;
                border: none;
            }}
        """)

    def set_button_enabled(self, action_key: str, enabled: bool) -> None:
        if action_key in self._buttons:
            self._buttons[action_key].setEnabled(enabled)

    def set_button_loading(self, action_key: str, loading: bool) -> None:
        if action_key in self._buttons:
            self._buttons[action_key].set_loading(loading)


class CollapsibleToolSection(QWidget):
    action_triggered = pyqtSignal(str)

    def __init__(
        self,
        title: str,
        emoji: str,
        actions: List[ActionTuple],
        *,
        collapsed: bool = False,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._title = title
        self._emoji = emoji
        self._actions = actions
        self._collapsed = collapsed
        self._buttons: dict[str, ToolButton] = {}

        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        buttons_widget = self._create_buttons_widget()
        self._panel = CollapsiblePanel(
            f"{self._emoji} {self._title}",
            buttons_widget,
            collapsed=self._collapsed,
            compact=True,
        )
        layout.addWidget(self._panel)

    def _create_buttons_widget(self) -> QWidget:
        container = QWidget()
        grid = QGridLayout(container)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(8)

        cols = 3
        for i, (label, action_key, icon_key, emoji) in enumerate(self._actions):
            btn = ToolButton(label, action_key, icon_key, emoji, hero=False)
            btn.clicked.connect(
                lambda checked, k=action_key: self.action_triggered.emit(k)
            )
            self._buttons[action_key] = btn
            row, col = divmod(i, cols)
            grid.addWidget(btn, row, col)

        return container

    def set_collapsed(self, collapsed: bool) -> None:
        self._panel.set_collapsed(collapsed)

    def is_collapsed(self) -> bool:
        return self._panel.is_collapsed()

    def set_button_enabled(self, action_key: str, enabled: bool) -> None:
        if action_key in self._buttons:
            self._buttons[action_key].setEnabled(enabled)

    def set_button_loading(self, action_key: str, loading: bool) -> None:
        if action_key in self._buttons:
            self._buttons[action_key].set_loading(loading)


__all__ = ["ToolButton", "QuickActionsSection", "CollapsibleToolSection"]
