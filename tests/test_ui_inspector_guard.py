import os
import unittest
from unittest.mock import patch

from utils.ui_inspector_utils import check_ui_inspector_prerequisites


class UIInspectorPrerequisitesTests(unittest.TestCase):
    def test_missing_display_on_linux_blocks_launch(self):
        with patch('utils.ui_inspector_utils.platform.system', return_value='Linux'):
            with patch('utils.ui_inspector_utils.adb_tools.is_adb_installed', return_value=True):
                with patch.dict('utils.ui_inspector_utils.os.environ', {}, clear=True):
                    ready, message = check_ui_inspector_prerequisites()

        self.assertFalse(ready)
        self.assertIsNotNone(message)
        self.assertIn('DISPLAY', message)

    def test_missing_adb_reports_error(self):
        with patch('utils.ui_inspector_utils.platform.system', return_value='Linux'):
            with patch('utils.ui_inspector_utils.adb_tools.is_adb_installed', return_value=False):
                with patch.dict('utils.ui_inspector_utils.os.environ', {'DISPLAY': ':0'}, clear=True):
                    ready, message = check_ui_inspector_prerequisites()

        self.assertFalse(ready)
        self.assertIsNotNone(message)
        self.assertIn('ADB', message)

    def test_ready_when_dependencies_present(self):
        with patch('utils.ui_inspector_utils.platform.system', return_value='Linux'):
            with patch('utils.ui_inspector_utils.adb_tools.is_adb_installed', return_value=True):
                env = {'DISPLAY': ':0'}
                with patch.dict('utils.ui_inspector_utils.os.environ', env, clear=True):
                    ready, message = check_ui_inspector_prerequisites()

        self.assertTrue(ready)
        self.assertIsNone(message)

    def test_minimal_qt_platform_is_blocked(self):
        with patch('utils.ui_inspector_utils.platform.system', return_value='Linux'):
            with patch('utils.ui_inspector_utils.adb_tools.is_adb_installed', return_value=True):
                env = {'QT_QPA_PLATFORM': 'minimal'}
                with patch.dict('utils.ui_inspector_utils.os.environ', env, clear=True):
                    ready, message = check_ui_inspector_prerequisites()

        self.assertFalse(ready)
        self.assertIsNotNone(message)
        self.assertIn('QT_QPA_PLATFORM=minimal', message)


if __name__ == '__main__':
    unittest.main()
