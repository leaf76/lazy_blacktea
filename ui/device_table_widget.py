"""Tabular device list widget with header sorting and checkbox selection."""

from __future__ import annotations

from typing import Dict, Iterable, List, Optional, Sequence

from PyQt6.QtCore import QPoint, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QBrush, QFont
from PyQt6.QtWidgets import QAbstractItemView, QHeaderView, QTableWidget, QTableWidgetItem

from utils import adb_models


class DeviceTableWidget(QTableWidget):
    """Table-based device list with sortable columns and checkbox selection."""

    selection_toggled = pyqtSignal(str, bool)
    device_context_menu_requested = pyqtSignal(QPoint, str)
    list_context_menu_requested = pyqtSignal(QPoint)

    _COLUMN_HEADERS: Sequence[str] = (
        '',
        'Model',
        'Serial',
        'Android',
        'API',
        'GMS',
        'WiFi',
        'BT',
    )

    _SERIAL_ROLE = Qt.ItemDataRole.UserRole

    def __init__(self, parent=None) -> None:
        super().__init__(0, len(self._COLUMN_HEADERS), parent)
        self.setHorizontalHeaderLabels(self._COLUMN_HEADERS)
        self.verticalHeader().setVisible(False)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.setSortingEnabled(True)
        self.horizontalHeader().setSectionsClickable(True)
        self.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.horizontalHeader().setStretchLastSection(True)
        self.setAlternatingRowColors(True)
        self._configure_column_widths()

        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._handle_custom_context_menu)

        self._serial_to_row: Dict[str, int] = {}
        self._checked_serials: List[str] = []
        self._active_serial: Optional[str] = None
        self._updating_items = False

        self.itemChanged.connect(self._handle_item_changed)

    # ------------------------------------------------------------------
    # Public API consumed by controllers
    # ------------------------------------------------------------------
    def update_devices(self, devices: Dict[str, adb_models.DeviceInfo] | Sequence[adb_models.DeviceInfo]) -> None:
        """Populate the table with the provided devices."""
        device_list: List[adb_models.DeviceInfo]
        if isinstance(devices, dict):
            device_list = list(devices.values())
        else:
            device_list = list(devices)

        serials_order = [device.device_serial_num for device in device_list]
        available_serials = set(serials_order)
        self._checked_serials = [serial for serial in self._checked_serials if serial in available_serials]
        if self._active_serial not in available_serials:
            self._active_serial = self._checked_serials[-1] if self._checked_serials else None

        sorting_enabled = self.isSortingEnabled()
        self._updating_items = True
        try:
            if sorting_enabled:
                self.setSortingEnabled(False)
            self.setRowCount(0)
            self._serial_to_row.clear()

            for device in device_list:
                serial = device.device_serial_num
                row = self.rowCount()
                self.insertRow(row)
                self._serial_to_row[serial] = row
                self._set_checkbox_item(row, serial)
                self._set_text_item(row, 1, device.device_model or 'Unknown')
                self._set_text_item(row, 2, serial)
                self._set_text_item(row, 3, device.android_ver or 'Unknown')
                self._set_text_item(row, 4, device.android_api_level or 'Unknown')
                gms_display = device.gms_version if device.gms_version and device.gms_version != 'N/A' else 'N/A'
                self._set_text_item(row, 5, gms_display)
                self._set_text_item(row, 6, self._format_on_off(device.wifi_is_on))
                self._set_text_item(row, 7, self._format_on_off(device.bt_is_on))

            self._refresh_row_styles()
        finally:
            if sorting_enabled:
                self.setSortingEnabled(True)
            self._updating_items = False

    def set_checked_serials(self, serials: Iterable[str], *, active_serial: Optional[str] = None) -> None:
        """Synchronise checkbox state with the provided serials."""
        serial_list = list(serials)
        self._checked_serials = serial_list
        if active_serial is not None:
            self._active_serial = active_serial
        else:
            self._active_serial = serial_list[-1] if serial_list else None

        self._updating_items = True
        try:
            for serial, row in self._serial_to_row.items():
                item = self.item(row, 0)
                if item is None:
                    continue
                desired = Qt.CheckState.Checked if serial in serial_list else Qt.CheckState.Unchecked
                item.setCheckState(desired)
        finally:
            self._updating_items = False
        self._refresh_row_styles()

    def get_checked_serials(self) -> List[str]:
        """Return checked serials in their current table order."""
        ordered_serials: List[str] = []
        for row in range(self.rowCount()):
            item = self.item(row, 0)
            if item is None:
                continue
            if item.checkState() == Qt.CheckState.Checked:
                serial = item.data(self._SERIAL_ROLE)
                if serial:
                    ordered_serials.append(serial)
        self._checked_serials = ordered_serials
        return ordered_serials

    def set_active_serial(self, serial: Optional[str]) -> None:
        """Highlight the active device row."""
        self._active_serial = serial
        self._refresh_row_styles()

    def apply_visibility_filter(self, visible_serials: Iterable[str]) -> None:
        """Show only rows whose serials are in the provided iterable."""
        visible_set = set(visible_serials)
        for row in range(self.rowCount()):
            item = self.item(row, 0)
            if item is None:
                self.setRowHidden(row, True)
                continue
            serial = item.data(self._SERIAL_ROLE)
            self.setRowHidden(row, serial not in visible_set)
        self._refresh_row_styles()

    def get_sort_indicator(self) -> tuple[int, Qt.SortOrder]:
        """Return the current sort column and order."""
        header = self.horizontalHeader()
        return header.sortIndicatorSection(), header.sortIndicatorOrder()

    def restore_sort_indicator(self, column: int, order: Qt.SortOrder) -> None:
        """Restore a previously captured sort indicator."""
        header = self.horizontalHeader()
        header.blockSignals(True)
        try:
            header.setSortIndicator(column, order)
            self.sortItems(column, order)
        finally:
            header.blockSignals(False)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _configure_column_widths(self) -> None:
        widths = [32, 160, 160, 100, 70, 110, 70, 70]
        for index, width in enumerate(widths):
            if index < len(widths):
                self.setColumnWidth(index, width)

    def _set_checkbox_item(self, row: int, serial: str) -> None:
        item = QTableWidgetItem('')
        item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsUserCheckable)
        item.setCheckState(Qt.CheckState.Checked if serial in self._checked_serials else Qt.CheckState.Unchecked)
        item.setData(self._SERIAL_ROLE, serial)
        item.setToolTip('Toggle to include this device in multi-device actions')
        self.setItem(row, 0, item)

    def _set_text_item(self, row: int, column: int, value) -> None:
        if value is None or value == '':
            display = 'Unknown'
        else:
            display = str(value)
        item = QTableWidgetItem(display)
        item.setFlags(Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled)
        if column == 1:
            bold_font = QFont(item.font())
            bold_font.setBold(True)
            item.setFont(bold_font)
        if column >= 3:
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setItem(row, column, item)

    def _refresh_row_styles(self) -> None:
        previous_state = self._updating_items
        self._updating_items = True
        try:
            active_brush = QBrush(QColor('#e6f4ff'))
            default_brush = QBrush(Qt.GlobalColor.transparent)
            highlighted_rows = set()
            if self._active_serial in self._serial_to_row:
                highlighted_rows.add(self._serial_to_row[self._active_serial])

            for serial, row in self._serial_to_row.items():
                for column in range(self.columnCount()):
                    item = self.item(row, column)
                    if item is None:
                        continue
                    if row in highlighted_rows:
                        item.setBackground(active_brush)
                    else:
                        item.setBackground(default_brush)
        finally:
            self._updating_items = previous_state

    def _handle_item_changed(self, item: QTableWidgetItem) -> None:
        if self._updating_items or item.column() != 0:
            return
        serial = item.data(self._SERIAL_ROLE)
        if not serial:
            return
        checked = item.checkState() == Qt.CheckState.Checked
        if checked:
            if serial in self._checked_serials:
                self._checked_serials.remove(serial)
            self._checked_serials.append(serial)
            self._active_serial = serial
        else:
            if serial in self._checked_serials:
                self._checked_serials.remove(serial)
            if self._active_serial == serial:
                self._active_serial = self._checked_serials[-1] if self._checked_serials else None
        self._refresh_row_styles()
        self.selection_toggled.emit(serial, checked)

    @staticmethod
    def _format_on_off(state: Optional[bool]) -> str:
        if state is None:
            return 'Unknown'
        return 'On' if state else 'Off'

    def _handle_custom_context_menu(self, position: QPoint) -> None:
        index = self.indexAt(position)
        if index.isValid():
            serial_item = self.item(index.row(), 0)
            serial = serial_item.data(self._SERIAL_ROLE) if serial_item is not None else None
            if serial:
                self.device_context_menu_requested.emit(position, serial)
                return
        self.list_context_menu_requested.emit(position)


__all__ = ["DeviceTableWidget"]
