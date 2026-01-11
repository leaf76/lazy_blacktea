"""Widget displaying currently selected devices for batch operations."""

from __future__ import annotations

from typing import TYPE_CHECKING, List, Optional

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QWidget,
    QHBoxLayout,
    QVBoxLayout,
    QLabel,
    QFrame,
    QSizePolicy,
)

from config.constants import PanelText
from ui.style_manager import StyleManager

if TYPE_CHECKING:
    from utils.adb_models import DeviceInfo


class DeviceChip(QFrame):
    """A small chip displaying device info (model + serial snippet)."""

    def __init__(
        self,
        model: str,
        serial: str,
        *,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("device_chip")
        self._model = model
        self._serial = serial

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(4)

        serial_display = serial[-6:] if len(serial) > 6 else serial
        display_text = f"{model} ({serial_display})"

        label = QLabel(display_text)
        label.setObjectName("device_chip_label")
        layout.addWidget(label)

        self._apply_style()

    def _apply_style(self) -> None:
        colors = StyleManager.COLORS
        bg = colors.get("tile_bg", "#2E3449")
        border = colors.get("tile_border", "#454C63")
        text = colors.get("text_secondary", "#C8C8C8")

        self.setStyleSheet(f"""
            QFrame#device_chip {{
                background-color: {bg};
                border: 1px solid {border};
                border-radius: 4px;
            }}
            QLabel#device_chip_label {{
                color: {text};
                font-size: 11px;
                background: transparent;
                border: none;
            }}
        """)


class SelectedDevicesBar(QWidget):
    """Bar showing currently selected devices for ADB Tools batch operations.

    Features:
    - Shows device count and list of selected devices
    - Chips display model name + truncated serial
    - Overflow indicator when > MAX_VISIBLE_CHIPS devices selected
    - Updates dynamically via update_devices() method
    """

    MAX_VISIBLE_CHIPS = 5

    clicked = pyqtSignal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("selected_devices_bar")
        self._devices: List["DeviceInfo"] = []

        self._root = QVBoxLayout(self)
        self._root.setContentsMargins(0, 0, 0, 0)
        self._root.setSpacing(4)

        self._header = QLabel(PanelText.SELECTED_DEVICES_HEADER.format(count=0))
        self._header.setObjectName("selected_devices_header")
        self._root.addWidget(self._header)

        self._chips_container = QFrame()
        self._chips_container.setObjectName("chips_container")
        self._chips_layout = QHBoxLayout(self._chips_container)
        self._chips_layout.setContentsMargins(0, 0, 0, 0)
        self._chips_layout.setSpacing(6)
        self._chips_layout.addStretch()
        self._root.addWidget(self._chips_container)

        self._apply_style()
        self._update_visibility()

    def _apply_style(self) -> None:
        colors = StyleManager.COLORS
        bg = colors.get("panel_background", "#252A37")
        border = colors.get("panel_border", "#3E4455")
        text_primary = colors.get("text_primary", "#EAEAEA")
        text_hint = colors.get("text_hint", "#9DA5B3")

        self.setStyleSheet(f"""
            QWidget#selected_devices_bar {{
                background-color: {bg};
                border: 1px solid {border};
                border-radius: 8px;
                padding: 8px 12px;
            }}
            QLabel#selected_devices_header {{
                color: {text_primary};
                font-size: 12px;
                font-weight: 600;
                background: transparent;
                border: none;
            }}
            QFrame#chips_container {{
                background: transparent;
                border: none;
            }}
        """)

    def update_devices(self, devices: List["DeviceInfo"]) -> None:
        """Update the bar with the current list of selected devices."""
        self._devices = devices
        self._rebuild_chips()
        self._update_visibility()

    def _rebuild_chips(self) -> None:
        """Clear and rebuild device chips."""
        while self._chips_layout.count() > 1:
            item = self._chips_layout.takeAt(0)
            if item is not None:
                widget = item.widget()
                if widget is not None:
                    widget.deleteLater()

        if not self._devices:
            self._header.setText(PanelText.SELECTED_DEVICES_HEADER.format(count=0))
            return

        count = len(self._devices)
        self._header.setText(PanelText.SELECTED_DEVICES_HEADER.format(count=count))

        visible_count = min(count, self.MAX_VISIBLE_CHIPS)
        for i in range(visible_count):
            device = self._devices[i]
            model = device.device_model or device.device_prod or "Unknown"
            chip = DeviceChip(model, device.device_serial_num)
            self._chips_layout.insertWidget(i, chip)

        if count > self.MAX_VISIBLE_CHIPS:
            overflow_count = count - self.MAX_VISIBLE_CHIPS
            overflow_label = QLabel(
                PanelText.SELECTED_DEVICES_OVERFLOW.format(count=overflow_count)
            )
            overflow_label.setObjectName("overflow_label")
            overflow_label.setStyleSheet(f"""
                QLabel#overflow_label {{
                    color: {StyleManager.COLORS.get("text_hint", "#9DA5B3")};
                    font-size: 11px;
                    font-style: italic;
                    background: transparent;
                    border: none;
                }}
            """)
            self._chips_layout.insertWidget(visible_count, overflow_label)

    def _update_visibility(self) -> None:
        """Show/hide the chips container based on device count."""
        has_devices = len(self._devices) > 0
        self._chips_container.setVisible(has_devices)

    def get_device_count(self) -> int:
        """Return the number of currently selected devices."""
        return len(self._devices)

    def get_device_serials(self) -> List[str]:
        """Return the serial numbers of selected devices."""
        return [d.device_serial_num for d in self._devices]

    def mousePressEvent(self, a0) -> None:
        """Emit clicked signal when bar is clicked."""
        super().mousePressEvent(a0)
        self.clicked.emit()


__all__ = ["SelectedDevicesBar", "DeviceChip"]
