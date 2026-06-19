"""Compact active-device summary shown in the app-shell inspector (#13).

Fills the previously empty inspector pane with the active device's key facts so
the Ctrl+I inspector is useful, instead of showing a permanent placeholder.
"""

from typing import Optional

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QLabel, QVBoxLayout, QWidget

from ui.style_manager import StyleManager


class DeviceInspectorWidget(QWidget):
    """Key/value summary of the active device for the inspector region."""

    _FIELDS = (
        ("Model", "device_model"),
        ("Serial", "device_serial_num"),
        ("Android", "android_ver"),
        ("API", "android_api_level"),
        ("Wi-Fi", "wifi_is_on"),
        ("Bluetooth", "bt_is_on"),
    )

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("device_inspector")
        self._value_labels = {}
        self._build()
        self.set_device(None)

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(6)

        self._title = QLabel("Active device")
        self._title.setObjectName("device_inspector_title")
        layout.addWidget(self._title)

        self._placeholder = QLabel("Select a device to see its details.")
        self._placeholder.setWordWrap(True)
        self._placeholder.setObjectName("device_inspector_placeholder")
        layout.addWidget(self._placeholder)

        self._rows_container = QWidget()
        rows = QVBoxLayout(self._rows_container)
        rows.setContentsMargins(0, 0, 0, 0)
        rows.setSpacing(4)
        for label_text, key in self._FIELDS:
            row = QLabel()
            row.setObjectName("device_inspector_row")
            row.setWordWrap(True)
            self._value_labels[key] = (label_text, row)
            rows.addWidget(row)
        layout.addWidget(self._rows_container)
        layout.addStretch()

        self.refresh_theme()

    @staticmethod
    def _format_value(key: str, value) -> str:
        if key in ("wifi_is_on", "bt_is_on"):
            return "On" if value else "Off"
        if value in (None, ""):
            return "Unknown"
        return str(value)

    def set_device(self, device, serial: Optional[str] = None) -> None:
        """Populate the inspector from a DeviceInfo, or show the placeholder."""
        if device is None:
            self._placeholder.setVisible(True)
            self._rows_container.setVisible(False)
            return

        self._placeholder.setVisible(False)
        self._rows_container.setVisible(True)
        for key, (label_text, row) in self._value_labels.items():
            value = getattr(device, key, None)
            if key == "device_serial_num" and serial:
                value = serial
            row.setText(f"{label_text}: {self._format_value(key, value)}")

    def refresh_theme(self) -> None:
        """Theme-aware label colours (re-applied on theme switch, #9)."""
        colors = StyleManager.COLORS
        fg = colors.get("text_primary", "#EAEAEA")
        muted = colors.get("text_hint", "#9DA5B3")
        self._title.setStyleSheet(f"color: {fg}; font-weight: 600; font-size: 13px;")
        self._placeholder.setStyleSheet(f"color: {muted}; font-size: 12px;")
        for _label_text, row in self._value_labels.values():
            row.setStyleSheet(f"color: {fg}; font-size: 12px;")


__all__ = ["DeviceInspectorWidget"]
