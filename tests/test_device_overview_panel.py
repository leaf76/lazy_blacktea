import types
import unittest
from collections import OrderedDict
from unittest.mock import Mock

from PyQt6.QtWidgets import QApplication, QTabWidget, QLabel

from utils import adb_models
from ui.device_selection_manager import DeviceSelectionManager
from ui.tools_panel_controller import ToolsPanelController


class DeviceOverviewPanelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.stub_window = types.SimpleNamespace(
            device_selection_manager=DeviceSelectionManager(),
            device_dict={},
            refresh_active_device_overview=lambda: None,
            copy_active_device_overview=lambda: None,
        )
        self.controller = ToolsPanelController(self.stub_window)

    def test_overview_tab_is_added_first(self):
        tab_widget = QTabWidget()
        self.controller._create_device_overview_tab(tab_widget)
        self.controller._create_adb_tools_tab(tab_widget)

        self.assertEqual(tab_widget.count(), 2)
        self.assertEqual(tab_widget.tabText(0), 'Overview')
        self.assertIs(self.stub_window.device_overview_widget, tab_widget.widget(0))

    def test_update_device_overview_refreshes_widget(self):
        from lazy_blacktea_pyqt import WindowMain
        from ui.device_overview_widget import DeviceOverviewWidget

        window = WindowMain.__new__(WindowMain)
        window.device_selection_manager = DeviceSelectionManager()
        window.device_dict = {}
        window.device_list_controller = types.SimpleNamespace(
            get_device_detail_text=Mock(return_value='basic detail'),
            get_on_off_status=lambda value: 'On' if value else 'Off',
            get_device_overview_summary=lambda device, serial: OrderedDict(
                (
                    ('device', [('Model', device.device_model), ('Serial', serial)]),
                    ('connectivity', [('WiFi', 'On'), ('Bluetooth', 'Off')]),
                    ('hardware', [('CPU Architecture', 'arm64')]),
                    ('battery', [('Battery Level', '82%')]),
                    ('status', [('Audio', 'mode=NORMAL')]),
                )
            ),
        )
        window.show_warning = lambda *args, **kwargs: None
        window.show_error = lambda *args, **kwargs: None
        window.device_overview_widget = DeviceOverviewWidget(window)

        device = adb_models.DeviceInfo(
            device_serial_num='SER12345',
            device_usb='usb',
            device_prod='prod',
            device_model='Pixel',
            wifi_is_on=True,
            bt_is_on=False,
            android_ver='14',
            android_api_level='34',
            gms_version='1.2',
            build_fingerprint='fp',
        )
        window.device_dict[device.device_serial_num] = device
        window.device_selection_manager.apply_toggle(device.device_serial_num, True)

        window.update_device_overview()

        detail_mock = window.device_list_controller.get_device_detail_text
        self.assertEqual(detail_mock.call_count, 1)
        _, kwargs = detail_mock.call_args
        self.assertIn('include_additional', kwargs)
        self.assertFalse(kwargs['include_additional'])
        self.assertIn('include_identity', kwargs)
        self.assertFalse(kwargs['include_identity'])
        self.assertIn('include_connectivity', kwargs)
        self.assertFalse(kwargs['include_connectivity'])
        self.assertIn('include_status', kwargs)
        self.assertTrue(kwargs['include_status'])
        self.assertIn('basic detail', window.device_overview_widget.get_current_detail_text())
        model_label = window.device_overview_widget.findChild(QLabel, 'device_overview_value_device_model')
        self.assertIsNotNone(model_label)
        self.assertEqual(model_label.text(), 'Pixel')

        hardware_label = window.device_overview_widget.findChild(
            QLabel, 'device_overview_value_hardware_cpu_architecture'
        )
        self.assertIsNotNone(hardware_label)
        self.assertEqual(hardware_label.text(), 'arm64')

        status_label = window.device_overview_widget.findChild(
            QLabel, 'device_overview_value_status_audio'
        )
        self.assertIsNotNone(status_label)
        self.assertEqual(status_label.text(), 'mode=NORMAL')

        condensed_text = window.device_overview_widget.get_current_detail_text()
        self.assertNotIn('Model:', condensed_text)
        self.assertNotIn('Serial:', condensed_text)

        # Clear selection should reset the widget state
        window.device_selection_manager.clear()
        window.update_device_overview()
        self.assertFalse(window.device_overview_widget.refresh_button.isEnabled())
        self.assertIn('Select a device', window.device_overview_widget.get_current_detail_text())


if __name__ == '__main__':
    unittest.main()
