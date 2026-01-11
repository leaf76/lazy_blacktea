# UI MODULE

## OVERVIEW

PyQt6 widgets, managers, and controllers. 61 files, Manager-Worker-Facade architecture.

## STRUCTURE

```
ui/
├── main_window.py           # Central orchestrator (2568 lines - consider delegation)
├── async_device_manager.py  # Non-blocking discovery, 16 pyqtSignals
├── device_manager.py        # Legacy facade, delegates to AsyncDeviceManager
├── device_operations_manager.py  # Batch ADB ops via TaskDispatcher
├── logcat_viewer.py         # Log streaming, custom Model/View (2033 lines)
├── style_manager.py         # QSS themes, CSS templates (1522 lines)
├── logcat/                  # Recording, filters, scrcpy widgets
├── components/              # Reusable: expandable_device_list, filter_bar/chip
└── *_facade.py              # Thin API wrappers for managers
```

## WHERE TO LOOK

| Task | File | Notes |
|------|------|-------|
| Device discovery | `async_device_manager.py` | Two-phase: basic → detailed |
| Device actions | `device_operations_manager.py` | reboot, install, screenshot, record |
| Logcat streaming | `logcat_viewer.py` | Uses `LogcatListModel`, `_LogListItemDelegate` |
| Logcat filters | `logcat/filter_panel_widget.py` | Three-level: Live, Active, Presets |
| Recording | `logcat/recording_control_widget.py` | Segment-based (170s max per segment) |
| Styling/themes | `style_manager.py` | Light/Dark, all QSS here |
| File browser | `device_file_browser_manager.py` | Pull/push, preview |
| App management | `app_management_manager.py` | List, uninstall, force stop |

## SIGNAL FLOW

```
TrackDevicesWorker (QThread)
    ↓ device_list_changed
AsyncDeviceManager
    ↓ device_basic_loaded / device_detailed_loaded
DeviceManager (facade)
    ↓ device_found / device_lost / status_updated
MainWindow
    → UI update
```

## CONVENTIONS

### Adding New Manager
1. Create `*_manager.py` extending `QObject`
2. Define signals for state changes
3. Use `TaskDispatcher` for background work
4. Wire in `main_window.py` constructor
5. Optionally create `*_facade.py` for thin API

### Widget Styling
- **Always** use `style_manager.py` for QSS
- Check `ui/qss/` for existing stylesheets
- Follow light/dark theme support

### Threading
- Never block UI thread with ADB calls
- Use `TaskDispatcher.submit(fn, callback)`
- Workers emit signals, managers catch and forward

## ANTI-PATTERNS

| Forbidden | Instead |
|-----------|---------|
| Add more to `main_window.py` | Extract new Manager class |
| Direct `subprocess` call | Use `utils/adb_tools.py` via TaskDispatcher |
| Inline CSS strings | Add to `style_manager.py` |
| Signal without typed payload | Use `signal_payloads.py` or define dataclass |

## COMPLEXITY HOTSPOTS

| File | Lines | Issue | Suggestion |
|------|-------|-------|------------|
| main_window.py | 2568 | 77 imports, God Object | Delegate to managers |
| logcat_viewer.py | 2033 | Model + View + Delegate | Already modular, maintain |
| style_manager.py | 1522 | CSS templates | Consider external .qss files |
| async_device_manager.py | 1127 | 16 signals | Document signal contract |
