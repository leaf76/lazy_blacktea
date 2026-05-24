import os
import sys
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt6.QtWidgets import QApplication, QLabel  # noqa: E402


_APP = QApplication.instance() or QApplication([])


class ToolsWorkspaceTests(unittest.TestCase):
    def setUp(self):
        from ui.shell import ToolsWorkspace

        self.workspace = ToolsWorkspace()
        self.addCleanup(self.workspace.deleteLater)

    def test_add_page_sets_initial_page(self):
        self.workspace.add_page("overview", "Overview", QLabel("Overview"))

        self.assertEqual(self.workspace.page_names(), ["overview"])
        self.assertEqual(self.workspace.active_page(), "overview")

    def test_page_switch_by_name_and_label(self):
        seen = []
        self.workspace.page_changed.connect(seen.append)
        self.workspace.add_page("overview", "Overview", QLabel("Overview"))
        self.workspace.add_page("shell", "Shell Commands", QLabel("Shell"))

        self.assertTrue(self.workspace.set_active_page_by_label("Shell Commands"))

        self.assertEqual(self.workspace.active_page(), "shell")
        self.assertIn("shell", seen)

    def test_unknown_page_returns_false(self):
        self.workspace.add_page("overview", "Overview", QLabel("Overview"))

        self.assertFalse(self.workspace.set_active_page("missing"))
        self.assertFalse(self.workspace.set_active_page_by_label("Missing"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
