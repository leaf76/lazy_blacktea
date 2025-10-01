"""Controller responsible for device list rendering logic."""

from __future__ import annotations

from typing import Dict, Iterable, List, Optional, TYPE_CHECKING

from PyQt6.QtCore import QPoint, Qt
from PyQt6.QtWidgets import QStackedWidget

from utils import adb_models, adb_tools, common
from ui.device_table_widget import DeviceTableWidget

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
        self._syncing_selection = False
        self._captured_sort: Optional[tuple[int, Qt.SortOrder]] = None

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

    # ------------------------------------------------------------------
    # Public API used by WindowMain
    # ------------------------------------------------------------------
    def update_device_list(self, device_dict: Dict[str, adb_models.DeviceInfo]) -> None:
        """Update the device list display with the current device dictionary."""
        self.window.device_dict = device_dict
        if self.table is None:
            logger.warning('Device table not attached; skipping update')
            return

        selected_serials = self.window.device_selection_manager.prune_selection(device_dict.keys())
        active_serial = self.window.device_selection_manager.get_active_serial()

        filtered_devices = self._get_filtered_sorted_devices(device_dict)
        sort_indicator = self._captured_sort or self.table.get_sort_indicator()

        logger.debug('Rendering %s devices (%s visible after search)', len(device_dict), len(filtered_devices))

        self.table.update_devices(filtered_devices)
        self.table.restore_sort_indicator(*sort_indicator)
        self._synchronize_ui_selection(selected_serials, active_serial)
        self._refresh_check_devices()
        self._update_empty_state(len(device_dict), len(filtered_devices))
        self.update_selection_count()

    def select_all_devices(self) -> None:
        """Select every available device."""
        serials = list(self.window.device_dict.keys())
        self.window.device_selection_manager.set_selected_serials(serials)
        self._synchronize_ui_selection(serials, self.window.device_selection_manager.get_active_serial())
        self.update_selection_count()
        logger.info('Selected all %s devices', len(serials))

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

        if search_text:
            title_text = f'Connected Devices ({visible_count}/{total_count}) - Selected: {selected_count}'
        else:
            title_text = f'Connected Devices ({total_count}) - Selected: {selected_count}'

        if hasattr(self.window, 'title_label') and self.window.title_label is not None:
            self.window.title_label.setText(title_text)

        if hasattr(self.window, 'selection_summary_label') and self.window.selection_summary_label is not None:
            if active_serial and active_serial in self.window.device_dict:
                device = self.window.device_dict[active_serial]
                active_label = f'{device.device_model} ({active_serial[:8]}...)'
            elif active_serial:
                active_label = active_serial
            else:
                active_label = 'None'
            self.window.selection_summary_label.setText(
                f'Selected {selected_count} of {total_count} · Active: {active_label}'
            )

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
        table_widget = self.table
        no_devices_label = getattr(self.window, 'no_devices_label', None)
        if table_widget is None:
            return

        show_placeholder = total_count == 0
        device_stack = getattr(self.window, 'device_panel_stack', None)
        handled_by_stack = isinstance(device_stack, QStackedWidget)

        if handled_by_stack:
            target_widget = no_devices_label if show_placeholder else table_widget
            if target_widget is not None and device_stack.indexOf(target_widget) != -1:
                if device_stack.currentWidget() is not target_widget:
                    device_stack.setCurrentWidget(target_widget)
        else:
            table_widget.setHidden(show_placeholder)

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

    def get_device_detail_text(self, device: adb_models.DeviceInfo, serial: str) -> str:
        return self._build_device_detail_text(device, serial)

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

    def _build_device_detail_text(self, device: adb_models.DeviceInfo, serial: str) -> str:
        operation_status = self.get_device_operation_status(serial)
        recording_status = self.get_device_recording_status(serial)

        android_ver = device.android_ver or 'Unknown'
        android_api = device.android_api_level or 'Unknown'
        gms_display = device.gms_version if device.gms_version and device.gms_version != 'N/A' else 'N/A'

        wifi_status = self.get_on_off_status(device.wifi_is_on)
        bt_status = self.get_on_off_status(device.bt_is_on)

        base_tooltip = (
            f"{self._format_title(device.device_model)}\n"
            f"{self._format_subtitle(device.device_serial_num)}\n"
            '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n'
            '📱 Device Overview\n'
            f"{self._format_detail('Model', device.device_model)}\n"
            f"{self._format_detail('Serial', device.device_serial_num)}\n"
            f"{self._format_detail('Android', android_ver)} "
            f"(API {android_api})\n"
            f"{self._format_detail('GMS Version', gms_display)}\n"
            f"{self._format_detail('Build Fingerprint', device.build_fingerprint)}\n"
            f"{self._format_detail('Product', device.device_prod)}\n"
            f"{self._format_detail('USB', device.device_usb)}\n"
            '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n'
            '📡 Connectivity\n'
            f"{self._format_detail('WiFi', wifi_status)}\n"
            f"{self._format_detail('Bluetooth', bt_status)}\n"
            f"{self._format_detail('Audio', device.audio_state)}\n"
            f"{self._format_detail('BT Manager', device.bluetooth_manager_state)}\n"
        )

        try:
            additional_info = self._get_additional_device_info(serial)
            return base_tooltip + (
                f'━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n'
                f'🖥️ Hardware Information\n'
                f"{self._format_detail('Screen Size', additional_info.get('screen_size', 'Unknown'))}\n"
                f"{self._format_detail('Screen Density', additional_info.get('screen_density', 'Unknown'))}\n"
                f"{self._format_detail('CPU Architecture', additional_info.get('cpu_arch', 'Unknown'))}\n"
                f'━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n'
                f'🔋 Battery Information\n'
                f"{self._format_detail('Battery Level', additional_info.get('battery_level', 'Unknown'))}\n"
                f"{self._format_detail('Capacity (mAh)', additional_info.get('battery_capacity_mah', 'Unknown'))}\n"
                f"{self._format_detail('Battery mAs', additional_info.get('battery_mas', 'Unknown'))}\n"
                f"{self._format_detail('Estimated DOU', additional_info.get('battery_dou_hours', 'Unknown'))}"
            )
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.debug('Failed to build extended tooltip for %s: %s', serial, exc)
            return base_tooltip

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
