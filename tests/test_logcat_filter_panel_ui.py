import os
import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from PyQt6.QtWidgets import QApplication

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


class FilterPanelWidgetPresetUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        cls._app = QApplication.instance() or QApplication([])

    def test_save_as_preset_defaults_to_selected_preset_name(self) -> None:
        from ui.logcat.filter_panel_widget import FilterPanelWidget
        from ui.logcat.preset_manager import PresetManager

        preset_manager = Mock(spec=PresetManager)
        preset_manager.list_presets.return_value = []
        preset_manager.preset_exists.return_value = False
        preset_manager.save_preset.return_value = True

        widget = FilterPanelWidget(preset_manager=preset_manager)
        widget.add_active_pattern("error")

        widget._preset_combo.clear()
        widget._preset_combo.addItem("MyPreset")
        widget._preset_combo.setCurrentText("MyPreset")

        with patch("ui.logcat.filter_panel_widget.QInputDialog.getText") as get_text:
            get_text.return_value = ("MyPreset", True)
            with patch("ui.logcat.filter_panel_widget.QMessageBox.information"):
                widget._save_as_preset()

            _, kwargs = get_text.call_args
            self.assertEqual(kwargs.get("text"), "MyPreset")

    def test_active_list_items_are_text_selectable(self) -> None:
        from ui.logcat.filter_panel_widget import FilterPanelWidget
        from ui.logcat.preset_manager import PresetManager
        from PyQt6.QtCore import Qt
        from PyQt6.QtWidgets import QLabel

        preset_manager = Mock(spec=PresetManager)
        preset_manager.list_presets.return_value = []

        widget = FilterPanelWidget(preset_manager=preset_manager)
        widget.add_active_pattern("alpha")

        item = widget._active_list.item(0)
        label = widget._active_list.itemWidget(item)
        self.assertIsInstance(label, QLabel)
        flags = label.textInteractionFlags()
        self.assertTrue(flags & Qt.TextInteractionFlag.TextSelectableByMouse)

    def test_update_preset_overwrites_selected_name(self) -> None:
        from ui.logcat.filter_panel_widget import FilterPanelWidget
        from ui.logcat.preset_manager import PresetManager
        from PyQt6.QtWidgets import QMessageBox

        preset_manager = Mock(spec=PresetManager)
        preset_manager.list_presets.return_value = []
        preset_manager.preset_exists.return_value = True
        preset_manager.save_preset.return_value = True

        widget = FilterPanelWidget(preset_manager=preset_manager)
        widget.add_active_pattern("fatal")
        widget._preset_combo.clear()
        widget._preset_combo.addItem("CrashPreset")
        widget._preset_combo.setCurrentText("CrashPreset")

        with patch("ui.logcat.filter_panel_widget.QMessageBox.question") as question:
            question.return_value = QMessageBox.StandardButton.Yes
            with patch("ui.logcat.filter_panel_widget.QMessageBox.information"):
                widget._overwrite_selected_preset()

        preset_manager.save_preset.assert_called_once()
        saved = preset_manager.save_preset.call_args.args[0]
        self.assertEqual(saved.name, "CrashPreset")


if __name__ == "__main__":
    unittest.main()
