import os
import sys
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt6.QtWidgets import QApplication, QMainWindow  # noqa: E402

from config.config_manager import ConfigManager, UISettings  # noqa: E402
from ui.preferences_dialog import PreferencesResult  # noqa: E402


_APP = QApplication.instance() or QApplication([])


class _FakePreferencesDialog:
    def __init__(self, config, initial_section="appearance", parent=None):
        self.config = config
        self.initial_section = initial_section
        self.parent = parent
        self.exec_called = False
        self._result = None

    def exec(self):
        self.exec_called = True
        return 0

    def get_result(self):
        return self._result


class _ConfigCapture:
    def __init__(self):
        self.config = ConfigManager()._create_default_config()
        self.saved = []

    def load_config(self):
        return self.config

    def save_config(self, config):
        self.saved.append(config)
        self.config = config


class _SelectionManager:
    def __init__(self):
        self.single = True

    def set_single_selection(self, value):
        self.single = bool(value)

    def is_single_selection(self):
        return self.single


class _StatusBarManager:
    def __init__(self):
        self.selection_updates = []

    def update_selection_mode(self, value):
        self.selection_updates.append(value)


class MainWindowPreferencesIntegrationTests(unittest.TestCase):
    def setUp(self):
        from ui.main_window import WindowMain

        self.window = WindowMain.__new__(WindowMain)
        QMainWindow.__init__(self.window)
        self.addCleanup(self.window.deleteLater)
        self.window.config_manager = _ConfigCapture()
        self.window._preferences_dialog_factory = _FakePreferencesDialog

    def test_command_palette_includes_preferences_deep_links(self):
        self.window.app_shell = None

        actions = self.window._build_command_palette_actions()
        titles = [action.title for action in actions]

        self.assertIn("Preferences", titles)
        self.assertIn("Appearance Settings", titles)
        self.assertIn("Output Settings", titles)
        self.assertIn("Update Settings", titles)

    def test_open_preferences_dialog_uses_requested_section(self):
        self.window.open_preferences_dialog("updates")

        dialog = self.window.preferences_dialog
        self.assertTrue(dialog.exec_called)
        self.assertEqual(dialog.initial_section, "updates")

    def test_preferences_result_persists_and_applies_runtime_settings(self):
        config = self.window.config_manager.load_config()
        result = PreferencesResult(
            ui=UISettings(
                theme="light",
                ui_scale=1.25,
                density="compact",
                show_console_panel=True,
                single_selection=False,
            ),
            device=config.device,
            screenshot=config.screenshot,
            screen_record=config.screen_record,
            apk_install=config.apk_install,
            scrcpy=config.scrcpy,
            update=config.update,
        )
        result.device.refresh_interval = 60
        result.device.auto_connect = False
        calls = []
        self.window.apply_theme = lambda theme, persist=False, initial=False: calls.append(("theme", theme, persist))
        self.window.set_ui_scale = lambda scale: calls.append(("scale", scale))
        self.window.apply_density = lambda density, persist=False: calls.append(("density", density, persist))
        self.window.set_console_panel_visibility = lambda visible, persist=True: calls.append(("console", visible, persist))
        self.window.set_refresh_interval = lambda interval: calls.append(("refresh", interval))
        self.window.device_selection_manager = _SelectionManager()
        self.window.status_bar_manager = _StatusBarManager()
        self.window._sync_selection_mode_dependent_ui = lambda: calls.append(("selection_sync",))

        self.window._apply_preferences_result(result)

        self.assertEqual(self.window.config_manager.saved[-1].ui.density, "compact")
        self.assertFalse(self.window.config_manager.saved[-1].device.auto_connect)
        self.assertIn(("theme", "light", False), calls)
        self.assertIn(("scale", 1.25), calls)
        self.assertIn(("density", "compact", False), calls)
        self.assertIn(("console", True, False), calls)
        self.assertIn(("refresh", 60), calls)
        self.assertFalse(self.window.device_selection_manager.is_single_selection())
        self.assertEqual(self.window.status_bar_manager.selection_updates, [False])


if __name__ == "__main__":
    unittest.main(verbosity=2)
