import unittest

from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import QApplication, QMainWindow

from lazy_blacktea_pyqt import WindowMain
from ui.panels_manager import PanelsManager


class DummyConfigManager:
    """Capture UI scale updates for verification."""

    def __init__(self):
        self.saved_scales = []

    def update_ui_settings(self, **kwargs):
        self.saved_scales.append(kwargs.get('ui_scale'))


class MenuCaptureWindow(QMainWindow):
    """Stub main window to observe PanelsManager menu wiring."""

    def __init__(self):
        super().__init__()
        self.user_scale = 1.0
        self.registered_actions = None
        self.handled_scales = []
        self.auto_refresh_enabled = True
        self.refresh_interval_actions = {}

    def refresh_device_list(self):
        """Stub refresh handler."""

    def set_auto_refresh_enabled(self, enabled):
        self.auto_refresh_enabled = enabled

    def adb_start_server(self):
        """Stub ADB start."""

    def adb_kill_server(self):
        """Stub ADB kill."""

    def set_refresh_interval(self, interval):
        self.refresh_interval = interval

    def show_about_dialog(self):
        """Stub about dialog."""

    def _update_auto_refresh_action(self, enabled):
        self.auto_refresh_enabled = enabled

    def _update_refresh_interval_actions(self, interval):
        for value, action in self.refresh_interval_actions.items():
            action.setChecked(value == interval)

    def register_ui_scale_actions(self, actions):
        self.registered_actions = actions

    def handle_ui_scale_selection(self, scale):
        self.handled_scales.append(scale)


class UIScaleMenuTest(unittest.TestCase):
    """Verify UI scale menu integrates with WindowMain state."""

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.window = WindowMain.__new__(WindowMain)
        QMainWindow.__init__(self.window)
        self.window.user_scale = 1.0
        self.window.config_manager = DummyConfigManager()
        self.window.ui_scale_actions = {}
        self.addCleanup(self.window.deleteLater)

    def _create_actions(self):
        actions = {}
        for label, scale in [('Default', 1.0), ('Large', 1.25), ('Extra Large', 1.5)]:
            action = QAction(label, self.window)
            action.setCheckable(True)
            actions[scale] = action
        return actions

    def test_set_ui_scale_checks_matching_action(self):
        actions = self._create_actions()
        self.window.register_ui_scale_actions(actions)

        self.window.set_ui_scale(1.25)

        self.assertTrue(actions[1.25].isChecked())
        self.assertFalse(actions[1.0].isChecked())
        self.assertFalse(actions[1.5].isChecked())

    def test_handle_ui_scale_selection_updates_state_and_persists(self):
        actions = self._create_actions()
        self.window.register_ui_scale_actions(actions)

        self.window.handle_ui_scale_selection(1.5)

        self.assertEqual(self.window.user_scale, 1.5)
        self.assertTrue(actions[1.5].isChecked())
        self.assertIn(1.5, self.window.config_manager.saved_scales)

    def test_panels_manager_registers_and_triggers_ui_scale_actions(self):
        capture_window = MenuCaptureWindow()
        self.addCleanup(capture_window.deleteLater)

        panels = PanelsManager()
        panels.create_menu_bar(capture_window)

        self.assertIsNotNone(capture_window.registered_actions)
        self.assertSetEqual(set(capture_window.registered_actions.keys()), {1.0, 1.25, 1.5})

        capture_window.registered_actions[1.25].trigger()
        self.assertIn(1.25, capture_window.handled_scales)


if __name__ == '__main__':
    unittest.main()
