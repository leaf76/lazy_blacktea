"""Filter chip components for quick device filtering."""

from __future__ import annotations

from typing import Any, List, Optional, Tuple

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QCursor
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QMenu,
    QPushButton,
    QWidget,
)

from ui.style_manager import StyleManager


class FilterChip(QWidget):
    """Base class for filter chip components."""

    filter_changed = pyqtSignal(str, object)  # (filter_name, value)

    def __init__(
        self,
        name: str,
        label: str,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._name = name
        self._label = label
        self._active = False
        self._value: Any = None
        self._setup_ui()

    @property
    def name(self) -> str:
        return self._name

    @property
    def is_active(self) -> bool:
        return self._active

    @property
    def value(self) -> Any:
        return self._value

    def _setup_ui(self) -> None:
        raise NotImplementedError

    def reset(self) -> None:
        """Reset the filter to its default state."""
        self._active = False
        self._value = None
        self._update_appearance()

    def _update_appearance(self) -> None:
        """Update visual appearance based on state."""
        raise NotImplementedError

    def _emit_change(self) -> None:
        """Emit the filter_changed signal."""
        self.filter_changed.emit(self._name, self._value)


class ToggleFilterChip(FilterChip):
    """A simple toggle chip that can be on or off."""

    def __init__(
        self,
        name: str,
        label: str,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(name, label, parent)

    def _setup_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._button = QPushButton(self._label)
        self._button.setCheckable(True)
        self._button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._button.clicked.connect(self._on_clicked)
        self._button.setObjectName(f'filter_chip_{self._name}')
        self._apply_button_style()

        layout.addWidget(self._button)
        self._update_appearance()

    def _apply_button_style(self) -> None:
        """Apply chip button style."""
        self._button.setStyleSheet(StyleManager.get_filter_chip_style())

    def _on_clicked(self) -> None:
        self._active = self._button.isChecked()
        self._value = self._active if self._active else None
        self._update_appearance()
        self._emit_change()

    def _update_appearance(self) -> None:
        self._button.setChecked(self._active)
        if self._active:
            self._button.setProperty('active', True)
        else:
            self._button.setProperty('active', False)
        # Force style refresh
        self._button.style().unpolish(self._button)
        self._button.style().polish(self._button)

    def reset(self) -> None:
        self._active = False
        self._value = None
        self._button.setChecked(False)
        self._update_appearance()

    def set_state(self, active: bool, value: Any = None) -> None:
        """Set the filter state programmatically.

        Args:
            active: Whether the filter is active
            value: The filter value (defaults to active state if None)
        """
        self._active = active
        self._value = value if value is not None else (active if active else None)
        self._button.setChecked(active)
        self._update_appearance()


class DropdownFilterChip(FilterChip):
    """A filter chip with dropdown options."""

    def __init__(
        self,
        name: str,
        label: str,
        options: List[Tuple[str, Any]],
        parent: Optional[QWidget] = None,
    ) -> None:
        """
        Initialize dropdown filter chip.

        Args:
            name: Filter identifier
            label: Display label
            options: List of (display_text, value) tuples. First option is default.
            parent: Parent widget
        """
        self._options = options
        self._selected_index = 0
        super().__init__(name, label, parent)

    def _setup_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._button = QPushButton()
        self._button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._button.clicked.connect(self._show_menu)
        self._button.setObjectName(f'filter_chip_{self._name}')
        self._apply_button_style()

        layout.addWidget(self._button)
        self._update_button_text()
        self._update_appearance()

    def _apply_button_style(self) -> None:
        """Apply chip button style."""
        self._button.setStyleSheet(StyleManager.get_filter_chip_style())

    def _update_button_text(self) -> None:
        if self._selected_index == 0:
            # Default/All state - show label with dropdown arrow
            self._button.setText(f'{self._label} \u25be')
        else:
            # Active filter - show selected option
            display_text = self._options[self._selected_index][0]
            self._button.setText(f'{self._label}: {display_text} \u25be')

    def _show_menu(self) -> None:
        menu = QMenu(self)
        menu.setObjectName('filter_chip_menu')

        for index, (display_text, value) in enumerate(self._options):
            action = menu.addAction(display_text)
            action.setCheckable(True)
            action.setChecked(index == self._selected_index)
            # Use default argument to capture index value
            action.triggered.connect(
                lambda checked, idx=index: self._select_option(idx)
            )

        # Show menu below button
        pos = self._button.mapToGlobal(self._button.rect().bottomLeft())
        menu.exec(pos)

    def _select_option(self, index: int) -> None:
        if index == self._selected_index:
            return

        self._selected_index = index
        if index == 0:
            # Default option selected - filter inactive
            self._active = False
            self._value = None
        else:
            self._active = True
            self._value = self._options[index][1]

        self._update_button_text()
        self._update_appearance()
        self._emit_change()

    def _update_appearance(self) -> None:
        # Use string value for property to match stylesheet selector [active="true"]
        self._button.setProperty('active', 'true' if self._active else 'false')
        # Force style refresh
        self._button.style().unpolish(self._button)
        self._button.style().polish(self._button)

    def reset(self) -> None:
        self._selected_index = 0
        self._active = False
        self._value = None
        self._update_button_text()
        self._update_appearance()

    def set_options(self, options: List[Tuple[str, Any]]) -> None:
        """Update the available options."""
        self._options = options
        self._selected_index = 0
        self._active = False
        self._value = None
        self._update_button_text()
        self._update_appearance()

    def set_value(self, value: Any) -> None:
        """Set the filter value programmatically.

        Args:
            value: The value to select. If not found in options, resets to default.
        """
        for idx, (_, opt_value) in enumerate(self._options):
            if opt_value == value:
                if idx != self._selected_index:
                    self._selected_index = idx
                    if idx == 0:
                        self._active = False
                        self._value = None
                    else:
                        self._active = True
                        self._value = value
                    self._update_button_text()
                    self._update_appearance()
                return
        # Value not found, reset to default
        self.reset()


__all__ = ['FilterChip', 'ToggleFilterChip', 'DropdownFilterChip']
