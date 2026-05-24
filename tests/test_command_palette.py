import os
import sys
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt6.QtWidgets import QApplication  # noqa: E402


_APP = QApplication.instance() or QApplication([])


class _Provider:
    def __init__(self, entries):
        self._entries = entries

    def section_label(self):
        return "Actions"

    def entries(self, query):
        return list(self._entries)


class CommandPaletteTests(unittest.TestCase):
    def setUp(self):
        from ui.shell import CommandPalette

        self.palette = CommandPalette()
        self.addCleanup(self.palette.deleteLater)

    def test_provider_registration_is_stable(self):
        provider = _Provider([])

        self.palette.register_provider(provider)
        self.palette.register_provider(provider)

        self.assertEqual(self.palette.providers(), [provider])
        self.assertTrue(self.palette.unregister_provider(provider))
        self.assertEqual(self.palette.providers(), [])

    def test_query_filters_and_ranks_entries(self):
        from ui.shell import PaletteEntry

        entries = [
            PaletteEntry(title="Take Screenshot", invoke=lambda: None, keywords=("capture",)),
            PaletteEntry(title="Open Logcat", invoke=lambda: None, keywords=("logs",)),
        ]
        self.palette.register_provider(_Provider(entries))

        self.palette._query_edit.setText("screen")
        visible = self.palette.visible_entries()

        self.assertEqual([entry.title for entry in visible], ["Take Screenshot"])

    def test_activate_top_entry_invokes_action(self):
        from ui.shell import PaletteEntry

        calls = []
        self.palette.register_provider(
            _Provider([PaletteEntry(title="Open Workspace", invoke=lambda: calls.append("run"))])
        )
        self.palette._query_edit.setText("workspace")

        self.assertTrue(self.palette.activate_top_entry())
        self.assertEqual(calls, ["run"])

    def test_failed_activation_emits_signal(self):
        from ui.shell import PaletteEntry

        failures = []

        def fail():
            raise RuntimeError("boom")

        self.palette.activation_failed.connect(lambda title, exc: failures.append((title, exc)))
        self.palette.register_provider(_Provider([PaletteEntry(title="Fail Action", invoke=fail)]))
        self.palette._query_edit.setText("fail")

        self.assertTrue(self.palette.activate_top_entry())
        self.assertEqual(failures[0][0], "Fail Action")
        self.assertIsInstance(failures[0][1], RuntimeError)


if __name__ == "__main__":
    unittest.main(verbosity=2)
