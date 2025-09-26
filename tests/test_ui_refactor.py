import importlib
import os
import sys
import tempfile
import unittest
from contextlib import contextmanager


@contextmanager
def temporary_home(reload_modules):
    with tempfile.TemporaryDirectory() as tmp_home:
        original_home = os.environ.get('HOME')
        try:
            os.environ['HOME'] = tmp_home
            for module_name in reload_modules:
                sys.modules.pop(module_name, None)
            yield
        finally:
            if original_home is not None:
                os.environ['HOME'] = original_home
            else:
                os.environ.pop('HOME', None)


class TestUIRefactor(unittest.TestCase):
    def test_clickable_screenshot_label_module_exports_class(self):
        module = importlib.import_module('ui.screenshot_widget')
        label_cls = getattr(module, 'ClickableScreenshotLabel', None)
        self.assertIsNotNone(label_cls)
        self.assertEqual(label_cls.__module__, 'ui.screenshot_widget')

    def test_ui_inspector_dialog_module_exports_class(self):
        module = importlib.import_module('ui.ui_inspector_dialog')
        dialog_cls = getattr(module, 'UIInspectorDialog', None)
        self.assertIsNotNone(dialog_cls)
        self.assertEqual(dialog_cls.__module__, 'ui.ui_inspector_dialog')

    def test_lazy_blacktea_console_handler_reuses_logging_manager(self):
        modules_to_reload = ['lazy_blacktea_pyqt', 'utils.common', 'ui.logging_manager']
        with temporary_home(modules_to_reload):
            main_module = importlib.import_module('lazy_blacktea_pyqt')
            logging_module = importlib.import_module('ui.logging_manager')
            self.assertTrue(hasattr(main_module, 'ConsoleHandler'))
            self.assertIs(main_module.ConsoleHandler, logging_module.ConsoleHandler)

    def test_device_list_controller_module_exports_class(self):
        modules_to_reload = ['ui.device_list_controller', 'lazy_blacktea_pyqt', 'utils.common']
        with temporary_home(modules_to_reload):
            module = importlib.import_module('ui.device_list_controller')
            controller_cls = getattr(module, 'DeviceListController', None)
            self.assertIsNotNone(controller_cls)
            self.assertEqual(controller_cls.__module__, 'ui.device_list_controller')

            main_module = importlib.import_module('lazy_blacktea_pyqt')
            self.assertTrue(hasattr(main_module, 'DeviceListController'))
            self.assertIs(main_module.DeviceListController, controller_cls)

    def test_tools_panel_controller_module_exports_class(self):
        modules_to_reload = ['ui.tools_panel_controller', 'lazy_blacktea_pyqt', 'utils.common']
        with temporary_home(modules_to_reload):
            module = importlib.import_module('ui.tools_panel_controller')
            controller_cls = getattr(module, 'ToolsPanelController', None)
            self.assertIsNotNone(controller_cls)
            self.assertEqual(controller_cls.__module__, 'ui.tools_panel_controller')

            main_module = importlib.import_module('lazy_blacktea_pyqt')
            self.assertTrue(hasattr(main_module, 'ToolsPanelController'))
            self.assertIs(main_module.ToolsPanelController, controller_cls)


if __name__ == '__main__':
    unittest.main()
