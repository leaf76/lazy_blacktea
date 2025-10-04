"""Shared UI-level constants for Lazy Blacktea."""

from PyQt6.QtCore import Qt

__all__ = [
    "DEVICE_FILE_PATH_ROLE",
    "DEVICE_FILE_IS_DIR_ROLE",
]

DEVICE_FILE_PATH_ROLE = Qt.ItemDataRole.UserRole + 1
DEVICE_FILE_IS_DIR_ROLE = Qt.ItemDataRole.UserRole + 2
