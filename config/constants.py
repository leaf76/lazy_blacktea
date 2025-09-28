"""Application constants and configuration values."""


class UIConstants:
    """UI-related constants."""

    # Window dimensions
    WINDOW_WIDTH = 1200
    WINDOW_HEIGHT = 800
    WINDOW_MIN_WIDTH = 800
    WINDOW_MIN_HEIGHT = 600

    # Refresh intervals (milliseconds) - Optimized for performance
    DEVICE_REFRESH_INTERVAL_MS = 30000  # Increased to 30s for auto refresh cadence
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
    DEVICE_STATE_SIDELOAD = 'sideload'

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

    # Project loggers that should mirror console output
    RELATED_LOGGERS = [
        'adb_tools',
        'async_device_manager',
        'batched_ui_updater',
        'command_executor',
        'command_history',
        'common',
        'config_manager',
        'debounced_refresh',
        'device_manager',
        'device_operations_manager',
        'device_refresh',
        'dump_device_ui',
        'error_handler',
        'file_generation',
        'json_utils',
        'panels_manager',
        'perf_refresh',
        'recording',
        'recording_status_refresh',
        'screenshot',
        'ui_factory',
        'ui_inspector_factory',
        'ui_inspector_utils',
    ]


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
    TAB_DEVICE_FILES = 'Device Files'
    TAB_DEVICE_GROUPS = 'Device Groups'

    GROUP_OUTPUT_PATH = 'Output Path'
    GROUP_LOGCAT = '📄 Logcat'
    GROUP_DEVICE_CONTROL = '📱 Device Control'
    GROUP_CAPTURE = '📱 Screen Capture & Recording'
    GROUP_COMMAND_TEMPLATES = '📋 Command Templates'
    GROUP_BATCH_COMMANDS = '📝 Batch Commands'
    GROUP_COMMAND_HISTORY = '📜 Command History'
    GROUP_DEVICE_FILES = '📁 Device Browser'
    GROUP_DEVICE_FILE_OUTPUT = '💾 Download'
    GROUP_CREATE_UPDATE = 'Create/Update Group'
    GROUP_EXISTING = 'Existing Groups'

    PLACEHOLDER_OUTPUT_DIR = 'Select output path (screenshots, recordings, etc.)'
    PLACEHOLDER_GROUP_NAME = 'Enter group name...'
    PLACEHOLDER_DEVICE_FILE_PATH = '/sdcard'
    PLACEHOLDER_DEVICE_FILE_OUTPUT = 'Select download destination...'
    PLACEHOLDER_SHELL_COMMAND = 'adb shell input keyevent 26'

    BUTTON_BROWSE = '📂 Browse'
    BUTTON_CLEAR = '🗑️ Clear'
    BUTTON_EXPORT = '📤 Export'
    BUTTON_IMPORT = '📥 Import'
    BUTTON_SAVE_GROUP = 'Save Current Selection as Group'
    BUTTON_SELECT_GROUP = 'Select Devices in Group'
    BUTTON_DELETE_GROUP = 'Delete Selected Group'
    BUTTON_RUN_SINGLE_COMMAND = '▶️ Run Single Command'
    BUTTON_RUN_ALL_COMMANDS = '🚀 Run All Commands'
    BUTTON_RUN_SINGLE_SHELL = '▶️ Run Single Shell Command'
    BUTTON_REFRESH = '🔄 Refresh'
    BUTTON_GO = 'Go'
    BUTTON_UP = '⬆️ Up'
    BUTTON_DOWNLOAD_SELECTED = '⬇️ Download Selected'

    LABEL_NO_RECORDING = 'No active recordings'
    LABEL_RECORDING_PREFIX = '🔴 Recording: {count} device(s)'


class PanelConfig:
    """Configuration collections used by tool panels."""

    DEVICE_ACTIONS = [
        ('🔄 Reboot Device', 'reboot_device'),
        ('📦 Install APK', 'install_apk'),
        ('🔵 Enable Bluetooth', 'enable_bluetooth'),
        ('🔴 Disable Bluetooth', 'disable_bluetooth'),
    ]

    SHELL_TEMPLATE_COMMANDS = [
        ('📱 Device Info', 'getprop ro.build.version.release'),
        ('🔋 Battery Info', 'dumpsys battery'),
        ('📊 Memory Info', 'dumpsys meminfo'),
        ('🌐 Network Info', 'dumpsys connectivity'),
        ('📱 App List', 'pm list packages -3'),
        ('🗑️ Clear Cache', 'pm trim-caches 1000000000'),
    ]



class RecordingConstants:
    """Recording-related defaults and safety limits."""

    # Android screenrecord hard-limits at 180s; use a slightly smaller segment.
    SEGMENT_DURATION_SECONDS = 170

    # Poll intervals for verifying recording state (seconds)
    SEGMENT_POLL_INTERVAL = 0.5
    VERIFICATION_POLL_INTERVAL = 0.2

    # Retry behaviour for start/stop and file pulls
    START_RETRY_COUNT = 2
    START_RETRY_DELAY = 1.0
    STOP_RETRY_COUNT = 3
    STOP_RETRY_DELAY = 1.5
    FILE_PULL_RETRY_COUNT = 3
    FILE_PULL_RETRY_DELAY = 1.0
