import os
import sys
import unittest

from PyQt6.QtWidgets import (
    QApplication,
    QLineEdit,
    QMainWindow,
    QScrollArea,
    QTabWidget,
    QSizePolicy,
)

# Ensure project root is on the import path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ui.tools_panel_controller import ToolsPanelController


class DummyDeviceFileController:
    def register_widgets(self, **kwargs):
        self.registered_widgets = kwargs


class DummyWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.file_gen_output_path_edit = QLineEdit()
        self.device_file_controller = DummyDeviceFileController()

    # Methods used by button wiring
    def navigate_device_files_up(self):
        self.navigate_up_called = True

    def refresh_device_file_browser(self):
        self.refresh_called = True

    def navigate_device_files_to_path(self):
        self.navigate_to_path_called = True

    def on_device_file_item_double_clicked(self, item, column):
        self.double_clicked = (item, column)

    def on_device_file_context_menu(self, pos):
        self.context_menu_pos = pos

    def browse_file_generation_output_path(self):
        self.browse_called = True

    def download_selected_device_files(self):
        self.download_called = True


class DeviceFilesLayoutTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.window = DummyWindow()
        self.controller = ToolsPanelController(self.window)
        self.tab_widget = QTabWidget()

    def test_device_files_tab_is_scrollable(self):
        original_count = self.tab_widget.count()
        self.controller._create_device_file_browser_tab(self.tab_widget)
        self.assertEqual(self.tab_widget.count(), original_count + 1)

        tab_widget = self.tab_widget.widget(original_count)
        self.assertIsInstance(tab_widget, QScrollArea)
        self.assertTrue(tab_widget.widgetResizable(), 'Device Files tab should allow scrolling to avoid cramped layout')
        self.assertIsNotNone(tab_widget.widget())

    def test_device_file_tree_expands_with_layout(self):
        self.controller._create_device_file_browser_tab(self.tab_widget)
        tree = self.window.device_file_tree
        policy = tree.sizePolicy().verticalPolicy()
        self.assertEqual(policy, QSizePolicy.Policy.Expanding)
        self.assertGreater(tree.minimumHeight(), 200)

        controller = self.window.device_file_controller
        self.assertIn('tree', controller.registered_widgets)


if __name__ == '__main__':
    unittest.main()
