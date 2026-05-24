"""Tests for utils.font_loader.

Phase 1 introduces a font fallback contract — bundled fonts may or may not be
present, but the loader must always pick a workable family and apply it to
the QApplication.
"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt6.QtWidgets import QApplication  # noqa: E402

_APP = QApplication.instance() or QApplication([])


class TestFontLoader(unittest.TestCase):
    def setUp(self):
        from utils import font_loader

        font_loader.reset_for_testing()
        self.font_loader = font_loader

    def test_register_with_missing_directory_returns_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            registered = self.font_loader.register_bundled_fonts(
                Path(tmp) / "nonexistent"
            )
        self.assertEqual(registered, [])

    def test_resolve_falls_back_to_system_when_unbundled(self):
        ui_family = self.font_loader.resolve_ui_family()
        # When no bundled font matches we may get None; that's acceptable.
        # The contract is that the function does not raise.
        self.assertTrue(ui_family is None or isinstance(ui_family, str))

    def test_configure_application_fonts_returns_resolved_dict(self):
        info = self.font_loader.configure_application_fonts(_APP)
        self.assertIn("ui_family", info)
        self.assertIn("mono_family", info)
        self.assertIn("registered_families", info)
        self.assertIsInstance(info["ui_family"], str)
        self.assertIsInstance(info["mono_family"], str)
        self.assertIsInstance(info["registered_families"], list)

    def test_configure_application_fonts_is_idempotent(self):
        first = self.font_loader.configure_application_fonts(_APP)
        second = self.font_loader.configure_application_fonts(_APP)
        self.assertEqual(first, second)

    def test_configure_handles_object_without_setfont(self):
        class Dummy:
            pass

        info = self.font_loader.configure_application_fonts(Dummy())
        self.assertIn("ui_family", info)


if __name__ == "__main__":
    unittest.main(verbosity=2)
