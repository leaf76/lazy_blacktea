"""Application constants and configuration values."""


class UIConstants:
    """UI-related constants."""

    # Window dimensions
    WINDOW_WIDTH = 1200
    WINDOW_HEIGHT = 800
    WINDOW_MIN_WIDTH = 800
    WINDOW_MIN_HEIGHT = 600

    # Refresh intervals (milliseconds) - Optimized for performance
    DEVICE_REFRESH_INTERVAL_MS = 10000  # Increased from 5s to 10s
    RECORDING_STATUS_REFRESH_MS = 2000   # Increased from 1s to 2s
    PROGRESS_HIDE_DELAY_MS = 1500
    UI_UPDATE_DEBOUNCE_MS = 300          # Increased from 100ms to 300ms

    # UI component dimensions
    CONSOLE_MAX_HEIGHT = 200
    DEVICE_SCROLL_MAX_HEIGHT = 400
    BUTTON_MIN_HEIGHT = 40
    BUTTON_MIN_HEIGHT_SMALL = 35

    # Font sizes
    TITLE_FONT_SIZE = 12
    CONSOLE_FONT_SIZE = 9

    # UI scaling factors
    DEFAULT_UI_SCALE = 1.0
    LARGE_UI_SCALE = 1.25
    EXTRA_LARGE_UI_SCALE = 1.5


class PathConstants:
    """File and directory path constants."""

    # Icon paths (in order of preference)
    ICON_PATHS = [
        'assets/icons/icon_128x128.png',
        'assets/icons/AppIcon.icns',
        'assets/icons/app_icon.ico',
        'icon_128x128.png',
        'AppIcon.icns',
        'app_icon.ico'
    ]

    # Default directories
    DEFAULT_OUTPUT_DIR = 'output'
    DEFAULT_SCREENSHOTS_DIR = 'screenshots'
    DEFAULT_RECORDINGS_DIR = 'recordings'
    DEFAULT_REPORTS_DIR = 'reports'

    # File extensions
    SCREENSHOT_EXT = '.png'
    RECORDING_EXT = '.mp4'
    REPORT_EXT = '.txt'
    APK_EXT = '.apk'


class ADBConstants:
    """ADB-related constants."""

    # Command timeouts (seconds)
    DEFAULT_COMMAND_TIMEOUT = 30
    INSTALL_COMMAND_TIMEOUT = 120
    RECORDING_COMMAND_TIMEOUT = 300
    SCREENSHOT_COMMAND_TIMEOUT = 15

    # Device states
    DEVICE_STATE_DEVICE = 'device'
    DEVICE_STATE_OFFLINE = 'offline'
    DEVICE_STATE_UNAUTHORIZED = 'unauthorized'
    DEVICE_STATE_RECOVERY = 'recovery'
    DEVICE_STATE_BOOTLOADER = 'bootloader'

    # Common ADB commands
    CMD_DEVICES = 'adb devices -l'
    CMD_KILL_SERVER = 'adb kill-server'
    CMD_START_SERVER = 'adb start-server'
    CMD_REBOOT = 'adb reboot'
    CMD_REBOOT_RECOVERY = 'adb reboot recovery'
    CMD_REBOOT_BOOTLOADER = 'adb reboot bootloader'


class MessageConstants:
    """User-facing message constants."""

    # Success messages
    SUCCESS_DEVICE_REFRESH = "Device list refreshed successfully"
    SUCCESS_SCREENSHOT_TAKEN = "Screenshot taken successfully"
    SUCCESS_RECORDING_STARTED = "Recording started successfully"
    SUCCESS_RECORDING_STOPPED = "Recording stopped successfully"
    SUCCESS_APK_INSTALLED = "APK installed successfully"

    # Error messages
    ERROR_NO_DEVICES = "No devices selected. Please select at least one device."
    ERROR_NO_DEVICES_FOUND = "No devices found. Please connect a device and refresh."
    ERROR_ADB_NOT_FOUND = "ADB not found. Please ensure Android SDK is installed."
    ERROR_DEVICE_OFFLINE = "Device is offline or disconnected"
    ERROR_INVALID_OUTPUT_PATH = "Invalid output path. Please select a valid directory."
    ERROR_RECORDING_ALREADY_ACTIVE = "Recording is already active for this device"
    ERROR_NO_RECORDING_ACTIVE = "No active recording found for this device"

    # Warning messages
    WARNING_DEVICE_UNAUTHORIZED = "Device is unauthorized. Please check USB debugging."
    WARNING_LARGE_APK = "APK file is large. Installation may take longer."
    WARNING_MULTIPLE_DEVICES = "Multiple devices selected. Operation will run on all selected devices."

    # Info messages
    INFO_INITIALIZING = "Initializing application..."
    INFO_LOADING_DEVICES = "Loading connected devices..."
    INFO_OPERATION_CANCELLED = "Operation cancelled by user"
    INFO_BACKGROUND_OPERATION = "Operation is running in background..."


class LoggingConstants:
    """Logging configuration constants."""

    # Log levels
    DEFAULT_LOG_LEVEL = 'INFO'
    DEBUG_LOG_LEVEL = 'DEBUG'

    # Log format
    LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    CONSOLE_LOG_FORMAT = '%(levelname)s: %(message)s'

    # Log file settings
    MAX_LOG_FILE_SIZE = 10 * 1024 * 1024  # 10MB
    LOG_BACKUP_COUNT = 5


class NetworkConstants:
    """Network-related constants."""

    # Timeouts
    HTTP_TIMEOUT = 30
    SOCKET_TIMEOUT = 10

    # Retry settings
    MAX_RETRIES = 3
    RETRY_DELAY = 1.0  # seconds


class PerformanceConstants:
    """Performance tuning constants."""

    # Thread pool settings
    MAX_WORKER_THREADS = 4
    THREAD_TIMEOUT = 60  # seconds

    # Memory management
    MAX_DEVICE_HISTORY = 100
    MAX_LOG_ENTRIES = 1000

    # UI update batching
    UI_BATCH_UPDATE_SIZE = 10
    UI_BATCH_UPDATE_DELAY_MS = 50


class ApplicationConstants:
    """General application constants."""

    # Application info
    APP_NAME = "Lazy Blacktea"
    APP_VERSION = "2.0.0"
    APP_DESCRIPTION = "A PyQt6 GUI application for simplifying Android ADB and automation tasks"

    # Configuration
    CONFIG_FILE_NAME = "config.json"
    SETTINGS_FILE_NAME = "settings.ini"

    # Feature flags
    ENABLE_EXPERIMENTAL_FEATURES = False
    ENABLE_DEBUG_MODE = False
    ENABLE_PERFORMANCE_MONITORING = False


class PanelText:
    """Shared labels and titles for UI panels."""

    TAB_ADB_TOOLS = 'ADB Tools'
    TAB_SHELL_COMMANDS = 'Shell Commands'
    TAB_FILE_GENERATION = 'File Generation'
    TAB_DEVICE_GROUPS = 'Device Groups'

    GROUP_OUTPUT_PATH = 'Output Path'
    GROUP_FILE_GENERATION = '🛠️ File Generation Tools'
    GROUP_COMMAND_HISTORY = '📜 Command History'
    GROUP_CREATE_UPDATE = 'Create/Update Group'
    GROUP_EXISTING = 'Existing Groups'

    PLACEHOLDER_OUTPUT_DIR = 'Select output directory...'
    PLACEHOLDER_GROUP_NAME = 'Enter group name...'

    BUTTON_BROWSE = '📂 Browse'
    BUTTON_CLEAR = '🗑️ Clear'
    BUTTON_EXPORT = '📤 Export'
    BUTTON_IMPORT = '📥 Import'
    BUTTON_SAVE_GROUP = 'Save Current Selection as Group'
    BUTTON_SELECT_GROUP = 'Select Devices in Group'
    BUTTON_DELETE_GROUP = 'Delete Selected Group'
