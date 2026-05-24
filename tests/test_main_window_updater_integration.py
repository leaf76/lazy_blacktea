import os
import sys
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt6.QtWidgets import QApplication, QMainWindow  # noqa: E402


_APP = QApplication.instance() or QApplication([])


class _FakeUpdateSettings:
    def __init__(
        self,
        *,
        auto_check_enabled=True,
        check_interval_hours=24,
        last_check_at="",
        skipped_version="",
    ):
        self.auto_check_enabled = auto_check_enabled
        self.check_interval_hours = check_interval_hours
        self.last_check_at = last_check_at
        self.skipped_version = skipped_version
        self.download_dir = ""
        self.channel = "stable"


class _FakeConfigManager:
    def __init__(self, settings):
        self.settings = settings
        self.update_calls = []

    def get_update_settings(self):
        return self.settings

    def update_update_settings(self, **kwargs):
        self.update_calls.append(kwargs)
        for key, value in kwargs.items():
            setattr(self.settings, key, value)


class _FakeDialog:
    def __init__(self, update_service=None, config_manager=None, parent=None):
        self.update_service = update_service
        self.config_manager = config_manager
        self.parent = parent
        self.started = False
        self.shown = False

    def start_check(self):
        self.started = True

    def show(self):
        self.shown = True

    def raise_(self):
        pass

    def activateWindow(self):
        pass


class MainWindowUpdaterIntegrationTests(unittest.TestCase):
    def setUp(self):
        from ui.main_window import WindowMain

        self.window = WindowMain.__new__(WindowMain)
        QMainWindow.__init__(self.window)
        self.addCleanup(self.window.deleteLater)

    def test_command_palette_includes_check_for_updates(self):
        self.window.app_shell = None

        actions = self.window._build_command_palette_actions()

        self.assertIn("Check for Updates", [action.title for action in actions])

    def test_show_update_dialog_uses_factory_and_starts_check(self):
        fake_dialog = _FakeDialog()
        self.window.update_service = object()
        self.window.config_manager = _FakeConfigManager(_FakeUpdateSettings())
        self.window._update_dialog_factory = lambda update_service, config_manager, parent: fake_dialog

        self.window.show_update_dialog()

        self.assertIs(self.window.update_dialog, fake_dialog)
        self.assertTrue(fake_dialog.shown)
        self.assertTrue(fake_dialog.started)

    def test_auto_update_check_respects_interval(self):
        self.window.config_manager = _FakeConfigManager(
            _FakeUpdateSettings(last_check_at="2026-05-24T00:00:00+00:00")
        )

        self.assertFalse(
            self.window._should_check_for_updates(now_iso="2026-05-24T12:00:00+00:00")
        )
        self.assertTrue(
            self.window._should_check_for_updates(now_iso="2026-05-25T01:00:00+00:00")
        )

    def test_auto_update_check_honors_disabled_setting(self):
        self.window.config_manager = _FakeConfigManager(
            _FakeUpdateSettings(auto_check_enabled=False)
        )

        self.assertFalse(
            self.window._should_check_for_updates(now_iso="2026-05-25T01:00:00+00:00")
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
