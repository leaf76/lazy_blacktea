"""Unit tests for ConfigManager."""

import unittest
import tempfile
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.config_manager import (
    ConfigManager,
    AppConfig,
    UISettings,
    DeviceSettings,
    LogcatSettings,
    ScrcpySettings,
    UpdateSettings,
)


class TestConfigManager(unittest.TestCase):
    """Test cases for ConfigManager."""

    def setUp(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.config_path = Path(self.temp_dir) / "test_config.json"
        self.config_manager = ConfigManager(str(self.config_path))

    def tearDown(self):
        """Clean up test environment."""
        import shutil
        if Path(self.temp_dir).exists():
            shutil.rmtree(self.temp_dir)

    def test_create_default_config(self):
        """Test default configuration creation."""
        config = self.config_manager.load_config()

        self.assertIsInstance(config, AppConfig)
        self.assertIsInstance(config.ui, UISettings)
        self.assertIsInstance(config.device, DeviceSettings)
        self.assertIsInstance(config.logcat, LogcatSettings)
        self.assertIsInstance(config.scrcpy, ScrcpySettings)
        self.assertIsInstance(config.update, UpdateSettings)

        # Check default values
        self.assertEqual(config.ui.window_width, 1200)
        self.assertEqual(config.ui.window_height, 800)
        self.assertEqual(config.device.refresh_interval, 30)
        self.assertEqual(config.command.max_history_size, 50)
        self.assertEqual(config.logcat.max_lines, 1000)
        self.assertEqual(config.logcat.history_multiplier, 5)
        self.assertEqual(config.ui.density, "cozy")
        self.assertTrue(config.scrcpy.stay_awake)
        self.assertTrue(config.scrcpy.turn_screen_off)
        self.assertTrue(config.scrcpy.disable_screensaver)
        self.assertTrue(config.update.auto_check_enabled)
        self.assertEqual(config.update.check_interval_hours, 24)
        self.assertEqual(config.update.channel, "stable")

    def test_save_and_load_config(self):
        """Test configuration saving and loading."""
        # Create and modify config
        config = self.config_manager.load_config()
        config.ui.window_width = 1600
        config.ui.window_height = 900
        config.device.refresh_interval = 20

        # Save config
        self.config_manager.save_config(config)

        # Create new manager and load
        new_manager = ConfigManager(str(self.config_path))
        loaded_config = new_manager.load_config()

        # Verify values
        self.assertEqual(loaded_config.ui.window_width, 1600)
        self.assertEqual(loaded_config.ui.window_height, 900)
        self.assertEqual(loaded_config.device.refresh_interval, 20)

    def test_config_validation(self):
        """Test configuration validation."""
        # Create invalid config
        invalid_config = {
            "ui": {
                "window_width": 1200,
                "ui_scale": 5.0  # Invalid scale
            },
            "device": {
                "refresh_interval": -1  # Invalid interval
            }
        }

        # Write invalid config
        with open(self.config_path, 'w') as f:
            json.dump(invalid_config, f)

        # Load and verify validation
        config = self.config_manager.load_config()
        self.assertEqual(config.ui.ui_scale, 1.0)  # Should be reset to default
        self.assertEqual(config.device.refresh_interval, 30)  # Should be reset to default

    def test_update_scrcpy_settings(self):
        """Test scrcpy settings update and persistence."""
        self.config_manager.update_scrcpy_settings(
            stay_awake=False,
            turn_screen_off=False,
            disable_screensaver=False,
            enable_audio_playback=False,
            bitrate='12M',
            max_size=1080,
            extra_args='--always-on-top'
        )

        config = self.config_manager.load_config()
        scrcpy_settings = config.scrcpy

        self.assertFalse(scrcpy_settings.stay_awake)
        self.assertFalse(scrcpy_settings.turn_screen_off)
        self.assertFalse(scrcpy_settings.disable_screensaver)
        self.assertFalse(scrcpy_settings.enable_audio_playback)
        self.assertEqual(scrcpy_settings.bitrate, '12M')
        self.assertEqual(scrcpy_settings.max_size, 1080)
        self.assertEqual(scrcpy_settings.extra_args, '--always-on-top')

    def test_update_settings(self):
        """Test settings update methods."""
        # Update UI settings
        self.config_manager.update_ui_settings(
            window_width=1800,
            ui_scale=1.5,
            density="compact",
        )

        config = self.config_manager.load_config()
        self.assertEqual(config.ui.window_width, 1800)
        self.assertEqual(config.ui.ui_scale, 1.5)
        self.assertEqual(config.ui.density, "compact")

        # Update device settings
        self.config_manager.update_device_settings(
            refresh_interval=15,
            auto_connect=False
        )

        config = self.config_manager.load_config()
        self.assertEqual(config.device.refresh_interval, 15)
        self.assertEqual(config.device.auto_connect, False)

    def test_update_logcat_settings(self):
        """Test logcat performance settings update."""
        self.config_manager.update_logcat_settings(
            max_lines=2000,
            history_multiplier=7,
            update_interval_ms=150,
            max_lines_per_update=80,
            max_buffer_size=250,
        )

        config = self.config_manager.load_config()
        self.assertEqual(config.logcat.max_lines, 2000)
        self.assertEqual(config.logcat.history_multiplier, 7)
        self.assertEqual(config.logcat.update_interval_ms, 150)
        self.assertEqual(config.logcat.max_lines_per_update, 80)
        self.assertEqual(config.logcat.max_buffer_size, 250)

    def test_update_settings_section_persists(self):
        """Test application updater settings update and persistence."""
        self.config_manager.update_update_settings(
            auto_check_enabled=False,
            check_interval_hours=48,
            last_check_at="2026-05-24T00:00:00+00:00",
            skipped_version="0.0.52",
            download_dir="/tmp/lazy-blacktea",
        )

        new_manager = ConfigManager(str(self.config_path))
        config = new_manager.load_config()

        self.assertFalse(config.update.auto_check_enabled)
        self.assertEqual(config.update.check_interval_hours, 48)
        self.assertEqual(config.update.last_check_at, "2026-05-24T00:00:00+00:00")
        self.assertEqual(config.update.skipped_version, "0.0.52")
        self.assertEqual(config.update.download_dir, "/tmp/lazy-blacktea")
        self.assertEqual(config.update.channel, "stable")

    def test_invalid_update_settings_fall_back_to_safe_defaults(self):
        """Invalid updater settings should not persist unsafe or noisy behavior."""
        invalid_config = {
            "update": {
                "auto_check_enabled": "yes",
                "check_interval_hours": 0,
                "last_check_at": 123,
                "skipped_version": None,
                "download_dir": None,
                "channel": "beta",
            }
        }

        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump(invalid_config, f)

        config = self.config_manager.load_config()

        self.assertTrue(config.update.auto_check_enabled)
        self.assertEqual(config.update.check_interval_hours, 24)
        self.assertEqual(config.update.last_check_at, "")
        self.assertEqual(config.update.skipped_version, "")
        self.assertEqual(config.update.download_dir, "")
        self.assertEqual(config.update.channel, "stable")

    def test_invalid_ui_density_falls_back_to_cozy(self):
        """Invalid density values should not leak into runtime styling."""
        invalid_config = {
            "ui": {
                "density": "spacious",
            }
        }

        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump(invalid_config, f)

        config = self.config_manager.load_config()

        self.assertEqual(config.ui.density, "cozy")

    def test_load_legacy_ui_scale_from_flat_config(self):
        """Ensure legacy flat ui_scale values are respected."""
        legacy_config = {
            "ui_scale": 1.4,
            "refresh_interval": 45  # Legacy device interval placement
        }

        with open(self.config_path, 'w', encoding='utf-8') as f:
            json.dump(legacy_config, f)

        config = self.config_manager.load_config()

        self.assertAlmostEqual(config.ui.ui_scale, 1.4)
        self.assertEqual(config.device.refresh_interval, 45)

    def test_export_import_config(self):
        """Test configuration export and import."""
        export_path = Path(self.temp_dir) / "exported_config.json"

        # Modify config
        config = self.config_manager.load_config()
        config.ui.theme = "light"
        config.command_history = ["test command 1", "test command 2"]
        self.config_manager.save_config(config)

        # Export config
        self.config_manager.export_config(str(export_path))
        self.assertTrue(export_path.exists())

        # Reset config
        self.config_manager.reset_to_defaults()
        reset_config = self.config_manager.load_config()
        self.assertEqual(reset_config.ui.theme, "dark")  # Default theme

        # Import config
        self.config_manager.import_config(str(export_path))
        imported_config = self.config_manager.load_config()

        # Verify imported values
        self.assertEqual(imported_config.ui.theme, "light")
        self.assertEqual(len(imported_config.command_history), 2)


if __name__ == '__main__':
    unittest.main()
