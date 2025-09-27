import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class DummyAction:
    def __init__(self, text):
        self.text = text
        self.triggered_callbacks = []
        self.enabled = True

    @property
    def triggered(self):
        class _Signal:
            def __init__(self, outer):
                self._outer = outer

            def connect(self, callback):
                self._outer.triggered_callbacks.append(callback)

        return _Signal(self)

    def setEnabled(self, enabled):
        self.enabled = enabled

    def setText(self, text):
        self.text = text


class DummyMenu:
    def __init__(self, title=None):
        self.title = title
        self.actions = []
        self.submenus = []
        self.separators = 0
        self.exec_pos = None

    def addAction(self, text):
        action = DummyAction(text)
        self.actions.append(action)
        return action

    def addSeparator(self):
        self.separators += 1

    def addMenu(self, text):
        submenu = DummyMenu(title=text)
        self.submenus.append(submenu)
        return submenu

    def exec(self, pos):
        self.exec_pos = pos


class DummyDeviceManager:
    def __init__(self):
        self.refreshed = False

    def force_refresh(self):
        self.refreshed = True


class DummyDeviceScroll:
    def __init__(self):
        self.mapped_position = None

    def mapToGlobal(self, position):
        self.mapped_position = position
        return position


class DummyWindow:
    def __init__(self):
        self.device_groups = {}
        self.device_manager = DummyDeviceManager()
        self.device_scroll = DummyDeviceScroll()
        self.selected_all = False
        self.cleared = False
        self.copied = False
        self.group_selected = None
        self.reboot_called = False
        self.enable_bt_called = False
        self.disable_bt_called = False
        self.checked_devices = []

    def select_all_devices(self):
        self.selected_all = True

    def select_no_devices(self):
        self.cleared = True

    def copy_selected_device_info(self):
        self.copied = True

    def select_devices_in_group_by_name(self, name):
        self.group_selected = name

    def reboot_device(self):
        self.reboot_called = True

    def enable_bluetooth(self):
        self.enable_bt_called = True

    def disable_bluetooth(self):
        self.disable_bt_called = True

    def get_checked_devices(self):
        return list(self.checked_devices)


class DeviceListContextMenuManagerTest(unittest.TestCase):
    def setUp(self):
        from ui.device_list_context_menu import DeviceListContextMenuManager

        self.window = DummyWindow()
        self.manager = DeviceListContextMenuManager(
            self.window,
            menu_factory=lambda parent: DummyMenu(),
        )

    def test_basic_actions_connected(self):
        menu = self.manager.create_context_menu()
        action_texts = [action.text for action in menu.actions[:4]]
        self.assertEqual(
            action_texts,
            ['Refresh', 'Select All', 'Clear All', 'Copy Selected Device Info']
        )

        for action in menu.actions[:4]:
            for callback in action.triggered_callbacks:
                callback()

        self.assertTrue(self.window.device_manager.refreshed)
        self.assertTrue(self.window.selected_all)
        self.assertTrue(self.window.cleared)
        self.assertTrue(self.window.copied)

    def test_group_menu_populated(self):
        self.window.device_groups = {'beta': [], 'alpha': []}
        menu = self.manager.create_context_menu()
        self.assertEqual(len(menu.submenus), 1)
        group_menu = menu.submenus[0]
        names = [action.text for action in group_menu.actions]
        self.assertEqual(names, ['alpha', 'beta'])

        # Trigger first action
        for cb in group_menu.actions[0].triggered_callbacks:
            cb(True)
        self.assertEqual(self.window.group_selected, 'alpha')

    def test_group_action_disabled_when_empty(self):
        menu = self.manager.create_context_menu()
        # After separators, the next action should be the placeholder
        placeholder = menu.actions[4]
        self.assertFalse(placeholder.enabled)
        self.assertEqual(placeholder.text, 'No groups available')

    def test_device_specific_actions_added_when_selection(self):
        self.window.checked_devices = ['serial-1']
        menu = self.manager.create_context_menu()
        device_actions = [action.text for action in menu.actions[-3:]]
        self.assertEqual(
            device_actions,
            ['Reboot Selected', 'Enable Bluetooth', 'Disable Bluetooth']
        )
        for action in menu.actions[-3:]:
            for cb in action.triggered_callbacks:
                cb()
        self.assertTrue(self.window.reboot_called)
        self.assertTrue(self.window.enable_bt_called)
        self.assertTrue(self.window.disable_bt_called)

    def test_show_context_menu_maps_position(self):
        position = (10, 20)
        self.manager.show_context_menu(position)
        self.assertEqual(self.window.device_scroll.mapped_position, position)


if __name__ == "__main__":
    unittest.main()
