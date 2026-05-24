"""Tools workspace with a left rail and reusable page stack."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QListWidget,
    QListWidgetItem,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from ui.design_tokens import get_palette

DENSITY_RAIL_PADDING = {
    "compact": "6px 6px",
    "cozy": "10px 8px",
    "comfortable": "14px 10px",
}
DENSITY_ITEM_PADDING = {
    "compact": "5px 8px",
    "cozy": "8px 10px",
    "comfortable": "10px 12px",
}


@dataclass
class _ToolsPage:
    name: str
    label: str
    widget: QWidget


class ToolsWorkspace(QWidget):
    """Primary Tools pane with sidebar-style sub-navigation."""

    page_changed = pyqtSignal(str)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("toolsWorkspace")
        self._pages: Dict[str, _ToolsPage] = {}
        self._page_order: List[str] = []
        self._active_page: Optional[str] = None
        self._theme = "light"
        self._density = "cozy"

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._rail = QListWidget(self)
        self._rail.setObjectName("toolsWorkspaceRail")
        self._rail.setFixedWidth(200)
        self._rail.setFrameShape(QFrame.Shape.NoFrame)
        self._rail.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        self._rail.itemSelectionChanged.connect(self._on_selection_changed)
        layout.addWidget(self._rail)

        self._stack = QStackedWidget(self)
        self._stack.setObjectName("toolsWorkspaceStack")
        layout.addWidget(self._stack, stretch=1)

        self._apply_palette()

    def add_page(self, name: str, label: str, widget: QWidget) -> None:
        """Add or replace a workspace page."""

        if name in self._pages:
            self.remove_page(name)

        self._pages[name] = _ToolsPage(name=name, label=label, widget=widget)
        self._page_order.append(name)
        self._stack.addWidget(widget)

        item = QListWidgetItem(label)
        item.setData(Qt.ItemDataRole.UserRole, name)
        item.setToolTip(label)
        self._rail.addItem(item)

        if self._active_page is None:
            self.set_active_page(name)

    def remove_page(self, name: str) -> bool:
        page = self._pages.pop(name, None)
        if page is None:
            return False
        self._page_order = [existing for existing in self._page_order if existing != name]

        for row in range(self._rail.count()):
            item = self._rail.item(row)
            if item and item.data(Qt.ItemDataRole.UserRole) == name:
                self._rail.takeItem(row)
                break

        index = self._stack.indexOf(page.widget)
        if index != -1:
            self._stack.removeWidget(page.widget)

        if self._active_page == name:
            self._active_page = None
            if self._page_order:
                self.set_active_page(self._page_order[0])
        return True

    def page_names(self) -> List[str]:
        return list(self._page_order)

    def active_page(self) -> Optional[str]:
        return self._active_page

    def set_active_page(self, name: str) -> bool:
        page = self._pages.get(name)
        if page is None:
            return False
        if self._active_page == name:
            return True
        self._active_page = name
        self._stack.setCurrentWidget(page.widget)

        for row in range(self._rail.count()):
            item = self._rail.item(row)
            if item and item.data(Qt.ItemDataRole.UserRole) == name:
                self._rail.blockSignals(True)
                self._rail.setCurrentRow(row)
                self._rail.blockSignals(False)
                break

        self.page_changed.emit(name)
        return True

    def set_active_page_by_label(self, label: str) -> bool:
        for page in self._pages.values():
            if page.label == label:
                return self.set_active_page(page.name)
        return False

    def set_theme(self, theme: str) -> None:
        self._theme = theme if theme in ("light", "dark") else "light"
        self._apply_palette()

    def set_density(self, density: str) -> None:
        self._density = density if density in DENSITY_RAIL_PADDING else "cozy"
        self._apply_palette()

    def _on_selection_changed(self) -> None:
        item = self._rail.currentItem()
        if item is None:
            return
        name = item.data(Qt.ItemDataRole.UserRole)
        if isinstance(name, str):
            self.set_active_page(name)

    def _apply_palette(self) -> None:
        palette = get_palette(self._theme)
        rail_padding = DENSITY_RAIL_PADDING[self._density]
        item_padding = DENSITY_ITEM_PADDING[self._density]
        self.setStyleSheet(
            f"""
            #toolsWorkspace {{
                background-color: {palette['bg_canvas']};
                color: {palette['fg_primary']};
            }}
            QListWidget#toolsWorkspaceRail {{
                background-color: {palette['bg_surface']};
                border: none;
                border-right: 1px solid {palette['border_subtle']};
                color: {palette['fg_secondary']};
                font-size: 13px;
                padding: {rail_padding};
            }}
            QListWidget#toolsWorkspaceRail::item {{
                padding: {item_padding};
                border-radius: 6px;
                margin: 1px 0;
            }}
            QListWidget#toolsWorkspaceRail::item:selected {{
                background-color: {palette['bg_active']};
                color: {palette['fg_primary']};
            }}
            QListWidget#toolsWorkspaceRail::item:hover {{
                background-color: {palette['bg_hover']};
                color: {palette['fg_primary']};
            }}
            #toolsWorkspaceStack {{
                background-color: {palette['bg_canvas']};
            }}
            """
        )


__all__ = ["ToolsWorkspace"]
