import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt6.QtCore import QPoint
from PyQt6.QtWidgets import QApplication

from utils import adb_models
from ui.device_actions_controller import DeviceActionsController
from ui.device_list_controller import DeviceListController
from ui.device_detail_dialog import DeviceDetailDialog


class FakeTrigger:
    def __init__(self):
        self._callbacks = []

    def connect(self, callback):
        self._callbacks.append(callback)

    def emit(self):
        for callback in self._callbacks:
            callback()


class FakeAction:
    def __init__(self, text):
        self.text = text
        self.enabled = True
        self.triggered = FakeTrigger()

    def setEnabled(self, enabled):
        self.enabled = enabled


class FakeMenu:
    last_instance = None

    def __init__(self, *args, **kwargs):
        self.actions = []
        self.style = ''
        self.exec_pos = None
        FakeMenu.last_instance = self

    def setStyleSheet(self, style):
        self.style = style

    def addAction(self, text):
        action = FakeAction(text)
        self.actions.append(action)
        return action

    def addSeparator(self):
        self.actions.append(None)

    def exec(self, global_pos):
        self.exec_pos = global_pos


class StubCheckbox:
    def mapToGlobal(self, point):
        return point


class StubWindow:
    def __init__(self, device):
        self.device_dict = {device.device_serial_num: device}
        self.device_actions_controller = None
        self.details_called_with = None


class DeviceActionsControllerContextMenuTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.device = adb_models.DeviceInfo(
            device_serial_num='SERIAL123',
            device_usb='usb:1',
            device_prod='prodX',
            device_model='ModelX',
            wifi_is_on=True,
            bt_is_on=False,
            android_ver='13',
            android_api_level='33',
            gms_version='1.0',
            build_fingerprint='fingerprint',
            audio_state='mode=NORMAL',
            bluetooth_manager_state='ON',
        )
        self.window = StubWindow(self.device)
        self.controller = DeviceActionsController(self.window)
        self.window.device_actions_controller = self.controller

    def test_context_menu_excludes_detail_action(self):
        checkbox = StubCheckbox()
        with patch('ui.device_actions_controller.QMenu', FakeMenu):
            self.controller.show_context_menu(QPoint(0, 0), self.device.device_serial_num, checkbox)

        menu = FakeMenu.last_instance
        self.assertIsNotNone(menu)

        detail_actions = [a for a in menu.actions if isinstance(a, FakeAction) and a.text == 'ℹ️ Device Details']
        self.assertEqual(len(detail_actions), 0)


class DeviceDetailTextTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.window = type('W', (), {'battery_info_manager': None})()
        self.controller = DeviceListController(self.window)

    def test_detail_text_includes_audio_and_bt_manager(self):
        device = adb_models.DeviceInfo(
            device_serial_num='SERIAL321',
            device_usb='usb',
            device_prod='prod',
            device_model='ModelY',
            wifi_is_on=True,
            bt_is_on=True,
            android_ver='14',
            android_api_level='34',
            gms_version='2.0',
            build_fingerprint='fp',
            audio_state='mode=NORMAL | music_active=false',
            bluetooth_manager_state='ON',
        )

        with patch.object(self.controller, '_get_additional_device_info', return_value={}):
            detail_text = self.controller.get_device_detail_text(device, device.device_serial_num)

        self.assertIn('Audio: mode=NORMAL | music_active=false', detail_text)
        self.assertIn('BT Manager: ON', detail_text)
        self.assertIn('Build Fingerprint: fp', detail_text)


class DeviceDetailDialogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._app = QApplication.instance() or QApplication([])

    def test_refresh_button_updates_text(self):
        device = adb_models.DeviceInfo(
            device_serial_num='SERIAL999',
            device_usb='usb',
            device_prod='prod',
            device_model='ModelZ',
            wifi_is_on=True,
            bt_is_on=True,
            android_ver='14',
            android_api_level='34',
            gms_version='2.0',
            build_fingerprint='fp',
        )

        texts = ['initial', 'refreshed']

        def refresh_callback():
            return texts[1]

        dialog = DeviceDetailDialog(None, device, texts[0], refresh_callback, None)
        dialog._refresh_details()
        self.assertEqual(dialog.detail_view.toPlainText(), texts[1])
        dialog.close()

    def test_copy_button_calls_callback_with_detail_text(self):
        device = adb_models.DeviceInfo(
            device_serial_num='SERIAL1000',
            device_usb='usb',
            device_prod='prod',
            device_model='ModelCopy',
            wifi_is_on=True,
            bt_is_on=True,
            android_ver='15',
            android_api_level='35',
            gms_version='3.0',
            build_fingerprint='fp-copy',
        )

        received_payloads = []

        def copy_callback(detail_text):
            received_payloads.append(detail_text)

        dialog = DeviceDetailDialog(None, device, 'initial details', lambda: 'refreshed', copy_callback)
        dialog.copy_button.click()

        self.assertEqual(received_payloads, ['initial details'])
        dialog.close()

    @patch('ui.device_detail_dialog.QGuiApplication')
    def test_copy_button_without_callback_uses_clipboard(self, mock_gui_app):
        device = adb_models.DeviceInfo(
            device_serial_num='SERIAL2000',
            device_usb='usb',
            device_prod='prod',
            device_model='ModelClipboard',
            wifi_is_on=True,
            bt_is_on=True,
            android_ver='15',
            android_api_level='35',
            gms_version='3.1',
            build_fingerprint='fp-clip',
        )

        clipboard_stub = mock_gui_app.clipboard.return_value

        dialog = DeviceDetailDialog(None, device, 'detail text payload', lambda: 'detail text payload', None)
        dialog.copy_button.click()

        clipboard_stub.setText.assert_called_once_with('detail text payload')
        dialog.close()


if __name__ == '__main__':
    unittest.main()
