import os
import sys
import unittest
from unittest.mock import patch

from PyQt6.QtWidgets import QApplication, QMainWindow
from PyQt6.QtCore import QRect

# Ensure project root is on the import path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.config_manager import UISettings
from ui.main_window import WindowMain


class FakeScreen:
    """Simple screen stub returning a predefined available geometry."""

    def __init__(self, rect: QRect):
        self._rect = rect

    def availableGeometry(self) -> QRect:
        return QRect(self._rect)


class WindowGeometryTest(unittest.TestCase):
    """Verify that window geometry respects configuration and screen bounds."""

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.window = WindowMain.__new__(WindowMain)
        QMainWindow.__init__(self.window)
        self.addCleanup(self.window.deleteLater)

    def test_applies_configured_window_geometry(self):
        """The window should prefer the persisted geometry when it fits the screen."""
        ui_settings = UISettings(window_width=1000, window_height=700, window_x=50, window_y=60)
        screen_rect = QRect(0, 0, 1920, 1080)
        fake_screen = FakeScreen(screen_rect)

        with patch('ui.main_window.QGuiApplication.primaryScreen', return_value=fake_screen):
            self.window._apply_window_geometry(ui_settings)

        geometry = self.window.geometry()
        self.assertEqual(geometry.width(), 1000)
        self.assertEqual(geometry.height(), 700)
        self.assertEqual(geometry.x(), 50)
        self.assertEqual(geometry.y(), 60)

    def test_clamps_geometry_to_available_screen(self):
        """Oversized or off-screen geometry should be clamped to the available bounds."""
        ui_settings = UISettings(window_width=3000, window_height=2000, window_x=5000, window_y=4000)
        screen_rect = QRect(10, 20, 1200, 800)
        fake_screen = FakeScreen(screen_rect)

        with patch('ui.main_window.QGuiApplication.primaryScreen', return_value=fake_screen):
            self.window._apply_window_geometry(ui_settings)

        geometry = self.window.geometry()
        self.assertEqual(geometry.width(), 1200)
        self.assertEqual(geometry.height(), 800)
        self.assertEqual(geometry.x(), 10)
        self.assertEqual(geometry.y(), 20)


if __name__ == '__main__':
    unittest.main()
