import os
import sys
import unittest
from pathlib import Path

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

PROJECT_ROOT = Path(__file__).resolve().parents[1]
os.environ['HOME'] = str(PROJECT_ROOT / '.test_home')
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from PyQt6.QtWidgets import QApplication

from ui.device_list_controller import DeviceListController
from ui.device_selection_manager import DeviceSelectionManager
from ui.device_table_widget import DeviceTableWidget
from ui.device_search_manager import DeviceSearchManager
from utils import adb_models


class _Window:
    def __init__(self):
        self.device_table = DeviceTableWidget()
        self.device_selection_manager = DeviceSelectionManager()
        self.device_search_manager = DeviceSearchManager(main_window=self)
        self.title_label = type('L', (), {'setText': lambda *_: None})()
        self.selection_summary_label = type('L', (), {'setText': lambda *_: None})()
        self.no_devices_label = type('L', (), {'setVisible': lambda *_: None, 'setText': lambda *_: None})()
        self.device_dict = {}
        self.check_devices = {}

    def get_checked_devices(self):
        selected = self.device_selection_manager.get_selected_serials()
        return [self.device_dict[s] for s in selected if s in self.device_dict]


class SelectionPersistenceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.window = _Window()
        self.controller = DeviceListController(self.window)
        devices = {
            'A': adb_models.DeviceInfo('A', 'usb', 'prod', 'Device A', True, False, '14', '34', '35', 'fp'),
            'B': adb_models.DeviceInfo('B', 'usb', 'prod', 'Device B', False, True, '13', '33', '34', 'fp'),
        }
        self.window.device_dict = devices
        self.controller.update_device_list(devices)
        self.controller._set_selection(['A'])

    def test_selection_persists_after_refresh(self):
        expanded = {
            **self.window.device_dict,
            'C': adb_models.DeviceInfo('C', 'usb', 'prod', 'Device C', True, True, '12', '32', '33', 'fp'),
        }
        self.window.device_dict = expanded
        self.controller.update_device_list(expanded)
        self.assertEqual(self.window.device_selection_manager.get_selected_serials(), ['A'])


if __name__ == '__main__':
    unittest.main()
