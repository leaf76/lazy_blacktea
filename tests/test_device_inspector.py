"""Tests for the active-device inspector summary (audit finding #13)."""

import os
import sys
import unittest
from types import SimpleNamespace

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt6.QtWidgets import QApplication

from ui.components.device_inspector import DeviceInspectorWidget


def _device():
    return SimpleNamespace(
        device_model='Pixel 7',
        device_serial_num='SER1',
        android_ver='14',
        android_api_level='34',
        wifi_is_on=True,
        bt_is_on=False,
    )


class DeviceInspectorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_none_shows_placeholder(self):
        w = DeviceInspectorWidget()
        w.set_device(None)
        self.assertTrue(w._placeholder.isVisibleTo(w) or not w.isVisible())
        self.assertFalse(w._rows_container.isVisibleTo(w))

    def test_device_populates_rows(self):
        w = DeviceInspectorWidget()
        w.set_device(_device(), 'SER1')
        text = "\n".join(row.text() for _label, row in w._value_labels.values())
        self.assertIn('Model: Pixel 7', text)
        self.assertIn('Serial: SER1', text)
        self.assertIn('Android: 14', text)
        self.assertIn('Wi-Fi: On', text)
        self.assertIn('Bluetooth: Off', text)

    def test_serial_override_used(self):
        w = DeviceInspectorWidget()
        dev = _device()
        dev.device_serial_num = 'STALE'
        w.set_device(dev, 'OVERRIDE')
        serial_row = w._value_labels['device_serial_num'][1].text()
        self.assertIn('OVERRIDE', serial_row)


if __name__ == '__main__':
    unittest.main()
