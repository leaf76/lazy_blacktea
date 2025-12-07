"""Logcat viewer components package.

This package contains modularized components for the Logcat viewer:
- filter_models: Data structures for filter patterns and presets
- preset_manager: Preset CRUD operations and migration
- device_watcher: Device state monitoring
- filter_panel_widget: Three-level filter UI component
- search_bar_widget: Floating search bar with highlighting support
"""

from ui.logcat.filter_models import FilterPattern, FilterPreset, ActiveFilterState
from ui.logcat.preset_manager import PresetManager
from ui.logcat.device_watcher import DeviceWatcher
from ui.logcat.filter_panel_widget import FilterPanelWidget
from ui.logcat.search_bar_widget import SearchBarWidget

__all__ = [
    "FilterPattern",
    "FilterPreset",
    "ActiveFilterState",
    "PresetManager",
    "DeviceWatcher",
    "FilterPanelWidget",
    "SearchBarWidget",
]
