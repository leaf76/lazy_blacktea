#!/usr/bin/env python3
"""Tests for preserving selection when switching to the virtualized device list."""

import os
import pathlib
import unittest
from types import SimpleNamespace


PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
os.environ["HOME"] = str(PROJECT_ROOT / ".test_home")

from lazy_blacktea_pyqt import WindowMain


class FakeCheckbox:
    """Minimal checkbox stub that tracks checked state."""

    def __init__(self, checked: bool = False):
        self._checked = checked

    def isChecked(self) -> bool:
        return self._checked

    def setChecked(self, value: bool) -> None:
        self._checked = value


class FakeWidget:
    """Minimal widget stub modeling Qt parent relationships."""

    def __init__(self):
        self._parent = None

    def parent(self):  # noqa: D401 - mimic Qt API
        return self._parent

    def setParent(self, parent):  # noqa: D401 - mimic Qt API
        self._parent = parent


class FakeScrollArea:
    """Simplified scroll area used to host widgets in tests."""

    def __init__(self, widget=None):
        self._widget = None
        if widget is not None:
            self.setWidget(widget)

    def takeWidget(self):
        widget = self._widget
        self._widget = None
        return widget

    def setWidget(self, widget):
        self._widget = widget
        widget.setParent(self)

    def widget(self):
        return self._widget

    def setUpdatesEnabled(self, _):  # pragma: no cover - compatibility stub
        pass


class FakeVirtualizedDeviceList:
    """Test double mirroring the ordering behaviour of the real widget."""

    def __init__(self):
        self.device_dict = {}
        self.sorted_devices = []
        self.checked_devices = set()
        self.call_history = []
        self._widget = FakeWidget()

    def get_widget(self):
        return self._widget

    def update_device_list(self, device_dict):
        self.call_history.append("update")
        self.device_dict = device_dict
        self.sorted_devices = list(device_dict.items())

    def apply_search_and_sort(self):  # pragma: no cover - compatibility stub
        pass

    def set_checked_serials(self, serials):
        self.call_history.append("set")
        serials_set = set(serials)
        current_serials = set(self.device_dict.keys())
        self.checked_devices = serials_set & current_serials

    def clear_widgets(self):  # pragma: no cover - compatibility stub
        pass

    def get_checked_devices(self):  # pragma: no cover - compatibility stub
        return [self.device_dict[s] for s in self.checked_devices]


class VirtualizedSelectionPreservationTest(unittest.TestCase):
    """Behavioural tests around switching to the virtualized device list."""

    def setUp(self):
        self.window = WindowMain.__new__(WindowMain)
        self.window.device_dict = {}
        self.window.virtualized_active = False
        self.window.pending_checked_serials = set()
        self.window.check_devices = {}
        self.window.checkbox_pool = []
        self.window.device_layout = None

        standard_widget = FakeWidget()
        self.window.device_scroll = FakeScrollArea(standard_widget)
        self.window.standard_device_widget = standard_widget

        self.window.virtualized_device_list = FakeVirtualizedDeviceList()
        self.window.virtualized_widget = self.window.virtualized_device_list.get_widget()

        self.window._release_all_standard_checkboxes = lambda: self.window.check_devices.clear()
        self.window._update_virtualized_title = lambda: None
        self.window.update_selection_count = lambda: None
        self.window._release_device_checkbox = lambda checkbox: None
        self.window._apply_device_checkbox_style = lambda checkbox: None
        self.window._get_filtered_sorted_devices = lambda device_dict: list(device_dict.values())

    def test_preserves_selection_when_virtualization_is_enabled(self):
        """Ensure checked devices remain selected after switching views."""
        selected_serial = "device-1"
        for idx in range(5):
            serial = f"device-{idx}"
            self.window.check_devices[serial] = FakeCheckbox(checked=(serial == selected_serial))

        initial_devices = {
            serial: SimpleNamespace(device_serial_num=serial)
            for serial in self.window.check_devices
        }
        self.window.device_dict = initial_devices

        expanded_devices = {
            f"device-{idx}": SimpleNamespace(device_serial_num=f"device-{idx}")
            for idx in range(12)
        }

        self.window.update_device_list(expanded_devices)

        self.assertEqual(
            self.window.virtualized_device_list.call_history,
            ["update", "set"],
            "Virtualized list should receive data before selections are applied."
        )
        self.assertIn(
            selected_serial,
            self.window.virtualized_device_list.checked_devices,
            "Previously checked devices should stay selected after virtualization switches on."
        )


if __name__ == "__main__":  # pragma: no cover - manual execution helper
    unittest.main()
