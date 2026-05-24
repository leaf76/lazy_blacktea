import os
import sys
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt6.QtWidgets import QApplication, QLabel  # noqa: E402


_APP = QApplication.instance() or QApplication([])


class AppShellPhase3Tests(unittest.TestCase):
    def setUp(self):
        from ui.shell import AppShell

        self.shell = AppShell()
        self.addCleanup(self.shell.deleteLater)

    def _sidebar_texts(self):
        return [
            self.shell._sidebar_list.item(row).text()
            for row in range(self.shell._sidebar_list.count())
        ]

    def test_sidebar_badge_provider_renders_and_refreshes(self):
        badge = {"value": "2"}
        self.shell.add_pane(
            "tasks",
            "Tasks",
            QLabel("Tasks"),
            badge_text_provider=lambda: badge["value"],
        )

        self.assertEqual(self._sidebar_texts(), ["Tasks · 2"])

        badge["value"] = "5"
        self.shell.refresh_badges()

        self.assertEqual(self._sidebar_texts(), ["Tasks · 5"])

    def test_collapsed_sidebar_keeps_short_label_without_badge(self):
        self.shell.add_pane(
            "tasks",
            "Tasks",
            QLabel("Tasks"),
            badge_text_provider=lambda: "9",
        )

        self.shell.set_sidebar_collapsed(True)

        self.assertEqual(self._sidebar_texts(), ["T"])
        self.assertEqual(self.shell._sidebar_list.item(0).toolTip(), "Tasks · 9")

    def test_activate_pane_by_index_matches_shortcut_contract(self):
        self.shell.add_pane("devices", "Devices", QLabel("Devices"))
        self.shell.add_pane("tools", "Tools", QLabel("Tools"))

        self.assertTrue(self.shell.activate_pane_at(1))

        self.assertEqual(self.shell.active_pane(), "tools")


if __name__ == "__main__":
    unittest.main(verbosity=2)
