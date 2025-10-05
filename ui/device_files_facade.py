"""Facade for device file browser and preview interactions.

This consolidates thin delegations from the main window to `DeviceFileController`
so that UI logic and state synchronization stay in one place.
"""

from __future__ import annotations

from typing import Optional, TYPE_CHECKING

from PyQt6.QtCore import QPoint
from PyQt6.QtWidgets import QTreeWidgetItem

if TYPE_CHECKING:  # pragma: no cover
    from ui.main_window import WindowMain
    from ui.device_file_controller import DeviceFileController
    from ui.device_file_preview_window import DeviceFilePreviewWindow


class DeviceFilesFacade:
    """Facade that delegates device file interactions to the controller.

    Keeps `WindowMain` lean and centralizes synchronization of UI state such as
    `device_file_browser_current_serial` and `device_file_browser_current_path`.
    """

    def __init__(self, window: "WindowMain", controller: "DeviceFileController") -> None:
        self.window = window
        self.controller = controller

    # Status helpers
    def set_status(self, message: str) -> None:
        self.controller.set_status(message)

    # Navigation and refresh
    def refresh_browser(self, path: Optional[str] = None) -> None:
        self.controller.refresh_browser(path)
        # Keep main window snapshot in sync
        self.window.device_file_browser_current_serial = self.controller.current_serial
        self.window.device_file_browser_current_path = self.controller.current_path

    def navigate_up(self) -> None:
        self.controller.navigate_up()

    def navigate_to_path(self) -> None:
        self.controller.navigate_to_path()

    # Item interactions
    def handle_item_double_clicked(self, item: QTreeWidgetItem, column: int) -> None:
        self.controller.handle_item_double_clicked(item, column)

    def download_selected_files(self) -> None:
        self.controller.download_selected_files()

    def preview_selected_file(self, item: Optional[QTreeWidgetItem] = None) -> None:
        self.controller.preview_selected_file(item)

    # Preview handling
    def display_preview(self, local_path: str) -> None:
        self.controller.display_preview(local_path)

    def clear_preview(self) -> None:
        self.controller.clear_preview()

    def hide_preview_loading(self) -> None:
        self.controller.hide_preview_loading()

    def ensure_preview_window(self) -> "DeviceFilePreviewWindow":
        return self.controller.ensure_preview_window()

    def handle_preview_cleanup(self, local_path: str) -> None:
        self.controller.handle_preview_cleanup(local_path)

    def open_preview_externally(self) -> None:
        self.controller.open_preview_externally()

    def clear_preview_cache(self) -> None:
        self.controller.clear_preview_cache()

    # Misc actions
    def copy_path(self, item: Optional[QTreeWidgetItem] = None) -> None:
        self.controller.copy_path(item)

    def download_item(self, item: Optional[QTreeWidgetItem] = None) -> None:
        self.controller.download_item(item)

    def show_context_menu(self, position: QPoint) -> None:
        self.controller.show_context_menu(position)


__all__ = ["DeviceFilesFacade"]
