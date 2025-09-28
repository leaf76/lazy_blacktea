"""Device list context menu management."""

from __future__ import annotations

from typing import Callable, Iterable, Optional, Sequence, TYPE_CHECKING

from PyQt6.QtWidgets import QMenu

from utils import common

if TYPE_CHECKING:  # pragma: no cover
    from lazy_blacktea_pyqt import WindowMain


logger = common.get_logger("device_list_context_menu")

MenuFactory = Callable[[object], QMenu]


class DeviceListContextMenuManager:
    """Build and display the device list context menu."""

    def __init__(self, window: "WindowMain", menu_factory: Optional[MenuFactory] = None) -> None:
        self.window = window
        self._menu_factory = menu_factory or (lambda parent: QMenu(parent))

    def create_context_menu(self) -> QMenu:
        menu = self._menu_factory(self.window)

        self._add_basic_actions(menu)
        self._add_group_section(menu)
        self._add_device_actions(menu)

        return menu

    def show_context_menu(self, position) -> None:
        menu = self.create_context_menu()
        table = getattr(self.window, 'device_table', None)
        anchor = table.viewport() if table is not None else self.window
        global_pos = anchor.mapToGlobal(position)
        menu.exec(global_pos)

    # ------------------------------------------------------------------
    # Section builders
    # ------------------------------------------------------------------
    def _add_basic_actions(self, menu: QMenu) -> None:
        refresh_action = menu.addAction("Refresh")
        refresh_action.triggered.connect(self.window.device_manager.force_refresh)

        select_all_action = menu.addAction("Select All")
        select_all_action.triggered.connect(self.window.select_all_devices)

        clear_all_action = menu.addAction("Clear All")
        clear_all_action.triggered.connect(self.window.select_no_devices)

        copy_info_action = menu.addAction("Copy Selected Device Info")
        copy_info_action.triggered.connect(self.window.copy_selected_device_info)

        menu.addSeparator()

    def _add_group_section(self, menu: QMenu) -> None:
        device_groups = getattr(self.window, "device_groups", {}) or {}
        if device_groups:
            group_menu = menu.addMenu("Select Group")
            for group_name in sorted(device_groups.keys()):
                action = group_menu.addAction(group_name)
                action.triggered.connect(
                    lambda checked=False, name=group_name: self.window.select_devices_in_group_by_name(name)
                )
        else:
            placeholder = menu.addAction("Select Group")
            placeholder.setEnabled(False)
            placeholder.setText("No groups available")

        menu.addSeparator()

    def _add_device_actions(self, menu: QMenu) -> None:
        checked_devices = self.window.get_checked_devices()
        if not checked_devices:
            return

        reboot_action = menu.addAction("Reboot Selected")
        reboot_action.triggered.connect(self.window.reboot_device)

        enable_bt_action = menu.addAction("Enable Bluetooth")
        enable_bt_action.triggered.connect(self.window.enable_bluetooth)

        disable_bt_action = menu.addAction("Disable Bluetooth")
        disable_bt_action.triggered.connect(self.window.disable_bluetooth)


__all__ = ["DeviceListContextMenuManager"]
