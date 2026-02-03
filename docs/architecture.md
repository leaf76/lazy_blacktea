# Architecture Overview

## Project Tour
| Path | Purpose | Highlights |
| --- | --- | --- |
| `lazy_blacktea_pyqt.py` | Application entry point | Bootstraps Qt, registers managers, configures logging |
| `ui/` | UI widgets and controllers | Device list, tool panels, file browser, logcat viewer |
| `utils/` | Shared utilities | ADB facade, logging, scheduling, Qt dependency checks, native bridge |
| `config/` | Configuration modules | Constants, preference storage, paths, logcat options |
| `tests/` | Test suites | Unit, integration, performance smoke tests via `tests/run_tests.py` |
| `assets/` | Static assets | Icons and branding resources |
| `build_scripts/`, `build-scripts/` | Packaging toolchain | PyInstaller specs, platform launch scripts, build helpers |
| `native_lbb/` | Rust project | Optimized routines for high-volume operations |
| `scripts/` | Automation scripts | Utilities like `bump_version.py` for release chores |

## Architecture Overview
- `lazy_blacktea_pyqt.py` orchestrates UI composition and cross-module signals.
- `ui/` manages visual components and state via explicit signal/slot wiring.
- `utils/` wraps ADB, scheduling, structured logging, and the native bridge.
- `config/` stores defaults and persists user preferences.
- `native_lbb/` delivers optimized routines for intensive I/O workloads.
- `tests/` enforces the testing pyramid for functionality, performance, and concurrency safety.

## Native Companion
- `native_lbb` is the Rust crate powering batched file operations and metadata gathering.
- Build it locally with:
  ```bash
  cd native_lbb
  cargo build --release
  ```
- Python loads the resulting shared library through `utils.native_bridge`; ensure the artifact sits on the dynamic loader path or configure environment variables accordingly.

## Performance, Observability & Troubleshooting
- Key techniques: debounced refreshes, batched UI updates, async I/O, and offloading to Rust helpers.
- Logging uses `utils.common.get_logger` for structured messages and trace IDs.
- Common issues:
  - **ADB not found**: set `ANDROID_HOME` or `ANDROID_SDK_ROOT`, or configure a custom path in-app.
  - **Permission errors**: enable USB Debugging and root access where required.
  - **Slow discovery**: restart ADB (`adb kill-server && adb start-server`) and clear `/tmp/lazy_blacktea_*` artifacts.
  - **Qt plugin warnings**: run `utils.qt_dependency_checker.check_and_fix_qt_dependencies()` and confirm clean output.
  - **Headless runs**: export `QT_QPA_PLATFORM=offscreen`.
