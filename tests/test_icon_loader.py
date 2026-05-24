"""Tests for ui.components.icon.

Validates that the SVG icon set ships with the expected entries, that the
loader resolves token names to colors, and that missing icons fail soft.
"""

from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Headless-friendly: ensure QApplication exists for any QPixmap creation.
from PyQt6.QtWidgets import QApplication  # noqa: E402

_APP = QApplication.instance() or QApplication([])


class TestIconLoader(unittest.TestCase):
    def setUp(self):
        from ui.components import icon

        icon.clear_cache()
        self.icon = icon

    def test_starter_icon_set_is_bundled(self):
        bundled = set(self.icon.available())
        # Sample of icons promised by the Phase 1 plan.
        expected_subset = {
            "search",
            "refresh-cw",
            "settings",
            "x",
            "check",
            "chevron-down",
            "chevron-right",
            "triangle-alert",
            "circle-check",
            "smartphone",
        }
        missing = expected_subset - bundled
        self.assertFalse(missing, msg=f"missing icons: {missing}")

    def test_load_icon_returns_non_null_for_known_name(self):
        icon = self.icon.load_icon("search", color="fg_secondary", size=16)
        self.assertFalse(icon.isNull())

    def test_load_pixmap_uses_token_color(self):
        pix_a = self.icon.load_pixmap("search", color="fg_primary", size=24)
        pix_b = self.icon.load_pixmap("search", color="accent_danger", size=24)
        self.assertFalse(pix_a.isNull())
        self.assertFalse(pix_b.isNull())
        # Different colors must produce visually distinct images. Compare
        # the rasterised bytes directly because individual stroke pixels
        # may overlap in either output.
        ba_a = pix_a.toImage().bits().asstring(pix_a.toImage().sizeInBytes())
        ba_b = pix_b.toImage().bits().asstring(pix_b.toImage().sizeInBytes())
        self.assertNotEqual(ba_a, ba_b)

    def test_load_pixmap_accepts_literal_color(self):
        pix = self.icon.load_pixmap("check", color="#123456", size=16)
        self.assertFalse(pix.isNull())

    def test_unknown_icon_returns_null_icon(self):
        icon = self.icon.load_icon("definitely-not-real")
        self.assertTrue(icon.isNull())


if __name__ == "__main__":
    unittest.main(verbosity=2)
