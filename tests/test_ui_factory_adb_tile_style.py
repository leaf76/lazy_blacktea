import os
import sys
import unittest

from PyQt6.QtCore import Qt, QSize
from PyQt6.QtWidgets import (
    QApplication,
    QGroupBox,
    QTabWidget,
    QSizePolicy,
    QToolButton,
    QWidget,
)

# Ensure project root is on the path for direct test execution
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from ui.ui_factory import UIFactory  # noqa: E402


class UIFactoryAdbTileStyleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.factory = UIFactory()
        self.tab_widget = QTabWidget()
        self.factory.create_adb_tools_tab(self.tab_widget)
        self.adb_tab = self.tab_widget.widget(self.tab_widget.count() - 1)

    def _find_group(self, title: str) -> QGroupBox:
        layout = self.adb_tab.layout()
        for index in range(layout.count()):
            widget = layout.itemAt(index).widget()
            if isinstance(widget, QGroupBox) and widget.title() == title:
                return widget
        raise AssertionError(f'Group "{title}" not found in ADB Tools tab')

    def _collect_tile_buttons(self, group: QGroupBox) -> list[QToolButton]:
        buttons: list[QToolButton] = []
        group_layout = group.layout()
        for index in range(group_layout.count()):
            tile_widget = group_layout.itemAt(index).widget()
            if not isinstance(tile_widget, QWidget):
                continue
            inner_layout = tile_widget.layout()
            if inner_layout is None or inner_layout.count() == 0:
                continue
            button = inner_layout.itemAt(0).widget()
            if isinstance(button, QToolButton):
                buttons.append(button)
        return buttons

    def _assert_tile_button_style(self, button: QToolButton) -> None:
        self.assertIsInstance(button, QToolButton)
        self.assertEqual(
            button.toolButtonStyle(),
            Qt.ToolButtonStyle.ToolButtonTextUnderIcon,
            'ADB tool button should display text under icon',
        )
        self.assertEqual(
            button.iconSize(),
            QSize(48, 48),
            'ADB tool button should use 48px icons for visual consistency',
        )
        self.assertEqual(
            button.sizePolicy().horizontalPolicy(),
            QSizePolicy.Policy.Expanding,
            'ADB tool button should expand to fill available space',
        )

    def test_device_control_buttons_use_tile_style(self):
        group = self._find_group("📱 Device Control")
        buttons = self._collect_tile_buttons(group)
        self.assertEqual(
            {button.objectName() for button in buttons},
            {"reboot_device", "reboot_recovery", "reboot_bootloader", "restart_adb"},
            'Device control group should expose known actions via tile buttons',
        )
        for button in buttons:
            self._assert_tile_button_style(button)

    def test_connectivity_buttons_use_tile_style(self):
        group = self._find_group("📶 Connectivity")
        buttons = self._collect_tile_buttons(group)
        self.assertEqual(
            {button.objectName() for button in buttons},
            {"enable_wifi", "disable_wifi", "enable_bluetooth", "disable_bluetooth"},
            'Connectivity group should expose WiFi/Bluetooth actions via tile buttons',
        )
        for button in buttons:
            self._assert_tile_button_style(button)

    def test_system_tool_buttons_use_tile_style(self):
        group = self._find_group("🔧 System Tools")
        buttons = self._collect_tile_buttons(group)
        self.assertEqual(
            {button.objectName() for button in buttons},
            {
                "device_info",
                "go_home",
                "take_screenshot",
                "start_recording",
                "stop_recording",
                "launch_ui_inspector",
            },
            'System tools group should expose system actions via tile buttons',
        )
        for button in buttons:
            self._assert_tile_button_style(button)

    def test_installation_buttons_use_tile_style(self):
        group = self._find_group("📦 Installation")
        buttons = self._collect_tile_buttons(group)
        self.assertEqual(
            {button.objectName() for button in buttons},
            {"install_apk", "launch_scrcpy"},
            'Installation group should expose install-related actions via tile buttons',
        )
        for button in buttons:
            self._assert_tile_button_style(button)


if __name__ == '__main__':
    unittest.main()
