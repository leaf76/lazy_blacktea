"""Encapsulates device group operations for the main window."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Sequence, Set, Tuple, TYPE_CHECKING

from PyQt6.QtWidgets import QMessageBox

from utils import common

logger = common.get_logger("lazy_blacktea")

if TYPE_CHECKING:  # pragma: no cover - imported only for typing hints
    from lazy_blacktea_pyqt import WindowMain


@dataclass(frozen=True)
class DeviceGroupSelection:
    """Utility to classify serials that can be selected vs. missing."""

    available_checkboxes: Set[str]
    available_device_serials: Set[str]

    def classify(self, serials: Sequence[str], use_device_dict: bool) -> Tuple[List[str], List[str]]:
        reference = self.available_device_serials if use_device_dict else self.available_checkboxes
        connected = [serial for serial in serials if serial in reference]
        missing = [serial for serial in serials if serial not in reference]
        return connected, missing


class DeviceGroupManager:
    """Manage lifecycle of device groups and related UI interactions."""

    def __init__(self, window: "WindowMain") -> None:
        self.window = window

    def save_group(self) -> None:
        group_name = self.window.group_name_edit.text().strip()
        if not group_name:
            self.window.error_handler.show_error("Error", "Group name cannot be empty.")
            return

        checked_devices = self.window.get_checked_devices()
        if not checked_devices:
            self.window.error_handler.show_warning("Warning", "No devices selected to save in the group.")
            return

        if group_name in self.window.device_groups:
            reply = QMessageBox.question(
                self.window,
                "Confirm",
                f"Group '{group_name}' already exists. Do you want to overwrite it?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return

        serial_numbers = [device.device_serial_num for device in checked_devices]
        self.window.device_groups[group_name] = serial_numbers

        self.window.show_info(
            "Success",
            f"Group '{group_name}' saved with {len(serial_numbers)} devices.",
        )
        self.update_groups_listbox()
        logger.info("Saved group '%s' with devices: %s", group_name, serial_numbers)

    def delete_group(self) -> None:
        current_item = self.window.groups_listbox.currentItem()
        if not current_item:
            self.window.show_error("Error", "No group selected to delete.")
            return

        group_name = current_item.text()
        reply = QMessageBox.question(
            self.window,
            "Confirm",
            f"Are you sure you want to delete group '{group_name}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )

        if reply != QMessageBox.StandardButton.Yes:
            return

        if group_name in self.window.device_groups:
            del self.window.device_groups[group_name]
            logger.info("Group '%s' deleted.", group_name)
            self.update_groups_listbox()
            self.window.group_name_edit.clear()

    def select_devices_in_group(self) -> None:
        current_item = self.window.groups_listbox.currentItem()
        if not current_item:
            self.window.show_error("Error", "No group selected.")
            return

        self.select_devices_in_group_by_name(current_item.text())

    def select_devices_in_group_by_name(self, group_name: str) -> None:
        serials_in_group = self.window.device_groups.get(group_name, [])
        if not serials_in_group:
            logger.info("Group '%s' is empty.", group_name)
            return

        self.window.select_no_devices()

        selection = DeviceGroupSelection(
            available_checkboxes=set(self.window.check_devices.keys()),
            available_device_serials=set(self.window.device_dict.keys()),
        )

        if self.window.virtualized_active and self.window.virtualized_device_list is not None:
            connected, missing = selection.classify(serials_in_group, use_device_dict=True)
            self.window.virtualized_device_list.set_checked_serials(set(connected))
            connected_devices = len(connected)
        else:
            connected, missing = selection.classify(serials_in_group, use_device_dict=False)
            for serial in connected:
                checkbox = self.window.check_devices.get(serial)
                if checkbox is not None:
                    checkbox.setChecked(True)
            connected_devices = len(connected)

        if missing:
            self.window.show_info(
                "Info",
                f"The following devices from group '{group_name}' are not currently connected:\n" + "\n".join(missing),
            )

        logger.info("Selected %s devices in group '%s'.", connected_devices, group_name)

    def update_groups_listbox(self) -> None:
        self.window.groups_listbox.clear()
        for group_name in sorted(self.window.device_groups.keys()):
            self.window.groups_listbox.addItem(group_name)

    def on_group_select(self) -> None:
        current_item = self.window.groups_listbox.currentItem()
        if current_item:
            self.window.group_name_edit.setText(current_item.text())


__all__ = ["DeviceGroupManager", "DeviceGroupSelection"]
