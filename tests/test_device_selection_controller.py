import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ui.device_list_controller import DeviceListController


class DummyVirtualizedList:
    def __init__(self):
        self.select_all_called = False
        self.deselect_all_called = False
        self.checked_devices = set()

    def select_all_devices(self):
        self.select_all_called = True
        self.checked_devices = {"A", "B", "C"}

    def deselect_all_devices(self):
        self.deselect_all_called = True
        self.checked_devices.clear()


class DummySearchManager:
    def __init__(self):
        self._search_text = ""
        self._sort_mode = "default"

    def get_search_text(self):
        return self._search_text

    def set_search_text(self, text):
        self._search_text = text

    def get_sort_mode(self):
        return self._sort_mode


class DummyLabel:
    def __init__(self):
        self.text_value = ""

    def setText(self, value):
        self.text_value = value


class DummyWindow:
    def __init__(self):
        self.virtualized_active = False
        self.virtualized_device_list = None
        self.check_devices = {}
        self.device_dict = {}
        self.device_search_manager = DummySearchManager()
        self.title_label = DummyLabel()

    def get_checked_devices(self):
        return [serial for serial, checkbox in self.check_devices.items() if checkbox.isChecked()]


class DummyCheckbox:
    def __init__(self):
        self.checked = False
        self.visible = True

    def setChecked(self, value):
        self.checked = bool(value)

    def isChecked(self):
        return self.checked

    def setVisible(self, value):
        self.visible = bool(value)

    def isVisible(self):
        return self.visible


class DeviceSelectionControllerTest(unittest.TestCase):
    def setUp(self):
        self.window = DummyWindow()
        self.controller = DeviceListController(self.window)

    def test_select_all_devices_standard_mode_checks_all(self):
        checkbox_a = DummyCheckbox()
        checkbox_b = DummyCheckbox()
        self.window.check_devices = {"A": checkbox_a, "B": checkbox_b}

        self.controller.select_all_devices()

        self.assertTrue(checkbox_a.checked)
        self.assertTrue(checkbox_b.checked)

    def test_select_all_devices_virtualized_uses_virtual_list(self):
        vlist = DummyVirtualizedList()
        self.window.virtualized_active = True
        self.window.virtualized_device_list = vlist

        self.controller.select_all_devices()

        self.assertTrue(vlist.select_all_called)

    def test_select_no_devices_clears_all(self):
        checkbox_a = DummyCheckbox()
        checkbox_b = DummyCheckbox()
        checkbox_a.setChecked(True)
        checkbox_b.setChecked(True)
        self.window.check_devices = {"A": checkbox_a, "B": checkbox_b}

        self.controller.select_no_devices()

        self.assertFalse(checkbox_a.checked)
        self.assertFalse(checkbox_b.checked)

    def test_update_selection_count_without_search(self):
        checkbox_a = DummyCheckbox()
        checkbox_b = DummyCheckbox()
        checkbox_b.setChecked(True)
        self.window.check_devices = {"A": checkbox_a, "B": checkbox_b}
        self.window.device_dict = {"A": object(), "B": object(), "C": object()}

        self.controller.update_selection_count()

        self.assertIn("Connected Devices (3)", self.window.title_label.text_value)
        self.assertIn("Selected: 1", self.window.title_label.text_value)

    def test_update_selection_count_with_search(self):
        checkbox_a = DummyCheckbox()
        checkbox_b = DummyCheckbox()
        checkbox_b.setChecked(True)
        checkbox_b.setVisible(False)
        self.window.check_devices = {"A": checkbox_a, "B": checkbox_b}
        self.window.device_dict = {"A": object(), "B": object()}
        self.window.device_search_manager.set_search_text("pixel")

        self.controller.update_selection_count()

        self.assertIn("Connected Devices (1/2)", self.window.title_label.text_value)
        self.assertIn("Selected: 1", self.window.title_label.text_value)


if __name__ == "__main__":
    unittest.main()
