# LOGCAT SUBMODULE

## OVERVIEW

Logcat-related widgets: recording, filtering, scrcpy integration. Extracted from `logcat_viewer.py`.

## STRUCTURE

```
logcat/
├── __init__.py              # Exports
├── recording_control_widget.py   # Start/stop/segment recording
├── recording_sync_manager.py     # Cross-device recording state
├── filter_panel_widget.py        # Three-level filter UI
├── filter_models.py              # Filter data classes
├── preset_manager.py             # Save/load filter presets
├── search_bar_widget.py          # Quick search input
├── device_watcher.py             # Auto-stop on device disconnect
├── scrcpy_control_widget.py      # Scrcpy launch/stop
└── scrcpy_preview_panel.py       # Scrcpy stream preview
```

## WHERE TO LOOK

| Task | File |
|------|------|
| Recording logic | `recording_control_widget.py` |
| Filter presets | `preset_manager.py` |
| Live search | `search_bar_widget.py` |
| Scrcpy integration | `scrcpy_control_widget.py` |

## CONVENTIONS

### Recording
- Android `screenrecord` hard-limits at 180s
- Use 170s segments (see `RecordingConstants.SEGMENT_DURATION_SECONDS`)
- Always verify recording state before stop

### Filter Architecture
```
Live Filter (UI input)
    ↓ applies to
Active Filters (current session list)
    ↓ can save to
Saved Presets (persistent storage)
```

### Device Watcher
- `DeviceWatcher` monitors device connectivity
- Auto-stops logcat/recording if device disconnects
- Uses `AsyncDeviceManager` signals

## ANTI-PATTERNS

| Forbidden | Instead |
|-----------|---------|
| Recording >180s single segment | Use segment-based approach |
| Ignore device disconnect | Use `DeviceWatcher` |
