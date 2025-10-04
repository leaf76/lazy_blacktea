import os
import sys
import unittest

from PyQt6.QtWidgets import (
    QApplication,
    QMainWindow,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)
from PyQt6.QtGui import QAction

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lazy_blacktea_pyqt import WindowMain
from ui.console_manager import ConsoleManager
from ui.panels_manager import PanelsManager


class DummyConfigManager:
    def __init__(self):
        self.updates = []

    def update_ui_settings(self, **kwargs):
        self.updates.append(kwargs)


class DummyLoggingManager:
    def initialize_logging(self, *_):
        self.initialized = True


class ConsoleVisibilityTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.window = WindowMain.__new__(WindowMain)
        QMainWindow.__init__(self.window)
        self.window.config_manager = DummyConfigManager()
        self.window.logging_manager = DummyLoggingManager()
        self.window.write_to_console = lambda message: None
        self.window.show_console_panel = False
        self.window.console_panel = None
        self.window.console_panel_action = None
        self.window.console_manager = ConsoleManager(self.window)

        self.container = QWidget()
        layout = QVBoxLayout(self.container)
        self.window.create_console_panel(layout)
        self.container.show()
        QApplication.processEvents()

        toggle_action = QAction('Show Console Output', self.window, checkable=True)
        self.window.register_console_panel_action(toggle_action)

    def test_set_console_visibility_updates_panel_and_persists(self):
        self.assertFalse(self.window.console_panel.isVisible())
        self.assertFalse(self.window.console_panel_action.isChecked())

        self.window.set_console_panel_visibility(True)
        self.assertTrue(self.window.console_panel.isVisible())
        self.assertTrue(self.window.console_panel_action.isChecked())
        self.assertIn({'show_console_panel': True}, self.window.config_manager.updates)

        self.window.set_console_panel_visibility(False)
        self.assertFalse(self.window.console_panel.isVisible())
        self.assertFalse(self.window.console_panel_action.isChecked())
        self.assertIn({'show_console_panel': False}, self.window.config_manager.updates)


class MenuToggleHarness(QMainWindow):
    def __init__(self):
        super().__init__()
        self.show_console_panel = False
        self.console_panel_action = None
        self.toggled_state = None
        self.refresh_interval_actions = {}

    def refresh_device_list(self):
        pass

    def set_auto_refresh_enabled(self, enabled):
        pass

    def _update_auto_refresh_action(self, enabled):
        pass

    def adb_start_server(self):
        pass

    def adb_kill_server(self):
        pass

    def handle_theme_selection(self, theme_key):
        pass

    def register_theme_actions(self, actions):
        pass

    def handle_ui_scale_selection(self, scale):
        pass

    def register_ui_scale_actions(self, actions):
        pass

    def set_refresh_interval(self, interval):
        pass

    def _update_refresh_interval_actions(self, interval):
        pass

    def show_about_dialog(self):
        pass

    def handle_console_panel_toggle(self, visible: bool):
        self.toggled_state = visible

    def register_console_panel_action(self, action):
        self.console_panel_action = action

    def set_console_panel_visibility(self, visible: bool, persist: bool = True):
        self.show_console_panel = visible


class ConsoleMenuIntegrationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_menu_action_reflects_initial_state_and_triggers_toggle(self):
        window = MenuToggleHarness()
        panels = PanelsManager()
        panels.create_menu_bar(window)

        self.assertIsNotNone(window.console_panel_action)
        self.assertFalse(window.console_panel_action.isChecked())

        window.console_panel_action.trigger()
        self.assertTrue(window.console_panel_action.isChecked())
        self.assertTrue(window.toggled_state)


if __name__ == '__main__':
    unittest.main()
