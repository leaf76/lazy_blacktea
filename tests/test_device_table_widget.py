import os
import sys
import unittest
from pathlib import Path

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from PyQt6.QtCore import QPoint, Qt
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication

from utils import adb_models


class DeviceTableWidgetTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self):
        from ui.device_table_widget import DeviceTableWidget  # noqa: WPS433

        self.table = DeviceTableWidget()

    def test_sorting_by_header_reorders_rows(self):
        devices = {
            'serial-b': adb_models.DeviceInfo(
                device_serial_num='serial-b',
                device_usb='usb1',
                device_prod='prod',
                device_model='Pixel 7',
                wifi_is_on=True,
                bt_is_on=False,
                android_ver='14',
                android_api_level='34',
                gms_version='35.1',
                build_fingerprint='fp',
            ),
            'serial-a': adb_models.DeviceInfo(
                device_serial_num='serial-a',
                device_usb='usb2',
                device_prod='prod',
                device_model='Galaxy S23',
                wifi_is_on=False,
                bt_is_on=True,
                android_ver='13',
                android_api_level='33',
                gms_version='34.0',
                build_fingerprint='fp',
            ),
        }

        self.table.update_devices(devices)

        # 依據型號排序（升冪）
        header = self.table.horizontalHeader()
        header.setSortIndicator(1, Qt.SortOrder.AscendingOrder)
        self.table.sortItems(1, Qt.SortOrder.AscendingOrder)
        self._app.processEvents()

        ordered_models = [
            self.table.model().index(row, 1).data(Qt.ItemDataRole.DisplayRole)
            for row in range(self.table.rowCount())
        ]
        self.assertEqual(ordered_models[0], 'Galaxy S23')
        self.assertEqual(ordered_models[1], 'Pixel 7')

        # 改為降冪
        self.table.sortItems(1, Qt.SortOrder.DescendingOrder)
        self._app.processEvents()
        ordered_models = [
            self.table.model().index(row, 1).data(Qt.ItemDataRole.DisplayRole)
            for row in range(self.table.rowCount())
        ]
        self.assertEqual(ordered_models[0], 'Pixel 7')
        self.assertEqual(ordered_models[1], 'Galaxy S23')

    def test_checking_row_updates_selection_state(self):
        devices = {
            'serial-a': adb_models.DeviceInfo(
                device_serial_num='serial-a',
                device_usb='usb1',
                device_prod='prod',
                device_model='Pixel 7',
                wifi_is_on=True,
                bt_is_on=False,
                android_ver='14',
                android_api_level='34',
                gms_version='35.1',
                build_fingerprint='fp',
            ),
        }

        self.table.update_devices(devices)

        checkbox_item = self.table.item(0, 0)
        checkbox_item.setCheckState(Qt.CheckState.Checked)

        self.assertEqual(self.table.get_checked_serials(), ['serial-a'])

    def test_table_items_are_not_editable(self):
        devices = [
            adb_models.DeviceInfo(
                device_serial_num='serial-a',
                device_usb='usb1',
                device_prod='prod',
                device_model='Pixel 8',
                wifi_is_on=True,
                bt_is_on=True,
                android_ver='15',
                android_api_level='35',
                gms_version='35.2',
                build_fingerprint='fp',
            ),
        ]

        self.table.update_devices(devices)

        model_index = self.table.model().index(0, 1)
        flags = self.table.model().flags(model_index)

        self.assertFalse(flags & Qt.ItemFlag.ItemIsEditable)

    def test_context_menu_emits_device_signal(self):
        devices = [
            adb_models.DeviceInfo(
                device_serial_num='serial-a',
                device_usb='usb1',
                device_prod='prod',
                device_model='Pixel 8',
                wifi_is_on=True,
                bt_is_on=True,
                android_ver='15',
                android_api_level='35',
                gms_version='35.2',
                build_fingerprint='fp',
            ),
        ]

        captured = []

        def _capture(position: QPoint, serial: str) -> None:
            captured.append((position, serial))

        self.table.device_context_menu_requested.connect(_capture)

        self.table.update_devices(devices)

        target_rect = self.table.visualItemRect(self.table.item(0, 1))
        local_pos = target_rect.center()

        self.table.customContextMenuRequested.emit(local_pos)

        self.assertEqual(len(captured), 1)
        emitted_pos, serial = captured[0]
        self.assertEqual(serial, 'serial-a')
        self.assertEqual(emitted_pos, local_pos)

    def test_list_context_menu_emitted_for_empty_area(self):
        captured_positions = []
        self.table.list_context_menu_requested.connect(captured_positions.append)

        # Emit from empty region below existing rows
        empty_pos = self.table.viewport().rect().bottomRight()
        self.table.customContextMenuRequested.emit(empty_pos)

        self.assertEqual(captured_positions, [empty_pos])

    def test_refresh_row_styles_does_not_trigger_extra_toggle(self):
        devices = [
            adb_models.DeviceInfo(
                device_serial_num='serial-a',
                device_usb='usb1',
                device_prod='prod',
                device_model='Pixel 8',
                wifi_is_on=True,
                bt_is_on=True,
                android_ver='15',
                android_api_level='35',
                gms_version='35.2',
                build_fingerprint='fp',
            ),
        ]

        toggles: list[tuple[str, bool]] = []

        self.table.selection_toggled.connect(lambda serial, state: toggles.append((serial, state)))

        self.table.update_devices(devices)

        checkbox_item = self.table.item(0, 0)
        checkbox_item.setCheckState(Qt.CheckState.Checked)

        # 確認第一次勾選有觸發一次
        self.assertEqual(len(toggles), 1)

        toggles.clear()

        try:
            self.table._refresh_row_styles()
        except RecursionError as exc:  # pragma: no cover - guard for regression
            self.fail(f'Refreshing row styles should not recurse: {exc}')

        self.assertEqual(toggles, [])

    def test_row_click_toggles_checkbox_selection(self):
        devices = [
            adb_models.DeviceInfo(
                device_serial_num='serial-a',
                device_usb='usb1',
                device_prod='prod',
                device_model='Pixel 8',
                wifi_is_on=True,
                bt_is_on=True,
                android_ver='15',
                android_api_level='35',
                gms_version='35.2',
                build_fingerprint='fp',
            ),
        ]

        toggles: list[tuple[str, bool]] = []
        self.table.selection_toggled.connect(lambda serial, state: toggles.append((serial, state)))

        self.table.update_devices(devices)

        target_rect = self.table.visualItemRect(self.table.item(0, 1))
        click_position = target_rect.center()

        QTest.mouseClick(self.table.viewport(), Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, click_position)
        self.assertEqual(self.table.item(0, 0).checkState(), Qt.CheckState.Checked)
        self.assertEqual(toggles[-1], ('serial-a', True))

        QTest.mouseClick(self.table.viewport(), Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, click_position)
        self.assertEqual(self.table.item(0, 0).checkState(), Qt.CheckState.Unchecked)
        self.assertEqual(toggles[-1], ('serial-a', False))


if __name__ == '__main__':
    unittest.main()
