#!/usr/bin/env python3
"""Tests for icon resolution helper to support Linux packaging."""

import os
import sys
import tempfile
import unittest
from pathlib import Path

# Ensure project root is in sys.path for direct execution
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


class IconResolverTestCase(unittest.TestCase):
    """Validate icon lookup for standard and bundled environments."""

    def setUp(self):
        self.assets_icon = PROJECT_ROOT / 'assets' / 'icons' / 'icon_128x128.png'
        if not self.assets_icon.exists():
            self.skipTest('Project icon asset missing')

    def test_default_icon_path_is_discovered(self):
        """The resolver should locate the PNG icon from the source tree."""
        from utils.icon_resolver import resolve_icon_path

        icon_path = resolve_icon_path()

        self.assertIsNotNone(icon_path, 'Expected a resolved icon path')
        self.assertTrue(icon_path.exists(), 'Resolved icon path must exist')
        self.assertEqual(icon_path.name, 'icon_128x128.png')
        self.assertEqual(icon_path.resolve(), self.assets_icon.resolve())

    def test_meipass_bundle_preferred_over_source_tree(self):
        """When running in a PyInstaller bundle, prefer the bundled icon."""
        from utils.icon_resolver import resolve_icon_path

        original_meipass = getattr(sys, '_MEIPASS', None)
        with tempfile.TemporaryDirectory() as temp_dir:
            meipass_root = Path(temp_dir)
            bundle_icon_dir = meipass_root / 'assets' / 'icons'
            bundle_icon_dir.mkdir(parents=True, exist_ok=True)

            bundle_icon = bundle_icon_dir / 'icon_128x128.png'
            bundle_icon.write_bytes(self.assets_icon.read_bytes())

            sys._MEIPASS = str(meipass_root)
            try:
                icon_path = resolve_icon_path()
                self.assertIsNotNone(icon_path, 'Expected a bundled icon when _MEIPASS is set')
                self.assertEqual(icon_path.resolve(), bundle_icon.resolve())
            finally:
                if original_meipass is None:
                    delattr(sys, '_MEIPASS')
                else:
                    sys._MEIPASS = original_meipass


if __name__ == '__main__':
    unittest.main()
