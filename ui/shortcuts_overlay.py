"""Read-only keyboard-shortcuts reference overlay (audit findings #30/#31).

Opened with ``?`` so keyboard-first users can discover the available bindings.
"""

from typing import List, Tuple

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QGridLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

# (binding, description) grouped by section.
SHORTCUTS: List[Tuple[str, List[Tuple[str, str]]]] = [
    (
        "Navigation",
        [
            ("Ctrl+K", "Open command palette"),
            ("Ctrl+1 … Ctrl+9", "Switch to pane by position"),
            ("Ctrl+B", "Toggle sidebar"),
            ("Ctrl+I", "Toggle inspector"),
            ("/", "Focus the device search"),
            ("?", "Show this shortcuts overlay"),
        ],
    ),
    (
        "Devices list",
        [
            ("↑ / ↓", "Move the active device"),
            ("Space", "Toggle selection of the active device"),
            ("Ctrl+A", "Select all devices"),
            ("Ctrl+Shift+A", "Clear the selection"),
        ],
    ),
]


class ShortcutsOverlay(QDialog):
    """Modal, read-only list of keyboard shortcuts."""

    def __init__(self, parent: QWidget = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Keyboard Shortcuts")
        self.setModal(True)
        self._build()

    def _build(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(20, 16, 20, 16)
        outer.setSpacing(12)

        for section, bindings in SHORTCUTS:
            header = QLabel(section)
            header.setStyleSheet("font-weight: 600; font-size: 13px;")
            outer.addWidget(header)

            grid = QGridLayout()
            grid.setHorizontalSpacing(24)
            grid.setVerticalSpacing(4)
            for row, (keys, desc) in enumerate(bindings):
                key_label = QLabel(keys)
                key_label.setStyleSheet("font-family: monospace;")
                grid.addWidget(key_label, row, 0, Qt.AlignmentFlag.AlignLeft)
                grid.addWidget(QLabel(desc), row, 1, Qt.AlignmentFlag.AlignLeft)
            outer.addLayout(grid)


__all__ = ["ShortcutsOverlay", "SHORTCUTS"]
