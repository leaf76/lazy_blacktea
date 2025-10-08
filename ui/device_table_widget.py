"""Tabular device list widget with header sorting and checkbox selection."""

from __future__ import annotations

from typing import Dict, Iterable, List, Optional, Sequence

from PyQt6.QtCore import QPoint, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QBrush, QFont
from PyQt6.QtWidgets import QAbstractItemView, QHeaderView, QTableWidget, QTableWidgetItem

from utils import adb_models
from ui.style_manager import StyleManager


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

            # Build the initial mapping then refresh styles
            self._rebuild_serial_row_mapping()
            self._refresh_row_styles()
        finally:
            if sorting_enabled:
                self.setSortingEnabled(True)
                # When re-enabling sorting, Qt may reorder rows based on the
                # active sort indicator. Rebuild mapping to stay in sync.
                self._rebuild_serial_row_mapping()
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
            # Iterate visible rows to avoid stale mapping after sort/filter
            for row in range(self.rowCount()):
                item = self.item(row, 0)
                if item is None:
                    continue
                serial = item.data(self._SERIAL_ROLE)
                desired = Qt.CheckState.Checked if serial in serial_list else Qt.CheckState.Unchecked
                item.setCheckState(desired)
        finally:
            self._updating_items = False
        self._rebuild_serial_row_mapping()
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
        self._rebuild_serial_row_mapping()
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
        self._rebuild_serial_row_mapping()
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
            # Colors tuned for better contrast; pick palette by theme brightness
            if self._is_dark_theme():
                # Dark theme palette: darker bg with bright text for contrast
                active_bg = QBrush(QColor('#2d3b52'))
                active_text = QBrush(QColor('#b8dcff'))
                selected_bg = QBrush(QColor('#3a3a28'))
            else:
                # Light theme palette
                active_bg = QBrush(QColor('#cde9ff'))  # Higher-contrast than previous '#e6f4ff'
                active_text = QBrush(QColor('#0b5394'))  # Accessible dark blue text
                selected_bg = QBrush(QColor('#fff4cc'))  # Subtle yellow for non-active selections
            default_bg = QBrush(Qt.GlobalColor.transparent)
            default_text = QBrush(self.palette().color(self.foregroundRole()))

            # Build current row mapping and sets for quick lookup
            active_row = self._serial_to_row.get(self._active_serial) if self._active_serial else None
            selected_set = set(self._checked_serials)

            for row in range(self.rowCount()):
                key_item = self.item(row, 0)
                for column in range(self.columnCount()):
                    item = self.item(row, column)
                    if item is None:
                        continue
                    if active_row is not None and row == active_row:
                        item.setBackground(active_bg)
                        item.setForeground(active_text)
                    else:
                        # If the row corresponds to a selected device, use a readable background
                        serial = key_item.data(self._SERIAL_ROLE) if key_item is not None else None
                        if serial and serial in selected_set:
                            item.setBackground(selected_bg)
                        else:
                            item.setBackground(default_bg)
                        item.setForeground(default_text)
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

    # Keep serial-to-row mapping in sync after sorts
    def sortItems(self, column: int, order: Qt.SortOrder = Qt.SortOrder.AscendingOrder) -> None:  # type: ignore[override]
        super().sortItems(column, order)
        self._rebuild_serial_row_mapping()

    def _rebuild_serial_row_mapping(self) -> None:
        """Recompute the serial->row mapping from current table order."""
        mapping: Dict[str, int] = {}
        for row in range(self.rowCount()):
            item = self.item(row, 0)
            if item is None:
                continue
            serial = item.data(self._SERIAL_ROLE)
            if serial:
                mapping[str(serial)] = row
        self._serial_to_row = mapping

    # ------------------------------------------------------------------
    # Theme helpers
    # ------------------------------------------------------------------
    def _is_dark_theme(self) -> bool:
        """Heuristically detect dark theme using StyleManager.COLORS background.

        Falls back to False (light) if parsing fails.
        """
        bg = (StyleManager.COLORS or {}).get('background', '#FFFFFF')
        rgb = self._parse_hex_rgb(bg)
        if rgb is None:
            return False
        r, g, b = rgb
        # Perceived brightness (0..255)
        brightness = (r * 299 + g * 587 + b * 114) / 1000
        return brightness < 128

    @staticmethod
    def _parse_hex_rgb(value: str) -> Optional[tuple[int, int, int]]:
        try:
            s = value.strip()
            if s.startswith('#'):
                s = s[1:]
            if len(s) == 3:
                r = int(s[0] * 2, 16)
                g = int(s[1] * 2, 16)
                b = int(s[2] * 2, 16)
                return r, g, b
            if len(s) >= 6:
                r = int(s[0:2], 16)
                g = int(s[2:4], 16)
                b = int(s[4:6], 16)
                return r, g, b
        except Exception:
            pass
        return None

    # ------------------------------------------------------------------
    # Qt event overrides
    # ------------------------------------------------------------------
    def mousePressEvent(self, event) -> None:  # type: ignore[override]
        if event.button() == Qt.MouseButton.LeftButton:
            point = event.position().toPoint() if hasattr(event, 'position') else event.pos()
            index = self.indexAt(point)
            if index.isValid() and index.column() != 0:
                checkbox_item = self.item(index.row(), 0)
                if checkbox_item is not None and checkbox_item.flags() & Qt.ItemFlag.ItemIsUserCheckable:
                    new_state = (
                        Qt.CheckState.Unchecked
                        if checkbox_item.checkState() == Qt.CheckState.Checked
                        else Qt.CheckState.Checked
                    )
                    checkbox_item.setCheckState(new_state)
                    event.accept()
                    return
        super().mousePressEvent(event)


__all__ = ["DeviceTableWidget"]
