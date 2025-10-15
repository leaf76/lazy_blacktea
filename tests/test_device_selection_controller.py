import os
import sys
import unittest
from pathlib import Path

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

PROJECT_ROOT = Path(__file__).resolve().parents[1]
os.environ['HOME'] = str(PROJECT_ROOT / '.test_home')
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication

from ui.device_list_controller import DeviceListController
from ui.device_selection_manager import DeviceSelectionManager
from ui.device_table_widget import DeviceTableWidget
from ui.device_search_manager import DeviceSearchManager
from utils import adb_models


class _Label:
    def __init__(self):
        self.text_value = ''

    def setText(self, value):
        self.text_value = value

    def setVisible(self, _value):
        return None


class _WindowStub:
    def __init__(self):
        self.device_table = DeviceTableWidget()
        self.device_selection_manager = DeviceSelectionManager()
        self.device_search_manager = DeviceSearchManager(main_window=self)
        self.title_label = _Label()
        self.selection_summary_label = _Label()
        self.device_dict = {}
        self.no_devices_label = _Label()
        self.device_list_controller = None  # populated later
        self.check_devices = {}

    def get_checked_devices(self):
        selected = self.device_selection_manager.get_selected_serials()
        return [self.device_dict[s] for s in selected if s in self.device_dict]


class DeviceSelectionControllerTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.window = _WindowStub()
        self.controller = DeviceListController(self.window)
        self.window.device_list_controller = self.controller
        devices = {
            'A': adb_models.DeviceInfo('A', 'usb', 'prod', 'Device A', True, False, '14', '34', '35', 'fp'),
            'B': adb_models.DeviceInfo('B', 'usb', 'prod', 'Device B', False, True, '13', '33', '34', 'fp'),
            'C': adb_models.DeviceInfo('C', 'usb', 'prod', 'Device C', True, True, '12', '32', '33', 'fp'),
        }
        self.window.device_dict = devices
        self.controller.update_device_list(devices)

    def test_select_all_devices_marks_all_selected(self):
        self.controller.select_all_devices()
        selected = set(self.window.device_selection_manager.get_selected_serials())
        self.assertEqual(selected, set(self.window.device_dict.keys()))
        self.assertIn('Selected 3 of 3', self.window.selection_summary_label.text_value)

    def test_select_no_devices_clears_selection(self):
        self.controller.select_all_devices()
        self.controller.select_no_devices()
        self.assertEqual(self.window.device_selection_manager.get_selected_serials(), [])
        self.assertIn('Selected 0 of 3', self.window.selection_summary_label.text_value)

    def test_update_selection_count_with_search_reflects_visible_total(self):
        self.window.device_search_manager.set_search_text('Device B')
        self.controller.filter_and_sort_devices()
        self.controller._set_selection(['B'])
        self.controller.update_selection_count()
        self.assertIn('Connected Devices (1/3)', self.window.title_label.text_value)
        self.assertIn('Selected: 1', self.window.title_label.text_value)

    def test_sort_by_selected_groups_checked_devices_first(self):
        """Sorting by the checkbox column should group checked devices."""
        selected_order = ['C', 'A']
        self.controller._set_selection(selected_order)

        # Simulate the user clicking the checkbox column header.
        self.controller._on_sort_indicator_changed(0, Qt.SortOrder.AscendingOrder)
        self.controller.filter_and_sort_devices()

        table = self.window.device_table
        selected_serials = set(self.window.device_selection_manager.get_selected_serials())

        self.assertTrue(selected_serials, 'Selection should not be empty for the test')
        self.assertNotEqual(len(selected_serials), table.rowCount(), 'Need both selected and unselected devices')

        # Ensure Qt's own sorting honours the checkbox priority.
        table.sortItems(0, Qt.SortOrder.AscendingOrder)

        seen_unselected = False
        for row in range(table.rowCount()):
            item = table.item(row, 0)
            serial = item.data(DeviceTableWidget._SERIAL_ROLE)
            is_selected = serial in selected_serials
            if seen_unselected:
                self.assertFalse(
                    is_selected,
                    f'Selected device {serial} must not appear after unselected rows when sorting by selection',
                )
            if not is_selected:
                seen_unselected = True

        self.assertTrue(seen_unselected, 'Device list should contain at least one unselected row')
        self.assertTrue(
            self.window.device_search_manager.get_sort_mode().startswith('selected'),
            'Sort mode should be mapped to the checkbox column',
        )


if __name__ == '__main__':
    unittest.main()
