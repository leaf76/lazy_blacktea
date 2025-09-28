import os
import sys
import unittest
from pathlib import Path

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

PROJECT_ROOT = Path(__file__).resolve().parents[1]
os.environ['HOME'] = str(PROJECT_ROOT / '.test_home')
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from PyQt6.QtWidgets import QApplication, QLabel, QStackedWidget

from ui.device_list_controller import DeviceListController
from ui.device_selection_manager import DeviceSelectionManager
from ui.device_table_widget import DeviceTableWidget
from ui.device_search_manager import DeviceSearchManager


class _LabelProxy:
    def __init__(self) -> None:
        self._text = ''

    def setText(self, value: str) -> None:
        self._text = value

    @property
    def text(self) -> str:
        return self._text


class _WindowStub:
    def __init__(self) -> None:
        self.device_table = DeviceTableWidget()
        self.no_devices_label = QLabel('No devices found')
        self.device_panel_stack = QStackedWidget()
        self.device_panel_stack.addWidget(self.device_table)
        self.device_panel_stack.addWidget(self.no_devices_label)
        self.device_panel_stack.setCurrentWidget(self.device_table)

        self.device_selection_manager = DeviceSelectionManager()
        self.device_search_manager = DeviceSearchManager(main_window=self)
        self.title_label = _LabelProxy()
        self.selection_summary_label = _LabelProxy()
        self.device_list_controller = None
        self.device_dict = {}
        self.check_devices = {}

    def get_checked_devices(self):
        selected = self.device_selection_manager.get_selected_serials()
        return [self.device_dict[s] for s in selected if s in self.device_dict]


class DeviceListEmptyStateLayoutTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.window = _WindowStub()
        self.controller = DeviceListController(self.window)
        self.window.device_list_controller = self.controller
        self.controller.attach_table(self.window.device_table)

    def test_empty_state_switches_to_placeholder_in_stack(self):
        stack = self.window.device_panel_stack
        placeholder = self.window.no_devices_label
        table = self.window.device_table

        # Verify baseline
        self.assertIs(stack.currentWidget(), table)

        # Trigger empty state
        self.controller._update_empty_state(total_count=0, visible_count=0)
        self.assertIs(stack.currentWidget(), placeholder)
        self.assertIn('No devices', placeholder.text())

        # Restore populated state
        self.controller._update_empty_state(total_count=2, visible_count=2)
        self.assertIs(stack.currentWidget(), table)


if __name__ == '__main__':
    unittest.main()
