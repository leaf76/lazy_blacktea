"""Embedded Logcat pane for the AppShell."""

from __future__ import annotations

from typing import Callable, Dict, Iterable, Optional

from PyQt6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)
from PyQt6.QtGui import QCloseEvent

from ui.design_tokens import get_palette


ViewerFactory = Callable[[object, Optional[QWidget]], QWidget]


class LogcatPane(QWidget):
    """Host an embedded logcat viewer for the active device."""

    def __init__(
        self,
        *,
        viewer_factory: Optional[ViewerFactory] = None,
        on_open_devices: Optional[Callable[[], None]] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("logcatPane")
        self._viewer_factory = viewer_factory or self._default_viewer_factory
        self._on_open_devices = on_open_devices
        self._devices: Dict[str, object] = {}
        self._current_viewer: Optional[QWidget] = None
        self._theme = "light"
        self._setup_ui()

    def set_devices(self, devices: Iterable[object]) -> None:
        current = self.active_serial()
        self._devices = {}
        self._device_combo.blockSignals(True)
        self._device_combo.clear()

        for device in devices:
            serial = getattr(device, "device_serial_num", "")
            if not serial:
                continue
            self._devices[serial] = device
            label = f"{getattr(device, 'device_model', 'Device')} · {serial}"
            self._device_combo.addItem(label, serial)

        if current in self._devices:
            index = self._device_combo.findData(current)
            self._device_combo.setCurrentIndex(index)
        elif self._device_combo.count() > 0:
            self._device_combo.setCurrentIndex(0)

        self._device_combo.blockSignals(False)
        self._sync_empty_state()

    def active_serial(self) -> Optional[str]:
        serial = self._device_combo.currentData()
        return serial if isinstance(serial, str) and serial else None

    def is_empty(self) -> bool:
        return not bool(self._devices)

    def current_viewer(self) -> Optional[QWidget]:
        return self._current_viewer

    def open_active_device(self) -> bool:
        serial = self.active_serial()
        if serial is None:
            self._sync_empty_state()
            return False
        device = self._devices.get(serial)
        if device is None:
            self._sync_empty_state()
            return False
        return self.open_device(device)

    def open_device(self, device: object) -> bool:
        self._clear_viewer()
        viewer = self._viewer_factory(device, self._viewer_host)
        self._current_viewer = viewer
        self._viewer_layout.addWidget(viewer)
        self._stack.setCurrentWidget(self._viewer_host)
        return True

    def set_theme(self, theme: str) -> None:
        self._theme = theme if theme in ("light", "dark") else "light"
        self._apply_palette()

    def cleanup(self) -> None:
        """Release the embedded viewer before the pane is destroyed."""
        self._clear_viewer()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        toolbar = QHBoxLayout()
        self._device_combo = QComboBox()
        self._device_combo.currentIndexChanged.connect(lambda _idx: self._sync_empty_state())
        toolbar.addWidget(QLabel("Device:"))
        toolbar.addWidget(self._device_combo, stretch=1)

        open_btn = QPushButton("Open stream")
        open_btn.clicked.connect(self.open_active_device)
        toolbar.addWidget(open_btn)
        layout.addLayout(toolbar)

        self._stack = QStackedWidget(self)
        layout.addWidget(self._stack, stretch=1)

        self._empty = QWidget()
        empty_layout = QVBoxLayout(self._empty)
        empty_layout.addStretch(1)
        self._empty_label = QLabel("Select a device to view logcat.")
        self._empty_label.setObjectName("logcatEmptyLabel")
        self._empty_label.setWordWrap(True)
        empty_layout.addWidget(self._empty_label)
        devices_btn = QPushButton("Open Devices")
        devices_btn.clicked.connect(self._handle_open_devices)
        empty_layout.addWidget(devices_btn)
        empty_layout.addStretch(1)
        self._stack.addWidget(self._empty)

        self._viewer_host = QWidget()
        self._viewer_layout = QVBoxLayout(self._viewer_host)
        self._viewer_layout.setContentsMargins(0, 0, 0, 0)
        self._viewer_layout.setSpacing(0)
        self._stack.addWidget(self._viewer_host)
        self._stack.setCurrentWidget(self._empty)
        self._apply_palette()

    def _handle_open_devices(self) -> None:
        if self._on_open_devices is not None:
            self._on_open_devices()

    def _sync_empty_state(self) -> None:
        if self.is_empty():
            self._stack.setCurrentWidget(self._empty)
            self._empty_label.setText("No devices available for logcat.")
        elif self._current_viewer is None:
            self._stack.setCurrentWidget(self._empty)
            self._empty_label.setText("Select a device to view logcat.")

    def _clear_viewer(self) -> None:
        if self._current_viewer is None:
            return
        cleanup = getattr(self._current_viewer, "cleanup", None)
        if callable(cleanup):
            cleanup()
        self._viewer_layout.removeWidget(self._current_viewer)
        self._current_viewer.setParent(None)
        self._current_viewer.deleteLater()
        self._current_viewer = None

    def closeEvent(self, event: QCloseEvent) -> None:  # type: ignore[override]
        self.cleanup()
        super().closeEvent(event)

    def _default_viewer_factory(self, device: object, parent: Optional[QWidget]) -> QWidget:
        from ui.logcat_viewer import LogcatViewerWidget

        return LogcatViewerWidget(device, parent)

    def _apply_palette(self) -> None:
        palette = get_palette(self._theme)
        self.setStyleSheet(
            f"""
            #logcatPane {{
                background-color: {palette['bg_canvas']};
                color: {palette['fg_primary']};
            }}
            #logcatEmptyLabel {{
                color: {palette['fg_secondary']};
                font-size: 14px;
            }}
            """
        )


__all__ = ["LogcatPane", "ViewerFactory"]
