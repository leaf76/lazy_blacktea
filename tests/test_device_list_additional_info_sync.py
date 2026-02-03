import os
import sys
import unittest
from unittest.mock import Mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class DummyDeviceList:
    def __init__(self) -> None:
        self.update_devices_calls = []
        self.set_selected_calls = []
        self.additional_info_calls = []

    def update_devices(self, devices):
        self.update_devices_calls.append(list(devices))

    def set_selected_serials(self, serials, active_serial=None):
        self.set_selected_calls.append((list(serials), active_serial))

    def set_additional_info(self, serial: str, info: dict):
        self.additional_info_calls.append((serial, dict(info)))


class DummySelectionManager:
    def prune_selection(self, existing_serials):
        return []

    def get_active_serial(self):
        return None

    def get_selected_serials(self):
        return []


class DummyBatteryInfoManager:
    def __init__(self, cache: dict) -> None:
        self._cache = cache

    def get_cached_info(self, serial: str) -> dict:
        return dict(self._cache.get(serial, {}))


class DeviceListAdditionalInfoSyncTests(unittest.TestCase):
    def test_update_device_list_pushes_cached_additional_info_to_rows(self) -> None:
        from ui.device_list_controller import DeviceListController
        from utils.adb_models import DeviceInfo

        device_a = DeviceInfo(
            device_serial_num="serial_a",
            device_usb="usb",
            device_prod="prod",
            device_model="Model A",
            wifi_is_on=False,
            bt_is_on=False,
            android_ver="14",
            android_api_level="34",
            gms_version="Unknown",
            build_fingerprint="fp",
        )
        device_b = DeviceInfo(
            device_serial_num="serial_b",
            device_usb="usb",
            device_prod="prod",
            device_model="Model B",
            wifi_is_on=False,
            bt_is_on=False,
            android_ver="13",
            android_api_level="33",
            gms_version="Unknown",
            build_fingerprint="fp",
        )

        device_dict = {"serial_a": device_a, "serial_b": device_b}
        battery_cache = {
            "serial_a": {"battery_level": "55"},
            "serial_b": {"battery_level": "90"},
        }

        window = Mock()
        window.device_dict = {}
        window.device_selection_manager = DummySelectionManager()
        window.device_search_manager = Mock()
        window.device_search_manager.get_search_text.return_value = ""
        window.device_search_manager.get_sort_mode.return_value = "name"
        window.battery_info_manager = DummyBatteryInfoManager(battery_cache)

        controller = DeviceListController(window)
        controller.table = None
        controller.device_list = DummyDeviceList()

        controller._get_filtered_sorted_devices = lambda *_args, **_kwargs: [
            device_a,
            device_b,
        ]
        controller._update_empty_state = lambda *_args, **_kwargs: None
        controller.update_selection_count = lambda *_args, **_kwargs: None

        controller.update_device_list(device_dict)

        self.assertEqual(
            controller.device_list.additional_info_calls,
            [
                ("serial_a", {"battery_level": "55"}),
                ("serial_b", {"battery_level": "90"}),
            ],
        )


if __name__ == "__main__":
    unittest.main()

