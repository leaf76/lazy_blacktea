import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ui.device_selection_manager import DeviceSelectionManager


class DeviceSelectionManagerTest(unittest.TestCase):
    def setUp(self):
        self.manager = DeviceSelectionManager()

    def test_apply_toggle_adds_selection_and_sets_active(self):
        self.manager.apply_toggle('device-a', True)

        self.assertEqual(self.manager.get_selected_serials(), ['device-a'])
        self.assertEqual(self.manager.get_active_serial(), 'device-a')

    def test_apply_toggle_uncheck_updates_active(self):
        self.manager.apply_toggle('device-a', True)
        self.manager.apply_toggle('device-b', True)
        self.assertEqual(self.manager.get_active_serial(), 'device-b')

        self.manager.apply_toggle('device-b', False)

        self.assertEqual(self.manager.get_selected_serials(), ['device-a'])
        self.assertEqual(self.manager.get_active_serial(), 'device-a')

    def test_set_selected_serials_uses_last_as_active(self):
        self.manager.set_selected_serials(['device-a', 'device-b', 'device-c'])

        self.assertEqual(self.manager.get_selected_serials(), ['device-a', 'device-b', 'device-c'])
        self.assertEqual(self.manager.get_active_serial(), 'device-c')

    def test_prune_selection_reassigns_active(self):
        self.manager.set_selected_serials(['device-a', 'device-b'])
        self.manager.set_active_serial('device-b')

        remaining = self.manager.prune_selection({'device-a'})

        self.assertEqual(remaining, ['device-a'])
        self.assertEqual(self.manager.get_active_serial(), 'device-a')

    def test_require_single_device_prefers_active(self):
        self.manager.set_selected_serials(['device-a', 'device-b'])
        self.manager.set_active_serial('device-a')

        valid, serials, message = self.manager.require_single_device('Screenshot')

        self.assertTrue(valid)
        self.assertEqual(serials, ['device-a'])
        self.assertIsNone(message)

    def test_require_single_device_defaults_to_last_when_no_active(self):
        self.manager.set_selected_serials(['device-a', 'device-b'])
        self.manager.set_active_serial(None)

        valid, serials, message = self.manager.require_single_device('Screenshot')

        self.assertTrue(valid)
        self.assertEqual(serials, ['device-b'])
        self.assertIsNone(message)

    def test_require_any_device(self):
        valid, serials, message = self.manager.require_any_device('Batch Install')
        self.assertFalse(valid)
        self.assertEqual(serials, [])
        self.assertIn('select at least one', message)

        self.manager.apply_toggle('device-a', True)
        valid, serials, message = self.manager.require_any_device('Batch Install')

        self.assertTrue(valid)
        self.assertEqual(serials, ['device-a'])
        self.assertIsNone(message)


if __name__ == '__main__':
    unittest.main()
