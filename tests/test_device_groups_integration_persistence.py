import os
import sys
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt


class _Label:
    def setText(self, *_):
        return None

    def setVisible(self, *_):
        return None


class _Window:
    def __init__(self):
        from ui.device_table_widget import DeviceTableWidget  # noqa: WPS433
        from ui.device_selection_manager import DeviceSelectionManager  # noqa: WPS433
        from ui.device_search_manager import DeviceSearchManager  # noqa: WPS433
        from ui.device_list_controller import DeviceListController  # noqa: WPS433

        self.device_table = DeviceTableWidget()
        self.device_selection_manager = DeviceSelectionManager()
        self.device_search_manager = DeviceSearchManager(main_window=self)
        self.title_label = _Label()
        self.selection_summary_label = _Label()
        self.selection_hint_label = _Label()
        self.no_devices_label = _Label()
        self.device_panel_stack = None

        self.device_list_controller = DeviceListController(self)
        self.device_groups = {}
        self.device_dict = {}

    def get_checked_devices(self):
        selected = self.device_selection_manager.get_selected_serials()
        return [self.device_dict[s] for s in selected if s in self.device_dict]


class DeviceGroupsIntegrationPersistenceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self):
        from utils import adb_models  # noqa: WPS433

        self.window = _Window()
        self.devices = {
            'A': adb_models.DeviceInfo('A', 'usb', 'prod', 'Alpha', True, False, '14', '34', '35', 'fp'),
            'B': adb_models.DeviceInfo('B', 'usb', 'prod', 'Bravo', False, True, '13', '33', '34', 'fp'),
            'C': adb_models.DeviceInfo('C', 'usb', 'prod', 'Charlie', True, True, '12', '32', '33', 'fp'),
        }
        self.window.device_dict = self.devices
        self.window.device_list_controller.update_device_list(self.devices)

    def test_group_selection_persists_after_update_and_sort(self):
        from ui.device_group_manager import DeviceGroupManager  # noqa: WPS433

        self.window.device_groups = {'team': ['B', 'C']}
        mgr = DeviceGroupManager(self.window)

        # Select devices by group
        mgr.select_devices_in_group_by_name('team')
        self._app.processEvents()
        self.assertEqual(set(self.window.device_selection_manager.get_selected_serials()), {'B', 'C'})

        # Simulate tab change/refresh: update and sort
        self.window.device_list_controller.update_device_list(self.devices)
        self.window.device_table.sortItems(1, Qt.SortOrder.DescendingOrder)
        self._app.processEvents()

        # Selection should persist and checkboxes reflect it
        selected = set(self.window.device_selection_manager.get_selected_serials())
        self.assertEqual(selected, {'B', 'C'})
        checked = set(self.window.device_table.get_checked_serials())
        self.assertEqual(checked, {'B', 'C'})

    def test_group_selection_then_enable_single_mode_collapses_to_one(self):
        from ui.device_group_manager import DeviceGroupManager  # noqa: WPS433

        self.window.device_groups = {'team': ['B', 'C']}
        mgr = DeviceGroupManager(self.window)
        mgr.select_devices_in_group_by_name('team')
        self._app.processEvents()
        self.assertEqual(set(self.window.device_selection_manager.get_selected_serials()), {'B', 'C'})

        # Enable single-select; should collapse to exactly one selection, not clear all
        self.window.device_selection_manager.set_single_selection(True)
        remaining = self.window.device_selection_manager.get_selected_serials()
        self.assertEqual(len(remaining), 1)
        self.assertIn(remaining[0], {'B', 'C'})


if __name__ == '__main__':
    unittest.main()

