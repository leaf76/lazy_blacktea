# 🍵 Lazy Blacktea - Android ADB GUI Tool

A powerful and user-friendly GUI application for Android debugging and automation tasks using ADB (Android Debug Bridge).

## ✨ Features

### 🔧 Device Management
- **Auto Device Detection**: Automatically discovers connected Android devices
- **Device Information**: Shows device serial, model, Android version, API level
- **Connection Status**: Real-time WiFi and Bluetooth status
- **Device Groups**: Save and manage groups of devices for batch operations

### 📱 Device Operations
- **System Control**: Reboot devices, run as root
- **Connectivity**: Toggle Bluetooth on/off
- **APK Installation**: Install APK files to multiple devices
- **Screen Capture**: Take screenshots and record screen
- **Shell Commands**: Execute custom ADB shell commands

### 📊 Advanced Features
- **Bug Reports**: Generate comprehensive Android bug reports
- **Device Discovery**: Extract discovery service information
- **DCIM Transfer**: Pull device camera/photos folder
- **UI Dump**: Extract device UI hierarchy
- **Flag Configuration**: Manage various system flags and settings

### 🎛️ SASS Automation
- **Test Automation**: Run SASS (System Automation Script Suite) tests
- **Batch Processing**: Execute tests across multiple devices
- **Configuration Management**: Handle test configurations and cases

## 🚀 Getting Started

### Prerequisites
- **Python 3.8+**: Required to run the application
- **ADB (Android Debug Bridge)**: Required for device communication
  - Install via Android SDK, Homebrew, or package manager
  - ADB will be automatically detected from common installation locations

### 🏗️ Building & Installation

#### Cross-Platform Builder (Recommended)
Use the intelligent build script that automatically detects your platform and creates optimized distributions:

```bash
# Automatic platform detection and build
python3 build.py
```

**What it does:**
- 🔍 **Auto-detects** your platform (macOS/Linux)
- 📦 **Installs dependencies** automatically
- 🔨 **Builds optimized** platform-specific distributions
- 📱 **Creates packages**: App bundles, DMG, AppImage, tarballs

#### Platform-Specific Building

**macOS:**
```bash
# Build macOS .app bundle
bash build_macos.sh
# Output: dist/LazyBlacktea.app + LazyBlacktea.dmg
```

**Linux:**
```bash
# Build Linux executable and packages
bash build_linux.sh
# Output: dist/lazyblacktea/ + LazyBlacktea-x86_64.AppImage + tarball
```

#### Distribution Outputs

**macOS:**
- 📱 `LazyBlacktea.app` - Native macOS app bundle
- 💿 `LazyBlacktea.dmg` - Disk image for distribution
- ✅ **Smart ADB Detection**: Automatically finds ADB in Homebrew, system paths

**Linux:**
- 🐧 `lazyblacktea/` - Executable directory
- 📦 `LazyBlacktea-x86_64.AppImage` - Portable Linux app
- 🗜️ `lazyblacktea-linux.tar.gz` - Compressed distribution
- ✅ **Smart ADB Detection**: Automatically finds ADB from package managers, SDK installs

### Quick Launch
1. **Use pre-built distributions** (recommended):
   - **macOS**: Double-click `LazyBlacktea.app` or drag to Applications
   - **Linux**: Run `./LazyBlacktea-x86_64.AppImage` or extract tarball

2. **Or run from source**:
   ```bash
   ./start_lazy_blacktea.sh
   # Or directly:
   python3 lazy_blacktea_pyqt.py
   ```

## 🎨 UI Improvements & Performance (v2.0)

This version includes major architectural improvements and optimizations:

### 🏗️ Architecture Refactoring
- **Modular Design**: Split monolithic code into specialized modules
  - `ui/panels_manager.py` - UI panel creation and management
  - `ui/device_manager.py` - Device operations and state management
  - `ui/command_executor.py` - Command execution and validation
  - `ui/error_handler.py` - Centralized error handling
  - `config/config_manager.py` - Configuration management
  - `config/constants.py` - Application constants and settings
- **Separation of Concerns**: Clear boundaries between UI, business logic, and data
- **Reduced Main File Size**: From 3762 to 3686 lines (improved maintainability)

### 🖥️ Enhanced User Interface
- **Progress Indicators**: Visual feedback for all operations
- **Status Bar**: Shows current operation status and timing
- **Hover Effects**: Interactive device list with visual feedback
- **Responsive Layout**: Better scaling and window management
- **Tabbed Interface**: Organized tools into logical categories
- **Context Menus**: Right-click actions for enhanced UX

### ⚡ Performance Optimizations
- **Debounced Refresh**: Intelligent update batching to prevent excessive UI refreshes
- **Memory Management**: Proper widget cleanup with `deleteLater()` for memory efficiency
- **Batch UI Updates**: Uses `setUpdatesEnabled()` for smooth bulk operations
- **Smart Caching**: Font and UI element caching for faster rendering
- **Background Processing**: All operations run in background threads
- **Performance Monitoring**: Built-in operation timing and performance metrics

### 🧹 Code Quality & Maintainability
- **Type Hints**: Comprehensive type annotations throughout codebase
- **Constants Management**: Centralized configuration in dedicated constants module
- **Error Handling**: Comprehensive error handling with specific error codes
- **Clean Code**: Removed unused imports, variables, and redundant code
- **Consistent Naming**: Unified naming conventions across modules
- **Documentation**: Improved docstrings and inline documentation
- **Thread Safety**: Proper signal-slot patterns for UI updates

## 🛠️ New Utility Modules

### Performance & Optimization
- **`utils/debounced_refresh.py`**: Smart refresh debouncing to prevent UI spam
- **`utils/screenshot_utils.py`**: Optimized screenshot operations
- **`utils/recording_utils.py`**: Enhanced screen recording management
- **`utils/file_generation_utils.py`**: Batch file generation utilities

### UI Components
- **`ui/panels_manager.py`**: Centralized UI panel creation and management
- **`ui/device_manager.py`**: Device lifecycle and state management
- **`ui/command_executor.py`**: Command validation and execution
- **`ui/error_handler.py`**: Unified error handling with user-friendly messages

### Configuration & Constants
- **`config/config_manager.py`**: Application configuration management
- **`config/constants.py`**: Centralized constants for UI, paths, and settings

## 📋 Main Interface

The application is organized into several tabs:

1. **General**: Basic device operations and flag settings
2. **Actions**: APK installation, screen recording, shell commands
3. **Files**: File generation tools (bug reports, device discovery)
4. **SASS**: Automation testing framework
5. **Groups**: Device group management

## 🔧 Settings

- **UI Scale**: Adjust interface size (Default, Large, Extra Large)
- **Output Path**: Set default folder for generated files
- **Device Groups**: Save frequently used device combinations

## 📝 Console Output

The bottom panel shows real-time logs and command output with:
- **Color-coded messages**: Info (black), Warning (orange), Error (red)
- **Copy functionality**: Right-click to copy logs
- **Timestamp tracking**: All operations are timestamped

## 🛠️ Troubleshooting

### ADB Not Found
The application includes **Smart ADB Detection** that automatically searches common installation locations:

**macOS:**
- Homebrew: `/opt/homebrew/bin/adb`, `/usr/local/bin/adb`
- Android Studio: App Contents and Library paths
- Manual installs: `~/Library/Android/sdk/platform-tools/adb`

**Linux:**
- Package managers: `/usr/bin/adb`, `/usr/local/bin/adb`
- Snap packages: `/snap/bin/adb`
- Android Studio: `/opt/android-studio/platform-tools/adb`
- User installs: `~/Android/Sdk/platform-tools/adb`

**If ADB is still not found:**
- Install via system package manager:
  - **macOS**: `brew install android-platform-tools`
  - **Linux**: `sudo apt install adb` or `sudo yum install android-tools`
- Or download Android SDK Platform Tools
- The app will automatically detect and use ADB from these locations

### No Devices Detected
- Enable USB Debugging on your Android device
- Check USB connection
- Run `adb devices` in terminal to verify connection

### Permission Issues
- Some operations require device to be rooted
- Enable "USB Debugging (Security settings)" for system-level changes

## 📄 License

This project is for Android automation and debugging purposes.

## 🤝 Contributing

Feel free to submit issues, feature requests, or pull requests to improve the application.

---

**Happy Android Debugging! 🍵✨**