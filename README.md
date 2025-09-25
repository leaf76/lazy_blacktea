# 🍵 Lazy Blacktea - Android ADB GUI Tool

[![Build Status](https://github.com/cy76/lazy_blacktea/workflows/build/badge.svg)](https://github.com/cy76/lazy_blacktea/actions)
[![Test Status](https://github.com/cy76/lazy_blacktea/workflows/test/badge.svg)](https://github.com/cy76/lazy_blacktea/actions)
[![Python](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![PyQt6](https://img.shields.io/badge/PyQt6-6.4+-green.svg)](https://pypi.org/project/PyQt6/)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

A powerful and user-friendly GUI application for Android debugging and automation tasks using ADB (Android Debug Bridge).

> **Current Version:** v0.0.11

## 📖 Table of Contents

- [Features](#-features)
- [Screenshots](#-screenshots)
- [Getting Started](#-getting-started)
- [Installation](#-installation)
- [Development Setup](#-development-setup)
- [Project Structure](#-project-structure)
- [Usage](#-usage)
- [API Documentation](#-api-documentation)
- [Contributing](#-contributing)
- [Testing](#-testing)
- [Troubleshooting](#-troubleshooting)
- [Changelog](#-changelog)
- [License](#-license)
- [Support](#-support)

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

## 📷 Screenshots

> **Note**: Screenshots will be added soon to showcase the application interface and key features.

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

## 🛠️ Development Setup

### Prerequisites for Development
- **Python 3.8+**
- **Git**
- **ADB (Android Debug Bridge)**

### Setting up Development Environment

1. **Clone the repository**:
   ```bash
   git clone https://github.com/cy76/lazy_blacktea.git
   cd lazy_blacktea
   ```

2. **Create virtual environment** (recommended):
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Run the application**:
   ```bash
   python3 lazy_blacktea_pyqt.py
   ```

### Development Dependencies
- **PyQt6 >= 6.4.0**: GUI framework
- **PyInstaller >= 5.13.0**: For building executables
- **setuptools >= 65.0.0**: Build tools

## 📁 Project Structure

```
lazy_blacktea/
├── 📄 lazy_blacktea_pyqt.py       # Main application entry point
├── 📁 config/                     # Configuration management
│   ├── config_manager.py          # Application settings manager
│   └── constants.py               # Application constants
├── 📁 ui/                         # User interface modules
│   ├── command_executor.py        # Command execution logic
│   ├── device_manager.py          # Device operations management
│   ├── error_handler.py           # Error handling utilities
│   └── panels_manager.py          # UI panel management
├── 📁 utils/                      # Utility modules
│   ├── adb_commands.py            # ADB command implementations
│   ├── adb_models.py              # Data models for ADB operations
│   ├── adb_tools.py               # ADB utility functions
│   ├── common.py                  # Common utilities
│   ├── debounced_refresh.py       # Performance optimization
│   ├── dump_device_ui.py          # UI hierarchy extraction
│   ├── file_generation_utils.py   # File generation utilities
│   ├── json_utils.py              # JSON processing utilities
│   ├── recording_utils.py         # Screen recording utilities
│   ├── screenshot_utils.py        # Screenshot utilities
│   ├── ui_inspector_utils.py      # UI inspection tools
│   └── ui_widgets.py              # Custom UI widgets
├── 📁 build-scripts/              # Build automation
│   ├── build.py                   # Cross-platform builder
│   ├── build_linux.sh            # Linux build script
│   ├── build_macos.sh            # macOS build script
│   └── *.spec                     # PyInstaller specifications
├── 📁 tests/                      # Test suite
│   ├── test_*.py                  # Unit and integration tests
│   └── run_tests.py               # Test runner
├── 📁 assets/                     # Application resources
│   └── icons/                     # Application icons
├── 📁 .github/                    # GitHub workflows
│   └── workflows/                 # CI/CD configurations
├── 📄 requirements.txt            # Python dependencies
├── 📄 README.md                   # Project documentation
└── 📄 start_lazy_blacktea.sh      # Launch script
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

## 📚 API Documentation

### Core Modules

#### `config.config_manager.ConfigManager`
Manages application configuration and settings.

```python
from config.config_manager import ConfigManager

config = ConfigManager()
config.get_setting('ui_scale')
config.set_setting('output_path', '/path/to/output')
```

#### `utils.adb_tools`
Core ADB utilities and device management.

```python
from utils.adb_tools import get_connected_devices, execute_adb_command

devices = get_connected_devices()
result = execute_adb_command(device_id, 'shell getprop ro.build.version.release')
```

#### `ui.device_manager.DeviceManager`
High-level device operations and state management.

```python
from ui.device_manager import DeviceManager

device_manager = DeviceManager()
device_manager.refresh_devices()
device_manager.install_apk(device_id, apk_path)
```

### Extension Points

The application supports extensions through:
- **Custom commands**: Add new ADB commands in `utils/adb_commands.py`
- **UI panels**: Create new UI panels using the panels manager
- **Device operations**: Extend device operations in the device manager

## 📋 Changelog

### Version 2.0.0 (Current)
#### 🚀 Major Features
- **Complete UI/UX overhaul** with modern design
- **Modular architecture** for better maintainability
- **Performance optimizations** with debounced refresh
- **Enhanced error handling** with user-friendly messages
- **Cross-platform build system** with automatic detection

#### 🔧 Technical Improvements
- **Type hints** throughout the codebase
- **Centralized configuration** management
- **Memory optimizations** with proper widget cleanup
- **Thread-safe operations** with proper signal-slot patterns
- **Comprehensive test suite** with multiple test categories

#### 🐛 Bug Fixes
- Fixed memory leaks in device list updates
- Improved ADB detection on various platforms
- Resolved UI freezing during long operations
- Fixed inconsistent device state management

### Version 1.0.0
- Initial release with basic ADB GUI functionality
- Device management and basic operations
- Simple UI with essential features

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

### Linux Qt Platform Plugin Issues

If you encounter this error on Linux:
```
qt.qpa.plugin: From 6.5.0, xcb-cursor0 or libxcb-cursor0 is needed to load the Qt xcb platform plugin.
qt.qpa.plugin: Could not load the Qt platform plugin "xcb" in "" even though it was found.
This application failed to start because no Qt platform plugin could be initialized.
```

**Solution: Install missing Qt dependencies**

**Ubuntu/Debian:**
```bash
sudo apt-get update
sudo apt-get install -y \
    libxcb-cursor0 \
    libxcb1 \
    libxcb-xkb1 \
    libxcb-xinput0 \
    libxcb-icccm4 \
    libxcb-image0 \
    libxcb-keysyms1 \
    libxcb-randr0 \
    libxcb-render-util0 \
    libxcb-xinerama0 \
    libxcb-xfixes0 \
    libxcb-shape0 \
    libxcb-sync1 \
    libxcb-shm0 \
    libxcb-render0 \
    libxcb-util1 \
    libfontconfig1 \
    libfreetype6 \
    libx11-6 \
    libx11-xcb1 \
    libxi6 \
    libxrender1 \
    libdbus-1-3 \
    libgl1-mesa-dev \
    libxkbcommon-x11-0
```

**CentOS/RHEL/Fedora:**
```bash
sudo yum install -y libxcb libxcb-devel xcb-util xcb-util-devel \
    libXrender libXi fontconfig freetype libX11 dbus-libs mesa-libGL
# Or for newer Fedora:
sudo dnf install -y libxcb libxcb-devel xcb-util xcb-util-devel \
    libXrender libXi fontconfig freetype libX11 dbus-libs mesa-libGL
```

**Alternative: Use offscreen rendering**
If you only need CLI functionality without GUI:
```bash
export QT_QPA_PLATFORM=offscreen
./LazyBlacktea-x86_64.AppImage
```

### Permission Issues
- Some operations require device to be rooted
- Enable "USB Debugging (Security settings)" for system-level changes

## 🧪 Testing

### Running Tests

Run the test suite to ensure everything works correctly:

```bash
# Run all tests
python tests/run_tests.py

# Run specific test categories
python tests/test_config_manager.py
python tests/test_functional.py
python tests/test_integration.py
```

### Test Structure
- **Unit Tests**: Test individual components and functions
- **Integration Tests**: Test component interactions
- **Functional Tests**: Test complete user workflows
- **All Functions Test**: Comprehensive test coverage

## 🤝 Contributing

We welcome contributions from the community! Here's how you can help:

### 🐛 Reporting Bugs

1. **Check existing issues** to avoid duplicates
2. **Use the bug report template** when creating new issues
3. **Include system information**:
   - OS version
   - Python version
   - ADB version
   - Application version
4. **Provide steps to reproduce** the issue
5. **Include screenshots** if applicable

### 🚀 Feature Requests

1. **Check existing feature requests** to avoid duplicates
2. **Describe the feature** and its use case
3. **Explain why it would be valuable** to other users
4. **Consider implementation complexity**

### 💻 Code Contributions

1. **Fork the repository**
2. **Create a feature branch**:
   ```bash
   git checkout -b feature/amazing-feature
   ```
3. **Follow coding standards**:
   - Use type hints
   - Follow PEP 8 style guide
   - Add docstrings to functions
   - Include unit tests for new features
4. **Test your changes**:
   ```bash
   python tests/run_tests.py
   ```
5. **Commit your changes**:
   ```bash
   git commit -m "Add amazing feature"
   ```
6. **Push to your fork**:
   ```bash
   git push origin feature/amazing-feature
   ```
7. **Open a Pull Request**

### 📋 Development Guidelines

- **Code Style**: Follow PEP 8 and use type hints
- **Testing**: Add tests for new features and bug fixes
- **Documentation**: Update README and docstrings as needed
- **Commit Messages**: Use clear, descriptive commit messages
- **Branch Naming**: Use descriptive branch names (feature/, bugfix/, hotfix/)

### 🔍 Code Review Process

1. All PRs require review before merging
2. Ensure CI tests pass
3. Address reviewer feedback
4. Maintain backwards compatibility when possible

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

### Third-Party Licenses

This project uses the following open-source libraries:
- **PyQt6**: GPLv3 License
- **PyInstaller**: GPLv2 License with exception

## 📞 Support

### Getting Help

- 📖 **Documentation**: Check this README and inline code documentation
- 🐛 **Issues**: [GitHub Issues](https://github.com/cy76/lazy_blacktea/issues)
- 💬 **Discussions**: [GitHub Discussions](https://github.com/cy76/lazy_blacktea/discussions)

### Community

- **Be respectful** and inclusive
- **Help others** when you can
- **Share your experience** and improvements
- **Follow the Code of Conduct**

### Reporting Security Vulnerabilities

If you discover a security vulnerability, please report it privately through GitHub's security advisory feature instead of opening a public issue.

---

**Happy Android Debugging! 🍵✨**
