import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class DummyItem:
    def __init__(self, text: str) -> None:
        self._text = text

    def text(self) -> str:
        return self._text


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
        self.current = DummyItem(text)


class DummyLineEdit:
    def __init__(self) -> None:
        self.text_value = ""

    def setText(self, value: str) -> None:
        self.text_value = value

    def clear(self) -> None:
        self.text_value = ""


class DummyCheckbox:
    def __init__(self) -> None:
        self.checked = False

    def setChecked(self, value: bool) -> None:
        self.checked = bool(value)


class DummyVirtualizedList:
    def __init__(self) -> None:
        self.checked_serials = set()

    def set_checked_serials(self, serials):
        self.checked_serials = set(serials)


class DummyWindow:
    def __init__(self) -> None:
        self.device_groups = {}
        self.device_dict = {}
        self.groups_listbox = DummyListBox()
        self.group_name_edit = DummyLineEdit()
        self.virtualized_active = False
        self.virtualized_device_list = None
        self.check_devices = {}
        self.info_messages = []
        self.cleared_groups = 0

    def show_info(self, _title: str, message: str) -> None:
        self.info_messages.append(message)

    def show_error(self, _title: str, message: str) -> None:
        self.info_messages.append(message)

    def select_no_devices(self) -> None:
        for checkbox in self.check_devices.values():
            checkbox.setChecked(False)
        self.cleared_groups += 1


class DeviceGroupManagerTest(unittest.TestCase):
    def setUp(self) -> None:
        from ui.device_group_manager import DeviceGroupManager

        self.window = DummyWindow()
        self.manager = DeviceGroupManager(self.window)

    def test_update_groups_listbox_sorts_names(self):
        self.window.device_groups = {"beta": [], "alpha": []}
        self.manager.update_groups_listbox()
        self.assertEqual(self.window.groups_listbox.items, ["alpha", "beta"])

    def test_select_devices_marks_present_checkboxes(self):
        self.window.device_groups = {"team": ["A", "B"]}
        self.window.check_devices = {"A": DummyCheckbox()}
        self.manager.select_devices_in_group_by_name("team")
        self.assertTrue(self.window.check_devices["A"].checked)
        self.assertIn("B", self.window.info_messages[-1])

        from ui.device_group_manager import DeviceGroupSelection

        selection = DeviceGroupSelection(
            available_checkboxes=set(self.window.check_devices.keys()),
            available_device_serials=set(self.window.device_dict.keys()),
        )
        connected, missing = selection.classify(self.window.device_groups["team"], use_device_dict=False)
        self.assertEqual(connected, ["A"])
        self.assertEqual(missing, ["B"])

    def test_virtualized_selection_sets_checked_serials(self):
        self.window.virtualized_active = True
        self.window.virtualized_device_list = DummyVirtualizedList()
        self.window.device_groups = {"qa": ["A", "C"]}
        self.window.device_dict = {"A": object()}

        self.manager.select_devices_in_group_by_name("qa")
        self.assertEqual(self.window.virtualized_device_list.checked_serials, {"A"})
        self.assertIn("C", self.window.info_messages[-1])


if __name__ == "__main__":
    unittest.main()
