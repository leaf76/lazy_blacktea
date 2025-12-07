"""Reusable collapsible panel widget with theme support."""

from __future__ import annotations

from typing import Optional

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QPushButton,
)

from ui.style_manager import StyleManager


class CollapsiblePanel(QWidget):
    """A collapsible panel controlled by a header button.

    - The header is a button with a disclosure indicator (▾/▸).
    - Clicking toggles the visibility of the content widget.
    - Supports theme-aware styling via StyleManager.
    """

    collapsed_changed = pyqtSignal(bool)

    def __init__(
        self,
        title: str,
        content: Optional[QWidget] = None,
        *,
        collapsed: bool = False,
        compact: bool = False,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._collapsed = collapsed
        self._compact = compact
        self._title = title
        self._content_widget: Optional[QWidget] = None

        self._root = QVBoxLayout(self)
        self._root.setContentsMargins(0, 0, 0, 0)
        self._root.setSpacing(2 if compact else 4)

        self._toggle_btn = QPushButton(self._title_text(title))
        self._toggle_btn.setCheckable(True)
        self._toggle_btn.setChecked(not collapsed)
        self._toggle_btn.setFlat(True)
        self._toggle_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._toggle_btn.clicked.connect(self._on_toggled)
        self._apply_toggle_button_style()
        self._root.addWidget(self._toggle_btn)

        self._content_container = QWidget()
        self._content_container.setObjectName('collapsible_content')
        self._apply_content_container_style()
        self._content_layout = QVBoxLayout(self._content_container)
        padding = 6 if compact else 10
        self._content_layout.setContentsMargins(padding, padding, padding, padding)
        self._content_layout.setSpacing(4 if compact else 6)
        self._root.addWidget(self._content_container)

        if content is not None:
            self.set_content(content)

        self._apply_collapsed_state()

    def _title_text(self, title: str) -> str:
        indicator = '▸ ' if self._collapsed else '▾ '
        return indicator + title

    def _apply_toggle_button_style(self) -> None:
        colors = StyleManager.COLORS
        bg = colors.get('tile_bg', '#2E3449')
        bg_hover = colors.get('tile_hover', '#3A4159')
        border = colors.get('tile_border', '#454C63')
        text = colors.get('text_primary', '#EAEAEA')

        padding = '4px 8px' if self._compact else '6px 10px'
        font_size = '11px' if self._compact else '12px'

        self._toggle_btn.setStyleSheet(f"""
            QPushButton {{
                text-align: left;
                padding: {padding};
                color: {text};
                background-color: {bg};
                border: 1px solid {border};
                border-radius: 6px;
                font-weight: 600;
                font-size: {font_size};
            }}
            QPushButton:hover {{
                background-color: {bg_hover};
            }}
            QPushButton:pressed {{
                background-color: {bg};
            }}
        """)

    def _apply_content_container_style(self) -> None:
        colors = StyleManager.COLORS
        bg = colors.get('panel_background', '#252A37')
        border = colors.get('panel_border', '#3E4455')

        self._content_container.setStyleSheet(f"""
            QWidget#collapsible_content {{
                background-color: {bg};
                border: 1px solid {border};
                border-radius: 6px;
            }}
        """)

    def _on_toggled(self) -> None:
        self._collapsed = not self._toggle_btn.isChecked()
        self._apply_collapsed_state()
        self.collapsed_changed.emit(self._collapsed)

    def _apply_collapsed_state(self) -> None:
        self._content_container.setVisible(not self._collapsed)
        self._toggle_btn.setText(self._title_text(self._title))

    def set_content(self, widget: QWidget) -> None:
        """Set the content widget inside the collapsible panel."""
        while self._content_layout.count():
            item = self._content_layout.takeAt(0)
            if item is not None and (w := item.widget()) is not None:
                w.setParent(None)
        self._content_widget = widget
        self._content_layout.addWidget(widget)
        self._apply_collapsed_state()

    def set_collapsed(self, collapsed: bool) -> None:
        """Set the collapsed state programmatically."""
        if self._collapsed == collapsed:
            return
        self._collapsed = bool(collapsed)
        self._toggle_btn.setChecked(not self._collapsed)
        self._apply_collapsed_state()
        self.collapsed_changed.emit(self._collapsed)

    def is_collapsed(self) -> bool:
        """Return whether the panel is currently collapsed."""
        return self._collapsed

    def set_title(self, title: str) -> None:
        """Update the panel title."""
        self._title = title
        self._toggle_btn.setText(self._title_text(title))

    def content_layout(self) -> QVBoxLayout:
        """Return the content layout for adding widgets directly."""
        return self._content_layout


__all__ = ['CollapsiblePanel']
