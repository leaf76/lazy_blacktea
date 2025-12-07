"""Logcat viewer components package.

This package contains modularized components for the Logcat viewer:
- filter_models: Data structures for filter patterns and presets
- preset_manager: Preset CRUD operations and migration
- device_watcher: Device state monitoring
- filter_panel_widget: Three-level filter UI component
- search_bar_widget: Floating search bar with highlighting support
- recording_sync_manager: Recording-logcat synchronization
- scrcpy_control_widget: scrcpy launch controls
- recording_control_widget: Screen recording controls
- scrcpy_preview_panel: Side panel for preview and recording
"""

from ui.logcat.filter_models import FilterPattern, FilterPreset, ActiveFilterState
from ui.logcat.preset_manager import PresetManager
from ui.logcat.device_watcher import DeviceWatcher
from ui.logcat.filter_panel_widget import FilterPanelWidget
from ui.logcat.search_bar_widget import SearchBarWidget
from ui.logcat.recording_sync_manager import RecordingSyncManager, RecordingSession
from ui.logcat.scrcpy_control_widget import ScrcpyControlWidget
from ui.logcat.recording_control_widget import RecordingControlWidget
from ui.logcat.scrcpy_preview_panel import ScrcpyPreviewPanel

__all__ = [
    "FilterPattern",
    "FilterPreset",
    "ActiveFilterState",
    "PresetManager",
    "DeviceWatcher",
    "FilterPanelWidget",
    "SearchBarWidget",
    "RecordingSyncManager",
    "RecordingSession",
    "ScrcpyControlWidget",
    "RecordingControlWidget",
    "ScrcpyPreviewPanel",
]
