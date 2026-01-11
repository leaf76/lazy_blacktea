# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Lazy Blacktea is a PyQt6 desktop application for Android device automation via ADB. It supports multi-device monitoring, batch operations (install, record, capture, shell commands), logcat streaming, and file management.

## Build & Run Commands

```bash
# Run the application (using uv)
uv run python lazy_blacktea_pyqt.py

# Run full test suite (unit + integration)
uv run python tests/run_tests.py

# Run specific test file
uv run pytest tests/test_async_device_performance.py

# Functional tests (requires connected Android device)
uv run python tests/test_functional.py

# Build native Rust module
cd native_lbb && cargo build --release

# Package for distribution
uv run python build-scripts/build.py

# Headless/CI environment
QT_QPA_PLATFORM=offscreen uv run python lazy_blacktea_pyqt.py

# Sync dependencies (after pulling changes)
uv sync
```

## Architecture

### Entry Point
`lazy_blacktea_pyqt.py` → configures Qt plugins → checks dependencies → launches `ui.main_window.WindowMain`

### Module Organization
| Directory | Purpose |
|-----------|---------|
| `ui/` | Qt widgets and controllers (signal/slot wiring) |
| `utils/` | Shared services: ADB façade, logging, scheduling, native bridge |
| `config/` | Constants (`config/constants.py`) and user preferences |
| `native_lbb/` | Rust crate for high-performance I/O operations |
| `tests/` | Unit, integration, and performance tests |

### Key UI Components
- `ui/main_window.py` - Main application window
- `ui/device_manager.py`, `ui/async_device_manager.py` - Device discovery and state
- `ui/device_operations_manager.py` - Batch operations (install, record, capture)
- `ui/logcat_viewer.py` - Real-time logcat streaming
- `ui/device_file_browser_manager.py` - Device file browsing and transfer

### Key Utilities
- `utils/adb_tools.py` - ADB command wrapper
- `utils/common.py` - Logging via `get_logger()` (structured JSON + trace ID)
- `utils/debounced_refresh.py` - UI update throttling
- `utils/native_bridge.py` - Python-Rust FFI bridge

## Coding Conventions

- Follow PEP 8, use type hints on public interfaces
- `snake_case` for functions/modules, `PascalCase` for Qt classes, `UPPER_SNAKE_CASE` for constants
- Logs and code comments in English
- Route all logging through `utils.common.get_logger`
- Version is read from `VERSION` file; sync with `config/constants.py::ApplicationConstants.APP_VERSION`

## Testing

- Practice TDD: write tests first, then implement
- Run `python3 tests/run_tests.py` before every commit
- Tests create temp files in `/tmp/lazy_blacktea_*` - clean after runs
- For concurrency tests: `python3 -m pytest tests/test_async_device_performance.py`

## Version Management

Version sources (keep in sync):
- `VERSION` file (source of truth)
- README badge (`Current release: vX.X.X`)
- Use `scripts/bump_version.py` for releases
