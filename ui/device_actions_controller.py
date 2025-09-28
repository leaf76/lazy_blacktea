"""Controller managing device-context actions and exports."""

from __future__ import annotations

import datetime
from typing import Dict, Optional, TYPE_CHECKING

from PyQt6.QtGui import QGuiApplication
from PyQt6.QtWidgets import QMenu

from utils import common
from ui.style_manager import StyleManager

if TYPE_CHECKING:  # pragma: no cover
    from lazy_blacktea_pyqt import WindowMain


logger = common.get_logger('lazy_blacktea')


class DeviceActionsController:
    """Encapsulates context menu interactions and device info exports."""

    def __init__(self, main_window: "WindowMain") -> None:
        self.window = main_window

    # ------------------------------------------------------------------
    # Context menu and selection helpers
    # ------------------------------------------------------------------
    def show_context_menu(self, position, device_serial: str, checkbox_widget) -> None:
        if device_serial not in self.window.device_dict:
            return

        device = self.window.device_dict[device_serial]
        context_menu = QMenu(self.window)
        context_menu.setStyleSheet(StyleManager.get_menu_style())

        device_name = f'📱 {device.device_model} ({device_serial[:8]}...)'
        header_action = context_menu.addAction(device_name)
        header_action.setEnabled(False)
        context_menu.addSeparator()

        select_only_action = context_menu.addAction('✅ Select Only This Device')
        select_only_action.triggered.connect(lambda: self.select_only_device(device_serial))

        deselect_action = context_menu.addAction('❌ Deselect This Device')
        deselect_action.triggered.connect(lambda: self.deselect_device(device_serial))

        view_logcat_action = context_menu.addAction('👁️ View Logcat')
        view_logcat_action.triggered.connect(lambda: self.window.view_logcat_for_device(device_serial))

        context_menu.addSeparator()

        ui_inspector_action = context_menu.addAction('🔍 Launch UI Inspector')
        ui_inspector_action.triggered.connect(lambda: self.launch_ui_inspector_for_device(device_serial))
        context_menu.addSeparator()

        reboot_action = context_menu.addAction('🔄 Reboot Device')
        reboot_action.triggered.connect(lambda: self.reboot_single_device(device_serial))

        screenshot_action = context_menu.addAction('📷 Take Screenshot')
        screenshot_action.triggered.connect(lambda: self.take_screenshot_single_device(device_serial))

        scrcpy_action = context_menu.addAction('🖥️ Mirror Device (scrcpy)')
        scrcpy_action.triggered.connect(lambda: self.launch_scrcpy_single_device(device_serial))

        context_menu.addSeparator()

        copy_info_action = context_menu.addAction('📋 Copy Device Info')
        copy_info_action.triggered.connect(lambda: self.copy_single_device_info(device_serial))

        details_action = context_menu.addAction('ℹ️ Device Details')
        details_action.triggered.connect(lambda: self.window.show_device_details(device_serial))

        global_pos = checkbox_widget.mapToGlobal(position)
        context_menu.exec(global_pos)

    def select_only_device(self, target_serial: str) -> None:
        self.window.device_list_controller._set_selection([target_serial])

    def deselect_device(self, target_serial: str) -> None:
        current = set(self.window.device_selection_manager.get_selected_serials())
        if target_serial in current:
            current.discard(target_serial)
        self.window.device_list_controller._set_selection(current)

    def launch_ui_inspector_for_device(self, device_serial: str) -> None:
        self._with_temporary_selection(device_serial, self.window.launch_ui_inspector)

    def reboot_single_device(self, device_serial: str) -> None:
        self._with_temporary_selection(device_serial, self.window.reboot_device)

    def take_screenshot_single_device(self, device_serial: str) -> None:
        self._with_temporary_selection(device_serial, self.window.take_screenshot)

    def launch_scrcpy_single_device(self, device_serial: str) -> None:
        self.window.app_management_manager.launch_scrcpy_for_device(device_serial)

    def copy_single_device_info(self, device_serial: str) -> None:
        device = self.window.device_dict.get(device_serial)
        if not device:
            return

        status_helper = self.window.device_list_controller.get_on_off_status
        device_info = f'''Device Information:
Model: {device.device_model}
Serial: {device.device_serial_num}
Android Version: {device.android_ver if device.android_ver else 'Unknown'} (API Level {device.android_api_level if device.android_api_level else 'Unknown'})
GMS Version: {device.gms_version if device.gms_version else 'Unknown'}
Product: {device.device_prod}
USB: {device.device_usb}
WiFi Status: {status_helper(device.wifi_is_on)}
Bluetooth Status: {status_helper(device.bt_is_on)}
Audio State: {device.audio_state or 'Unknown'}
Bluetooth Manager: {device.bluetooth_manager_state or 'Unknown'}
Build Fingerprint: {device.build_fingerprint}'''

        try:
            clipboard = QGuiApplication.clipboard()
            clipboard.setText(device_info)
            self.window.show_info('📋 Copied!', f'Device information copied to clipboard for:\n{device.device_model}')
            logger.info('📋 Copied device info to clipboard: %s', device_serial)
        except Exception as exc:
            logger.error('❌ Failed to copy device info to clipboard: %s', exc)
            self.window.show_error('Error', f'Could not copy to clipboard:\n{exc}')

    def copy_selected_device_info(self) -> None:
        checked_devices = self.window.get_checked_devices()
        if not checked_devices:
            self.window.error_handler.show_info('Info', 'No devices selected.')
            return

        device_info_sections = []
        status_helper = self.window.device_list_controller.get_on_off_status

        for index, device in enumerate(checked_devices, start=1):
            section = [
                f'Device #{index}',
                '==================================================',
                'BASIC INFORMATION:',
                f'Model: {device.device_model}',
                f'Serial Number: {device.device_serial_num}',
                f'Product: {device.device_prod}',
                f'USB: {device.device_usb}',
                '',
                'SYSTEM INFORMATION:',
                f'Android Version: {device.android_ver if device.android_ver else "Unknown"}',
                f'API Level: {device.android_api_level if device.android_api_level else "Unknown"}',
                f'GMS Version: {device.gms_version if device.gms_version else "Unknown"}',
                f'Build Fingerprint: {device.build_fingerprint if device.build_fingerprint else "Unknown"}',
                '',
                'CONNECTIVITY:',
                f'WiFi Status: {status_helper(device.wifi_is_on)}',
                f'Bluetooth Status: {status_helper(device.bt_is_on)}',
                f'Audio State: {device.audio_state or "Unknown"}',
                f'Bluetooth Manager: {device.bluetooth_manager_state or "Unknown"}',
                '',
            ]

            try:
                additional_info = self.window.device_list_controller.get_additional_device_info(device.device_serial_num)
                section.extend([
                    'HARDWARE INFORMATION:',
                    f'Screen Size: {additional_info.get("screen_size", "Unknown")}',
                    f'Screen Density: {additional_info.get("screen_density", "Unknown")}',
                    f'CPU Architecture: {additional_info.get("cpu_arch", "Unknown")}',
                    '',
                    'BATTERY INFORMATION:',
                    f'Battery Level: {additional_info.get("battery_level", "Unknown")}',
                    f'Battery Capacity: {additional_info.get("battery_capacity_mah", "Unknown")}',
                    f'Battery mAs: {additional_info.get("battery_mas", "Unknown")}',
                    f'Estimated DOU: {additional_info.get("battery_dou_hours", "Unknown")}',
                ])
            except Exception as exc:
                section.extend([
                    'HARDWARE INFORMATION:',
                    'Hardware information unavailable',
                ])
                logger.warning('Could not retrieve hardware info for %s: %s', device.device_serial_num, exc)

            device_info_sections.append('\n'.join(section))

        header = (
            'ANDROID DEVICE INFORMATION REPORT\n'
            f'Generated: {datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}\n'
            f'Total Devices: {len(checked_devices)}\n\n'
        )
        footer = '\n' + '=' * 50 + '\nReport generated by lazy blacktea PyQt6 version'
        full_info_text = header + '\n\n'.join(device_info_sections) + footer

        clipboard = QGuiApplication.clipboard()
        clipboard.setText(full_info_text)
        self.window.show_info(
            'Success',
            f'Copied comprehensive information for {len(checked_devices)} device(s) to clipboard.\n\n'
            'Information includes:\n• Basic device details\n• System information\n• Connectivity status\n• Hardware specifications'
        )
        logger.info('Copied comprehensive information for %s devices', len(checked_devices))

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _with_temporary_selection(self, device_serial: str, action) -> None:
        if device_serial not in self.window.device_dict:
            self.window.show_error('Error', f'Device {device_serial} not found.')
            return

        original_selections, active_serial = self._backup_device_selections()
        self.select_only_device(device_serial)
        try:
            action()
        finally:
            self._restore_device_selections(original_selections, active_serial)

    def _backup_device_selections(self) -> tuple[Dict[str, bool], Optional[str]]:
        if self.window.virtualized_active and self.window.virtualized_device_list is not None:
            selections = {serial: True for serial in self.window.virtualized_device_list.checked_devices}
            active = self.window.device_selection_manager.get_active_serial()
            return selections, active

        selections = {
            serial: checkbox.isChecked()
            for serial, checkbox in self.window.check_devices.items()
        }
        active = self.window.device_selection_manager.get_active_serial()
        return selections, active

    def _restore_device_selections(self, selections: Dict[str, bool], active_serial: Optional[str]) -> None:
        if self.window.virtualized_active and self.window.virtualized_device_list is not None:
            selected_serials = {serial for serial, is_checked in selections.items() if is_checked}
            self.window.virtualized_device_list.set_checked_serials(selected_serials)
            self.window.device_selection_manager.set_active_serial(active_serial)
            self.window.device_list_controller.update_selection_count()
            return

        for serial, checkbox in self.window.check_devices.items():
            if serial in selections:
                checkbox.setChecked(selections[serial])

        self.window.device_selection_manager.set_active_serial(active_serial)
        self.window.device_list_controller.update_selection_count()


__all__ = ["DeviceActionsController"]
