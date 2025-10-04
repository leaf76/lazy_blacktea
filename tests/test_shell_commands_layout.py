import os
import sys
import unittest

from PyQt6.QtWidgets import QApplication, QMainWindow, QScrollArea, QTabWidget, QSizePolicy

# Ensure project root is on the import path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ui.tools_panel_controller import ToolsPanelController


class DummyCommandExecutionManager:
    def cancel_all_commands(self):
        self.cancelled = True


class DummyWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.command_execution_manager = DummyCommandExecutionManager()
        self.history_cleared = False
        self.history_exported = False
        self.history_imported = False

    # Methods invoked by the shell commands tab wiring
    def add_template_command(self, command: str) -> None:
        self.last_template_command = command

    def run_single_command(self) -> None:
        self.ran_single = True

    def run_batch_commands(self) -> None:
        self.ran_batch = True

    def run_shell_command(self) -> None:
        self.ran_shell = True

    def clear_command_history(self) -> None:
        self.history_cleared = True

    def export_command_history(self) -> None:
        self.history_exported = True

    def import_command_history(self) -> None:
        self.history_imported = True

    def update_history_display(self) -> None:
        self.history_display_updated = True

    def load_from_history(self, item) -> None:  # pragma: no cover - invoked via signal wiring
        self.loaded_history_item = item


class ShellCommandsLayoutTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.window = DummyWindow()
        self.controller = ToolsPanelController(self.window)
        self.tab_widget = QTabWidget()

    def test_shell_tab_is_scrollable(self):
        original_count = self.tab_widget.count()
        self.controller._create_shell_commands_tab(self.tab_widget)
        self.assertEqual(self.tab_widget.count(), original_count + 1)

        shell_widget = self.tab_widget.widget(original_count)
        self.assertIsInstance(shell_widget, QScrollArea)
        self.assertTrue(shell_widget.widgetResizable(), 'Shell tab must allow scrolling for constrained layouts')
        self.assertIsNotNone(shell_widget.widget())

    def test_batch_editor_no_longer_clamped(self):
        self.controller._create_shell_commands_tab(self.tab_widget)
        editor = self.window.batch_commands_edit
        self.assertGreater(editor.maximumHeight(), 1000, 'Batch command editor should not be hard-limited in height')
        self.assertEqual(
            editor.sizePolicy().verticalPolicy(),
            QSizePolicy.Policy.Expanding,
            'Batch command editor should expand and rely on scrollbars instead of shrinking'
        )


if __name__ == '__main__':
    unittest.main()
