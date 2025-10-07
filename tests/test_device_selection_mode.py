import os
import sys
import unittest
from pathlib import Path

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt

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
        self.device_dict = {}
        self.no_devices_label = _Label()
        self.device_panel_stack = None

        self.device_list_controller = DeviceListController(self)

    def get_checked_devices(self):
        selected = self.device_selection_manager.get_selected_serials()
        return [self.device_dict[s] for s in selected if s in self.device_dict]


class DeviceSelectionModeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.window = _WindowStub()

        # Prepare sample devices
        devices = {
            'A': adb_models.DeviceInfo('A', 'usb', 'prod', 'Device A', True, False, '14', '34', '35', 'fp'),
            'B': adb_models.DeviceInfo('B', 'usb', 'prod', 'Device B', False, True, '13', '33', '34', 'fp'),
            'C': adb_models.DeviceInfo('C', 'usb', 'prod', 'Device C', True, True, '12', '32', '33', 'fp'),
        }
        self.window.device_dict = devices
        self.window.device_list_controller.update_device_list(devices)

    def _toggle_row_checkbox(self, row_index: int, checked: bool) -> None:
        item = self.window.device_table.item(row_index, 0)
        item.setCheckState(Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked)
        self._app.processEvents()

    def test_multi_select_allows_multiple(self):
        # Default is multi-select; selecting two rows should keep both
        self._toggle_row_checkbox(0, True)
        self._toggle_row_checkbox(1, True)

        selected = self.window.device_selection_manager.get_selected_serials()
        self.assertEqual(set(selected), {'A', 'B'})

    def test_single_select_allows_only_one_on_toggle(self):
        # Enable single-select mode
        self.window.device_selection_manager.set_single_selection(True)

        # Select first row
        self._toggle_row_checkbox(0, True)
        selected = self.window.device_selection_manager.get_selected_serials()
        self.assertEqual(selected, ['A'])

        # Selecting another row should replace previous one
        self._toggle_row_checkbox(1, True)
        selected = self.window.device_selection_manager.get_selected_serials()
        self.assertEqual(selected, ['B'])

    def test_enabling_single_mode_collapses_existing_selection(self):
        # Select multiple in multi-select mode
        self._toggle_row_checkbox(0, True)
        self._toggle_row_checkbox(1, True)
        self.assertEqual(set(self.window.device_selection_manager.get_selected_serials()), {'A', 'B'})

        # Enable single-select; selection should collapse to active/last
        self.window.device_selection_manager.set_single_selection(True)
        collapsed = self.window.device_selection_manager.get_selected_serials()
        self.assertEqual(len(collapsed), 1)
        # Active should be consistent
        self.assertEqual(self.window.device_selection_manager.get_active_serial(), collapsed[0])


if __name__ == '__main__':
    unittest.main()

