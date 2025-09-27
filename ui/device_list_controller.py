"""Controller responsible for device list rendering logic."""

from __future__ import annotations

from typing import Dict, Iterable, List, Optional, TYPE_CHECKING

from PyQt6.QtCore import Qt, QTimer, QPoint
from PyQt6.QtGui import QCursor, QFont
from PyQt6.QtWidgets import QCheckBox, QToolTip

from utils import adb_models, adb_tools, common
from ui.style_manager import StyleManager
from ui.optimized_device_list import DeviceListPerformanceOptimizer

if TYPE_CHECKING:  # pragma: no cover
    from lazy_blacktea_pyqt import WindowMain


logger = common.get_logger('lazy_blacktea')


class DeviceListController:
    """Encapsulates device list updates to keep the main window lean."""

    def __init__(self, main_window: "WindowMain") -> None:
        self.window = main_window

    # ------------------------------------------------------------------
    # Public API used by WindowMain
    # ------------------------------------------------------------------
    def update_device_list(self, device_dict: Dict[str, adb_models.DeviceInfo]) -> None:
        """Update the device list display with performance optimisations."""
        self.window.device_dict = device_dict

        device_count = len(device_dict)
        if DeviceListPerformanceOptimizer.should_use_virtualization(device_count):
            preserved_serials = set(self._get_current_checked_serials())
            self._activate_virtualized_view(preserved_serials)
            if self.window.virtualized_device_list is not None:
                vlist = self.window.virtualized_device_list
                vlist.update_device_list(device_dict)
                vlist.set_checked_serials(preserved_serials)
                vlist.apply_search_and_sort()
            self._update_virtualized_title()
            self.window.update_selection_count()
            return

        self._deactivate_virtualized_view()

        if device_count > 5:
            logger.debug('Updating %s devices using optimized mode', device_count)
            self._update_device_list_optimized(device_dict)
            return

        logger.debug('Updating %s devices using standard mode', device_count)
        self._perform_standard_device_update(device_dict)

    def select_all_devices(self) -> None:
        """Select every device, respecting virtualized list state."""
        if self.window.virtualized_active and self.window.virtualized_device_list is not None:
            self.window.virtualized_device_list.select_all_devices()
            logger.info('Selected all devices (virtualized)')
            return

        for checkbox in self.window.check_devices.values():
            checkbox.setChecked(True)
        logger.info('Selected all %s devices', len(self.window.check_devices))

    def select_no_devices(self) -> None:
        """Deselect all devices, handling virtualized lists."""
        if self.window.virtualized_active and self.window.virtualized_device_list is not None:
            self.window.virtualized_device_list.deselect_all_devices()
            logger.info('Deselected all devices (virtualized)')
            return

        for checkbox in self.window.check_devices.values():
            checkbox.setChecked(False)
        logger.info('Deselected all devices')

    def update_selection_count(self) -> None:
        """Refresh device count title according to current selection/search."""
        if self.window.virtualized_active and self.window.virtualized_device_list is not None:
            self._update_virtualized_title()
            return

        device_count = len(self.window.device_dict)
        selected_count = len(self.window.get_checked_devices())
        search_text = self.window.device_search_manager.get_search_text()
        if search_text:
            visible_count = sum(
                1 for checkbox in self.window.check_devices.values() if checkbox.isVisible()
            )
            self.window.title_label.setText(
                f'Connected Devices ({visible_count}/{device_count}) - Selected: {selected_count}'
            )
        else:
            self.window.title_label.setText(
                f'Connected Devices ({device_count}) - Selected: {selected_count}'
            )

    def filter_and_sort_devices(self) -> None:
        """Filter and sort devices based on current search and sort settings."""
        if self.window.virtualized_active and self.window.virtualized_device_list is not None:
            self.window.virtualized_device_list.apply_search_and_sort()
            self._update_virtualized_title()
            return

        if not hasattr(self.window, 'device_layout'):
            return

        devices = list(self.window.device_dict.values())
        sorted_devices = self.window.device_search_manager.search_and_sort_devices(
            devices,
            self.window.device_search_manager.get_search_text(),
            self.window.device_search_manager.get_sort_mode(),
        )

        device_items = []
        for device in sorted_devices:
            serial = device.device_serial_num
            if serial in self.window.check_devices:
                checkbox = self.window.check_devices[serial]
                device_items.append((serial, device, checkbox))

        visible_serials = set()
        for i, (serial, _device, checkbox) in enumerate(device_items):
            self.window.device_layout.removeWidget(checkbox)
            self.window.device_layout.insertWidget(i, checkbox)
            checkbox.setVisible(True)
            visible_serials.add(serial)

        for serial, checkbox in self.window.check_devices.items():
            if serial not in visible_serials:
                checkbox.setVisible(False)

        visible_count = len(device_items)
        total_count = len(self.window.device_dict)
        if hasattr(self.window, 'title_label'):
            search_text = self.window.device_search_manager.get_search_text()
            if search_text:
                self.window.title_label.setText(
                    f'Connected Devices ({visible_count}/{total_count})'
                )
            else:
                self.window.title_label.setText(f'Connected Devices ({total_count})')

    def on_search_changed(self, text: str) -> None:
        """Handle search text change."""
        self.window.device_search_manager.set_search_text(text.strip())
        self.filter_and_sort_devices()

    def on_sort_changed(self, sort_mode: str) -> None:
        """Handle sort mode change."""
        self.window.device_search_manager.set_sort_mode(sort_mode)
        self.filter_and_sort_devices()

    def handle_virtualized_selection_change(self, serial: str, is_checked: bool) -> None:
        """Synchronize UI state after a virtualized checkbox toggle."""
        if not self.window.virtualized_active:
            return

        checkbox = self.window.check_devices.get(serial)
        if checkbox is not None and checkbox.isChecked() != is_checked:
            checkbox.blockSignals(True)
            checkbox.setChecked(is_checked)
            checkbox.blockSignals(False)

        self._update_virtualized_title()

    def acquire_device_checkbox(self) -> QCheckBox:
        """Fetch a checkbox from the shared pool or create a new one."""
        checkbox = (
            self.window.checkbox_pool.pop()
            if self.window.checkbox_pool
            else QCheckBox()
        )

        try:
            checkbox.stateChanged.disconnect()
        except TypeError:
            pass

        try:
            checkbox.customContextMenuRequested.disconnect()
        except TypeError:
            pass

        checkbox.enterEvent = lambda event, cb=checkbox: QCheckBox.enterEvent(cb, event)
        checkbox.leaveEvent = lambda event, cb=checkbox: QCheckBox.leaveEvent(cb, event)
        checkbox.show()
        return checkbox

    def release_device_checkbox(self, checkbox: QCheckBox) -> None:
        """Recycle checkbox widgets to reduce churn during list updates."""
        checkbox.blockSignals(True)
        checkbox.setChecked(False)
        checkbox.blockSignals(False)
        checkbox.hide()

        try:
            checkbox.stateChanged.disconnect()
        except TypeError:
            pass

        try:
            checkbox.customContextMenuRequested.disconnect()
        except TypeError:
            pass

        checkbox.enterEvent = lambda event, cb=checkbox: QCheckBox.enterEvent(cb, event)
        checkbox.leaveEvent = lambda event, cb=checkbox: QCheckBox.leaveEvent(cb, event)
        checkbox.setParent(None)
        self.window.checkbox_pool.append(checkbox)

    # ------------------------------------------------------------------
    # Internal helpers mirrored from the main window implementation
    # ------------------------------------------------------------------
    def _update_device_list_optimized(self, device_dict: Dict[str, adb_models.DeviceInfo]) -> None:
        if hasattr(self.window, '_update_timer') and self.window._update_timer.isActive():
            self.window._update_timer.stop()

        self.window._update_timer = QTimer()
        self.window._update_timer.setSingleShot(True)
        self.window._update_timer.timeout.connect(
            lambda: self._perform_batch_device_update(device_dict)
        )
        self.window._update_timer.start(5)

    def _perform_batch_device_update(self, device_dict: Dict[str, adb_models.DeviceInfo]) -> None:
        try:
            self.window.device_scroll.setUpdatesEnabled(False)
            checked_serials = self._get_current_checked_serials()

            current_serials = set(self.window.check_devices.keys())
            new_serials = set(device_dict.keys())

            self._batch_remove_devices(current_serials - new_serials)
            self._batch_add_devices(new_serials - current_serials, device_dict, checked_serials)
            self._batch_update_existing(current_serials & new_serials, device_dict)
        finally:
            self.window.device_scroll.setUpdatesEnabled(True)
            self.window.device_scroll.update()
            self.filter_and_sort_devices()
            logger.debug('Batch device update completed: %s devices', len(device_dict))

    def _batch_remove_devices(self, devices_to_remove: Iterable[str]) -> None:
        for serial in devices_to_remove:
            if serial in self.window.check_devices:
                checkbox = self.window.check_devices[serial]
                self.window.device_layout.removeWidget(checkbox)
                self.release_device_checkbox(checkbox)
                del self.window.check_devices[serial]

    def _batch_add_devices(
        self,
        devices_to_add: Iterable[str],
        device_dict: Dict[str, adb_models.DeviceInfo],
        checked_serials: Iterable[str],
    ) -> None:
        devices_list = list(devices_to_add)
        batch_size = max(
            1,
            DeviceListPerformanceOptimizer.calculate_batch_size(len(device_dict)),
        )

        def process_device_batch(start_idx: int) -> None:
            end_idx = min(start_idx + batch_size, len(devices_list))

            for idx in range(start_idx, end_idx):
                serial = devices_list[idx]
                if serial in device_dict:
                    self._create_single_device_ui(
                        serial,
                        device_dict[serial],
                        checked_serials,
                    )

            if end_idx < len(devices_list):
                QTimer.singleShot(2, lambda: process_device_batch(end_idx))

        if devices_list:
            process_device_batch(0)

    def _get_filtered_sorted_devices(
        self, device_dict: Optional[Dict[str, adb_models.DeviceInfo]] = None
    ) -> List[adb_models.DeviceInfo]:
        source = list((device_dict or self.window.device_dict).values())
        return self.window.device_search_manager.search_and_sort_devices(
            source,
            self.window.device_search_manager.get_search_text(),
            self.window.device_search_manager.get_sort_mode(),
        )

    def _build_device_display_text(self, device: adb_models.DeviceInfo, serial: str) -> str:
        operation_status = self.get_device_operation_status(serial)
        recording_status = self.get_device_recording_status(serial)

        android_ver = device.android_ver or 'Unknown'
        android_api = device.android_api_level or 'Unknown'
        gms_display = device.gms_version if device.gms_version and device.gms_version != 'N/A' else 'N/A'

        wifi_status = self.get_on_off_status(device.wifi_is_on)
        bt_status = self.get_on_off_status(device.bt_is_on)

        return (
            f'{operation_status}{recording_status}📱 {device.device_model:<20} | '
            f'🆔 {device.device_serial_num:<20} | '
            f'🤖 Android {android_ver:<7} (API {android_api:<7}) | '
            f'🎯 GMS: {gms_display:<12} | '
            f'📶 WiFi: {wifi_status:<3} | '
            f'🔵 BT: {bt_status}'
        )

    def _apply_checkbox_content(self, checkbox: QCheckBox, serial: str, device: adb_models.DeviceInfo) -> None:
        checkbox.setText(self._build_device_display_text(device, serial))
        tooltip_text = self._create_device_tooltip(device, serial)
        checkbox.enterEvent = lambda event, txt=tooltip_text, cb=checkbox: self._show_custom_tooltip(cb, txt)
        checkbox.leaveEvent = lambda event: QToolTip.hideText()

    def _configure_device_checkbox(
        self,
        checkbox: QCheckBox,
        serial: str,
        device: adb_models.DeviceInfo,
        checked_serials: Iterable[str],
    ) -> None:
        checked_set = set(checked_serials)
        checkbox.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        checkbox.customContextMenuRequested.connect(
            lambda pos, s=serial, cb=checkbox: self.window.device_actions_controller.show_context_menu(pos, s, cb)
        )
        checkbox.setFont(QFont('Segoe UI', 10))
        self._apply_device_checkbox_style(checkbox)
        self._apply_checkbox_content(checkbox, serial, device)

        is_checked = serial in checked_set
        checkbox.blockSignals(True)
        checkbox.setChecked(is_checked)
        checkbox.blockSignals(False)

        checkbox.stateChanged.connect(self.window.update_selection_count)
        checkbox.stateChanged.connect(
            lambda state, cb=checkbox: self._update_checkbox_visual_state(cb, state)
        )

    def _initialize_virtualized_checkbox(
        self,
        checkbox: QCheckBox,
        serial: str,
        device: adb_models.DeviceInfo,
        checked_serials: Iterable[str],
    ) -> None:
        self._configure_device_checkbox(checkbox, serial, device, checked_serials)

    def _get_current_checked_serials(self) -> set:
        if self.window.virtualized_active and self.window.virtualized_device_list is not None:
            return set(self.window.virtualized_device_list.checked_devices)

        selected = {serial for serial, cb in self.window.check_devices.items() if cb.isChecked()}
        if selected:
            self.window.pending_checked_serials = set(selected)
            return selected
        return set(self.window.pending_checked_serials)

    def _release_all_standard_checkboxes(self) -> None:
        for serial, checkbox in list(self.window.check_devices.items()):
            if isinstance(checkbox, QCheckBox):
                self.window.device_layout.removeWidget(checkbox)
                self.release_device_checkbox(checkbox)
        self.window.check_devices.clear()

    def _activate_virtualized_view(self, checked_serials: Optional[Iterable[str]] = None) -> None:
        if self.window.virtualized_device_list is None or self.window.virtualized_active:
            return

        preserved_serials = set(checked_serials or [])
        self.window.pending_checked_serials = set(preserved_serials)

        self._release_all_standard_checkboxes()

        current_widget = self.window.device_scroll.takeWidget()
        if current_widget is not None and current_widget is not self.window.virtualized_widget:
            self.window.standard_device_widget = current_widget

        if self.window.virtualized_widget.parent() is not None:
            self.window.virtualized_widget.setParent(None)
        self.window.device_scroll.setWidget(self.window.virtualized_widget)
        self.window.virtualized_active = True

    def _deactivate_virtualized_view(self) -> None:
        if not self.window.virtualized_active:
            return

        if self.window.virtualized_device_list is not None:
            self.window.pending_checked_serials = set(self.window.virtualized_device_list.checked_devices)

        current_widget = self.window.device_scroll.takeWidget()
        if current_widget is not None and current_widget is self.window.virtualized_widget:
            self.window.virtualized_widget.setParent(None)

        if self.window.standard_device_widget is not None:
            self.window.device_scroll.setWidget(self.window.standard_device_widget)

        if self.window.virtualized_device_list is not None:
            self.window.virtualized_device_list.clear_widgets()

        self.window.virtualized_active = False

    def _update_virtualized_title(self) -> None:
        if not hasattr(self.window, 'title_label') or self.window.title_label is None:
            return

        total = len(self.window.device_dict)
        if self.window.virtualized_device_list:
            visible = len(self.window.virtualized_device_list.sorted_devices)
            selected = len(self.window.virtualized_device_list.checked_devices)
        else:
            visible = total
            selected = 0

        search_text = self.window.device_search_manager.get_search_text() if hasattr(self.window, 'device_search_manager') else ''

        if search_text:
            self.window.title_label.setText(f'Connected Devices ({visible}/{total}) - Selected: {selected}')
        else:
            self.window.title_label.setText(f'Connected Devices ({total}) - Selected: {selected}')

    def _create_single_device_ui(
        self,
        serial: str,
        device: adb_models.DeviceInfo,
        checked_serials: Iterable[str],
    ) -> None:
        checkbox = self.acquire_device_checkbox()
        self._configure_device_checkbox(checkbox, serial, device, checked_serials)

        self.window.check_devices[serial] = checkbox
        insert_index = self.window.device_layout.count() - 1
        self.window.device_layout.insertWidget(insert_index, checkbox)

    def _batch_update_existing(
        self,
        devices_to_update: Iterable[str],
        device_dict: Dict[str, adb_models.DeviceInfo],
    ) -> None:
        for serial in devices_to_update:
            if serial in self.window.check_devices and serial in device_dict:
                device = device_dict[serial]
                checkbox = self.window.check_devices[serial]
                self._apply_checkbox_content(checkbox, serial, device)

    def _perform_standard_device_update(self, device_dict: Dict[str, adb_models.DeviceInfo]) -> None:
        self.window.device_scroll.setUpdatesEnabled(False)

        checked_serials = self._get_current_checked_serials()
        current_serials = set(self.window.check_devices.keys())
        new_serials = set(device_dict.keys())

        for serial in current_serials - new_serials:
            if serial in self.window.check_devices:
                checkbox = self.window.check_devices[serial]
                self.window.device_layout.removeWidget(checkbox)
                self.release_device_checkbox(checkbox)
                del self.window.check_devices[serial]

        for serial in new_serials - current_serials:
            if serial in device_dict:
                device = device_dict[serial]
                self._create_standard_device_ui(serial, device, checked_serials)

        for serial in current_serials & new_serials:
            if serial in self.window.check_devices and serial in device_dict:
                device = device_dict[serial]
                checkbox = self.window.check_devices[serial]
                self._apply_checkbox_content(checkbox, serial, device)

        self.window.device_scroll.setUpdatesEnabled(True)
        self.filter_and_sort_devices()

    def _create_standard_device_ui(
        self,
        serial: str,
        device: adb_models.DeviceInfo,
        checked_serials: Iterable[str],
    ) -> None:
        checkbox = self.acquire_device_checkbox()
        self._configure_device_checkbox(checkbox, serial, device, checked_serials)

        self.window.check_devices[serial] = checkbox
        insert_index = self.window.device_layout.count() - 1
        self.window.device_layout.insertWidget(insert_index, checkbox)

    def _update_device_checkbox_text(
        self, checkbox: QCheckBox, device: adb_models.DeviceInfo, serial: str
    ) -> None:
        self._apply_checkbox_content(checkbox, serial, device)

    # ------------------------------------------------------------------
    # Shared formatting helpers
    # ------------------------------------------------------------------
    def get_on_off_status(self, status) -> str:
        if status is None or status == 'None':
            return 'Unknown'
        return 'On' if status else 'Off'

    def get_device_operation_status(self, serial: str) -> str:
        operation = self.window.device_operations.get(serial)
        if operation:
            return f'⚙️ {operation.upper()} | '
        return ''

    def get_device_recording_status(self, serial: str) -> str:
        record_info = self.window.device_recordings.get(serial)
        if record_info and record_info.get('active', False):
            return '🔴 REC | '
        return ''

    def _create_device_tooltip(self, device: adb_models.DeviceInfo, serial: str) -> str:
        base_tooltip = (
            f'📱 Device Information\n'
            f'━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n'
            f'Model: {device.device_model}\n'
            f'Serial: {device.device_serial_num}\n'
            f'Android: {device.android_ver if device.android_ver else "Unknown"} '
            f'(API Level {device.android_api_level if device.android_api_level else "Unknown"})\n'
            f'GMS Version: {device.gms_version if device.gms_version else "Unknown"}\n'
            f'Product: {device.device_prod}\n'
            f'USB: {device.device_usb}\n'
            f'━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n'
            f'📡 Connectivity\n'
            f'WiFi: {self.get_on_off_status(device.wifi_is_on)}\n'
            f'Bluetooth: {self.get_on_off_status(device.bt_is_on)}\n'
            f'━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n'
            f'🔧 Build Information\n'
            f'Build Fingerprint: {(device.build_fingerprint[:50] + "...") if device.build_fingerprint else "Unknown"}'
        )

        try:
            additional_info = self._get_additional_device_info(serial)
            return base_tooltip + (
                f'\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n'
                f'🖥️ Hardware Information\n'
                f'Screen Size: {additional_info.get("screen_size", "Unknown")}\n'
                f'Screen Density: {additional_info.get("screen_density", "Unknown")}\n'
                f'CPU Architecture: {additional_info.get("cpu_arch", "Unknown")}\n'
                f'━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n'
                f'🔋 Battery Information\n'
                f'Battery Level: {additional_info.get("battery_level", "Unknown")}\n'
                f'Battery Capacity: {additional_info.get("battery_capacity_mah", "Unknown")}\n'
                f'Battery mAs: {additional_info.get("battery_mas", "Unknown")}\n'
                f'Estimated DOU: {additional_info.get("battery_dou_hours", "Unknown")}'
            )
        except Exception as exc:
            logger.debug('Failed to build extended tooltip for %s: %s', serial, exc)
            return base_tooltip

    def _get_additional_device_info(self, serial: str) -> Dict[str, str]:
        try:
            return adb_tools.get_additional_device_info(serial)
        except Exception as exc:
            logger.error('Error getting additional device info for %s: %s', serial, exc)
            return {
                'screen_density': 'Unknown',
                'screen_size': 'Unknown',
                'battery_level': 'Unknown',
                'battery_capacity_mah': 'Unknown',
                'battery_mas': 'Unknown',
                'battery_dou_hours': 'Unknown',
                'cpu_arch': 'Unknown',
            }

    def _apply_device_checkbox_style(self, checkbox: QCheckBox) -> None:
        checkbox.setStyleSheet(StyleManager.get_checkbox_style())

    def _update_checkbox_visual_state(self, checkbox: QCheckBox, state: int) -> None:
        # Styling handled by stylesheet; method retained for potential future hooks.
        if state not in (0, 2):
            return

    def _show_custom_tooltip(self, widget: QCheckBox, tooltip_text: str) -> None:
        cursor_pos = QCursor.pos()
        tooltip_pos = QPoint(cursor_pos.x() + 5, cursor_pos.y() + 5)
        QToolTip.showText(tooltip_pos, tooltip_text, widget)

    def get_additional_device_info(self, serial: str) -> Dict[str, str]:
        return self._get_additional_device_info(serial)

    def create_device_tooltip(self, device: adb_models.DeviceInfo, serial: str) -> str:
        return self._create_device_tooltip(device, serial)


__all__ = ["DeviceListController"]
