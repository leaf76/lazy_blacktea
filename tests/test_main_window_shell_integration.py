import os
import sys
import types
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt6.QtWidgets import QApplication, QMainWindow, QSplitter, QWidget  # noqa: E402
from PyQt6.QtCore import Qt  # noqa: E402


_APP = QApplication.instance() or QApplication([])


class MainWindowShellIntegrationTests(unittest.TestCase):
    def setUp(self):
        from ui.main_window import WindowMain

        self.window = WindowMain.__new__(WindowMain)
        QMainWindow.__init__(self.window)
        self.addCleanup(self.window.deleteLater)

    def test_shell_wraps_existing_workspace_splitter(self):
        splitter = QSplitter(Qt.Orientation.Vertical)

        self.window._install_app_shell(splitter)

        self.assertIs(self.window.app_shell, self.window.centralWidget())
        self.assertEqual(self.window.app_shell.pane_names(), ["workspace"])
        self.assertEqual(self.window.app_shell.active_pane(), "workspace")

    def test_command_palette_registers_navigation_and_actions(self):
        splitter = QSplitter(Qt.Orientation.Vertical)
        self.window._install_app_shell(splitter)
        self.window.handle_tool_action = lambda _key: None
        self.window.logcat_tool_tabs = types.SimpleNamespace(
            count=lambda: 0,
            tabText=lambda _idx: "",
            setCurrentIndex=lambda _idx: None,
        )

        self.window._setup_command_palette()

        self.assertIsNotNone(self.window.command_palette)
        self.assertGreaterEqual(len(self.window.command_palette.providers()), 2)

        self.window.command_palette._query_edit.setText("screenshot")
        titles = [entry.title for entry in self.window.command_palette.visible_entries()]
        self.assertIn("Take Screenshot", titles)

    def test_theme_sync_updates_shell_and_palette(self):
        splitter = QSplitter(Qt.Orientation.Vertical)
        self.window._install_app_shell(splitter)
        self.window._setup_command_palette()

        self.window._sync_shell_theme("dark")

        self.assertEqual(self.window.app_shell._theme, "dark")
        self.assertEqual(self.window.command_palette._theme, "dark")

    def test_focus_tools_tab_by_label_returns_false_when_missing(self):
        tab_widget = QWidget()
        tab_widget.count = lambda: 0
        tab_widget.tabText = lambda _idx: ""
        tab_widget.setCurrentIndex = lambda _idx: None
        self.window.logcat_tool_tabs = tab_widget

        self.assertFalse(self.window._focus_tools_tab_by_label("Apps"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
