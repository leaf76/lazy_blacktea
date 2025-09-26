import importlib
import os
import sys
import tempfile
import unittest


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
        with tempfile.TemporaryDirectory() as tmp_home:
            original_home = os.environ.get('HOME')
            try:
                os.environ['HOME'] = tmp_home
                if 'lazy_blacktea_pyqt' in sys.modules:
                    del sys.modules['lazy_blacktea_pyqt']
                if 'utils.common' in sys.modules:
                    del sys.modules['utils.common']
                main_module = importlib.import_module('lazy_blacktea_pyqt')
                logging_module = importlib.import_module('ui.logging_manager')
                self.assertTrue(hasattr(main_module, 'ConsoleHandler'))
                self.assertIs(main_module.ConsoleHandler, logging_module.ConsoleHandler)
            finally:
                if original_home is not None:
                    os.environ['HOME'] = original_home
                else:
                    os.environ.pop('HOME', None)


if __name__ == '__main__':
    unittest.main()
