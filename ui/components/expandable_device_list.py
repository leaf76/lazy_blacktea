"""Expandable device list with collapsible detail panels."""

from __future__ import annotations

from typing import Dict, List, Optional, Set

from PyQt6.QtCore import QPoint, Qt, pyqtSignal
from PyQt6.QtGui import QCursor
from PyQt6.QtWidgets import (
    QCheckBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from utils import adb_models
from ui.style_manager import StyleManager


class DeviceDetailPanel(QFrame):
    """Collapsible panel showing device details."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName('device_detail_panel')
        self.setFrameStyle(QFrame.Shape.StyledPanel | QFrame.Shadow.Plain)
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QGridLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(8)
        layout.setColumnStretch(1, 1)
        layout.setColumnStretch(3, 1)

        # Row 0: API, GMS
        self._api_label = self._create_detail_item(layout, 0, 0, 'API')
        self._gms_label = self._create_detail_item(layout, 0, 2, 'GMS')

        # Row 1: WiFi, BT
        self._wifi_label = self._create_detail_item(layout, 1, 0, 'WiFi')
        self._bt_label = self._create_detail_item(layout, 1, 2, 'BT')

        # Row 2: Battery, Screen
        self._battery_label = self._create_detail_item(layout, 2, 0, 'Battery')
        self._screen_label = self._create_detail_item(layout, 2, 2, 'Screen')

        # Row 3: CPU, Build
        self._cpu_label = self._create_detail_item(layout, 3, 0, 'CPU')
        self._build_label = self._create_detail_item(layout, 3, 2, 'Build')

    def _create_detail_item(
        self,
        layout: QGridLayout,
        row: int,
        col: int,
        label_text: str,
    ) -> QLabel:
        """Create a label pair (name: value) and add to layout."""
        name_label = QLabel(f'{label_text}:')
        name_label.setObjectName('detail_name_label')
        font = name_label.font()
        font.setBold(True)
        name_label.setFont(font)

        value_label = QLabel('--')
        value_label.setObjectName('detail_value_label')
        value_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )

        layout.addWidget(name_label, row, col)
        layout.addWidget(value_label, row, col + 1)

        return value_label

    def update_details(
        self,
        device: adb_models.DeviceInfo,
        additional_info: Optional[Dict[str, str]] = None,
    ) -> None:
        """Update the detail panel with device information."""
        info = additional_info or {}

        # API and GMS
        api = device.android_api_level or 'Unknown'
        self._api_label.setText(str(api))

        gms = device.gms_version
        if not gms or gms == 'N/A':
            gms = 'N/A'
        self._gms_label.setText(gms)

        # WiFi and BT
        wifi_status = 'On' if device.wifi_is_on else ('Off' if device.wifi_is_on is False else 'Unknown')
        self._wifi_label.setText(wifi_status)

        bt_status = 'On' if device.bt_is_on else ('Off' if device.bt_is_on is False else 'Unknown')
        self._bt_label.setText(bt_status)

        # Battery and Screen
        battery = info.get('battery_level', 'Unknown')
        self._battery_label.setText(str(battery))

        screen = info.get('screen_size', 'Unknown')
        self._screen_label.setText(str(screen))

        # CPU and Build
        cpu = info.get('cpu_arch', 'Unknown')
        self._cpu_label.setText(str(cpu))

        build = device.build_fingerprint or 'Unknown'
        # Truncate long build strings
        if len(build) > 40:
            build = build[:37] + '...'
        self._build_label.setText(build)
        self._build_label.setToolTip(device.build_fingerprint or '')


class DeviceRowWidget(QFrame):
    """A single device row with expandable details."""

    selection_toggled = pyqtSignal(str, bool)  # (serial, is_checked)
    expand_toggled = pyqtSignal(str, bool)  # (serial, is_expanded)
    context_menu_requested = pyqtSignal(QPoint, str)  # (position, serial)

    def __init__(
        self,
        device: adb_models.DeviceInfo,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._device = device
        self._serial = device.device_serial_num
        self._is_expanded = False
        self._is_active = False
        self._additional_info: Dict[str, str] = {}

        self.setObjectName('device_row')
        self.setFrameStyle(QFrame.Shape.NoFrame)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._on_context_menu)

        self._setup_ui()

    @property
    def serial(self) -> str:
        return self._serial

    @property
    def is_expanded(self) -> bool:
        return self._is_expanded

    @property
    def is_checked(self) -> bool:
        return self._checkbox.isChecked()

    def _setup_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Main row container
        row_container = QWidget()
        row_container.setObjectName('device_row_main')
        row_layout = QHBoxLayout(row_container)
        row_layout.setContentsMargins(8, 6, 8, 6)
        row_layout.setSpacing(12)

        # Checkbox
        self._checkbox = QCheckBox()
        self._checkbox.setToolTip('Select device for batch operations')
        self._checkbox.stateChanged.connect(self._on_checkbox_changed)
        row_layout.addWidget(self._checkbox)

        # Model
        self._model_label = QLabel(self._device.device_model or 'Unknown')
        self._model_label.setObjectName('device_model_label')
        font = self._model_label.font()
        font.setBold(True)
        self._model_label.setFont(font)
        self._model_label.setMinimumWidth(140)
        row_layout.addWidget(self._model_label)

        # Serial
        self._serial_label = QLabel(self._serial)
        self._serial_label.setObjectName('device_serial_label')
        self._serial_label.setMinimumWidth(120)
        self._serial_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        row_layout.addWidget(self._serial_label)

        # Android version
        android_ver = self._device.android_ver or 'Unknown'
        self._android_label = QLabel(f'Android {android_ver}')
        self._android_label.setObjectName('device_android_label')
        self._android_label.setMinimumWidth(90)
        row_layout.addWidget(self._android_label)

        # Stretch to push expand button to the right
        row_layout.addStretch()

        # Expand/collapse button
        self._expand_btn = QToolButton()
        self._expand_btn.setObjectName('device_expand_btn')
        self._expand_btn.setText('\u25b6')  # Right-pointing triangle
        self._expand_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._expand_btn.clicked.connect(self._toggle_expand)
        self._expand_btn.setToolTip('Show device details')
        self._expand_btn.setStyleSheet(StyleManager.get_device_expand_btn_style())
        row_layout.addWidget(self._expand_btn)

        main_layout.addWidget(row_container)

        # Detail panel (hidden by default)
        self._detail_panel = DeviceDetailPanel()
        self._detail_panel.setVisible(False)
        main_layout.addWidget(self._detail_panel)

        # Bottom separator
        self._separator = QFrame()
        self._separator.setFrameShape(QFrame.Shape.HLine)
        self._separator.setObjectName('device_row_separator')
        main_layout.addWidget(self._separator)

    def _on_checkbox_changed(self, state: int) -> None:
        is_checked = state == Qt.CheckState.Checked.value
        self.selection_toggled.emit(self._serial, is_checked)

    def _toggle_expand(self) -> None:
        self._is_expanded = not self._is_expanded
        self._detail_panel.setVisible(self._is_expanded)

        if self._is_expanded:
            self._expand_btn.setText('\u25bc')  # Down-pointing triangle
            self._expand_btn.setToolTip('Hide device details')
            self._detail_panel.update_details(self._device, self._additional_info)
        else:
            self._expand_btn.setText('\u25b6')  # Right-pointing triangle
            self._expand_btn.setToolTip('Show device details')

        self.expand_toggled.emit(self._serial, self._is_expanded)

    def _on_context_menu(self, position: QPoint) -> None:
        global_pos = self.mapToGlobal(position)
        self.context_menu_requested.emit(global_pos, self._serial)

    def set_checked(self, checked: bool) -> None:
        """Set checkbox state without emitting signal."""
        self._checkbox.blockSignals(True)
        self._checkbox.setChecked(checked)
        self._checkbox.blockSignals(False)

    def set_active(self, active: bool) -> None:
        """Set whether this row is the active device."""
        self._is_active = active
        self.setProperty('active', active)
        self.style().unpolish(self)
        self.style().polish(self)

    def set_expanded(self, expanded: bool) -> None:
        """Programmatically set expansion state."""
        if expanded != self._is_expanded:
            self._toggle_expand()

    def update_device(
        self,
        device: adb_models.DeviceInfo,
        additional_info: Optional[Dict[str, str]] = None,
    ) -> None:
        """Update the row with new device information."""
        self._device = device
        self._additional_info = additional_info or {}

        self._model_label.setText(device.device_model or 'Unknown')
        android_ver = device.android_ver or 'Unknown'
        self._android_label.setText(f'Android {android_ver}')

        if self._is_expanded:
            self._detail_panel.update_details(device, self._additional_info)

    def set_additional_info(self, info: Dict[str, str]) -> None:
        """Set additional device info for the detail panel."""
        self._additional_info = info
        if self._is_expanded:
            self._detail_panel.update_details(self._device, self._additional_info)


class ExpandableDeviceList(QScrollArea):
    """Scrollable list of expandable device rows."""

    selection_changed = pyqtSignal(list)  # List of selected serials
    device_expanded = pyqtSignal(str)  # Serial of expanded device
    context_menu_requested = pyqtSignal(QPoint, str)  # (position, serial)
    list_context_menu_requested = pyqtSignal(QPoint)  # Empty area context menu

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._rows: Dict[str, DeviceRowWidget] = {}
        self._selected_serials: List[str] = []
        self._active_serial: Optional[str] = None
        self._expanded_serials: Set[str] = set()
        self._syncing_selection = False

        self._setup_ui()

    def _setup_ui(self) -> None:
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setObjectName('expandable_device_list')

        # Container widget
        self._container = QWidget()
        self._container.setObjectName('device_list_container')
        self._layout = QVBoxLayout(self._container)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(0)
        self._layout.addStretch()  # Push items to top

        self.setWidget(self._container)

        # Context menu for empty area
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._on_list_context_menu)

    def _on_list_context_menu(self, position: QPoint) -> None:
        """Handle context menu on empty area."""
        global_pos = self.mapToGlobal(position)
        self.list_context_menu_requested.emit(global_pos)

    def update_devices(
        self,
        devices: List[adb_models.DeviceInfo],
    ) -> None:
        """Update the list with new device data."""
        device_dict = {d.device_serial_num: d for d in devices}
        current_serials = set(device_dict.keys())
        existing_serials = set(self._rows.keys())

        # Remove rows for disconnected devices
        for serial in existing_serials - current_serials:
            row = self._rows.pop(serial)
            self._layout.removeWidget(row)
            row.deleteLater()
            self._expanded_serials.discard(serial)

        # Add new rows for new devices
        for serial in current_serials - existing_serials:
            device = device_dict[serial]
            row = DeviceRowWidget(device)
            row.selection_toggled.connect(self._on_row_selection_toggled)
            row.expand_toggled.connect(self._on_row_expand_toggled)
            row.context_menu_requested.connect(self._on_row_context_menu)

            # Insert before the stretch
            insert_index = self._layout.count() - 1
            self._layout.insertWidget(insert_index, row)
            self._rows[serial] = row
            row.show()

            # Restore expansion state
            if serial in self._expanded_serials:
                row.set_expanded(True)

        # Update existing rows
        for serial in current_serials & existing_serials:
            device = device_dict[serial]
            self._rows[serial].update_device(device)

        # Prune selection to only include existing rows
        self._selected_serials = [s for s in self._selected_serials if s in self._rows]
        if self._active_serial not in self._rows:
            self._active_serial = self._selected_serials[-1] if self._selected_serials else None

        # Sync selection state
        self._sync_selection_ui()

    def _on_row_selection_toggled(self, serial: str, is_checked: bool) -> None:
        """Handle row checkbox toggle."""
        if self._syncing_selection:
            return

        if is_checked:
            if serial not in self._selected_serials:
                self._selected_serials.append(serial)
            self._active_serial = serial
        else:
            if serial in self._selected_serials:
                self._selected_serials.remove(serial)
            if self._active_serial == serial:
                self._active_serial = (
                    self._selected_serials[-1] if self._selected_serials else None
                )

        self._sync_selection_ui()
        self.selection_changed.emit(list(self._selected_serials))

    def _on_row_expand_toggled(self, serial: str, is_expanded: bool) -> None:
        """Handle row expansion toggle."""
        if is_expanded:
            self._expanded_serials.add(serial)
        else:
            self._expanded_serials.discard(serial)
        self.device_expanded.emit(serial)

    def _on_row_context_menu(self, position: QPoint, serial: str) -> None:
        """Forward context menu request."""
        self.context_menu_requested.emit(position, serial)

    def _sync_selection_ui(self) -> None:
        """Synchronize row UI with selection state."""
        self._syncing_selection = True
        try:
            for serial, row in self._rows.items():
                row.set_checked(serial in self._selected_serials)
                row.set_active(serial == self._active_serial)
        finally:
            self._syncing_selection = False

    def set_selected_serials(
        self,
        serials: List[str],
        active_serial: Optional[str] = None,
    ) -> None:
        """Set the selected devices from external source."""
        self._selected_serials = [s for s in serials if s in self._rows]
        if active_serial and active_serial in self._rows:
            self._active_serial = active_serial
        else:
            self._active_serial = (
                self._selected_serials[-1] if self._selected_serials else None
            )
        self._sync_selection_ui()

    def get_selected_serials(self) -> List[str]:
        """Get list of selected device serials."""
        return list(self._selected_serials)

    def get_active_serial(self) -> Optional[str]:
        """Get the currently active device serial."""
        return self._active_serial

    def set_additional_info(self, serial: str, info: Dict[str, str]) -> None:
        """Set additional info for a specific device."""
        row = self._rows.get(serial)
        if row:
            row.set_additional_info(info)

    def expand_device(self, serial: str) -> None:
        """Expand a specific device row."""
        row = self._rows.get(serial)
        if row and not row.is_expanded:
            row.set_expanded(True)

    def expand_all(self) -> None:
        """Expand all device rows."""
        for serial, row in self._rows.items():
            if not row.is_expanded:
                row.set_expanded(True)
            self._expanded_serials.add(serial)

    def collapse_all(self) -> None:
        """Collapse all expanded rows."""
        for row in self._rows.values():
            if row.is_expanded:
                row.set_expanded(False)
        self._expanded_serials.clear()

    def toggle_expand_all(self) -> bool:
        """Toggle between expand all and collapse all.

        Returns:
            True if expanded, False if collapsed
        """
        # If any row is collapsed, expand all; otherwise collapse all
        any_collapsed = any(not row.is_expanded for row in self._rows.values())
        if any_collapsed:
            self.expand_all()
            return True
        else:
            self.collapse_all()
            return False

    def is_all_expanded(self) -> bool:
        """Check if all rows are expanded."""
        if not self._rows:
            return False
        return all(row.is_expanded for row in self._rows.values())

    def get_row(self, serial: str) -> Optional[DeviceRowWidget]:
        """Get a device row by serial."""
        return self._rows.get(serial)

    def clear(self) -> None:
        """Remove all device rows."""
        for serial in list(self._rows.keys()):
            row = self._rows.pop(serial)
            self._layout.removeWidget(row)
            row.deleteLater()

        self._selected_serials.clear()
        self._active_serial = None
        self._expanded_serials.clear()


__all__ = ['ExpandableDeviceList', 'DeviceRowWidget', 'DeviceDetailPanel']
