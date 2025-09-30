# Lazy Blacktea

![Lazy Blacktea logo](assets/icons/icon_128x128.png)

[![Build Status](https://github.com/cy76/lazy_blacktea/workflows/build/badge.svg)](https://github.com/cy76/lazy_blacktea/actions)
[![Test Status](https://github.com/cy76/lazy_blacktea/workflows/test/badge.svg)](https://github.com/cy76/lazy_blacktea/actions)
[![Python](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

Lazy Blacktea is a PyQt-based Android ADB GUI for power-users. It streamlines multi-device workflows such as batch APK installs, bugreports, screen capture, and scripted automation, with cross-platform builds for macOS and Linux.

> Current release: v0.0.29

## Table of Contents
- [Highlights](#highlights)
- [Requirements](#requirements)
- [Quick Start](#quick-start)
- [Development Environment](#development-environment)
- [Project Structure](#project-structure)
- [Testing](#testing)
- [Build and Distribution](#build-and-distribution)
- [Troubleshooting](#troubleshooting)
- [Documentation and Support](#documentation-and-support)
- [Contributing](#contributing)
- [License](#license)

## Highlights
- Device inventory cockpit with live status, hardware metadata, and grouping utilities
- Batch operations for APK installation, bug reports, screen capture, and custom shell commands
- Automation helpers for SASS (System Automation Script Suite) scenarios across many devices
- Smart ADB discovery that detects standard SDK, Homebrew, and package-manager installs
- Cross-platform packaging for macOS (App bundle, DMG) and Linux (AppImage, tarball)

## Requirements
- Python 3.8 or newer
- ADB available on your PATH (`adb devices` must succeed)
- macOS 12+ or a modern Linux distribution with X11/Wayland and Qt dependencies

## Quick Start
### Run a packaged build
1. Download the latest bundle from `dist/` or your build pipeline
2. macOS: copy `LazyBlacktea.app` to Applications and open it
3. Linux: execute `./LazyBlacktea-x86_64.AppImage` or extract the tarball and run the launcher script

### Run from source
```bash
./start_lazy_blacktea.sh
# or
python3 lazy_blacktea_pyqt.py
```
The launcher verifies Python and ADB prerequisites before starting the GUI.

## Development Environment
1. Clone the repository and create a virtual environment
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate  # Windows: .venv\Scripts\activate
   ```
2. Install dependencies
   ```bash
   pip install -r requirements.txt
   ```
3. Launch the application from source to verify your setup
   ```bash
   python3 lazy_blacktea_pyqt.py
   ```
4. Configure logging through `utils.common.get_logger` when adding new modules

Keep ADB accessible on your PATH; scripts expect `adb devices` to list attached hardware.

## Project Structure
```
lazy_blacktea/
├── lazy_blacktea_pyqt.py      # Application entry point
├── assets/                    # Shared images, styles, and static resources
├── build-scripts/             # Packaging helpers that emit artifacts into dist/
├── config/                    # Configuration defaults and schema management
├── tests/                     # Unit, integration, and smoke suites
├── ui/                        # PyQt widgets, models, and view helpers
├── utils/                     # Cross-cutting utilities (ADB, logging, helpers)
├── start_lazy_blacktea.sh     # Environment bootstrap and launch script
└── dist/                      # Build outputs (ignored in VCS)
```

## Testing
Run the canonical test sweep before opening a pull request:
```bash
python3 tests/run_tests.py
```
Targeted checks that often matter for device-heavy changes:
```bash
python3 test_device_list_performance.py
```
Clean any `/tmp/lazy_blacktea_*` artifacts left by local experiments.

## Build and Distribution
Use the unified builder to produce platform-specific bundles:
```bash
python3 build-scripts/build.py
```
The script auto-detects macOS or Linux, resolves build dependencies, and writes results under `dist/` (App bundle + DMG on macOS, AppImage + tarball on Linux).

## Troubleshooting
- **ADB not found**: ensure `adb` is visible in your PATH or supply a custom location through the configuration UI
- **Permission errors**: some operations require rooted devices or enabling "USB Debugging (Security settings)"
- **Headless environments**: set `QT_QPA_PLATFORM=offscreen` when running without a display server
- **Device discovery lag**: rerun `adb kill-server && adb start-server` and confirm USB debugging authorization prompts are accepted

## Documentation and Support
- GitHub Actions workflows: [.github/workflows.md](.github/workflows.md)
- Issues: https://github.com/cy76/lazy_blacktea/issues
- Discussions: https://github.com/cy76/lazy_blacktea/discussions
- Security disclosures: use GitHub Security Advisories for private reports

## Contributing
We welcome contributions of all sizes. Review the guidelines in [CONTRIBUTING.md](CONTRIBUTING.md) before opening issues or pull requests.

## License
Lazy Blacktea is released under the [MIT License](LICENSE). PyQt6 and other bundled dependencies retain their respective upstream licenses.
