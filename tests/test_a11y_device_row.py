"""Accessibility regression tests for device rows (audit finding #8).

Each device checkbox must carry a per-device accessible name so screen-reader
users can tell which device a checkbox toggles.
"""

import os
import sys
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt6.QtWidgets import QApplication

from utils import adb_models
from ui.components.expandable_device_list import DeviceRowWidget


def _device(serial, model):
    return adb_models.DeviceInfo(
        serial, 'usb', 'prod', model, True, False, '14', '34', 'gms', 'fp'
    )


class DeviceRowAccessibilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_checkbox_has_per_device_accessible_name(self):
        row = DeviceRowWidget(_device('SER1', 'Pixel 7'))
        name = row._checkbox.accessibleName()
        self.assertIn('Pixel 7', name)
        self.assertIn('SER1', name)

    def test_accessible_name_updates_on_device_change(self):
        row = DeviceRowWidget(_device('SER1', 'Pixel 7'))
        row.update_device(_device('SER1', 'Galaxy S24'))
        self.assertIn('Galaxy S24', row._checkbox.accessibleName())


if __name__ == '__main__':
    unittest.main()
