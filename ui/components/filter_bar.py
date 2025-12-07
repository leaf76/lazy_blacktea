"""Filter bar containing all filter chips for device filtering."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QHBoxLayout, QPushButton, QWidget

from ui.components.filter_chip import DropdownFilterChip, ToggleFilterChip
from ui.style_manager import StyleManager


class FilterBar(QWidget):
    """Horizontal bar containing all filter chips."""

    filter_changed = pyqtSignal(dict)  # Emits complete filter state

    # Default API level options
    DEFAULT_API_OPTIONS: List[Tuple[str, Any]] = [
        ('All', None),
        ('33+ (Android 13)', 33),
        ('34+ (Android 14)', 34),
        ('35+ (Android 15)', 35),
    ]

    # WiFi/BT state options
    STATE_OPTIONS: List[Tuple[str, Any]] = [
        ('All', None),
        ('On', True),
        ('Off', False),
    ]

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._chips: Dict[str, Any] = {}
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(8)

        # WiFi dropdown filter
        wifi_chip = DropdownFilterChip(
            name='wifi',
            label='WiFi',
            options=self.STATE_OPTIONS,
        )
        wifi_chip.filter_changed.connect(self._on_chip_changed)
        self._chips['wifi'] = wifi_chip
        layout.addWidget(wifi_chip)

        # Bluetooth dropdown filter
        bt_chip = DropdownFilterChip(
            name='bt',
            label='BT',
            options=self.STATE_OPTIONS,
        )
        bt_chip.filter_changed.connect(self._on_chip_changed)
        self._chips['bt'] = bt_chip
        layout.addWidget(bt_chip)

        # Selected toggle filter
        selected_chip = ToggleFilterChip(
            name='selected',
            label='Selected',
        )
        selected_chip.filter_changed.connect(self._on_chip_changed)
        self._chips['selected'] = selected_chip
        layout.addWidget(selected_chip)

        # Recording toggle filter
        recording_chip = ToggleFilterChip(
            name='recording',
            label='Recording',
        )
        recording_chip.filter_changed.connect(self._on_chip_changed)
        self._chips['recording'] = recording_chip
        layout.addWidget(recording_chip)

        # API level dropdown filter
        api_chip = DropdownFilterChip(
            name='api',
            label='API',
            options=self.DEFAULT_API_OPTIONS,
        )
        api_chip.filter_changed.connect(self._on_chip_changed)
        self._chips['api'] = api_chip
        layout.addWidget(api_chip)

        # Clear all button
        self._clear_btn = QPushButton('Clear')
        self._clear_btn.setObjectName('filter_clear_btn')
        self._clear_btn.clicked.connect(self.clear_all)
        self._clear_btn.setStyleSheet(StyleManager.get_filter_clear_btn_style())
        self._clear_btn.setVisible(False)  # Hidden until filters are active
        layout.addWidget(self._clear_btn)

        # Add stretch to push chips to the left
        layout.addStretch()

    def _on_chip_changed(self, name: str, value: Any) -> None:
        """Handle individual chip state change."""
        self._update_clear_button_visibility()
        self.filter_changed.emit(self.get_active_filters())

    def _update_clear_button_visibility(self) -> None:
        """Show/hide clear button based on active filters."""
        has_active = any(chip.is_active for chip in self._chips.values())
        self._clear_btn.setVisible(has_active)

    def get_active_filters(self) -> Dict[str, Any]:
        """Get dictionary of currently active filters."""
        filters = {}
        for name, chip in self._chips.items():
            if chip.is_active:
                filters[name] = chip.value
        return filters

    def clear_all(self) -> None:
        """Reset all filters to default state."""
        for chip in self._chips.values():
            chip.reset()
        self._clear_btn.setVisible(False)
        self.filter_changed.emit({})

    def set_filter(self, name: str, value: Any) -> None:
        """Programmatically set a filter value."""
        chip = self._chips.get(name)
        if chip is None:
            return

        if isinstance(chip, ToggleFilterChip):
            chip.set_state(bool(value), value if value else None)
        elif isinstance(chip, DropdownFilterChip):
            chip.set_value(value)

        self._update_clear_button_visibility()

    def get_chip(self, name: str) -> Optional[Any]:
        """Get a specific filter chip by name."""
        return self._chips.get(name)

    def update_api_options(self, options: List[Tuple[str, Any]]) -> None:
        """Update the API filter options dynamically."""
        api_chip = self._chips.get('api')
        if isinstance(api_chip, DropdownFilterChip):
            api_chip.set_options(options)


__all__ = ['FilterBar']
