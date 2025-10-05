"""Facade wrapping device group operations used by the main window.

This wrapper preserves the existing `WindowMain` public API while keeping the
implementation details within a dedicated module.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    from ui.main_window import WindowMain


class DeviceGroupsFacade:
    """Simple pass-through facade for group management actions."""

    def __init__(self, window: "WindowMain") -> None:
        self.window = window

    def save_group(self) -> None:
        self.window.device_group_manager.save_group()

    def delete_group(self) -> None:
        self.window.device_group_manager.delete_group()

    def select_devices_in_group(self) -> None:
        self.window.device_group_manager.select_devices_in_group()

    def select_devices_in_group_by_name(self, group_name: str) -> None:
        self.window.device_group_manager.select_devices_in_group_by_name(group_name)

    def update_groups_listbox(self) -> None:
        self.window.device_group_manager.update_groups_listbox()

    def on_group_select(self) -> None:
        self.window.device_group_manager.on_group_select()


__all__ = ["DeviceGroupsFacade"]
