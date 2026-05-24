import os
import sys
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt6.QtCore import Qt  # noqa: E402
from PyQt6.QtWidgets import QApplication, QLabel, QMainWindow, QSplitter  # noqa: E402


_APP = QApplication.instance() or QApplication([])


class MainWindowPhase3IntegrationTests(unittest.TestCase):
    def setUp(self):
        from ui.main_window import WindowMain

        self.window = WindowMain.__new__(WindowMain)
        QMainWindow.__init__(self.window)
        self.addCleanup(self.window.deleteLater)
        self.window.app_shell = None
        self.window.command_palette = None

    def test_shell_installs_without_workspace_pane(self):
        host = QSplitter(Qt.Orientation.Vertical)

        shell = self.window._install_app_shell(host)

        self.assertIs(self.window.app_shell, shell)
        self.assertEqual(shell.pane_names(), [])
        self.assertIs(host.widget(0), shell)

    def test_register_shell_panes_uses_phase3_names(self):
        host = QSplitter(Qt.Orientation.Vertical)
        self.window._install_app_shell(host)
        panes = {
            "devices": QLabel("Devices"),
            "tools": QLabel("Tools"),
            "logcat": QLabel("Logcat"),
            "files": QLabel("Files"),
            "apps": QLabel("Apps"),
            "tasks": QLabel("Tasks"),
        }

        self.window._register_app_shell_panes(**panes)

        self.assertEqual(
            self.window.app_shell.pane_names(),
            ["devices", "tools", "logcat", "files", "apps", "tasks"],
        )

    def test_focus_tools_page_uses_tools_workspace_before_legacy_tabs(self):
        class _Workspace:
            def __init__(self):
                self.labels = []

            def set_active_page_by_label(self, label):
                self.labels.append(label)
                return True

        host = QSplitter(Qt.Orientation.Vertical)
        self.window._install_app_shell(host)
        self.window.app_shell.add_pane("tools", "Tools", QLabel("Tools"))
        self.window.tools_workspace = _Workspace()

        self.assertTrue(self.window._focus_tools_tab_by_label("Shell Commands"))
        self.assertEqual(self.window.app_shell.active_pane(), "tools")
        self.assertEqual(self.window.tools_workspace.labels, ["Shell Commands"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
