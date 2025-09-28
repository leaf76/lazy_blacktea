import os
import sys
import unittest
from types import SimpleNamespace

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ui.device_list_controller import DeviceListController
from ui.device_selection_manager import DeviceSelectionManager


class DummyVirtualizedList:
    def __init__(self):
        self.checked_devices = set()
        self.device_widgets = {}
        self.sorted_devices = []

    def set_checked_serials(self, serials, emit_signal=True):
        self.checked_devices = set(serials)


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
        self.selection_summary_label = DummyLabel()
        self.device_selection_manager = DeviceSelectionManager()
        self.pending_checked_serials = set()

    def get_checked_devices(self):
        return [serial for serial, checkbox in self.check_devices.items() if checkbox.isChecked()]


class DummyCheckbox:
    def __init__(self):
        self.checked = False
        self.visible = True
        self.tooltip = ''
        self.properties = {}
        self.blocked = False
        self._style = self._Style()

    def setChecked(self, value):
        self.checked = bool(value)

    def isChecked(self):
        return self.checked

    def setVisible(self, value):
        self.visible = bool(value)

    def isVisible(self):
        return self.visible

    def setToolTip(self, value):
        self.tooltip = value

    def blockSignals(self, value):
        self.blocked = bool(value)

    class _Style:
        def unpolish(self, _):
            pass

        def polish(self, _):
            pass

    def style(self):
        return self._style

    def update(self):
        pass

    def setProperty(self, key, value):
        self.properties[key] = value

    def setFont(self, _):
        pass

    def setContextMenuPolicy(self, _):
        pass

    class _Signal:
        def connect(self, _):
            pass

    customContextMenuRequested = _Signal()
    stateChanged = _Signal()


class DeviceSelectionControllerTest(unittest.TestCase):
    def setUp(self):
        self.window = DummyWindow()
        self.controller = DeviceListController(self.window)

    def test_select_all_devices_standard_mode_checks_all(self):
        checkbox_a = DummyCheckbox()
        checkbox_b = DummyCheckbox()
        self.window.check_devices = {"A": checkbox_a, "B": checkbox_b}
        self.window.device_dict = {
            "A": SimpleNamespace(device_model='Device A', device_serial_num='A'),
            "B": SimpleNamespace(device_model='Device B', device_serial_num='B'),
        }

        self.controller.select_all_devices()

        self.assertTrue(checkbox_a.checked)
        self.assertTrue(checkbox_b.checked)

    def test_select_all_devices_virtualized_uses_virtual_list(self):
        vlist = DummyVirtualizedList()
        self.window.virtualized_active = True
        self.window.virtualized_device_list = vlist
        self.window.device_dict = {
            "A": SimpleNamespace(device_model='Device A', device_serial_num='A'),
            "B": SimpleNamespace(device_model='Device B', device_serial_num='B'),
        }

        self.controller.select_all_devices()

        self.assertEqual(set(self.window.device_selection_manager.get_selected_serials()), {"A", "B"})

    def test_select_no_devices_clears_all(self):
        checkbox_a = DummyCheckbox()
        checkbox_b = DummyCheckbox()
        checkbox_a.setChecked(True)
        checkbox_b.setChecked(True)
        self.window.check_devices = {"A": checkbox_a, "B": checkbox_b}
        self.window.device_dict = {
            "A": SimpleNamespace(device_model='Device A', device_serial_num='A'),
            "B": SimpleNamespace(device_model='Device B', device_serial_num='B'),
        }
        self.controller._set_selection(["A", "B"])

        self.controller.select_no_devices()

        self.assertFalse(checkbox_a.checked)
        self.assertFalse(checkbox_b.checked)

    def test_update_selection_count_without_search(self):
        checkbox_a = DummyCheckbox()
        checkbox_b = DummyCheckbox()
        checkbox_b.setChecked(True)
        self.window.check_devices = {"A": checkbox_a, "B": checkbox_b}
        self.window.device_dict = {
            "A": SimpleNamespace(device_model='Device A', device_serial_num='A'),
            "B": SimpleNamespace(device_model='Device B', device_serial_num='B'),
            "C": SimpleNamespace(device_model='Device C', device_serial_num='C'),
        }
        self.controller._set_selection(["B"])

        self.controller.update_selection_count()

        self.assertIn("Connected Devices (3)", self.window.title_label.text_value)
        self.assertIn("Selected: 1", self.window.title_label.text_value)

    def test_update_selection_count_with_search(self):
        checkbox_a = DummyCheckbox()
        checkbox_b = DummyCheckbox()
        checkbox_b.setChecked(True)
        checkbox_b.setVisible(False)
        self.window.check_devices = {"A": checkbox_a, "B": checkbox_b}
        self.window.device_dict = {
            "A": SimpleNamespace(device_model='Device A', device_serial_num='A'),
            "B": SimpleNamespace(device_model='Device B', device_serial_num='B'),
        }
        self.window.device_search_manager.set_search_text("pixel")
        self.controller._set_selection(["B"])

        self.controller.update_selection_count()

        self.assertIn("Connected Devices (1/2)", self.window.title_label.text_value)
        self.assertIn("Selected: 1", self.window.title_label.text_value)

    def test_selection_summary_label_updates(self):
        self.window.device_dict = {
            "A": SimpleNamespace(device_model='Device A', device_serial_num='A'),
        }
        checkbox = DummyCheckbox()
        checkbox.setChecked(True)
        self.window.check_devices = {"A": checkbox}
        self.controller._set_selection(["A"])

        self.controller.update_selection_count()

        self.assertIn("Selected 1 of 1", self.window.selection_summary_label.text_value)
        self.assertIn("Active:", self.window.selection_summary_label.text_value)

    def test_active_device_property_reflects_last_selection(self):
        checkbox_a = DummyCheckbox()
        checkbox_b = DummyCheckbox()
        self.window.check_devices = {"A": checkbox_a, "B": checkbox_b}
        self.window.device_dict = {
            "A": SimpleNamespace(device_model='Device A', device_serial_num='A'),
            "B": SimpleNamespace(device_model='Device B', device_serial_num='B'),
        }

        self.controller._set_selection(["A"])
        self.controller.select_all_devices()

        active_serial = self.window.device_selection_manager.get_active_serial()
        self.assertEqual(active_serial, 'B')
        self.assertEqual(checkbox_b.properties.get('activeDevice'), 'true')
        self.assertNotEqual(checkbox_a.properties.get('activeDevice'), 'true')


if __name__ == "__main__":
    unittest.main()
