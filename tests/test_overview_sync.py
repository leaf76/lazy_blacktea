import os
import sys
import types
import unittest
from unittest.mock import Mock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication, QMainWindow
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ui.device_list_controller import DeviceListController
from ui.device_overview_widget import DeviceOverviewWidget
from ui.device_selection_manager import DeviceSelectionManager
from ui.main_window import WindowMain
from utils.adb_models import DeviceInfo


class DummyBatteryInfoManager:
    def __init__(self, cache):
        self._cache = dict(cache)

    def get_cached_info(self, serial):
        return dict(self._cache.get(serial, {}))

    def update_cache(self, serial, info):
        self._cache[serial] = dict(info)


class OverviewSyncTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._app = QApplication.instance() or QApplication([])

    def _build_window(self, cache):
        window = QMainWindow()
        window.refresh_active_device_overview = lambda: None
        window.device_selection_manager = DeviceSelectionManager()
        window.device_dict = {}
        window.device_search_manager = Mock()
        window.device_search_manager.get_search_text.return_value = ""
        window.device_search_manager.get_sort_mode.return_value = "name"
        window.device_search_manager.search_and_sort_devices.side_effect = (
            lambda source, *_args, **_kwargs: list(source)
        )
        window.title_label = None
        window.subtitle_label = None
        window.selection_summary_label = None
        window.selection_hint_label = None
        window.terminal_manager = None
        window.check_devices = {}
        window.show_warning = lambda *args, **kwargs: None
        window.show_error = lambda *args, **kwargs: None
        window.show_device_context_menu = lambda *args, **kwargs: None
        window.battery_info_manager = DummyBatteryInfoManager(cache)
        window.device_manager = Mock()
        window.device_manager.async_device_manager = Mock(
            is_device_unauthorized=Mock(return_value=False)
        )
        window.device_manager.get_device_operation_status.return_value = ""
        window.device_manager.get_device_recording_status.return_value = {}

        controller = DeviceListController(window)
        controller.table = None
        controller.device_list = None
        window.device_list_controller = controller
        window.device_overview_widget = DeviceOverviewWidget(window)
        window.update_device_overview = lambda: WindowMain.update_device_overview(window)
        return window

    def test_update_device_list_uses_latest_cached_info_for_active_overview(self):
        window = self._build_window(
            {
                "SER123": {
                    "battery_level": "55%",
                    "screen_size": "Physical size: 100x200",
                    "screen_density": "Physical density: 300",
                    "cpu_arch": "arm64",
                }
            }
        )
        device = DeviceInfo(
            device_serial_num="SER123",
            device_usb="usb",
            device_prod="prod",
            device_model="Pixel",
            wifi_is_on=True,
            bt_is_on=False,
            android_ver="14",
            android_api_level="34",
            gms_version="1.2",
            build_fingerprint="fp",
        )
        window.device_dict = {"SER123": device}
        window.device_selection_manager.apply_toggle("SER123", True)

        window.update_device_overview()
        self.assertEqual(
            window.device_overview_widget._summary_labels["battery_battery level"].text(),
            "55%",
        )

        window.battery_info_manager.update_cache(
            "SER123",
            {
                "battery_level": "80%",
                "screen_size": "Physical size: 999x999",
                "screen_density": "Physical density: 420",
                "cpu_arch": "x86",
            },
        )

        window.device_list_controller.update_device_list(window.device_dict)

        self.assertEqual(
            window.device_overview_widget._summary_labels["battery_battery level"].text(),
            "80%",
        )
        self.assertEqual(
            window.device_overview_widget._summary_labels["hardware_screen size"].text(),
            "Physical size: 999x999",
        )
        self.assertEqual(
            window.device_overview_widget._summary_labels[
                "hardware_cpu architecture"
            ].text(),
            "x86",
        )

    def test_refresh_detail_helper_leaves_overview_rendering_to_update_method(self):
        device = DeviceInfo(
            device_serial_num="SER123",
            device_usb="usb",
            device_prod="prod",
            device_model="Pixel",
            wifi_is_on=True,
            bt_is_on=False,
            android_ver="14",
            android_api_level="34",
            gms_version="1.2",
            build_fingerprint="fp",
        )
        window = types.SimpleNamespace()
        window.device_dict = {"SER123": device}
        window.device_manager = Mock()
        window.device_manager.device_dict = {}
        window.device_manager.update_device_list = Mock()
        window.device_list_controller = Mock()
        window.device_list_controller.get_device_detail_text = Mock(
            return_value="detail text"
        )
        window.device_overview_widget = Mock()
        window.device_overview_widget.get_active_serial.return_value = "SER123"
        window.battery_info_manager = Mock()
        window.battery_info_manager.update_cache = Mock()

        detail_info = {
            "wifi_status": "1",
            "bluetooth_status": "0",
            "android_version": "15",
            "android_api_level": "35",
            "gms_version": "26.06.32",
            "build_fingerprint": "new-fp",
            "audio_state": "mode=NORMAL",
            "bluetooth_manager_state": "ON",
        }
        additional_info = {
            "battery_level": "80%",
            "screen_size": "Physical size: 999x999",
            "screen_density": "Physical density: 420",
            "cpu_arch": "x86",
        }

        with patch(
            "ui.main_window.adb_tools.get_device_detailed_info",
            return_value=detail_info,
        ), patch(
            "ui.main_window.adb_tools.get_additional_device_info",
            return_value=additional_info,
        ):
            detail_text = WindowMain._refresh_device_detail_and_get_text(window, "SER123")

        self.assertEqual(detail_text, "detail text")
        window.battery_info_manager.update_cache.assert_called_once_with(
            "SER123", additional_info
        )
        window.device_manager.update_device_list.assert_called_once_with(
            window.device_dict
        )
        window.device_overview_widget.set_overview.assert_not_called()


if __name__ == "__main__":
    unittest.main()
