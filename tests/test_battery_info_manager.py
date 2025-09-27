import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class DummyTimer:
    class _Signal:
        def __init__(self):
            self.callback = None

        def connect(self, callback):
            self.callback = callback

    def __init__(self):
        self.interval = None
        self.started = False
        self.timeout = self._Signal()

    def setInterval(self, interval):
        self.interval = interval

    def start(self):
        self.started = True

    def stop(self):
        self.started = False

    def trigger(self):
        if self.timeout.callback:
            self.timeout.callback()


class DummyDeviceInfo:
    def __init__(self):
        self.bt_is_on = False


class DummyController:
    def __init__(self):
        self.update_calls = 0

    def update_device_list(self, device_dict):
        self.update_calls += 1
        self.last_dict = dict(device_dict)


class DummyWindow:
    def __init__(self):
        self.device_dict = {}
        self.device_list_controller = DummyController()
        self.run_in_thread = lambda func, *args, **kwargs: func()


class BatteryInfoManagerTest(unittest.TestCase):
    def setUp(self):
        from ui.battery_info_manager import BatteryInfoManager

        self.window = DummyWindow()
        self.timer = DummyTimer()
        self.fetch_calls = []

        def fetcher(serial):
            self.fetch_calls.append(serial)
            return {"battery_level": "75%"}

        self.manager = BatteryInfoManager(
            window=self.window,
            timer_factory=lambda: self.timer,
            info_fetcher=fetcher,
            post_callback=lambda func: func(),
        )

    def test_refresh_serials_updates_cache(self):
        self.window.device_dict = {"ABC": DummyDeviceInfo()}
        self.manager.refresh_serials(["ABC"])
        self.assertEqual(self.fetch_calls, ["ABC"])
        self.assertEqual(self.manager.get_cached_info("ABC")["battery_level"], "75%")
        self.assertEqual(self.window.device_list_controller.update_calls, 1)

    def test_remove_serial(self):
        self.window.device_dict = {"ABC": DummyDeviceInfo()}
        self.manager.update_cache("ABC", {"battery_level": "50%"})
        self.manager.remove("ABC")
        self.assertEqual(self.manager.get_cached_info("ABC"), {})

    def test_timer_start_and_trigger(self):
        self.window.device_dict = {"ABC": DummyDeviceInfo()}
        self.manager.start()
        self.assertTrue(self.timer.started)
        self.timer.trigger()
        self.assertIn("ABC", self.fetch_calls)


if __name__ == '__main__':
    unittest.main()
