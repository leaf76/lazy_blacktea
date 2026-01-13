"""Collapsible panel displaying active device operations."""

from __future__ import annotations

from typing import Dict, Optional

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QCursor
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from ui.signal_payloads import DeviceOperationEvent, OperationStatus

# Display constants
MAX_DEVICE_NAME_LENGTH = 15
TRUNCATE_LENGTH = 12


class OperationItemWidget(QFrame):
    """Single operation status row."""

    cancel_requested = pyqtSignal(str)

    def __init__(
        self,
        event: DeviceOperationEvent,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._event = event
        self._operation_id = event.operation_id
        self.setObjectName("operation_item")
        self._setup_ui()
        self._update_display()

    @property
    def operation_id(self) -> str:
        return self._operation_id

    def _setup_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(8)

        self._status_icon = QLabel()
        self._status_icon.setObjectName("operation_status_icon")
        self._status_icon.setFixedWidth(20)
        layout.addWidget(self._status_icon)

        self._device_label = QLabel()
        self._device_label.setObjectName("operation_device_label")
        self._device_label.setMinimumWidth(100)
        layout.addWidget(self._device_label)

        self._type_label = QLabel()
        self._type_label.setObjectName("operation_type_label")
        self._type_label.setMinimumWidth(100)
        layout.addWidget(self._type_label)

        self._progress_bar = QProgressBar()
        self._progress_bar.setObjectName("operation_progress_bar")
        self._progress_bar.setTextVisible(False)
        self._progress_bar.setFixedHeight(8)
        self._progress_bar.setMinimumWidth(80)
        self._progress_bar.hide()
        layout.addWidget(self._progress_bar)

        self._status_label = QLabel()
        self._status_label.setObjectName("operation_status_label")
        self._status_label.setMinimumWidth(80)
        layout.addWidget(self._status_label)

        layout.addStretch()

        self._cancel_btn = QToolButton()
        self._cancel_btn.setObjectName("operation_cancel_btn")
        self._cancel_btn.setText("\u2715")
        self._cancel_btn.setToolTip("Cancel operation")
        self._cancel_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._cancel_btn.clicked.connect(self._on_cancel_clicked)
        self._cancel_btn.hide()
        layout.addWidget(self._cancel_btn)

    def _update_display(self) -> None:
        ev = self._event
        self._status_icon.setText(ev.status_icon)

        device_text = ev.device_name or ev.device_serial
        if len(device_text) > MAX_DEVICE_NAME_LENGTH:
            device_text = device_text[:TRUNCATE_LENGTH] + "..."
        self._device_label.setText(device_text)
        self._device_label.setToolTip(f"{ev.device_name or ''} ({ev.device_serial})")

        self._type_label.setText(
            f"{ev.operation_type.icon} {ev.operation_type.display_name}"
        )

        if ev.status == OperationStatus.RUNNING and ev.progress is not None:
            self._progress_bar.setRange(0, 100)
            self._progress_bar.setValue(int(ev.progress * 100))
            self._progress_bar.show()
            self._status_label.setText(f"{int(ev.progress * 100)}%")
        elif ev.status == OperationStatus.RUNNING:
            self._progress_bar.setRange(0, 0)
            self._progress_bar.show()
            self._status_label.setText(ev.message or "Running...")
        else:
            self._progress_bar.hide()
            self._status_label.setText(ev.display_status)

        self._cancel_btn.setVisible(ev.can_cancel and ev.is_active)

        status_style = {
            OperationStatus.PENDING: "pending",
            OperationStatus.RUNNING: "running",
            OperationStatus.COMPLETED: "completed",
            OperationStatus.FAILED: "failed",
            OperationStatus.CANCELLED: "cancelled",
        }.get(ev.status, "")
        self.setProperty("operationStatus", status_style)
        self._repolish()

    def _repolish(self) -> None:
        style = self.style()
        if style:
            style.unpolish(self)
            style.polish(self)
        self.update()

    def _on_cancel_clicked(self) -> None:
        self.cancel_requested.emit(self._operation_id)

    def update_event(self, event: DeviceOperationEvent) -> None:
        self._event = event
        self._update_display()


class DeviceOperationStatusPanel(QFrame):
    """Collapsible panel showing all active device operations."""

    cancel_operation_requested = pyqtSignal(str)
    clear_completed_requested = pyqtSignal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("device_operation_status_panel")
        self._items: Dict[str, OperationItemWidget] = {}
        self._is_collapsed = False
        self._setup_ui()

    def _setup_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        header = QWidget()
        header.setObjectName("operation_panel_header")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(8, 4, 8, 4)
        header_layout.setSpacing(8)

        self._collapse_btn = QToolButton()
        self._collapse_btn.setObjectName("operation_collapse_btn")
        self._collapse_btn.setText("\u25bc")
        self._collapse_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._collapse_btn.clicked.connect(self._toggle_collapse)
        header_layout.addWidget(self._collapse_btn)

        self._title_label = QLabel("Device Operations")
        self._title_label.setObjectName("operation_panel_title")
        font = self._title_label.font()
        font.setBold(True)
        self._title_label.setFont(font)
        header_layout.addWidget(self._title_label)

        self._count_label = QLabel("(0)")
        self._count_label.setObjectName("operation_count_label")
        header_layout.addWidget(self._count_label)

        header_layout.addStretch()

        self._clear_btn = QPushButton("Clear")
        self._clear_btn.setObjectName("operation_clear_btn")
        self._clear_btn.setToolTip("Clear completed operations")
        self._clear_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._clear_btn.clicked.connect(self.clear_completed_requested.emit)
        self._clear_btn.hide()
        header_layout.addWidget(self._clear_btn)

        main_layout.addWidget(header)

        self._scroll_area = QScrollArea()
        self._scroll_area.setObjectName("operation_scroll_area")
        self._scroll_area.setWidgetResizable(True)
        self._scroll_area.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self._scroll_area.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        self._scroll_area.setMaximumHeight(150)

        self._content = QWidget()
        self._content.setObjectName("operation_content")
        self._content_layout = QVBoxLayout(self._content)
        self._content_layout.setContentsMargins(0, 0, 0, 0)
        self._content_layout.setSpacing(1)
        self._content_layout.addStretch()

        self._scroll_area.setWidget(self._content)
        main_layout.addWidget(self._scroll_area)

        self._empty_label = QLabel("No active operations")
        self._empty_label.setObjectName("operation_empty_label")
        self._empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._content_layout.insertWidget(0, self._empty_label)

        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)

    def _toggle_collapse(self) -> None:
        self._is_collapsed = not self._is_collapsed
        self._scroll_area.setVisible(not self._is_collapsed)
        self._collapse_btn.setText("\u25b6" if self._is_collapsed else "\u25bc")

    def add_operation(self, event: DeviceOperationEvent) -> None:
        if event.operation_id in self._items:
            self.update_operation(event)
            return

        item = OperationItemWidget(event)
        item.cancel_requested.connect(self.cancel_operation_requested.emit)

        insert_idx = self._content_layout.count() - 1
        self._content_layout.insertWidget(insert_idx, item)
        self._items[event.operation_id] = item

        self._update_counts()
        self._empty_label.hide()

    def update_operation(self, event: DeviceOperationEvent) -> None:
        item = self._items.get(event.operation_id)
        if item:
            item.update_event(event)
        self._update_counts()

    def remove_operation(self, operation_id: str) -> None:
        item = self._items.pop(operation_id, None)
        if item:
            self._content_layout.removeWidget(item)
            item.deleteLater()

        self._update_counts()
        if not self._items:
            self._empty_label.show()

    def _update_counts(self) -> None:
        total = len(self._items)
        active = sum(1 for item in self._items.values() if item._event.is_active)
        completed = total - active

        if active > 0:
            self._count_label.setText(f"({active} active)")
        else:
            self._count_label.setText(f"({total})")

        self._clear_btn.setVisible(completed > 0)
        self._title_label.setText(
            "Device Operations" if active > 0 else "Recent Operations"
        )

    def clear_all(self) -> None:
        for op_id in list(self._items.keys()):
            self.remove_operation(op_id)

    def get_operations_count(self) -> int:
        return len(self._items)

    def has_active_operations(self) -> bool:
        return any(item._event.is_active for item in self._items.values())


__all__ = ["DeviceOperationStatusPanel", "OperationItemWidget"]
