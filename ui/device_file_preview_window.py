"""Standalone window for device file previews."""

from __future__ import annotations

import os
from typing import Optional

from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QPlainTextEdit,
)

from config.constants import PanelText
from ui.device_file_preview_controller import DeviceFilePreviewController


class DeviceFilePreviewWindow(QDialog):
    """Dialog that renders device file previews with multiple content types."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle('Device File Preview')
        self.setMinimumSize(640, 480)

        layout = QVBoxLayout(self)

        self.stack = QStackedWidget(self)
        layout.addWidget(self.stack)

        self.text_widget = QPlainTextEdit(self)
        self.text_widget.setObjectName('device_file_preview_text')
        self.text_widget.setReadOnly(True)
        self.text_widget.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)

        self.image_widget = QLabel(self)
        self.image_widget.setObjectName('device_file_preview_image')
        self.image_widget.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_widget.setMinimumSize(240, 240)
        self.image_widget.setStyleSheet('background-color: #1d1d1d; border: 1px solid #333;')

        self.message_widget = QLabel(self)
        self.message_widget.setObjectName('device_file_preview_message')
        self.message_widget.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.message_widget.setWordWrap(True)

        self.open_button = QPushButton(PanelText.BUTTON_OPEN_EXTERNALLY, self)
        self.open_button.clicked.connect(self._open_externally)
        self.open_button.setEnabled(False)

        clear_button = QPushButton(PanelText.BUTTON_CLEAR_PREVIEW_CACHE, self)
        clear_button.clicked.connect(self.clear_preview)

        button_row = QHBoxLayout()
        button_row.addWidget(self.open_button)
        button_row.addWidget(clear_button)
        button_row.addStretch(1)
        layout.addLayout(button_row)

        self.controller = DeviceFilePreviewController(
            stack=self.stack,
            text_widget=self.text_widget,
            image_widget=self.image_widget,
            message_widget=self.message_widget,
            open_button=self.open_button,
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    @property
    def current_path(self) -> Optional[str]:
        return self.controller.current_path

    def display_preview(self, local_path: str) -> None:
        self.controller.display_preview(local_path)
        self.show()
        self.raise_()
        self.activateWindow()

    def clear_preview(self) -> None:
        self.controller.clear_preview()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _open_externally(self) -> None:
        path = self.controller.current_path
        if not path or not os.path.exists(path):
            return

        QDesktopServices.openUrl(QUrl.fromLocalFile(path))

    def closeEvent(self, event) -> None:  # pragma: no cover - Qt handles default path
        super().closeEvent(event)
        self.controller.clear_preview()


__all__ = ['DeviceFilePreviewWindow']
