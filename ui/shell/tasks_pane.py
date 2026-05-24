"""Tasks pane backed by DeviceOperationStatusManager."""

from __future__ import annotations

from typing import List, Optional

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ui.design_tokens import get_palette
from ui.signal_payloads import DeviceOperationEvent

DENSITY_PAGE = {
    "compact": {"margin": 10, "spacing": 8, "title": 16},
    "cozy": {"margin": 16, "spacing": 12, "title": 18},
    "comfortable": {"margin": 20, "spacing": 16, "title": 20},
}


class TasksPane(QWidget):
    """Display active and recent device operations in the AppShell."""

    def __init__(self, status_manager, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("tasksPane")
        self._status_manager = status_manager
        self._theme = "light"
        self._density = "cozy"
        self._setup_ui()
        self._connect_manager()
        self.refresh()

    def active_count(self) -> int:
        return len(self._active_operations())

    def recent_count(self) -> int:
        return len(self._recent_operations())

    def badge_text(self) -> str:
        active = self.active_count()
        return str(active) if active else ""

    def cancel_operation(self, operation_id: str) -> bool:
        return bool(self._status_manager.cancel_operation(operation_id))

    def refresh(self) -> None:
        self._active_list.clear()
        self._recent_list.clear()

        for event in self._active_operations():
            self._active_list.addItem(self._format_item(event))

        for event in self._recent_operations():
            self._recent_list.addItem(self._format_item(event))

        self._active_empty.setVisible(self._active_list.count() == 0)
        self._recent_empty.setVisible(self._recent_list.count() == 0)
        self._active_title.setText(f"Active ({self.active_count()})")
        self._recent_title.setText(f"Recent ({self.recent_count()})")

    def set_theme(self, theme: str) -> None:
        self._theme = theme if theme in ("light", "dark") else "light"
        self._apply_palette()

    def set_density(self, density: str) -> None:
        self._density = density if density in DENSITY_PAGE else "cozy"
        values = DENSITY_PAGE[self._density]
        self._layout.setContentsMargins(
            values["margin"],
            values["margin"],
            values["margin"],
            values["margin"],
        )
        self._layout.setSpacing(values["spacing"])
        self._apply_palette()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        self._layout = layout
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        header = QHBoxLayout()
        title = QLabel("Tasks")
        title.setObjectName("tasksPaneTitle")
        header.addWidget(title)
        header.addStretch(1)

        clear_btn = QPushButton("Clear completed")
        clear_btn.clicked.connect(self._clear_completed)
        header.addWidget(clear_btn)
        layout.addLayout(header)

        self._active_title = QLabel("Active (0)")
        self._active_title.setObjectName("tasksSectionTitle")
        layout.addWidget(self._active_title)

        self._active_list = QListWidget()
        self._active_list.setObjectName("tasksActiveList")
        self._active_list.setAlternatingRowColors(False)
        layout.addWidget(self._active_list, stretch=1)

        self._active_empty = QLabel("No active tasks")
        self._active_empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._active_empty)

        divider = QFrame()
        divider.setObjectName("tasksDivider")
        divider.setFrameShape(QFrame.Shape.HLine)
        layout.addWidget(divider)

        self._recent_title = QLabel("Recent (0)")
        self._recent_title.setObjectName("tasksSectionTitle")
        layout.addWidget(self._recent_title)

        self._recent_list = QListWidget()
        self._recent_list.setObjectName("tasksRecentList")
        layout.addWidget(self._recent_list, stretch=1)

        self._recent_empty = QLabel("Nothing here yet")
        self._recent_empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._recent_empty)

        self._apply_palette()

    def _connect_manager(self) -> None:
        self._status_manager.operation_added.connect(lambda _event: self.refresh())
        self._status_manager.operation_updated.connect(lambda _event: self.refresh())
        self._status_manager.operation_removed.connect(lambda _id: self.refresh())

    def _clear_completed(self) -> None:
        self._status_manager.clear_completed()
        self.refresh()

    def _active_operations(self) -> List[DeviceOperationEvent]:
        return list(self._status_manager.get_active_operations())

    def _recent_operations(self) -> List[DeviceOperationEvent]:
        return [
            event
            for event in self._status_manager.get_all_operations()
            if event.is_terminal
        ][-50:]

    def _format_item(self, event: DeviceOperationEvent) -> QListWidgetItem:
        device = event.device_name or event.device_serial
        status = event.display_status
        text = f"{event.status_icon} {event.operation_type.display_name} · {device} · {status}"
        item = QListWidgetItem(text)
        item.setData(Qt.ItemDataRole.UserRole, event.operation_id)
        if event.error_message:
            item.setToolTip(event.error_message)
        return item

    def _apply_palette(self) -> None:
        palette = get_palette(self._theme)
        title_size = DENSITY_PAGE[self._density]["title"]
        self.setStyleSheet(
            f"""
            #tasksPane {{
                background-color: {palette['bg_canvas']};
                color: {palette['fg_primary']};
            }}
            #tasksPaneTitle {{
                font-size: {title_size}px;
                font-weight: 600;
                color: {palette['fg_primary']};
            }}
            #tasksSectionTitle {{
                font-size: 12px;
                font-weight: 600;
                color: {palette['fg_secondary']};
            }}
            QListWidget {{
                background-color: {palette['bg_surface']};
                border: 1px solid {palette['border_subtle']};
                border-radius: 6px;
                color: {palette['fg_primary']};
            }}
            QLabel {{
                color: {palette['fg_secondary']};
            }}
            """
        )


__all__ = ["TasksPane"]
