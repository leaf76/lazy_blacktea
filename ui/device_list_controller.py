"""Controller responsible for device list rendering logic."""

from __future__ import annotations

from collections import OrderedDict
from typing import Dict, Iterable, List, Optional, Tuple, TYPE_CHECKING

from PyQt6.QtCore import QPoint, Qt
from PyQt6.QtWidgets import QStackedWidget

from utils import adb_models, adb_tools, common
from ui.device_table_widget import DeviceTableWidget
from ui.components.expandable_device_list import ExpandableDeviceList

if TYPE_CHECKING:  # pragma: no cover
    from lazy_blacktea_pyqt import WindowMain


logger = common.get_logger('lazy_blacktea')


class _SelectionProxy:
    """Compatibility proxy mimicking a QCheckBox interface for legacy code paths."""

    class _DummySignal:
        def __init__(self) -> None:
            self._callbacks = []

        def connect(self, callback):  # pragma: no cover - used by legacy hooks
            self._callbacks.append(callback)

        def emit(self, *args, **kwargs):  # pragma: no cover - reserved for future use
            for callback in self._callbacks:
                callback(*args, **kwargs)

    class _DummyStyle:
        def unpolish(self, _):  # pragma: no cover - no-op for compatibility
            return None

        def polish(self, _):  # pragma: no cover - no-op for compatibility
            return None

    def __init__(self, controller: 'DeviceListController', serial: str) -> None:
        self._controller = controller
        self._serial = serial
        self._visible = True
        self.customContextMenuRequested = self._DummySignal()
        self._style = self._DummyStyle()

    # Qt-like API ------------------------------------------------------
    def isChecked(self) -> bool:
        selected = self._controller.window.device_selection_manager.get_selected_serials()
        return self._serial in selected

    def setChecked(self, value: bool) -> None:
        manager = self._controller.window.device_selection_manager
        selected = manager.get_selected_serials()
        if value and self._serial not in selected:
            selected.append(self._serial)
        elif not value and self._serial in selected:
            selected = [serial for serial in selected if serial != self._serial]
        self._controller._set_selection(selected)

    def blockSignals(self, *_args, **_kwargs) -> None:  # pragma: no cover - compatibility hook
        return None

    def hide(self) -> None:  # pragma: no cover - legacy compatibility
        self._visible = False

    def show(self) -> None:  # pragma: no cover - legacy compatibility
        self._visible = True

    def setVisible(self, value: bool) -> None:
        self._visible = bool(value)

    def isVisible(self) -> bool:
        return self._visible

    def setToolTip(self, *_args, **_kwargs) -> None:  # pragma: no cover - no-op
        return None

    def setFont(self, *_args, **_kwargs) -> None:  # pragma: no cover - no-op
        return None

    def setContextMenuPolicy(self, *_args, **_kwargs) -> None:  # pragma: no cover - no-op
        return None

    def style(self):  # pragma: no cover - compatibility shim
        return self._style

    def setProperty(self, *_args, **_kwargs) -> None:  # pragma: no cover
        return None

    def update(self) -> None:  # pragma: no cover - no-op
        return None

    # Compatibility hooks for legacy lambdas --------------------------
    def enterEvent(self, *_args, **_kwargs) -> None:  # pragma: no cover
        return None

    def leaveEvent(self, *_args, **_kwargs) -> None:  # pragma: no cover
        return None


class DeviceListController:
    """Encapsulates device list updates to keep the main window lean."""

    _SORT_MODE_BY_COLUMN: Dict[int, str] = {
        0: 'selected',
        1: 'name',
        2: 'serial',
        3: 'android',
        4: 'api',
        5: 'gms',
        6: 'wifi',
        7: 'bt',
    }

    def __init__(self, main_window: "WindowMain") -> None:
        self.window = main_window
        self.table: Optional[DeviceTableWidget] = None
        self.device_list: Optional[ExpandableDeviceList] = None
        self._syncing_selection = False
        self._captured_sort: Optional[tuple[int, Qt.SortOrder]] = None

        # Try to attach the new device list component
        device_list = getattr(main_window, 'device_list', None)
        if isinstance(device_list, ExpandableDeviceList):
            self.attach_device_list(device_list)

        # Legacy: attach table if available
        table = getattr(main_window, 'device_table', None)
        if isinstance(table, DeviceTableWidget):
            self.attach_table(table)

    # ------------------------------------------------------------------
    # Wiring helpers
    # ------------------------------------------------------------------
    def attach_table(self, table: DeviceTableWidget) -> None:
        """Attach a table instance and wire signals."""
        if self.table is table:
            return

        if self.table is not None:
            try:
                self.table.selection_toggled.disconnect(self._on_table_selection_toggled)
            except TypeError:  # pragma: no cover - safeguard
                pass
            try:
                self.table.horizontalHeader().sortIndicatorChanged.disconnect(self._on_sort_indicator_changed)
            except TypeError:  # pragma: no cover
                pass
            try:
                self.table.device_context_menu_requested.disconnect(self._on_table_device_context_menu)
            except TypeError:  # pragma: no cover
                pass

        self.table = table
        self.table.selection_toggled.connect(self._on_table_selection_toggled)
        self.table.horizontalHeader().sortIndicatorChanged.connect(self._on_sort_indicator_changed)
        self.table.device_context_menu_requested.connect(self._on_table_device_context_menu)
        self._captured_sort = self.table.get_sort_indicator()

    def attach_device_list(self, device_list: ExpandableDeviceList) -> None:
        """Attach the new expandable device list component."""
        if self.device_list is device_list:
            return

        if self.device_list is not None:
            try:
                self.device_list.selection_changed.disconnect(self._on_device_list_selection_changed)
            except TypeError:
                pass
            try:
                self.device_list.context_menu_requested.disconnect(self._on_device_list_context_menu)
            except TypeError:
                pass

        self.device_list = device_list
        self.device_list.selection_changed.connect(self._on_device_list_selection_changed)
        self.device_list.context_menu_requested.connect(self._on_device_list_context_menu)

    def _on_device_list_selection_changed(self, serials: List[str]) -> None:
        """Handle selection changes from the new device list."""
        if self._syncing_selection:
            return

        self.window.device_selection_manager.set_selected_serials(serials)
        active = serials[-1] if serials else None
        if active:
            self.window.device_selection_manager.set_active_serial(active)

        self.update_selection_count()

    def _on_device_list_context_menu(self, position: QPoint, serial: str) -> None:
        """Handle context menu requests from the new device list."""
        if self.device_list is None:
            return
        self.window.show_device_context_menu(position, serial, self.device_list)

    # ------------------------------------------------------------------
    # Public API used by WindowMain
    # ------------------------------------------------------------------
    def update_device_list(self, device_dict: Dict[str, adb_models.DeviceInfo]) -> None:
        """Update the device list display with the current device dictionary."""
        self.window.device_dict = device_dict

        selected_serials = self.window.device_selection_manager.prune_selection(device_dict.keys())
        active_serial = self.window.device_selection_manager.get_active_serial()

        filtered_devices = self._get_filtered_sorted_devices(device_dict)

        # Update the new expandable device list
        if self.device_list is not None:
            self._syncing_selection = True
            try:
                self.device_list.update_devices(filtered_devices)
                self.device_list.set_selected_serials(selected_serials, active_serial)
            finally:
                self._syncing_selection = False

        # Legacy: Update table widget if attached
        if self.table is not None:
            sort_indicator = self._captured_sort or self.table.get_sort_indicator()
            self.table.update_devices(filtered_devices)
            self.table.restore_sort_indicator(*sort_indicator)
            self._synchronize_ui_selection(selected_serials, active_serial)

        self._refresh_check_devices()
        self._update_empty_state(len(device_dict), len(filtered_devices))
        self.update_selection_count()

    def select_all_devices(self) -> None:
        """Select every available device."""
        serials = list(self.window.device_dict.keys())
        if self.window.device_selection_manager.is_single_selection():
            # In single-select mode, keep only the last serial (stable order)
            keep = serials[-1:] if serials else []
            selected = self.window.device_selection_manager.set_selected_serials(keep)
        else:
            selected = self.window.device_selection_manager.set_selected_serials(serials)
        self._synchronize_ui_selection(selected, self.window.device_selection_manager.get_active_serial())
        self.update_selection_count()
        logger.info('Selected all %s devices', len(serials))

    def select_last_visible_device(self) -> None:
        """Select the last device in the currently visible (filtered/sorted) list."""
        devices = self._get_filtered_sorted_devices(self.window.device_dict)
        if not devices:
            logger.info('No visible devices to select')
            self._set_selection([])
            return
        last = devices[-1]
        serial = last.device_serial_num
        self._set_selection([serial], active_serial=serial)
        logger.info('Selected last visible device: %s', serial)

    def select_no_devices(self) -> None:
        """Clear selection state."""
        self.window.device_selection_manager.clear()
        self._synchronize_ui_selection([], None)
        self.update_selection_count()
        logger.info('Deselected all devices')

    def _set_selection(
        self,
        serials: Iterable[str],
        active_serial: Optional[str] = None,
    ) -> List[str]:
        """Programmatically replace the tracked selection."""
        serial_list = [serial for serial in serials if serial in self.window.device_dict]
        self.window.device_selection_manager.set_selected_serials(serial_list)
        if active_serial is not None:
            self.window.device_selection_manager.set_active_serial(active_serial)
        self._synchronize_ui_selection(serial_list, self.window.device_selection_manager.get_active_serial())
        self.update_selection_count()
        return serial_list

    def update_selection_count(self) -> None:
        """Refresh device count title according to current selection/search."""
        total_count = len(self.window.device_dict)
        selected_serials = self.window.device_selection_manager.get_selected_serials()
        selected_count = len(selected_serials)
        active_serial = self.window.device_selection_manager.get_active_serial()

        visible_count = self._visible_row_count()
        search_text = self.window.device_search_manager.get_search_text()

        # Build active device label
        if active_serial and active_serial in self.window.device_dict:
            device = self.window.device_dict[active_serial]
            active_label = f'{device.device_model} ({active_serial[:8]}...)'
        elif active_serial:
            active_label = active_serial
        else:
            active_label = 'None'

        # New compact title format: "X Devices • Y Selected"
        if search_text:
            title_text = f'{visible_count}/{total_count} Devices \u2022 {selected_count} Selected'
        else:
            title_text = f'{total_count} Devices \u2022 {selected_count} Selected'

        if hasattr(self.window, 'title_label') and self.window.title_label is not None:
            self.window.title_label.setText(title_text)

        # Update subtitle (new) or selection_summary_label (legacy)
        subtitle_text = f'Active: {active_label}'
        if hasattr(self.window, 'subtitle_label') and self.window.subtitle_label is not None:
            self.window.subtitle_label.setText(subtitle_text)

        if hasattr(self.window, 'selection_summary_label') and self.window.selection_summary_label is not None:
            # Legacy format for backward compatibility
            if self.window.selection_summary_label != getattr(self.window, 'subtitle_label', None):
                self.window.selection_summary_label.setText(
                    f'Selected {selected_count} of {total_count} \u00b7 Active: {active_label}'
                )

        # Update hint label according to selection mode
        if hasattr(self.window, 'selection_hint_label') and self.window.selection_hint_label is not None:
            if self.window.device_selection_manager.is_single_selection():
                hint_text = (
                    'Tip: Single-select mode is ON. Clicking a row selects only that device. '
                    'Toggle again to clear.'
                )
            else:
                hint_text = (
                    'Tip: Use the checkboxes for multi-select. Toggle a device last to mark it active for single-device actions.'
                )
            self.window.selection_hint_label.setText(hint_text)

        update_overview = getattr(self.window, 'update_device_overview', None)
        if callable(update_overview):
            update_overview()

    def filter_and_sort_devices(self) -> None:
        """Reapply search filtering and render the table."""
        self.update_device_list(self.window.device_dict)

    def on_search_changed(self, text: str) -> None:
        """Handle search text changes."""
        self.window.device_search_manager.set_search_text(text.strip())
        self.filter_and_sort_devices()

    def on_sort_changed(self, sort_mode: str) -> None:  # pragma: no cover - legacy hook
        """Compatibility shim kept for callers that still emit sort changes."""
        self.window.device_search_manager.set_sort_mode(sort_mode)
        self.filter_and_sort_devices()

    # ------------------------------------------------------------------
    # Selection synchronisation helpers
    # ------------------------------------------------------------------
    def _synchronize_ui_selection(
        self,
        selected_serials: Iterable[str],
        active_serial: Optional[str],
    ) -> None:
        if self.table is None:
            return
        selected_list = list(selected_serials)
        active_serial = active_serial if active_serial in selected_list else (selected_list[-1] if selected_list else None)

        self._syncing_selection = True
        try:
            self.table.set_checked_serials(selected_list, active_serial=active_serial)
            self.table.set_active_serial(active_serial)
        finally:
            self._syncing_selection = False

    def _on_table_selection_toggled(self, serial: str, is_checked: bool) -> None:
        if self._syncing_selection:
            return

        selected = self.window.device_selection_manager.apply_toggle(serial, is_checked, self.window.device_dict.keys())
        self._synchronize_ui_selection(selected, self.window.device_selection_manager.get_active_serial())
        self.update_selection_count()

    def _on_sort_indicator_changed(self, column: int, order: Qt.SortOrder) -> None:
        self._captured_sort = (column, order)
        sort_mode = self._SORT_MODE_BY_COLUMN.get(column)
        if sort_mode:
            mapped_mode = f'{sort_mode}:{order.name.lower()}'
            self.window.device_search_manager.set_sort_mode(mapped_mode)

    def _on_table_device_context_menu(self, position: QPoint, serial: str) -> None:
        if self.table is None:
            return
        anchor = self.table.viewport()
        self.window.show_device_context_menu(position, serial, anchor)

    # ------------------------------------------------------------------
    # Data helpers
    # ------------------------------------------------------------------
    def _visible_row_count(self) -> int:
        if self.table is None:
            return 0
        count = 0
        for row in range(self.table.rowCount()):
            if not self.table.isRowHidden(row):
                count += 1
        return count

    def _update_empty_state(self, total_count: int, visible_count: int) -> None:
        # Use device_list (ExpandableDeviceList) if available, fallback to table
        list_widget = self.device_list if self.device_list is not None else self.table
        no_devices_label = getattr(self.window, 'no_devices_label', None)
        if list_widget is None:
            return

        show_placeholder = total_count == 0
        device_stack = getattr(self.window, 'device_panel_stack', None)
        handled_by_stack = isinstance(device_stack, QStackedWidget)

        if handled_by_stack:
            target_widget = no_devices_label if show_placeholder else list_widget
            if target_widget is not None and device_stack.indexOf(target_widget) != -1:
                if device_stack.currentWidget() is not target_widget:
                    device_stack.setCurrentWidget(target_widget)
        else:
            list_widget.setHidden(show_placeholder)

        if no_devices_label is not None and hasattr(no_devices_label, 'setText'):
            if show_placeholder:
                if self.window.device_search_manager.get_search_text():
                    no_devices_label.setText('No devices match the current search')
                else:
                    no_devices_label.setText('No devices found')
            if not handled_by_stack and hasattr(no_devices_label, 'setVisible'):
                no_devices_label.setVisible(show_placeholder)

        logger.debug('Empty state updated (total=%s, visible=%s)', total_count, visible_count)

    def _refresh_check_devices(self) -> None:
        proxies = {
            serial: _SelectionProxy(self, serial)
            for serial in self.window.device_dict.keys()
        }
        self.window.check_devices = proxies

    def _get_filtered_sorted_devices(
        self, device_dict: Optional[Dict[str, adb_models.DeviceInfo]] = None
    ) -> List[adb_models.DeviceInfo]:
        source = list((device_dict or self.window.device_dict).values())
        return self.window.device_search_manager.search_and_sort_devices(
            source,
            self.window.device_search_manager.get_search_text(),
            self.window.device_search_manager.get_sort_mode(),
        )

    # ------------------------------------------------------------------
    # Device detail helpers used by other controllers
    # ------------------------------------------------------------------
    def get_additional_device_info(self, serial: str) -> Dict[str, str]:
        return self._get_additional_device_info(serial)

    def get_device_overview_summary(
        self,
        device: adb_models.DeviceInfo,
        serial: str,
    ) -> OrderedDict[str, List[Tuple[str, str]]]:
        status_helper = self.get_on_off_status

        try:
            additional_info = self._get_additional_device_info(serial)
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.debug('Failed to obtain additional info for %s: %s', serial, exc)
            additional_info = {}

        def _info(key: str, fallback: str = 'Unknown') -> str:
            value = additional_info.get(key)
            if value in (None, ''):
                return fallback
            return str(value)

        sections: OrderedDict[str, List[Tuple[str, str]]] = OrderedDict()
        sections['device'] = [
            ('Model', device.device_model or 'Unknown'),
            ('Serial', device.device_serial_num or 'Unknown'),
            (
                'Android',
                f"{device.android_ver or 'Unknown'} (API {device.android_api_level or 'Unknown'})",
            ),
            ('Build Fingerprint', device.build_fingerprint or 'Unknown'),
            ('Product', device.device_prod or 'Unknown'),
            ('USB', device.device_usb or 'Unknown'),
        ]

        sections['connectivity'] = [
            ('WiFi', status_helper(device.wifi_is_on)),
            ('Bluetooth', status_helper(device.bt_is_on)),
        ]

        sections['hardware'] = [
            ('Screen Size', _info('screen_size')),
            ('Screen Density', _info('screen_density')),
            ('CPU Architecture', _info('cpu_arch')),
        ]

        sections['battery'] = [
            ('Battery Level', _info('battery_level')),
            ('Capacity (mAh)', _info('battery_capacity_mah')),
            ('Battery mAs', _info('battery_mas')),
            ('Estimated DOU', _info('battery_dou_hours')),
        ]

        status_lines: List[Tuple[str, str]] = []
        operation_status = self.get_device_operation_status(serial)
        recording_status = self.get_device_recording_status(serial)
        if operation_status:
            status_lines.append(('Operation', operation_status))
        if recording_status:
            status_lines.append(('Recording', recording_status))
        if device.audio_state:
            status_lines.append(('Audio', device.audio_state))
        if device.bluetooth_manager_state:
            status_lines.append(('BT Manager', device.bluetooth_manager_state))

        if status_lines:
            sections['status'] = status_lines

        return sections

    def get_device_detail_text(
        self,
        device: adb_models.DeviceInfo,
        serial: str,
        *,
        include_additional: bool = True,
        include_identity: bool = True,
        include_connectivity: bool = True,
        include_status: bool = True,
    ) -> str:
        return self._build_device_detail_text(
            device,
            serial,
            include_additional=include_additional,
            include_identity=include_identity,
            include_connectivity=include_connectivity,
            include_status=include_status,
        )

    # Backward compatibility shim
    def create_device_tooltip(self, device: adb_models.DeviceInfo, serial: str) -> str:
        return self._build_device_detail_text(device, serial)

    # ------------------------------------------------------------------
    # Internal detail-building helpers (ported from legacy implementation)
    # ------------------------------------------------------------------
    def _get_additional_device_info(self, serial: str) -> Dict[str, str]:
        cache_source = getattr(self.window, 'battery_info_manager', None)
        if cache_source is not None:
            cached = cache_source.get_cached_info(serial)
            if cached:
                return cached

        try:
            info = adb_tools.get_additional_device_info(serial)
            if cache_source is not None:
                cache_source.update_cache(serial, info)
            return info
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.error('Error getting additional device info for %s: %s', serial, exc)
            info = {
                'screen_density': 'Unknown',
                'screen_size': 'Unknown',
                'battery_level': 'Unknown',
                'battery_capacity_mah': 'Unknown',
                'battery_mas': 'Unknown',
                'battery_dou_hours': 'Unknown',
                'cpu_arch': 'Unknown',
            }
            if cache_source is not None:
                cache_source.update_cache(serial, info)
            return info

    def _build_device_detail_text(
        self,
        device: adb_models.DeviceInfo,
        serial: str,
        *,
        include_additional: bool = True,
        include_identity: bool = True,
        include_connectivity: bool = True,
        include_status: bool = True,
    ) -> str:
        operation_status = self.get_device_operation_status(serial)
        recording_status = self.get_device_recording_status(serial)

        android_ver = device.android_ver or 'Unknown'
        android_api = device.android_api_level or 'Unknown'
        gms_display = device.gms_version if device.gms_version and device.gms_version != 'N/A' else 'N/A'

        wifi_status = self.get_on_off_status(device.wifi_is_on)
        bt_status = self.get_on_off_status(device.bt_is_on)

        sections: list[str] = []

        if include_identity:
            identity_lines = [
                self._format_detail('Model', device.device_model),
                self._format_detail('Serial', device.device_serial_num),
                f"{self._format_detail('Android', android_ver)} (API {android_api})",
                self._format_detail('GMS Version', gms_display),
                self._format_detail('Build Fingerprint', device.build_fingerprint),
                self._format_detail('Product', device.device_prod),
                self._format_detail('USB', device.device_usb),
            ]
            sections.append('📱 Device Overview\n' + '\n'.join(identity_lines))

        if include_connectivity:
            connectivity_lines = [
                self._format_detail('WiFi', wifi_status),
                self._format_detail('Bluetooth', bt_status),
            ]
            sections.append('📡 Connectivity\n' + '\n'.join(connectivity_lines))

        if include_status:
            status_lines = []
            if operation_status:
                status_lines.append(self._format_detail('Operation', operation_status))
            if recording_status:
                status_lines.append(self._format_detail('Recording', recording_status))
            if device.audio_state:
                status_lines.append(self._format_detail('Audio', device.audio_state))
            if device.bluetooth_manager_state:
                status_lines.append(self._format_detail('BT Manager', device.bluetooth_manager_state))
            if status_lines:
                sections.append('⚙️ Status\n' + '\n'.join(status_lines))
            elif not include_identity and not include_connectivity and not include_additional:
                sections.append('⚙️ Status\nNo additional status data.')

        if include_additional:
            try:
                additional_info = self._get_additional_device_info(serial)
            except Exception as exc:  # pragma: no cover - defensive logging
                logger.debug('Failed to build extended tooltip for %s: %s', serial, exc)
            else:
                hardware_lines = [
                    self._format_detail('Screen Size', additional_info.get('screen_size', 'Unknown')),
                    self._format_detail('Screen Density', additional_info.get('screen_density', 'Unknown')),
                    self._format_detail('CPU Architecture', additional_info.get('cpu_arch', 'Unknown')),
                ]
                battery_lines = [
                    self._format_detail('Battery Level', additional_info.get('battery_level', 'Unknown')),
                    self._format_detail('Capacity (mAh)', additional_info.get('battery_capacity_mah', 'Unknown')),
                    self._format_detail('Battery mAs', additional_info.get('battery_mas', 'Unknown')),
                    self._format_detail('Estimated DOU', additional_info.get('battery_dou_hours', 'Unknown')),
                ]
                sections.append('🖥️ Hardware Information\n' + '\n'.join(hardware_lines))
                sections.append('🔋 Battery Information\n' + '\n'.join(battery_lines))

        if not sections:
            return 'No additional details available.'

        separator = '\n' + '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━' + '\n'
        return separator.join(sections)

    # ------------------------------------------------------------------
    # Legacy compatibility helpers retained for other modules
    # ------------------------------------------------------------------
    def get_device_operation_status(self, serial: str) -> str:
        manager = getattr(self.window, 'device_manager', None)
        if manager is not None and hasattr(manager, 'get_device_operation_status'):
            return manager.get_device_operation_status(serial) or ''
        return ''

    def get_device_recording_status(self, serial: str) -> str:
        manager = getattr(self.window, 'device_manager', None)
        if manager is not None and hasattr(manager, 'get_device_recording_status'):
            status = manager.get_device_recording_status(serial)
            if status:
                return status.get('status', '')
        return ''

    @staticmethod
    def get_on_off_status(value: Optional[bool]) -> str:
        if value is None:
            return 'Unknown'
        return 'On' if value else 'Off'

    @staticmethod
    def _format_title(text: str) -> str:
        return f"{text or 'Unknown Device'}"

    @staticmethod
    def _format_subtitle(text: str) -> str:
        return f"Serial: {text or 'Unknown'}"

    @staticmethod
    def _format_detail(label: str, value: Optional[str]) -> str:
        return f"{label}: {value or 'Unknown'}"


__all__ = ["DeviceListController"]
