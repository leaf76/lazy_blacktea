"""Tests for logcat filter components.

Tests the three-level filter architecture:
- FilterPattern, FilterPreset, ActiveFilterState (data models)
- PresetManager (persistence)
- DeviceWatcher (device monitoring)
- FilterPanelWidget (UI)
"""

import json
import sys
import tempfile
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


class TestFilterPattern:
    """Tests for FilterPattern dataclass."""

    def test_valid_regex_returns_true(self):
        from ui.logcat.filter_models import FilterPattern

        pattern = FilterPattern("error.*fatal")
        assert pattern.is_valid_regex()

    def test_invalid_regex_returns_false(self):
        from ui.logcat.filter_models import FilterPattern

        pattern = FilterPattern("[invalid")
        assert not pattern.is_valid_regex()

    def test_compile_returns_pattern_for_valid_regex(self):
        from ui.logcat.filter_models import FilterPattern

        pattern = FilterPattern("test")
        compiled = pattern.compile()
        assert compiled is not None
        assert compiled.search("TEST")  # Case-insensitive

    def test_compile_returns_none_for_invalid_regex(self):
        from ui.logcat.filter_models import FilterPattern

        pattern = FilterPattern("[invalid")
        assert pattern.compile() is None


class TestFilterPreset:
    """Tests for FilterPreset dataclass."""

    def test_to_dict_serializes_correctly(self):
        from ui.logcat.filter_models import FilterPreset

        preset = FilterPreset(
            name="Test Preset",
            filters=["error", "crash"],
            created_at=1000.0,
            updated_at=2000.0,
        )
        data = preset.to_dict()
        assert data["name"] == "Test Preset"
        assert data["filters"] == ["error", "crash"]
        assert data["created_at"] == 1000.0
        assert data["updated_at"] == 2000.0

    def test_from_dict_deserializes_correctly(self):
        from ui.logcat.filter_models import FilterPreset

        data = {
            "name": "Loaded Preset",
            "filters": ["ANR"],
            "created_at": 500.0,
            "updated_at": 600.0,
        }
        preset = FilterPreset.from_dict(data)
        assert preset.name == "Loaded Preset"
        assert preset.filters == ["ANR"]
        assert preset.created_at == 500.0

    def test_is_empty_true_when_no_filters(self):
        from ui.logcat.filter_models import FilterPreset

        preset = FilterPreset(name="Empty")
        assert preset.is_empty()

    def test_is_empty_false_when_has_filters(self):
        from ui.logcat.filter_models import FilterPreset

        preset = FilterPreset(name="Has Filters", filters=["test"])
        assert not preset.is_empty()


class TestActiveFilterState:
    """Tests for ActiveFilterState dataclass."""

    def test_all_patterns_combines_live_and_active(self):
        from ui.logcat.filter_models import ActiveFilterState

        state = ActiveFilterState(
            live_pattern="live",
            active_patterns=["active1", "active2"],
        )
        patterns = state.all_patterns()
        assert patterns == ["live", "active1", "active2"]

    def test_all_patterns_excludes_empty_live(self):
        from ui.logcat.filter_models import ActiveFilterState

        state = ActiveFilterState(
            live_pattern="  ",
            active_patterns=["active"],
        )
        patterns = state.all_patterns()
        assert patterns == ["active"]

    def test_add_pattern_succeeds_for_new_pattern(self):
        from ui.logcat.filter_models import ActiveFilterState

        state = ActiveFilterState()
        assert state.add_pattern("new")
        assert "new" in state.active_patterns

    def test_add_pattern_fails_for_duplicate(self):
        from ui.logcat.filter_models import ActiveFilterState

        state = ActiveFilterState(active_patterns=["existing"])
        assert not state.add_pattern("existing")

    def test_remove_pattern_succeeds_for_existing(self):
        from ui.logcat.filter_models import ActiveFilterState

        state = ActiveFilterState(active_patterns=["remove_me"])
        assert state.remove_pattern("remove_me")
        assert "remove_me" not in state.active_patterns

    def test_clear_keeps_live_pattern(self):
        from ui.logcat.filter_models import ActiveFilterState

        state = ActiveFilterState(
            live_pattern="keep",
            active_patterns=["remove"],
        )
        state.clear()
        assert state.live_pattern == "keep"
        assert state.active_patterns == []

    def test_clear_all_removes_everything(self):
        from ui.logcat.filter_models import ActiveFilterState

        state = ActiveFilterState(
            live_pattern="remove",
            active_patterns=["also_remove"],
        )
        state.clear_all()
        assert state.live_pattern is None
        assert state.active_patterns == []

    def test_load_from_preset_replaces_active(self):
        from ui.logcat.filter_models import ActiveFilterState, FilterPreset

        state = ActiveFilterState(active_patterns=["old"])
        preset = FilterPreset(name="Test", filters=["new1", "new2"])
        state.load_from_preset(preset)
        assert state.active_patterns == ["new1", "new2"]

    def test_to_preset_creates_from_active(self):
        from ui.logcat.filter_models import ActiveFilterState

        state = ActiveFilterState(active_patterns=["a", "b"])
        preset = state.to_preset("My Preset")
        assert preset.name == "My Preset"
        assert preset.filters == ["a", "b"]


class TestPresetManager:
    """Tests for PresetManager class."""

    def test_save_and_list_preset(self):
        from ui.logcat.filter_models import FilterPreset
        from ui.logcat.preset_manager import PresetManager

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(PresetManager, "PRESETS_DIR", tmpdir):
                manager = PresetManager()
                preset = FilterPreset(name="Test", filters=["error"])
                assert manager.save_preset(preset)

                presets = manager.list_presets()
                assert len(presets) == 1
                assert presets[0].name == "Test"

    def test_save_preset_overwrites_existing(self):
        from ui.logcat.filter_models import FilterPreset
        from ui.logcat.preset_manager import PresetManager

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(PresetManager, "PRESETS_DIR", tmpdir):
                manager = PresetManager()

                original = FilterPreset(name="Test", filters=["error"])
                updated = FilterPreset(name="Test", filters=["fatal"])
                assert manager.save_preset(original)
                assert manager.save_preset(updated)

                loaded = manager.get_preset("Test")
                assert loaded is not None
                assert loaded.filters == ["fatal"]

    def test_delete_preset(self):
        from ui.logcat.filter_models import FilterPreset
        from ui.logcat.preset_manager import PresetManager

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(PresetManager, "PRESETS_DIR", tmpdir):
                manager = PresetManager()
                preset = FilterPreset(name="Delete Me", filters=["test"])
                manager.save_preset(preset)

                assert manager.delete_preset("Delete Me")
                assert len(manager.list_presets()) == 0

    def test_get_preset_returns_none_for_missing(self):
        from ui.logcat.preset_manager import PresetManager

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(PresetManager, "PRESETS_DIR", tmpdir):
                manager = PresetManager()
                assert manager.get_preset("nonexistent") is None

    def test_sanitize_filename_removes_special_chars(self):
        from ui.logcat.preset_manager import PresetManager

        assert PresetManager._sanitize_filename("test/file:name") == "test_file_name"
        assert PresetManager._sanitize_filename("") == "unnamed"

    def test_migrate_legacy_filters(self):
        from ui.logcat.preset_manager import PresetManager

        with tempfile.TemporaryDirectory() as tmpdir:
            legacy_file = Path(tmpdir) / "filters.json"
            legacy_file.write_text(json.dumps({
                "key1": "pattern1",
                "key2": "pattern2",
            }))

            with patch.object(PresetManager, "PRESETS_DIR", tmpdir):
                with patch.object(PresetManager, "LEGACY_FILTERS_FILE", str(legacy_file)):
                    manager = PresetManager()
                    migrated = manager.migrate_legacy_filters()
                    assert migrated == 2

                    # Check preset was created
                    preset = manager.get_preset("Migrated Filters")
                    assert preset is not None
                    assert set(preset.filters) == {"pattern1", "pattern2"}

                    # Check legacy file was renamed
                    assert not legacy_file.exists()
                    assert legacy_file.with_suffix(".json.migrated").exists()


class TestDeviceWatcher:
    """Tests for DeviceWatcher class."""

    def test_device_disconnected_signal_emitted(self):
        from PyQt6.QtWidgets import QApplication

        # Ensure QApplication exists
        app = QApplication.instance() or QApplication([])

        from ui.logcat.device_watcher import DeviceWatcher

        # Mock device manager
        mock_manager = MagicMock()
        mock_manager.device_lost = MagicMock()
        mock_manager.device_found = MagicMock()

        # Create watcher
        watcher = DeviceWatcher("TEST123", mock_manager)

        # Track signal emissions
        disconnected_calls = []
        watcher.device_disconnected.connect(lambda s: disconnected_calls.append(s))

        # Simulate device loss
        watcher._on_device_lost("TEST123")

        assert len(disconnected_calls) == 1
        assert disconnected_calls[0] == "TEST123"
        assert not watcher.is_connected

    def test_ignores_other_device_disconnect(self):
        from PyQt6.QtWidgets import QApplication

        app = QApplication.instance() or QApplication([])

        from ui.logcat.device_watcher import DeviceWatcher

        mock_manager = MagicMock()
        mock_manager.device_lost = MagicMock()
        mock_manager.device_found = MagicMock()

        watcher = DeviceWatcher("MY_DEVICE", mock_manager)

        disconnected_calls = []
        watcher.device_disconnected.connect(lambda s: disconnected_calls.append(s))

        # Different device disconnects
        watcher._on_device_lost("OTHER_DEVICE")

        assert len(disconnected_calls) == 0
        assert watcher.is_connected

    def test_cleanup_disconnects_signals(self):
        from PyQt6.QtWidgets import QApplication

        app = QApplication.instance() or QApplication([])

        from ui.logcat.device_watcher import DeviceWatcher

        mock_manager = MagicMock()
        mock_manager.device_lost = MagicMock()
        mock_manager.device_found = MagicMock()

        watcher = DeviceWatcher("TEST", mock_manager)
        watcher.cleanup()

        # Should not raise even if called twice
        watcher.cleanup()


class TestToastNotification:
    """Tests for ToastNotification widget."""

    def test_show_toast_makes_widget_visible(self):
        from PyQt6.QtWidgets import QApplication, QWidget

        app = QApplication.instance() or QApplication([])

        from ui.toast_notification import ToastNotification

        parent = QWidget()
        parent.resize(800, 600)
        toast = ToastNotification(parent=parent)

        assert not toast.isVisible()
        toast.show_toast("Test message")
        assert toast.isVisible()

    def test_dismiss_hides_widget(self):
        from PyQt6.QtWidgets import QApplication, QWidget

        app = QApplication.instance() or QApplication([])

        from ui.toast_notification import ToastNotification

        parent = QWidget()
        parent.resize(800, 600)
        toast = ToastNotification(parent=parent)

        toast.show_toast("Test")
        toast.dismiss()
        assert not toast.isVisible()

    def test_different_styles_apply(self):
        from PyQt6.QtWidgets import QApplication, QWidget

        app = QApplication.instance() or QApplication([])

        from ui.toast_notification import ToastNotification

        parent = QWidget()
        toast = ToastNotification(parent=parent)

        for style in [
            ToastNotification.STYLE_INFO,
            ToastNotification.STYLE_WARNING,
            ToastNotification.STYLE_ERROR,
            ToastNotification.STYLE_SUCCESS,
        ]:
            toast.show_toast(f"Test {style}", style=style)
            # Should not raise


class TestSearchBarWidget:
    """Tests for the floating search bar widget."""

    def test_initial_state_is_hidden(self):
        from PyQt6.QtWidgets import QApplication, QWidget

        app = QApplication.instance() or QApplication([])

        from ui.logcat.search_bar_widget import SearchBarWidget

        parent = QWidget()
        search_bar = SearchBarWidget(parent=parent)

        assert not search_bar.isVisible()
        assert search_bar.get_search_pattern() == ""
        assert not search_bar.is_case_sensitive()
        assert not search_bar.is_regex_mode()

    def test_show_search_calls_show_and_focus(self):
        from PyQt6.QtWidgets import QApplication, QWidget

        app = QApplication.instance() or QApplication([])

        from ui.logcat.search_bar_widget import SearchBarWidget

        parent = QWidget()
        parent.show()  # Parent must be visible for children to be visible
        search_bar = SearchBarWidget(parent=parent)

        search_bar.show_search()
        # After calling show_search, the widget should call show() and be in "shown" state
        # Note: In headless mode, isVisible() may still return False even after show()
        # So we test that the internal state is correct
        assert not search_bar.isHidden()  # isHidden() returns False after show() is called

    def test_close_search_hides_and_clears(self):
        from PyQt6.QtWidgets import QApplication, QWidget

        app = QApplication.instance() or QApplication([])

        from ui.logcat.search_bar_widget import SearchBarWidget

        parent = QWidget()
        search_bar = SearchBarWidget(parent=parent)

        search_bar.set_search_text("test")
        search_bar.show_search()
        search_bar.close_search()

        assert not search_bar.isVisible()
        assert search_bar.get_search_pattern() == ""

    def test_compile_pattern_returns_regex(self):
        from PyQt6.QtWidgets import QApplication, QWidget

        app = QApplication.instance() or QApplication([])

        from ui.logcat.search_bar_widget import SearchBarWidget

        parent = QWidget()
        search_bar = SearchBarWidget(parent=parent)

        search_bar.set_search_text("error")
        pattern = search_bar.compile_pattern()

        assert pattern is not None
        assert pattern.search("This is an error message")
        assert pattern.search("ERROR uppercase")  # Case insensitive by default
        assert not pattern.search("no match here")

    def test_compile_pattern_escapes_special_chars_in_literal_mode(self):
        from PyQt6.QtWidgets import QApplication, QWidget

        app = QApplication.instance() or QApplication([])

        from ui.logcat.search_bar_widget import SearchBarWidget

        parent = QWidget()
        search_bar = SearchBarWidget(parent=parent)

        # Search for literal "a.b" (not regex where . matches any char)
        search_bar.set_search_text("a.b")
        pattern = search_bar.compile_pattern()

        assert pattern is not None
        assert pattern.search("a.b")
        assert not pattern.search("aXb")  # . should not match X in literal mode

    def test_compile_pattern_uses_regex_mode(self):
        from PyQt6.QtWidgets import QApplication, QWidget

        app = QApplication.instance() or QApplication([])

        from ui.logcat.search_bar_widget import SearchBarWidget

        parent = QWidget()
        search_bar = SearchBarWidget(parent=parent)

        search_bar.set_search_text("a.b")
        search_bar._regex_checkbox.setChecked(True)
        pattern = search_bar.compile_pattern()

        assert pattern is not None
        assert pattern.search("aXb")  # . matches X in regex mode

    def test_compile_pattern_returns_none_for_invalid_regex(self):
        from PyQt6.QtWidgets import QApplication, QWidget

        app = QApplication.instance() or QApplication([])

        from ui.logcat.search_bar_widget import SearchBarWidget

        parent = QWidget()
        search_bar = SearchBarWidget(parent=parent)

        search_bar.set_search_text("[invalid")
        search_bar._regex_checkbox.setChecked(True)
        pattern = search_bar.compile_pattern()

        assert pattern is None

    def test_update_match_count_updates_label(self):
        from PyQt6.QtWidgets import QApplication, QWidget

        app = QApplication.instance() or QApplication([])

        from ui.logcat.search_bar_widget import SearchBarWidget

        parent = QWidget()
        search_bar = SearchBarWidget(parent=parent)

        search_bar.update_match_count(3, 10)
        assert "3 of 10" in search_bar._match_label.text()

        # When there's a search pattern but no results, show "No results"
        search_bar.set_search_text("test")
        search_bar.update_match_count(0, 0)
        assert "No results" in search_bar._match_label.text()

    def test_get_match_positions_finds_all_occurrences(self):
        from PyQt6.QtWidgets import QApplication, QWidget

        app = QApplication.instance() or QApplication([])

        from ui.logcat.search_bar_widget import SearchBarWidget

        parent = QWidget()
        search_bar = SearchBarWidget(parent=parent)

        search_bar.set_search_text("ab")
        positions = search_bar.get_match_positions("ab cd ab ef ab")

        assert len(positions) == 3
        assert positions[0] == (0, 2)
        assert positions[1] == (6, 8)
        assert positions[2] == (12, 14)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
