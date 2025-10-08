"""Device list context menu management."""

from __future__ import annotations

from typing import Callable, Iterable, Optional, Sequence, TYPE_CHECKING

from PyQt6.QtWidgets import QMenu
from PyQt6.QtCore import QPoint

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
        """Show context menu at a global position, resolving anchor defensively.

        Accepts either a QPoint or a tuple-like (x, y) position for easier testing.
        """
        menu = self.create_context_menu()

        # Prefer the device table's viewport when available
        table = getattr(self.window, 'device_table', None)
        if table is not None and hasattr(table, 'viewport'):
            anchor = table.viewport()
        else:
            # Fallback to an optional scroll/viewport shim used in tests
            anchor = getattr(self.window, 'device_scroll', self.window)

        # Map to global if supported; pass through raw tuple for test doubles
        if hasattr(anchor, 'mapToGlobal'):
            global_pos = anchor.mapToGlobal(position)
        else:
            # Normalise position to QPoint if a tuple was provided
            if not isinstance(position, QPoint):
                try:
                    x, y = position  # type: ignore[misc]
                    position = QPoint(int(x), int(y))
                except Exception:
                    position = QPoint(0, 0)
            global_pos = position
        menu.exec(global_pos)

    # ------------------------------------------------------------------
    # Section builders
    # ------------------------------------------------------------------
    def _add_basic_actions(self, menu: QMenu) -> None:
        refresh_action = menu.addAction("Refresh")
        refresh_action.triggered.connect(self.window.device_manager.force_refresh)

        # Adapt label and handler depending on selection mode
        selection_mgr = getattr(self.window, 'device_selection_manager', None)
        if selection_mgr is not None and selection_mgr.is_single_selection():
            select_all_action = menu.addAction("Select Last Visible")
            # Prefer context-aware handler if available
            if hasattr(self.window, 'handle_select_all_action'):
                select_all_action.triggered.connect(self.window.handle_select_all_action)
            else:
                # Fallback directly to controller method
                select_all_action.triggered.connect(self.window.device_list_controller.select_last_visible_device)
            if hasattr(select_all_action, 'setToolTip'):
                select_all_action.setToolTip('Select the last visible device (single-select mode)')
        else:
            select_all_action = menu.addAction("Select All")
            if hasattr(self.window, 'handle_select_all_action'):
                select_all_action.triggered.connect(self.window.handle_select_all_action)
            else:
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
