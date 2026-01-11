import os
import sys
import unittest

from PyQt6.QtWidgets import QApplication, QMainWindow, QTabWidget, QWidget

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ui.tools_panel_controller import ToolsPanelController


class DummyCommandExecutionManager:
    def cancel_all_commands(self):
        self.cancelled = True


class DummyWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.command_execution_manager = DummyCommandExecutionManager()

    def get_checked_devices(self):
        return []


class ShellCommandsLayoutTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.window = DummyWindow()
        self.controller = ToolsPanelController(self.window)
        self.tab_widget = QTabWidget()

    def test_shell_tab_creates_terminal_widget(self):
        original_count = self.tab_widget.count()
        self.controller._create_shell_commands_tab(self.tab_widget)
        self.assertEqual(self.tab_widget.count(), original_count + 1)

        shell_widget = self.tab_widget.widget(original_count)
        self.assertIsInstance(shell_widget, QWidget)

        self.assertTrue(
            hasattr(self.window, "terminal_widget"),
            "Terminal widget should be attached to window",
        )
        self.assertTrue(
            hasattr(self.window, "terminal_manager"),
            "Terminal manager should be attached to window",
        )

    def test_terminal_widget_has_required_components(self):
        self.controller._create_shell_commands_tab(self.tab_widget)

        terminal_widget = self.window.terminal_widget
        self.assertTrue(
            hasattr(terminal_widget, "output_area"),
            "Terminal widget should have output_area",
        )
        self.assertTrue(
            hasattr(terminal_widget, "input_line"),
            "Terminal widget should have input_line",
        )
        self.assertTrue(
            hasattr(terminal_widget, "command_submitted"),
            "Terminal widget should have command_submitted signal",
        )
        self.assertTrue(
            hasattr(terminal_widget, "cancel_requested"),
            "Terminal widget should have cancel_requested signal",
        )


if __name__ == "__main__":
    unittest.main()
