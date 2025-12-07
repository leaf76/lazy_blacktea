"""Dialog to configure global output path settings."""

from __future__ import annotations

import os
from typing import Optional

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
)


class OutputSettingsDialog(QDialog):
    """Settings dialog for configuring the global output path."""

    def __init__(self, current_path: str = "", parent=None):
        super().__init__(parent)
        self.setWindowTitle("Output Settings")
        self.setModal(True)
        self.setMinimumWidth(450)
        self._result_path: Optional[str] = None
        self._initial_path = current_path

        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)

        # Title
        title = QLabel("Output Directory")
        title.setStyleSheet("font-size: 14px; font-weight: bold;")
        layout.addWidget(title)

        # Description
        desc = QLabel(
            "All screenshots, recordings, and file downloads will be saved to this directory."
        )
        desc.setWordWrap(True)
        desc.setStyleSheet("color: #888; font-size: 12px;")
        layout.addWidget(desc)

        # Path input row
        path_row = QHBoxLayout()
        path_row.setSpacing(8)

        self._path_edit = QLineEdit()
        self._path_edit.setPlaceholderText("Select output directory...")
        self._path_edit.setText(self._initial_path)
        self._path_edit.setMinimumHeight(32)
        path_row.addWidget(self._path_edit)

        browse_btn = QPushButton("Browse...")
        browse_btn.setMinimumHeight(32)
        browse_btn.clicked.connect(self._browse_path)
        path_row.addWidget(browse_btn)

        layout.addLayout(path_row)

        # Current path display
        self._status_label = QLabel()
        self._status_label.setStyleSheet("color: #6b7280; font-size: 11px;")
        self._update_status()
        layout.addWidget(self._status_label)

        layout.addStretch()

        # Dialog buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._handle_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        # Connect text change to update status
        self._path_edit.textChanged.connect(self._update_status)

    def _browse_path(self) -> None:
        """Open directory picker."""
        current = self._path_edit.text().strip()
        if not current or not os.path.isdir(current):
            current = os.path.expanduser("~")

        directory = QFileDialog.getExistingDirectory(
            self,
            "Select Output Directory",
            current,
        )
        if directory:
            self._path_edit.setText(directory)

    def _update_status(self) -> None:
        """Update the status label based on current path."""
        path = self._path_edit.text().strip()
        if not path:
            self._status_label.setText("No path configured. Default location will be used.")
        elif os.path.isdir(path):
            self._status_label.setText(f"Valid directory")
            self._status_label.setStyleSheet("color: #4ade80; font-size: 11px;")
        else:
            self._status_label.setText("Directory does not exist")
            self._status_label.setStyleSheet("color: #f87171; font-size: 11px;")

    def _handle_accept(self) -> None:
        """Handle save button click."""
        self._result_path = self._path_edit.text().strip()
        self.accept()

    def get_output_path(self) -> Optional[str]:
        """Get the configured output path, or None if dialog was cancelled."""
        return self._result_path


__all__ = ["OutputSettingsDialog"]
