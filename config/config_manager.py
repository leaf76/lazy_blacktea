"""Configuration management module for application settings."""

import json
import logging
import os
from typing import Dict, Any, Optional
from dataclasses import dataclass, asdict
from pathlib import Path

from utils import common

logger = common.get_logger("config_manager")


@dataclass
class UISettings:
    """UI configuration settings."""

    window_width: int = 1200
    window_height: int = 800
    window_x: int = 100
    window_y: int = 100
    ui_scale: float = 1.0
    theme: str = "dark"
    font_size: int = 10
    show_console_panel: bool = False
    # Device list selection mode: True means Single-select, False means Multi-select
    single_selection: bool = True
    # Global default output path for screenshots, recordings, etc.
    default_output_path: str = ""


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

    log_level: str = "INFO"
    log_to_file: bool = True
    max_log_files: int = 10
    log_file_size_mb: int = 10


@dataclass
class LogcatSettings:
    """Logcat performance tuning settings."""

    max_lines: int = 1000
    history_multiplier: int = 5
    update_interval_ms: int = 200
    max_lines_per_update: int = 50
    max_buffer_size: int = 100


@dataclass
class ScrcpySettings:
    """scrcpy mirroring configuration."""

    stay_awake: bool = True
    turn_screen_off: bool = True
    disable_screensaver: bool = True
    enable_audio_playback: bool = True
    bitrate: str = ""
    max_size: int = 0
    extra_args: str = ""


@dataclass
class ApkInstallSettings:
    """APK install configuration.

    - replace_existing (-r): Replace existing application.
    - allow_downgrade (-d): Allow versionCode downgrade.
    - grant_permissions (-g): Grant all runtime permissions.
    - allow_test_packages (-t): Allow test apks.
    - extra_args: Additional adb install args.
    """

    replace_existing: bool = True
    allow_downgrade: bool = True
    grant_permissions: bool = True
    allow_test_packages: bool = False
    extra_args: str = ""


@dataclass
class ScreenshotSettings:
    """Screenshot capture configuration."""

    # Additional args for 'screencap' (e.g., -d 0)
    extra_args: str = ""
    # Display ID for multi-display devices (-1 = default primary)
    display_id: int = -1


@dataclass
class ScreenRecordSettings:
    """Screen recording configuration."""

    bit_rate: str = ""  # e.g., 8000000 (bps)
    time_limit_sec: int = 0  # 0 means unlimited
    size: str = ""  # e.g., 1280x720
    extra_args: str = ""  # Additional args for 'screenrecord'
    # Advanced toggles
    use_hevc: bool = False  # --codec hevc (device-dependent)
    bugreport: bool = False  # --bugreport
    verbose: bool = False  # --verbose
    display_id: int = -1  # --display-id N (-1 = default)


@dataclass
class LogcatViewerSettings:
    """Logcat viewer UI preferences for panel visibility and behavior persistence."""

    compact_mode: bool = True
    show_preview_panel: bool = False
    preview_collapsed: bool = True
    recording_collapsed: bool = True
    levels_collapsed: bool = True
    filters_collapsed: bool = True
    auto_scroll_enabled: bool = True


@dataclass
class AppConfig:
    """Main application configuration."""

    ui: UISettings
    device: DeviceSettings
    command: CommandSettings
    logging: LoggingSettings
    logcat: LogcatSettings
    scrcpy: ScrcpySettings
    apk_install: ApkInstallSettings
    screenshot: ScreenshotSettings
    screen_record: ScreenRecordSettings
    logcat_viewer: LogcatViewerSettings
    command_history: list = None
    version: str = "1.0.0"

    def __post_init__(self):
        if self.command_history is None:
            self.command_history = []


class ConfigManager:
    """Manages application configuration persistence and validation."""

    DEFAULT_CONFIG_PATH = "~/.lazy_blacktea_config.json"
    BACKUP_CONFIG_PATH = "~/.lazy_blacktea_config.backup.json"

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
            logging=LoggingSettings(),
            logcat=LogcatSettings(),
            scrcpy=ScrcpySettings(),
            apk_install=ApkInstallSettings(),
            screenshot=ScreenshotSettings(),
            screen_record=ScreenRecordSettings(),
            logcat_viewer=LogcatViewerSettings(),
        )

    def _validate_config(self, config_dict: Dict[str, Any]) -> Dict[str, Any]:
        """Validate and clean configuration dictionary."""
        # Normalize legacy flat keys before merging
        normalized: Dict[str, Any] = dict(config_dict)
        legacy_ui_scale = normalized.pop("ui_scale", None)
        if isinstance(legacy_ui_scale, (int, float)):
            normalized.setdefault("ui", {})["ui_scale"] = float(legacy_ui_scale)

        legacy_refresh = normalized.pop("refresh_interval", None)
        if isinstance(legacy_refresh, int):
            normalized.setdefault("device", {})["refresh_interval"] = legacy_refresh

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

        validated = merge_dict(default_config, normalized)

        # Validate specific constraints
        ui_settings = validated.get("ui", {})
        if (
            ui_settings.get("ui_scale", 1.0) < 0.5
            or ui_settings.get("ui_scale", 1.0) > 3.0
        ):
            ui_settings["ui_scale"] = 1.0
            logger.warning("UI scale out of range, reset to 1.0")
        if not isinstance(ui_settings.get("show_console_panel", True), bool):
            ui_settings["show_console_panel"] = True
            logger.warning("Console panel visibility invalid, reset to True")
        # Ensure selection mode is boolean; default to True (Single-select)
        if not isinstance(ui_settings.get("single_selection", True), bool):
            ui_settings["single_selection"] = True
            logger.warning("Selection mode invalid, reset to Single-select")

        device_settings = validated.get("device", {})
        if device_settings.get("refresh_interval", 30) < 1:
            device_settings["refresh_interval"] = 30
            logger.warning("Refresh interval too low, reset to 30 seconds")

        logcat_settings = validated.get("logcat", {})
        if logcat_settings.get("max_lines", 1000) < 100:
            logcat_settings["max_lines"] = 1000
            logger.warning("Logcat max_lines too low, reset to 1000")
        if logcat_settings.get("history_multiplier", 5) < 1:
            logcat_settings["history_multiplier"] = 5
            logger.warning("Logcat history multiplier too low, reset to 5")
        if logcat_settings.get("update_interval_ms", 200) < 50:
            logcat_settings["update_interval_ms"] = 200
            logger.warning("Logcat update interval too low, reset to 200 ms")
        if logcat_settings.get("max_lines_per_update", 50) < 5:
            logcat_settings["max_lines_per_update"] = 50
            logger.warning("Logcat lines per update too low, reset to 50")
        if logcat_settings.get("max_buffer_size", 100) < 10:
            logcat_settings["max_buffer_size"] = 100
            logger.warning("Logcat buffer size too low, reset to 100")

        scrcpy_settings = validated.setdefault("scrcpy", {})
        for flag in (
            "stay_awake",
            "turn_screen_off",
            "disable_screensaver",
            "enable_audio_playback",
        ):
            value = scrcpy_settings.get(
                flag, True if flag != "enable_audio_playback" else True
            )
            scrcpy_settings[flag] = bool(value)

        bitrate_value = scrcpy_settings.get("bitrate", "")
        scrcpy_settings["bitrate"] = (
            str(bitrate_value) if bitrate_value is not None else ""
        )

        max_size_value = scrcpy_settings.get("max_size", 0)
        if isinstance(max_size_value, (int, float)):
            max_size_int = int(max_size_value)
        else:
            max_size_int = 0
        if max_size_int < 0:
            max_size_int = 0
        scrcpy_settings["max_size"] = max_size_int

        extra_args_value = scrcpy_settings.get("extra_args", "")
        scrcpy_settings["extra_args"] = (
            str(extra_args_value) if extra_args_value is not None else ""
        )

        # Validate APK install settings
        apk_settings = validated.setdefault("apk_install", {})
        for flag in (
            "replace_existing",
            "allow_downgrade",
            "grant_permissions",
            "allow_test_packages",
        ):
            apk_settings[flag] = bool(
                apk_settings.get(flag, getattr(ApkInstallSettings(), flag))
            )
        apk_extra = apk_settings.get("extra_args", "")
        apk_settings["extra_args"] = str(apk_extra) if apk_extra is not None else ""

        # Validate screenshot settings
        screenshot_settings = validated.setdefault("screenshot", {})
        screenshot_extra = screenshot_settings.get("extra_args", "")
        screenshot_settings["extra_args"] = (
            str(screenshot_extra) if screenshot_extra is not None else ""
        )
        try:
            did = int(screenshot_settings.get("display_id", -1))
        except Exception:
            did = -1
        screenshot_settings["display_id"] = did

        # Validate screen record settings
        record_settings = validated.setdefault("screen_record", {})
        bit_rate_v = record_settings.get("bit_rate", "")
        record_settings["bit_rate"] = str(bit_rate_v) if bit_rate_v is not None else ""
        time_limit_v = record_settings.get("time_limit_sec", 0)
        try:
            time_limit_v = int(time_limit_v)
        except Exception:
            time_limit_v = 0
        if time_limit_v < 0:
            time_limit_v = 0
        record_settings["time_limit_sec"] = time_limit_v
        size_v = record_settings.get("size", "")
        record_settings["size"] = str(size_v) if size_v is not None else ""
        extra_v = record_settings.get("extra_args", "")
        record_settings["extra_args"] = str(extra_v) if extra_v is not None else ""
        # Booleans
        record_settings["use_hevc"] = bool(record_settings.get("use_hevc", False))
        record_settings["bugreport"] = bool(record_settings.get("bugreport", False))
        record_settings["verbose"] = bool(record_settings.get("verbose", False))
        try:
            rid = int(record_settings.get("display_id", -1))
        except Exception:
            rid = -1
        record_settings["display_id"] = rid

        return validated

    def load_config(self) -> AppConfig:
        """Load configuration from file."""
        if self._config is not None:
            return self._config

        try:
            if self.config_path.exists():
                with open(self.config_path, "r", encoding="utf-8") as f:
                    config_dict = json.load(f)

                validated_dict = self._validate_config(config_dict)

                # Convert to dataclass
                self._config = AppConfig(
                    ui=UISettings(**validated_dict["ui"]),
                    device=DeviceSettings(**validated_dict["device"]),
                    command=CommandSettings(**validated_dict["command"]),
                    logging=LoggingSettings(**validated_dict["logging"]),
                    logcat=LogcatSettings(**validated_dict["logcat"]),
                    scrcpy=ScrcpySettings(**validated_dict["scrcpy"]),
                    apk_install=ApkInstallSettings(**validated_dict["apk_install"]),
                    screenshot=ScreenshotSettings(**validated_dict["screenshot"]),
                    screen_record=ScreenRecordSettings(
                        **validated_dict["screen_record"]
                    ),
                    logcat_viewer=LogcatViewerSettings(
                        **validated_dict.get("logcat_viewer", {})
                    ),
                    command_history=validated_dict.get("command_history", []),
                    version=validated_dict.get("version", "1.0.0"),
                )

                logger.info(f"Configuration loaded from {self.config_path}")
            else:
                self._config = self._create_default_config()
                logger.info("Created default configuration")

        except Exception as e:
            logger.error(f"Failed to load config: {e}")
            # Try backup if available
            if self.backup_path.exists():
                try:
                    logger.info("Attempting to load from backup")
                    with open(self.backup_path, "r", encoding="utf-8") as f:
                        config_dict = json.load(f)
                    validated_dict = self._validate_config(config_dict)
                    self._config = AppConfig(
                        ui=UISettings(**validated_dict["ui"]),
                        device=DeviceSettings(**validated_dict["device"]),
                        command=CommandSettings(**validated_dict["command"]),
                        logging=LoggingSettings(**validated_dict["logging"]),
                        logcat=LogcatSettings(**validated_dict["logcat"]),
                        scrcpy=ScrcpySettings(**validated_dict["scrcpy"]),
                        apk_install=ApkInstallSettings(**validated_dict["apk_install"]),
                        screenshot=ScreenshotSettings(**validated_dict["screenshot"]),
                        screen_record=ScreenRecordSettings(
                            **validated_dict["screen_record"]
                        ),
                        logcat_viewer=LogcatViewerSettings(
                            **validated_dict.get("logcat_viewer", {})
                        ),
                        command_history=validated_dict.get("command_history", []),
                        version=validated_dict.get("version", "1.0.0"),
                    )
                    logger.info("Configuration loaded from backup")
                except Exception as backup_error:
                    logger.error(f"Backup config also failed: {backup_error}")
                    self._config = self._create_default_config()
            else:
                self._config = self._create_default_config()

        return self._config

    def save_config(self, config: Optional[AppConfig] = None):
        """Save configuration to file."""
        if config is None:
            config = self._config

        if config is None:
            logger.warning("No configuration to save")
            return

        try:
            # Create backup of existing config
            if self.config_path.exists():
                try:
                    import shutil

                    shutil.copy2(self.config_path, self.backup_path)
                except Exception as e:
                    logger.warning(f"Failed to create config backup: {e}")

            # Save new config
            config_dict = asdict(config)
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(config_dict, f, indent=4, ensure_ascii=False)

            self._config = config
            logger.info(f"Configuration saved to {self.config_path}")

        except Exception as e:
            logger.error(f"Failed to save config: {e}")
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

    def get_logcat_settings(self) -> LogcatSettings:
        """Get logcat performance settings."""
        return self.load_config().logcat

    def get_scrcpy_settings(self) -> ScrcpySettings:
        """Get scrcpy mirroring settings."""
        return self.load_config().scrcpy

    def get_apk_install_settings(self) -> ApkInstallSettings:
        """Get APK install settings."""
        return self.load_config().apk_install

    def get_screenshot_settings(self) -> ScreenshotSettings:
        """Get screenshot capture settings."""
        return self.load_config().screenshot

    def get_screen_record_settings(self) -> ScreenRecordSettings:
        """Get screen recording settings."""
        return self.load_config().screen_record

    def get_logcat_viewer_settings(self) -> LogcatViewerSettings:
        """Get logcat viewer UI settings."""
        return self.load_config().logcat_viewer

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

    def update_logcat_settings(self, **kwargs):
        """Update logcat performance settings."""
        config = self.load_config()
        for key, value in kwargs.items():
            if hasattr(config.logcat, key):
                setattr(config.logcat, key, value)
        self.save_config(config)

    def update_scrcpy_settings(self, **kwargs):
        """Update scrcpy mirroring settings."""
        config = self.load_config()
        for key, value in kwargs.items():
            if hasattr(config.scrcpy, key):
                setattr(config.scrcpy, key, value)
        self.save_config(config)

    def update_apk_install_settings(self, **kwargs):
        """Update APK install settings."""
        config = self.load_config()
        for key, value in kwargs.items():
            if hasattr(config.apk_install, key):
                setattr(config.apk_install, key, value)
        self.save_config(config)

    def update_screenshot_settings(self, **kwargs):
        """Update screenshot capture settings."""
        config = self.load_config()
        for key, value in kwargs.items():
            if hasattr(config.screenshot, key):
                setattr(config.screenshot, key, value)
        self.save_config(config)

    def update_screen_record_settings(self, **kwargs):
        """Update screen recording settings."""
        config = self.load_config()
        for key, value in kwargs.items():
            if hasattr(config.screen_record, key):
                setattr(config.screen_record, key, value)
        self.save_config(config)

    def set_scrcpy_settings(self, settings: ScrcpySettings):
        """Replace scrcpy settings with provided dataclass."""
        config = self.load_config()
        config.scrcpy = settings
        self.save_config(config)

    def set_apk_install_settings(self, settings: ApkInstallSettings):
        """Replace APK install settings with provided dataclass."""
        config = self.load_config()
        config.apk_install = settings
        self.save_config(config)

    def set_screenshot_settings(self, settings: ScreenshotSettings):
        """Replace screenshot settings with provided dataclass."""
        config = self.load_config()
        config.screenshot = settings
        self.save_config(config)

    def set_screen_record_settings(self, settings: ScreenRecordSettings):
        """Replace screen recording settings with provided dataclass."""
        config = self.load_config()
        config.screen_record = settings
        self.save_config(config)

    def update_logcat_viewer_settings(self, **kwargs):
        """Update logcat viewer UI settings."""
        config = self.load_config()
        for key, value in kwargs.items():
            if hasattr(config.logcat_viewer, key):
                setattr(config.logcat_viewer, key, value)
        self.save_config(config)

    def set_logcat_viewer_settings(self, settings: LogcatViewerSettings):
        """Replace logcat viewer settings with provided dataclass."""
        config = self.load_config()
        config.logcat_viewer = settings
        self.save_config(config)

    def reset_to_defaults(self):
        """Reset configuration to defaults."""
        self._config = self._create_default_config()
        self.save_config()
        logger.info("Configuration reset to defaults")

    def export_config(self, filepath: str):
        """Export configuration to file."""
        config = self.load_config()
        export_path = Path(filepath).expanduser()

        try:
            with open(export_path, "w", encoding="utf-8") as f:
                json.dump(asdict(config), f, indent=4, ensure_ascii=False)
            logger.info(f"Configuration exported to {export_path}")
        except Exception as e:
            logger.error(f"Failed to export config: {e}")
            raise

    def import_config(self, filepath: str):
        """Import configuration from file."""
        import_path = Path(filepath).expanduser()

        try:
            with open(import_path, "r", encoding="utf-8") as f:
                config_dict = json.load(f)

            validated_dict = self._validate_config(config_dict)
            imported_config = AppConfig(
                ui=UISettings(**validated_dict["ui"]),
                device=DeviceSettings(**validated_dict["device"]),
                command=CommandSettings(**validated_dict["command"]),
                logging=LoggingSettings(**validated_dict["logging"]),
                logcat=LogcatSettings(**validated_dict["logcat"]),
                scrcpy=ScrcpySettings(**validated_dict["scrcpy"]),
                apk_install=ApkInstallSettings(**validated_dict["apk_install"]),
                screenshot=ScreenshotSettings(**validated_dict["screenshot"]),
                screen_record=ScreenRecordSettings(**validated_dict["screen_record"]),
                logcat_viewer=LogcatViewerSettings(
                    **validated_dict.get("logcat_viewer", {})
                ),
                command_history=validated_dict.get("command_history", []),
                version=validated_dict.get("version", "1.0.0"),
            )

            self.save_config(imported_config)
            logger.info(f"Configuration imported from {import_path}")

        except Exception as e:
            logger.error(f"Failed to import config: {e}")
            raise
