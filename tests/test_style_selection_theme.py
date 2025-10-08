import os
import sys
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from PyQt6.QtWidgets import QApplication


class SelectionThemeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._app = QApplication.instance() or QApplication([])

    def test_active_text_color_light_theme_default(self):
        from ui.device_table_widget import DeviceTableWidget  # noqa: WPS433
        from utils import adb_models  # noqa: WPS433

        table = DeviceTableWidget()
        devices = [
            adb_models.DeviceInfo('s1', 'usb', 'prod', 'Alpha', True, False, '14', '34', '35', 'fp'),
        ]
        table.update_devices(devices)
        table.set_active_serial('s1')
        self._app.processEvents()

        active_color = table.item(0, 1).foreground().color().name()
        self.assertEqual(active_color, '#0b5394')  # accessible blue for light theme

    def test_active_text_color_dark_theme(self):
        # Switch theme to dark
        from ui.style_manager import ThemeManager  # noqa: WPS433
        from ui.device_table_widget import DeviceTableWidget  # noqa: WPS433
        from utils import adb_models  # noqa: WPS433

        mgr = ThemeManager()
        mgr.set_theme('dark')

        table = DeviceTableWidget()
        devices = [
            adb_models.DeviceInfo('s1', 'usb', 'prod', 'Alpha', True, False, '14', '34', '35', 'fp'),
        ]
        table.update_devices(devices)
        table.set_active_serial('s1')
        self._app.processEvents()

        active_color = table.item(0, 1).foreground().color().name()
        self.assertEqual(active_color, '#b8dcff')  # brighter text for dark theme

        # Restore theme to light for isolation
        mgr.set_theme('light')


if __name__ == '__main__':
    unittest.main()

