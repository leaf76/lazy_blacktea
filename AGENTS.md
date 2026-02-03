# LAZY BLACKTEA KNOWLEDGE BASE

**Generated:** 2026-02-03  
**Commit:** 8065c59  
**Branch:** master

## OVERVIEW

PyQt6 desktop app for Android device automation via ADB. Multi-device monitoring, batch operations, logcat streaming, file management. Rust native companion for high-performance I/O.

## STRUCTURE

```
lazy_blacktea/
├── docs/                    # Markdown guides (quickstart, architecture, deployment)
│   └── zh-TW/               # 繁體中文版本
├── lazy_blacktea_pyqt.py   # Entry point → Qt plugin → dependency check → WindowMain
├── ui/                      # Qt widgets, managers, facades (61 files, ~2500 LOC largest)
│   ├── main_window.py       # Central orchestrator (77 imports - God Object)
│   ├── async_device_manager.py  # Non-blocking discovery (16 signals)
│   ├── logcat_viewer.py     # Log streaming with custom Model/View
│   └── logcat/              # Recording, filters, scrcpy widgets
├── utils/                   # Shared services: ADB, logging, native bridge
│   ├── adb_tools.py         # 2943 lines - all ADB operations
│   ├── common.py            # get_logger(), trace_id_scope()
│   ├── task_dispatcher.py   # Thread pool for background ops
│   └── native_bridge.py     # Python-Rust FFI via ctypes
├── config/                  # Constants, config_manager
├── modules/bluetooth/       # BT state machine, parser, service
├── native_lbb/              # Rust crate (cdylib) for performance
├── tests/                   # 102 files, custom runner, TDD
├── build-scripts/           # PyInstaller specs, platform builds
└── build_scripts/           # Python build modules (native_support.py)
```

## WHERE TO LOOK

| Task | Location | Notes |
|------|----------|-------|
| Add device action | `ui/device_operations_manager.py` | Use `TaskDispatcher` for async |
| Add ADB command | `utils/adb_tools.py` | Follow existing pattern, add to tests |
| New UI panel | `ui/` + wire in `main_window.py` | Manager + Facade pattern |
| Modify logcat | `ui/logcat_viewer.py` or `ui/logcat/` | Custom QAbstractListModel |
| Config constant | `config/constants.py` | Grouped by domain |
| Logging | `utils/common.get_logger()` | Always use trace_id_scope |
| Native acceleration | `native_lbb/src/lib.rs` | Must pair alloc with `lb_free_string` |
| Bluetooth feature | `modules/bluetooth/` | Update state_machine.py + models.py |

## CODE MAP (Key Modules)

| Symbol | Type | Location | Role |
|--------|------|----------|------|
| `WindowMain` | Class | ui/main_window.py | Main window, orchestrates all managers |
| `AsyncDeviceManager` | Class | ui/async_device_manager.py | Non-blocking device discovery |
| `DeviceOperationsManager` | Class | ui/device_operations_manager.py | Batch ADB operations |
| `LogcatWindow` | Class | ui/logcat_viewer.py | Real-time log streaming |
| `TaskDispatcher` | Class | utils/task_dispatcher.py | Global thread pool |
| `get_logger` | Function | utils/common.py | Structured logging factory |
| `native_bridge` | Module | utils/native_bridge.py | Rust FFI interface |
| `BluetoothStateMachine` | Class | modules/bluetooth/state_machine.py | BT state aggregator |

## CONVENTIONS

### Naming
- `snake_case` functions/modules, `PascalCase` Qt classes, `UPPER_SNAKE_CASE` constants
- Managers: `*_manager.py`, Facades: `*_facade.py`, Controllers: `*_controller.py`

### Logging
- **Always**: `from utils.common import get_logger; logger = get_logger(__name__)`
- **Always**: Wrap operations with `trace_id_scope(trace_id)` for correlation
- Logs stored in `~/.lazy_blacktea_logs/` (macOS) or XDG paths (Linux)

### Signal/Slot
- Managers emit signals, MainWindow connects slots
- Use `pyqtSignal` with typed payloads (see `ui/signal_payloads.py`)
- 16 signals in AsyncDeviceManager - check before adding duplicates

### Threading
- UI thread: Qt widgets only
- Background: `TaskDispatcher.submit()` or `QThread` subclass
- Native ops: Use `native_bridge` for heavy I/O

### Error Handling
- Catch specific exceptions, log with trace_id
- UI errors: Toast via `error_handler.py`
- ADB errors: Parse stderr, classify by type

## ANTI-PATTERNS (THIS PROJECT)

| Forbidden | Why | Instead |
|-----------|-----|---------|
| Direct ADB subprocess in UI | Blocks event loop | Use `TaskDispatcher` or `AsyncDeviceWorker` |
| Modify `main_window.py` for small features | 2568 lines, 77 imports | Extract to new Manager |
| `as any` / `@ts-ignore` | N/A (Python) | Use proper typing |
| Empty `except:` | Hides errors | Catch specific, log with trace_id |
| Add Qt widget without QSS | Inconsistent styling | Use `ui/style_manager.py` |
| Forget `lb_free_string` | Memory leak | Always pair with Rust alloc |

## UNIQUE STYLES

### Manager-Worker-Facade Pattern
```
MainWindow → Manager (orchestration) → Worker (QThread) → Facade (thin API)
                ↑ signals                    ↓ results
```

### Two-Phase Device Discovery
1. **Basic** (fast): Serial, state, transport
2. **Detailed** (slow): Android version, API level, battery

### Rust FFI Protocol
- Request: `count\ncmd1\ncmd2` (newline-separated)
- Response: `\u001e` record separator, `\u001f` unit separator
- **Critical**: Call `lb_free_string(ptr)` after every Rust string return

## COMMANDS

```bash
# Run app
uv run python lazy_blacktea_pyqt.py

# Run tests (ALWAYS before commit)
uv run python tests/run_tests.py

# Specific test
uv run pytest tests/test_async_device_performance.py

# Build native module
cd native_lbb && cargo build --release

# Package for distribution
uv run python build-scripts/build.py

# Headless/CI
QT_QPA_PLATFORM=offscreen uv run python lazy_blacktea_pyqt.py
```

## VERSION MANAGEMENT

Sources (keep in sync):
- `VERSION` file (source of truth)
- `config/constants.py::ApplicationConstants.APP_VERSION` (reads from VERSION)
- README badge
- `CHANGELOG.md` for release notes
- Use `scripts/bump_version.py` for releases

## NOTES

- **God Object**: `main_window.py` has 77 imports - delegate to managers
- **Large Files**: `adb_tools.py` (2943 lines), `logcat_viewer.py` (2033 lines) - consider splitting
- **Dual Build Dirs**: `build-scripts/` (execution) vs `build_scripts/` (modules) - historical
- **Dead Code**: `main.py` in root is vestigial (prints "Hello") - can remove
- **Qt Plugin**: Must call `configure_qt_plugin_path()` before any Qt import
- **Coverage**: Track `utils/`, `ui/`, `config/` - see `.coveragerc`
- **Logcat Buffer**: Logcat start no longer clears the device buffer; use the Clear Buffer button in the viewer
