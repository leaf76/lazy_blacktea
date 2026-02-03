import os
import sys
import unittest
from unittest.mock import Mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class DummyStatusBarManager:
    def __init__(self) -> None:
        self.update_calls = []
        self.reset_calls = 0

    def update_progress(self, *, current: int, total: int, message: str) -> None:
        self.update_calls.append((current, total, message))

    def reset_progress(self) -> None:
        self.reset_calls += 1


class DummyApkManager:
    def __init__(self, state: object) -> None:
        self._state = state

    def get_installation_progress_state(self) -> object:
        return self._state


class DummyAppManagementManager:
    def __init__(self, apk_manager: DummyApkManager) -> None:
        self.apk_manager = apk_manager


class InstallApkProgressHandlerTests(unittest.TestCase):
    def test_handle_installation_progress_updates_status_bar(self) -> None:
        from ui.main_window import WindowMain

        state = object()

        window = Mock()
        window.status_bar_manager = DummyStatusBarManager()
        window.app_management_manager = DummyAppManagementManager(DummyApkManager(state))
        window.overlay_calls = []

        def apply_overlay(action_key: str, received_state: object) -> None:
            window.overlay_calls.append((action_key, received_state))

        window._apply_progress_state_to_overlay = apply_overlay

        WindowMain._handle_installation_progress(window, "Installing APK\nStep 1", 1, 3)

        self.assertEqual(window.status_bar_manager.update_calls[-1], (1, 3, "Installing APK"))
        self.assertEqual(window.overlay_calls[-1], ("install_apk", state))


class ApkInstallationManagerSignalTests(unittest.TestCase):
    def test_apk_manager_exposes_operation_signals(self) -> None:
        from ui.app_management_manager import ApkInstallationManager

        manager = ApkInstallationManager(Mock())

        self.assertTrue(hasattr(manager, "operation_started_signal"))
        self.assertTrue(hasattr(manager, "operation_finished_signal"))


class ApkPushProgressParsingTests(unittest.TestCase):
    def test_parse_push_progress_percent_and_speed(self) -> None:
        from ui.app_management_manager import ApkInstallationManager

        percent, speed = ApkInstallationManager._parse_adb_push_progress(
            "1234 KB/s (10%)"
        )
        self.assertEqual(percent, 10)
        self.assertEqual(speed, "1234 KB/s")

    def test_parse_push_progress_final_speed_marks_complete(self) -> None:
        from ui.app_management_manager import ApkInstallationManager

        percent, speed = ApkInstallationManager._parse_adb_push_progress(
            "my.apk: 1 file pushed. 12.3 MB/s (123456 bytes in 0.01s)"
        )
        self.assertEqual(percent, 100)
        self.assertEqual(speed, "12.3 MB/s")


class ApkCancellationTests(unittest.TestCase):
    def test_cancel_installation_terminates_active_processes(self) -> None:
        from ui.app_management_manager import ApkInstallationManager

        parent = Mock()
        parent.logger = Mock()

        manager = ApkInstallationManager(parent)
        manager._installation_in_progress = True

        class DummyProc:
            def __init__(self) -> None:
                self.terminated = 0

            def poll(self):
                return None

            def terminate(self):
                self.terminated += 1

        proc = DummyProc()
        manager._active_processes = {"device1": proc}  # type: ignore[attr-defined]

        manager.cancel_installation()

        self.assertEqual(proc.terminated, 1)


if __name__ == "__main__":
    unittest.main()
