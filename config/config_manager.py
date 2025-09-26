"""Configuration management module for application settings."""

import json
import logging
import os
from typing import Dict, Any, Optional
from dataclasses import dataclass, asdict
from pathlib import Path

from utils import common

logger = common.get_logger('config_manager')


@dataclass
class UISettings:
    """UI configuration settings."""
    window_width: int = 1200
    window_height: int = 800
    window_x: int = 100
    window_y: int = 100
    ui_scale: float = 1.0
    theme: str = 'dark'
    font_size: int = 10


@dataclass
class DeviceSettings:
    """Device-related settings."""
    refresh_interval: int = 30
    auto_connect: bool = True
    show_offline_devices: bool = False
    preferred_devices: list = None

    def __post_init__(self):
        if self.preferred_devices is None:
            self.preferred_devices = []


@dataclass
class CommandSettings:
    """Command execution settings."""
    max_history_size: int = 50
    auto_save_history: bool = True
    command_timeout: int = 30
    parallel_execution: bool = True


@dataclass
class LoggingSettings:
    """Logging configuration."""
    log_level: str = 'INFO'
    log_to_file: bool = True
    max_log_files: int = 10
    log_file_size_mb: int = 10


@dataclass
class AppConfig:
    """Main application configuration."""
    ui: UISettings
    device: DeviceSettings
    command: CommandSettings
    logging: LoggingSettings
    command_history: list = None
    version: str = "1.0.0"

    def __post_init__(self):
        if self.command_history is None:
            self.command_history = []


class ConfigManager:
    """Manages application configuration persistence and validation."""

    DEFAULT_CONFIG_PATH = '~/.lazy_blacktea_config.json'
    BACKUP_CONFIG_PATH = '~/.lazy_blacktea_config.backup.json'

    def __init__(self, config_path: Optional[str] = None):
        self.config_path = Path(config_path or self.DEFAULT_CONFIG_PATH).expanduser()
        self.backup_path = Path(self.BACKUP_CONFIG_PATH).expanduser()
        self._config: Optional[AppConfig] = None
        self._ensure_config_dir()

    def _ensure_config_dir(self):
        """Ensure configuration directory exists."""
        self.config_path.parent.mkdir(parents=True, exist_ok=True)

    def _create_default_config(self) -> AppConfig:
        """Create default configuration."""
        return AppConfig(
            ui=UISettings(),
            device=DeviceSettings(),
            command=CommandSettings(),
            logging=LoggingSettings()
        )

    def _validate_config(self, config_dict: Dict[str, Any]) -> Dict[str, Any]:
        """Validate and clean configuration dictionary."""
        # Ensure all required sections exist
        default_config = asdict(self._create_default_config())

        # Merge with defaults for missing keys
        def merge_dict(default: Dict, user: Dict) -> Dict:
            result = default.copy()
            for key, value in user.items():
                if key in result:
                    if isinstance(value, dict) and isinstance(result[key], dict):
                        result[key] = merge_dict(result[key], value)
                    else:
                        result[key] = value
            return result

        validated = merge_dict(default_config, config_dict)

        # Validate specific constraints
        ui_settings = validated.get('ui', {})
        if ui_settings.get('ui_scale', 1.0) < 0.5 or ui_settings.get('ui_scale', 1.0) > 3.0:
            ui_settings['ui_scale'] = 1.0
            logger.warning('UI scale out of range, reset to 1.0')

        device_settings = validated.get('device', {})
        if device_settings.get('refresh_interval', 30) < 1:
            device_settings['refresh_interval'] = 30
            logger.warning('Refresh interval too low, reset to 30 seconds')

        return validated

    def load_config(self) -> AppConfig:
        """Load configuration from file."""
        if self._config is not None:
            return self._config

        try:
            if self.config_path.exists():
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    config_dict = json.load(f)

                validated_dict = self._validate_config(config_dict)

                # Convert to dataclass
                self._config = AppConfig(
                    ui=UISettings(**validated_dict['ui']),
                    device=DeviceSettings(**validated_dict['device']),
                    command=CommandSettings(**validated_dict['command']),
                    logging=LoggingSettings(**validated_dict['logging']),
                    command_history=validated_dict.get('command_history', []),
                    version=validated_dict.get('version', '1.0.0')
                )

                logger.info(f'Configuration loaded from {self.config_path}')
            else:
                self._config = self._create_default_config()
                logger.info('Created default configuration')

        except Exception as e:
            logger.error(f'Failed to load config: {e}')
            # Try backup if available
            if self.backup_path.exists():
                try:
                    logger.info('Attempting to load from backup')
                    with open(self.backup_path, 'r', encoding='utf-8') as f:
                        config_dict = json.load(f)
                    validated_dict = self._validate_config(config_dict)
                    self._config = AppConfig(
                        ui=UISettings(**validated_dict['ui']),
                        device=DeviceSettings(**validated_dict['device']),
                        command=CommandSettings(**validated_dict['command']),
                        logging=LoggingSettings(**validated_dict['logging']),
                        command_history=validated_dict.get('command_history', []),
                        version=validated_dict.get('version', '1.0.0')
                    )
                    logger.info('Configuration loaded from backup')
                except Exception as backup_error:
                    logger.error(f'Backup config also failed: {backup_error}')
                    self._config = self._create_default_config()
            else:
                self._config = self._create_default_config()

        return self._config

    def save_config(self, config: Optional[AppConfig] = None):
        """Save configuration to file."""
        if config is None:
            config = self._config

        if config is None:
            logger.warning('No configuration to save')
            return

        try:
            # Create backup of existing config
            if self.config_path.exists():
                try:
                    import shutil
                    shutil.copy2(self.config_path, self.backup_path)
                except Exception as e:
                    logger.warning(f'Failed to create config backup: {e}')

            # Save new config
            config_dict = asdict(config)
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(config_dict, f, indent=4, ensure_ascii=False)

            self._config = config
            logger.info(f'Configuration saved to {self.config_path}')

        except Exception as e:
            logger.error(f'Failed to save config: {e}')
            raise

    def get_ui_settings(self) -> UISettings:
        """Get UI settings."""
        return self.load_config().ui

    def get_device_settings(self) -> DeviceSettings:
        """Get device settings."""
        return self.load_config().device

    def get_command_settings(self) -> CommandSettings:
        """Get command settings."""
        return self.load_config().command

    def get_logging_settings(self) -> LoggingSettings:
        """Get logging settings."""
        return self.load_config().logging

    def update_ui_settings(self, **kwargs):
        """Update UI settings."""
        config = self.load_config()
        for key, value in kwargs.items():
            if hasattr(config.ui, key):
                setattr(config.ui, key, value)
        self.save_config(config)

    def update_device_settings(self, **kwargs):
        """Update device settings."""
        config = self.load_config()
        for key, value in kwargs.items():
            if hasattr(config.device, key):
                setattr(config.device, key, value)
        self.save_config(config)

    def update_command_settings(self, **kwargs):
        """Update command settings."""
        config = self.load_config()
        for key, value in kwargs.items():
            if hasattr(config.command, key):
                setattr(config.command, key, value)
        self.save_config(config)

    def reset_to_defaults(self):
        """Reset configuration to defaults."""
        self._config = self._create_default_config()
        self.save_config()
        logger.info('Configuration reset to defaults')

    def export_config(self, filepath: str):
        """Export configuration to file."""
        config = self.load_config()
        export_path = Path(filepath).expanduser()

        try:
            with open(export_path, 'w', encoding='utf-8') as f:
                json.dump(asdict(config), f, indent=4, ensure_ascii=False)
            logger.info(f'Configuration exported to {export_path}')
        except Exception as e:
            logger.error(f'Failed to export config: {e}')
            raise

    def import_config(self, filepath: str):
        """Import configuration from file."""
        import_path = Path(filepath).expanduser()

        try:
            with open(import_path, 'r', encoding='utf-8') as f:
                config_dict = json.load(f)

            validated_dict = self._validate_config(config_dict)
            imported_config = AppConfig(
                ui=UISettings(**validated_dict['ui']),
                device=DeviceSettings(**validated_dict['device']),
                command=CommandSettings(**validated_dict['command']),
                logging=LoggingSettings(**validated_dict['logging']),
                command_history=validated_dict.get('command_history', []),
                version=validated_dict.get('version', '1.0.0')
            )

            self.save_config(imported_config)
            logger.info(f'Configuration imported from {import_path}')

        except Exception as e:
            logger.error(f'Failed to import config: {e}')
            raise
