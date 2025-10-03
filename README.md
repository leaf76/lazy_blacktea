# Lazy Blacktea

![Lazy Blacktea logo](assets/icons/icon_128x128.png)

[![Build Status](https://github.com/cy76/lazy_blacktea/workflows/build/badge.svg)](https://github.com/cy76/lazy_blacktea/actions)
[![Test Status](https://github.com/cy76/lazy_blacktea/workflows/test/badge.svg)](https://github.com/cy76/lazy_blacktea/actions)
[![Python](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

Lazy Blacktea is a PyQt-based Android ADB cockpit for power-users. It streamlines multi-device automation—batch APK installs, bug reports, screen capture, recording, log streaming—while packaging cleanly for macOS and Linux.

> Current release: v0.0.33

## Table of Contents
- [Overview](#overview)
- [Feature Matrix](#feature-matrix)
- [System Architecture](#system-architecture)
- [Directory Reference](#directory-reference)
- [Core Workflows](#core-workflows)
- [Setup & Tooling](#setup--tooling)
- [Testing Strategy](#testing-strategy)
- [Performance & Observability](#performance--observability)
- [Build & Distribution](#build--distribution)
- [Native Companion](#native-companion)
- [Scripts & Automation](#scripts--automation)
- [Troubleshooting](#troubleshooting)
- [Documentation & Support](#documentation--support)
- [Contributing](#contributing)
- [License](#license)

## Overview
- PyQt6 desktop application that discovers Android devices, surfaces live status, and fans out operations safely in parallel.
- Clean separation between UI widgets (`ui/`), cross-cutting utilities (`utils/`), configuration (`config/`), and packaging toolchain (`build-scripts/`).
- Native Rust sidecar (`native_lbb/`) accelerates heavy ADB operations and exposes bindings through `utils.native_bridge`.
- Structured logging, correlation IDs, and guard rails for long-running automation flows.
- Bundled test suites (unit, integration, performance smoke) protect regressions across device- and UI-facing features.

## Feature Matrix
| Area | Highlights | Key Modules |
| --- | --- | --- |
| Device lifecycle | Live discovery, async refresh, grouping, selection persistence | `ui.async_device_manager`, `ui.device_manager`, `ui.device_group_manager` |
| Operations & automation | Batch installs, bug reports, shell commands, recordings, screenshots | `ui.device_operations_manager`, `ui.command_execution_manager`, `utils.adb_tools` |
| File workflows | Device file browser, previews, output path orchestration | `ui.device_file_browser_manager`, `ui.file_operations_manager`, `utils.file_generation_utils` |
| Diagnostics | Logcat streaming, console relay, error classification, completion dialogs | `ui.logcat_viewer`, `ui.console_manager`, `ui.error_handler`, `ui.completion_dialog_manager` |
| UX polish | Optimized device table, status bar telemetry, style manager, theming | `ui.optimized_device_list`, `ui.status_bar_manager`, `ui.style_manager` |
| Performance | Debounced refresh, batched UI updates, native helpers | `utils.debounced_refresh`, `utils.task_dispatcher`, `native_lbb` |

## System Architecture
- **Entry point**: `lazy_blacktea_pyqt.py` wires Qt application startup, orchestrates managers, and owns top-level signals.
- **UI layer (`ui/`)**: Modular managers/controllers for each panel (device list, tools, file browser, logcat viewer) with explicit signal wiring.
- **Utilities (`utils/`)**: ADB façade, structured logging, scheduling helpers, Qt plugin setup, screenshot/recording utilities, native bridge bindings.
- **Configuration (`config/`)**: Static constants plus `ConfigManager` that persists user preferences, logcat options, and IO paths.
- **Testing (`tests/`)**: Rich suite of unit, integration, regression, and performance checks driven via `tests/run_tests.py` and targeted scripts.
- **Packaging (`build-scripts/`, `build_scripts/`)**: PyInstaller specifications, OS-specific shell entrypoints, and helper modules for translating build metadata.
- **Native layer (`native_lbb/`)**: Rust crate compiled into shared library for high-throughput device operations and file handling.

## Directory Reference
| Path | Purpose | Highlights |
| --- | --- | --- |
| `lazy_blacktea_pyqt.py` | Main application entry point | Bootstraps Qt app, registers managers, configures logging |
| `assets/` | Static assets | Icons, branding; keep `icon_128x128.png` present |
| `build-scripts/` | Build orchestration | `build.py`, platform shell scripts, PyInstaller specs |
| `build_scripts/` | Build helper package | Native packaging helpers, spec utilities |
| `config/` | Configuration modules | `constants.py`, `config_manager.py` (preferences + logcat settings) |
| `native_lbb/` | Rust crate | Provides native acceleration via Cargo build |
| `tests/` | Automated tests | Unit, integration, regression, performance harnesses |
| `ui/` | Qt widgets/controllers | Device managers, dialogs, logcat viewer, optimized tables |
| `utils/` | Shared utilities | ADB façade, logging, debounced refresh, Qt plugin loader |
| `scripts/` | Repo automation | `bump_version.py` to update `VERSION` & constants |
| `dist/` | Build outputs | Populated by build scripts (ignored by VCS) |

## Core Workflows
### Device lifecycle orchestration
- `ui.async_device_manager.AsyncDeviceManager` tracks connected devices using background threads and debounced refresh.
- Device metadata flows through `utils.adb_models.DeviceInfo`; grouping, selection, and persistence happen in `ui.device_group_manager` and `ui.device_selection_manager`.
- Status bar and panels listen for device signals via `ui.status_bar_manager` and `ui.panels_manager`.

### Operations, automation, and batching
- `ui.device_operations_manager` coordinates batch operations (install, bug report, reboot) while `ui.command_execution_manager` manages custom shell commands and history.
- Recording and screenshot flows live in `utils.recording_utils` and `utils.screenshot_utils`, with UI surfaces in `ui.recording_status_view` and `ui.screenshot_widget`.
- Output paths and file hygiene are handled by `ui.output_path_manager`, enforcing safe defaults and user overrides.

### Diagnostics & observability
- `ui.logcat_viewer.LogcatWindow` streams device logs with filters from `config.LogcatSettings`.
- Errors are classified by `ui.error_handler` and surfaced via structured dialogs and correlation logging.
- Console output is unified in `ui.console_manager`, ensuring device operations surface actionable messages.

## Setup & Tooling
1. Create a virtual environment and install dependencies:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate  # Windows: .venv\Scripts\activate
   pip install -r requirements.txt
   ```
2. Run the application from source:
   ```bash
   ./start_lazy_blacktea.sh
   # or
   python3 lazy_blacktea_pyqt.py
   ```
3. Ensure `adb devices` succeeds and that the Qt platform plugins can be resolved (handled automatically by `utils.qt_plugin_loader`).
4. Follow PEP 8, maintain type annotations for public surfaces, and route logs through `utils.common.get_logger`.

## Testing Strategy
- Full regression suite:
  ```bash
  python3 tests/run_tests.py
  ```
- Targeted checks:
  - `python3 tests/test_device_operations_refactor.py` — concurrency + retry coverage.
  - `python3 tests/test_logcat_viewer.py` — log streaming behaviours.
  - `python3 test_device_list_performance.py` — large inventory stress test.
  - Smoke scripts under `tests/smoke/` validate device workflows against ADB stubs.
- Follow the TDD discipline noted in the engineering agreement: add/adjust tests with every behaviour change and prevent silent failures.

## Performance & Observability
- Hot paths rely on `utils.debounced_refresh` (batched UI updates) and `utils.task_dispatcher` (thread pool orchestration); profile before altering refresh cadences.
- Use structured logging with correlation IDs via `utils.common.get_logger`; log levels adhere to `config.constants.LoggingConstants`.
- Performance regressions are caught by `tests/test_device_list_performance.py` and `tests/test_async_device_performance.py`—run them after touching device list rendering or async refresh.
- For heavy-duty analysis, leverage the native crate (`native_lbb`) or craft temporary scripts, but remove one-off helpers after use.

## Build & Distribution
- Build distributables via:
  ```bash
  python3 build-scripts/build.py
  ```
  - macOS: generates `.app` bundle plus DMG under `dist/`.
  - Linux: produces AppImage and tarball launchers.
- Platform-specific shell wrappers (`build-scripts/build_macos.sh`, `build-scripts/build_linux.sh`) prepare environments before invoking PyInstaller specs.
- Application version is defined in `config/constants.py::ApplicationConstants.APP_VERSION`; keep it aligned with the top-level `VERSION` file and README badge.

## Native Companion
- The `native_lbb` Rust crate houses performance-critical routines (e.g., batched file pulls, metadata gathering).
- Build locally with Cargo when iterating:
  ```bash
  cd native_lbb
  cargo build --release
  ```
- Python bindings live in `utils.native_bridge`; ensure compiled artifacts are discoverable on your platform before launching the GUI.

## Scripts & Automation
- `start_lazy_blacktea.sh`: environment bootstrap plus sanity checks for Python and ADB.
- `scripts/bump_version.py`: updates `VERSION`, `config/constants.py`, and README release notes.
- `.github/workflows/`: CI pipelines for build/test matrices (see [Documentation & Support](#documentation--support)).

## Troubleshooting
- **ADB not found**: set `ANDROID_HOME`/`ANDROID_SDK_ROOT` or export a custom path via the configuration UI.
- **Permission issues**: enable USB debugging (and security settings) on each device; some operations require root.
- **Headless usage**: run with `QT_QPA_PLATFORM=offscreen` when CI lacks a display server.
- **Device discovery lag**: restart the ADB server (`adb kill-server && adb start-server`) and clear stale `/tmp/lazy_blacktea_*` artifacts.
- **Qt plugin errors**: verify `utils.qt_dependency_checker.check_and_fix_qt_dependencies()` completes without warnings.

## Documentation & Support
- Contributor guide: [CONTRIBUTING.md](CONTRIBUTING.md)
- Repository operating playbook for agents: [AGENTS.md](AGENTS.md)
- GitHub issues: https://github.com/cy76/lazy_blacktea/issues
- Discussions: https://github.com/cy76/lazy_blacktea/discussions
- Security reports: submit privately via GitHub Security Advisories

## Contributing
Review the guidelines, keep commits focused (Conventional Commits), accompany changes with tests, and document performance assumptions. Request review only after `python3 tests/run_tests.py` passes on your machine.

## License
Lazy Blacktea is released under the [MIT License](LICENSE). PyQt6 and bundled dependencies retain their respective upstream licenses.
