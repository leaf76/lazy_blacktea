import os
import sys
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt6.QtWidgets import QApplication  # noqa: E402

from config.config_manager import ConfigManager, UISettings, UpdateSettings  # noqa: E402
from ui.preferences_dialog import PreferencesDialog  # noqa: E402


_APP = QApplication.instance() or QApplication([])


class PreferencesDialogTests(unittest.TestCase):
    def setUp(self):
        self.config = ConfigManager()._create_default_config()
        self.dialog = PreferencesDialog(self.config)
        self.addCleanup(self.dialog.deleteLater)

    def test_section_switching_supports_deep_links(self):
        self.assertEqual(self.dialog.current_section(), "appearance")

        self.assertTrue(self.dialog.set_section("updates"))

        self.assertEqual(self.dialog.current_section(), "updates")
        self.assertFalse(self.dialog.set_section("missing"))
        self.assertEqual(self.dialog.current_section(), "updates")

    def test_appearance_form_loads_and_returns_theme_scale_density(self):
        self.dialog.set_appearance_values(theme="light", ui_scale=1.5, density="compact")

        self.dialog.accept()
        result = self.dialog.get_result()

        self.assertIsNotNone(result)
        self.assertEqual(result.ui.theme, "light")
        self.assertEqual(result.ui.ui_scale, 1.5)
        self.assertEqual(result.ui.density, "compact")

    def test_reject_leaves_result_empty(self):
        self.dialog.set_appearance_values(theme="light", ui_scale=1.25, density="comfortable")

        self.dialog.reject()

        self.assertIsNone(self.dialog.get_result())

    def test_invalid_density_falls_back_to_cozy(self):
        self.config.ui = UISettings(density="wide")
        dialog = PreferencesDialog(self.config)
        self.addCleanup(dialog.deleteLater)

        dialog.accept()
        result = dialog.get_result()

        self.assertEqual(result.ui.density, "cozy")

    def test_restore_defaults_resets_only_current_section_before_save(self):
        self.config.ui = UISettings(theme="light", ui_scale=1.5, density="compact")
        self.config.update = UpdateSettings(
            auto_check_enabled=False,
            check_interval_hours=48,
            skipped_version="0.0.99",
            download_dir="/tmp/lazy-blacktea",
        )
        dialog = PreferencesDialog(self.config, initial_section="appearance")
        self.addCleanup(dialog.deleteLater)

        dialog.restore_current_section_defaults()
        dialog.accept()
        result = dialog.get_result()

        self.assertEqual(result.ui.theme, "dark")
        self.assertEqual(result.ui.ui_scale, 1.0)
        self.assertEqual(result.ui.density, "cozy")
        self.assertFalse(result.update.auto_check_enabled)
        self.assertEqual(result.update.check_interval_hours, 48)
        self.assertEqual(result.update.skipped_version, "0.0.99")
        self.assertEqual(result.update.download_dir, "/tmp/lazy-blacktea")


if __name__ == "__main__":
    unittest.main(verbosity=2)
