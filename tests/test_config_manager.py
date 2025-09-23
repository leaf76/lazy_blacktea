"""Unit tests for ConfigManager."""

import unittest
import tempfile
import json
from pathlib import Path

from config.config_manager import ConfigManager, AppConfig, UISettings, DeviceSettings


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

        # Check default values
        self.assertEqual(config.ui.window_width, 1200)
        self.assertEqual(config.ui.window_height, 800)
        self.assertEqual(config.device.refresh_interval, 5)
        self.assertEqual(config.command.max_history_size, 50)

    def test_save_and_load_config(self):
        """Test configuration saving and loading."""
        # Create and modify config
        config = self.config_manager.load_config()
        config.ui.window_width = 1600
        config.ui.window_height = 900
        config.device.refresh_interval = 10

        # Save config
        self.config_manager.save_config(config)

        # Create new manager and load
        new_manager = ConfigManager(str(self.config_path))
        loaded_config = new_manager.load_config()

        # Verify values
        self.assertEqual(loaded_config.ui.window_width, 1600)
        self.assertEqual(loaded_config.ui.window_height, 900)
        self.assertEqual(loaded_config.device.refresh_interval, 10)

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
        self.assertEqual(config.device.refresh_interval, 5)  # Should be reset to default

    def test_update_settings(self):
        """Test settings update methods."""
        # Update UI settings
        self.config_manager.update_ui_settings(
            window_width=1800,
            ui_scale=1.5
        )

        config = self.config_manager.load_config()
        self.assertEqual(config.ui.window_width, 1800)
        self.assertEqual(config.ui.ui_scale, 1.5)

        # Update device settings
        self.config_manager.update_device_settings(
            refresh_interval=15,
            auto_connect=False
        )

        config = self.config_manager.load_config()
        self.assertEqual(config.device.refresh_interval, 15)
        self.assertEqual(config.device.auto_connect, False)

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