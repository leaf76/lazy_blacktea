import os
import sys
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt6.QtWidgets import QApplication, QLabel  # noqa: E402


_APP = QApplication.instance() or QApplication([])


class AppShellTests(unittest.TestCase):
    def setUp(self):
        from ui.shell import AppShell

        self.shell = AppShell()
        self.addCleanup(self.shell.deleteLater)

    def test_add_pane_sets_initial_workspace(self):
        self.shell.add_pane("workspace", "Workspace", QLabel("Workspace"))

        self.assertEqual(self.shell.pane_names(), ["workspace"])
        self.assertEqual(self.shell.active_pane(), "workspace")

    def test_switching_panes_emits_signal(self):
        seen = []
        self.shell.pane_changed.connect(seen.append)
        self.shell.add_pane("workspace", "Workspace", QLabel("Workspace"))
        self.shell.add_pane("tasks", "Tasks", QLabel("Tasks"))

        changed = self.shell.set_active_pane("tasks")

        self.assertTrue(changed)
        self.assertEqual(self.shell.active_pane(), "tasks")
        self.assertIn("tasks", seen)

    def test_sidebar_can_collapse_and_expand(self):
        self.shell.add_pane("workspace", "Workspace", QLabel("Workspace"))

        self.shell.set_sidebar_collapsed(True)
        self.assertFalse(self.shell.sidebar_expanded())

        self.shell.set_sidebar_collapsed(False)
        self.assertTrue(self.shell.sidebar_expanded())

    def test_status_bar_chips_are_available_from_shell(self):
        from ui.shell import StatusChipIntent

        status_bar = self.shell.status_bar()
        status_bar.add_chip("devices", "0 devices", intent=StatusChipIntent.NEUTRAL)

        self.assertTrue(status_bar.has_chip("devices"))
        self.assertIn("devices", status_bar.chip_names())

        self.assertTrue(status_bar.update_chip("devices", "1 device"))
        self.assertTrue(status_bar.remove_chip("devices"))
        self.assertFalse(status_bar.has_chip("devices"))

    def test_status_bar_chip_callback_can_be_updated(self):
        status_bar = self.shell.status_bar()
        calls = []
        status_bar.add_chip("version", "v1", on_click=lambda: calls.append("old"))

        self.assertTrue(
            status_bar.update_chip("version", "v2", on_click=lambda: calls.append("new"))
        )

        status_bar._on_chip_clicked("version")
        self.assertEqual(calls, ["new"])

    def test_theme_switch_restores_valid_stylesheet(self):
        self.shell.add_pane("workspace", "Workspace", QLabel("Workspace"))

        self.shell.set_theme("dark")
        dark_style = self.shell.styleSheet()
        self.shell.set_theme("light")
        light_style = self.shell.styleSheet()

        self.assertIn("#appShell", dark_style)
        self.assertIn("#appShell", light_style)
        self.assertNotEqual(dark_style, light_style)


if __name__ == "__main__":
    unittest.main(verbosity=2)
