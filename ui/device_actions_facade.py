"""Facade for device-specific actions exposed by the main window.

This avoids duplicating controller delegation code in `WindowMain` and keeps
the public API identical.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # pragma: no cover
    from ui.main_window import WindowMain


class DeviceActionsFacade:
    def __init__(self, window: "WindowMain") -> None:
        self.window = window

    # Context menu
    def show_context_menu(self, position: Any, device_serial: str, checkbox_widget: Any) -> None:
        self.window.device_actions_controller.show_context_menu(position, device_serial, checkbox_widget)

    # Selection helpers
    def select_only_device(self, target_serial: str) -> None:
        self.window.device_actions_controller.select_only_device(target_serial)

    def deselect_device(self, target_serial: str) -> None:
        self.window.device_actions_controller.deselect_device(target_serial)

    # Info and utilities
    def copy_selected_device_info(self) -> None:
        self.window.device_actions_controller.copy_selected_device_info()

    def copy_single_device_info(self, device_serial: str) -> None:
        self.window.device_actions_controller.copy_single_device_info(device_serial)

    # Single-device operations
    def reboot_single_device(self, device_serial: str) -> None:
        self.window.device_actions_controller.reboot_single_device(device_serial)

    def take_screenshot_single_device(self, device_serial: str) -> None:
        self.window.device_actions_controller.take_screenshot_single_device(device_serial)

    def launch_scrcpy_single_device(self, device_serial: str) -> None:
        self.window.device_actions_controller.launch_scrcpy_single_device(device_serial)

    def launch_ui_inspector_for_device(self, device_serial: str) -> None:
        self.window.device_actions_controller.launch_ui_inspector_for_device(device_serial)


__all__ = ["DeviceActionsFacade"]
