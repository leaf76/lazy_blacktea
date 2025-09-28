import os
import sys
import unittest
from types import SimpleNamespace

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ['HOME'] = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.test_home')

from ui.device_group_manager import DeviceGroupManager
from ui.device_selection_manager import DeviceSelectionManager


class DummyListBox:
    def __init__(self) -> None:
        self.items = []
        self.current = None

    def clear(self) -> None:
        self.items.clear()

    def addItem(self, text: str) -> None:
        self.items.append(text)

    def currentItem(self):
        return self.current

    def setCurrent(self, text: str) -> None:
        self.current = SimpleNamespace(text=lambda: text)


class DummyLineEdit:
    def __init__(self) -> None:
        self.text_value = ""

    def setText(self, value: str) -> None:
        self.text_value = value

    def clear(self) -> None:
        self.text_value = ""

    def text(self) -> str:
        return self.text_value


class DummyWindow:
    def __init__(self) -> None:
        self.device_groups = {}
        self.device_dict = {}
        self.groups_listbox = DummyListBox()
        self.group_name_edit = DummyLineEdit()
        self.device_selection_manager = DeviceSelectionManager()
        self.device_list_controller = SimpleNamespace(_set_selection=self._set_selection_proxy)
        self.info_messages = []

    def _set_selection_proxy(self, serials):
        self.device_selection_manager.set_selected_serials(serials)

    def show_info(self, _title: str, message: str) -> None:
        self.info_messages.append(message)

    def show_error(self, _title: str, message: str) -> None:
        self.info_messages.append(message)

    def select_no_devices(self) -> None:
        self.device_selection_manager.clear()


class DeviceGroupManagerTest(unittest.TestCase):
    def setUp(self) -> None:
        self.window = DummyWindow()
        self.manager = DeviceGroupManager(self.window)

    def test_update_groups_listbox_sorts_names(self):
        self.window.device_groups = {"beta": [], "alpha": []}
        self.manager.update_groups_listbox()
        self.assertEqual(self.window.groups_listbox.items, ["alpha", "beta"])

    def test_select_devices_sets_selection_manager(self):
        self.window.device_groups = {"team": ["A", "B"]}
        self.window.device_dict = {
            "A": object(),
            "B": object(),
        }
        self.manager.select_devices_in_group_by_name("team")
        self.assertEqual(self.window.device_selection_manager.get_selected_serials(), ["A", "B"])

    def test_select_devices_reports_missing(self):
        self.window.device_groups = {"team": ["A", "C"]}
        self.window.device_dict = {"A": object()}
        self.manager.select_devices_in_group_by_name("team")
        self.assertIn("C", "\n".join(self.window.info_messages))


if __name__ == "__main__":
    unittest.main()
