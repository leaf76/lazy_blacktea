"""Regression tests for reboot confirmation (audit finding #2).

Right-click reboot entry points used to bypass confirmation because the prompt
only lived in the Tools panel handler. Confirmation now lives in
``WindowMain.reboot_device`` so every entry point is covered. These tests call
the unbound method against a lightweight stub ``self`` so we do not need to build
a full ``WindowMain``/``QApplication``.
"""

import os
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ui.main_window import WindowMain


def _device(serial, model):
    return SimpleNamespace(device_serial_num=serial, device_model=model)


class RebootConfirmationTests(unittest.TestCase):
    def _stub(self, devices, confirm):
        return SimpleNamespace(
            get_checked_devices=MagicMock(return_value=devices),
            _confirm_reboot=MagicMock(return_value=confirm),
            _on_operation_started=MagicMock(),
            _run_adb_tool_on_selected_devices=MagicMock(),
        )

    def test_reboot_aborts_when_user_declines(self):
        stub = self._stub([_device('S1', 'Pixel'), _device('S2', 'Galaxy')], confirm=False)

        WindowMain.reboot_device(stub)

        stub._confirm_reboot.assert_called_once_with(2)
        stub._run_adb_tool_on_selected_devices.assert_not_called()
        stub._on_operation_started.assert_not_called()

    def test_reboot_proceeds_when_confirmed(self):
        stub = self._stub([_device('S1', 'Pixel')], confirm=True)

        WindowMain.reboot_device(stub)

        stub._confirm_reboot.assert_called_once_with(1)
        stub._run_adb_tool_on_selected_devices.assert_called_once()

    def test_reboot_with_no_devices_does_not_prompt(self):
        stub = self._stub([], confirm=True)

        WindowMain.reboot_device(stub)

        stub._confirm_reboot.assert_not_called()

    def test_multi_device_confirm_message_includes_count(self):
        message = WindowMain._build_reboot_confirm_message(3)
        self.assertIn('3 devices', message)

    def test_single_device_confirm_message_omits_count(self):
        message = WindowMain._build_reboot_confirm_message(1)
        self.assertNotIn('devices.', message)
        self.assertNotIn('affect', message)


if __name__ == '__main__':
    unittest.main()
