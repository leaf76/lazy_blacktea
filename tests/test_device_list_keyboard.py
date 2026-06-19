"""Tests for keyboard-first device-list navigation (audit findings #30/#31)."""

import os
import sys
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QKeyEvent
from PyQt6.QtWidgets import QApplication

from utils import adb_models
from ui.components.expandable_device_list import ExpandableDeviceList
from ui.shortcuts_overlay import ShortcutsOverlay


def _device(serial, model='Model'):
    return adb_models.DeviceInfo(
        serial, 'usb', 'prod', model, True, False, '14', '34', 'gms', 'fp'
    )


def _key(key, modifiers=Qt.KeyboardModifier.NoModifier):
    return QKeyEvent(QKeyEvent.Type.KeyPress, key, modifiers)


class DeviceListKeyboardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def _list(self):
        lst = ExpandableDeviceList()
        lst.update_devices([_device('S1'), _device('S2'), _device('S3')])
        return lst

    def test_down_then_up_moves_active(self):
        lst = self._list()
        lst.keyPressEvent(_key(Qt.Key.Key_Down))
        self.assertEqual(lst.get_active_serial(), 'S1')
        lst.keyPressEvent(_key(Qt.Key.Key_Down))
        self.assertEqual(lst.get_active_serial(), 'S2')
        lst.keyPressEvent(_key(Qt.Key.Key_Up))
        self.assertEqual(lst.get_active_serial(), 'S1')

    def test_space_toggles_active_selection(self):
        lst = self._list()
        lst.keyPressEvent(_key(Qt.Key.Key_Down))  # active S1
        lst.keyPressEvent(_key(Qt.Key.Key_Space))
        self.assertIn('S1', lst.get_selected_serials())
        lst.keyPressEvent(_key(Qt.Key.Key_Space))
        self.assertNotIn('S1', lst.get_selected_serials())

    def test_ctrl_a_selects_all_and_ctrl_shift_a_clears(self):
        lst = self._list()
        lst.keyPressEvent(_key(Qt.Key.Key_A, Qt.KeyboardModifier.ControlModifier))
        self.assertEqual(set(lst.get_selected_serials()), {'S1', 'S2', 'S3'})
        lst.keyPressEvent(
            _key(
                Qt.Key.Key_A,
                Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier,
            )
        )
        self.assertEqual(lst.get_selected_serials(), [])


class ShortcutsOverlayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_overlay_builds(self):
        overlay = ShortcutsOverlay()
        self.assertEqual(overlay.windowTitle(), 'Keyboard Shortcuts')


if __name__ == '__main__':
    unittest.main()
