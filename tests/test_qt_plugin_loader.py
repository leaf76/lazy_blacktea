import os
import sys
import tempfile
import unittest
from pathlib import Path


class QtPluginLoaderTests(unittest.TestCase):
    def setUp(self):
        self._original_env = {
            key: os.environ.get(key)
            for key in ('QT_PLUGIN_PATH', 'QT_QPA_PLATFORM_PLUGIN_PATH')
        }
        for key in ('QT_PLUGIN_PATH', 'QT_QPA_PLATFORM_PLUGIN_PATH'):
            os.environ.pop(key, None)

        self._original_meipass = getattr(sys, '_MEIPASS', None)

    def tearDown(self):
        for key, value in self._original_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

        if self._original_meipass is None and hasattr(sys, '_MEIPASS'):
            delattr(sys, '_MEIPASS')
        elif self._original_meipass is not None:
            sys._MEIPASS = self._original_meipass

    def test_configures_environment_from_frozen_bundle(self):
        from utils import qt_plugin_loader

        with tempfile.TemporaryDirectory() as tmp_dir:
            base_path = Path(tmp_dir)
            plugin_dir = base_path / '_internal' / 'PyQt6' / 'Qt6' / 'plugins'
            platforms_dir = plugin_dir / 'platforms'
            platforms_dir.mkdir(parents=True)

            sys._MEIPASS = str(base_path)

            qt_plugin_loader.configure_qt_plugin_path()

            self.assertEqual(os.environ.get('QT_PLUGIN_PATH'), str(plugin_dir))
            self.assertEqual(
                os.environ.get('QT_QPA_PLATFORM_PLUGIN_PATH'),
                str(platforms_dir),
            )

    def test_no_changes_when_plugins_missing(self):
        from utils import qt_plugin_loader

        sys._MEIPASS = '/nonexistent/path'
        qt_plugin_loader.configure_qt_plugin_path()

        self.assertIsNone(os.environ.get('QT_PLUGIN_PATH'))
        self.assertIsNone(os.environ.get('QT_QPA_PLATFORM_PLUGIN_PATH'))

    def test_existing_environment_values_are_prefixed(self):
        from utils import qt_plugin_loader

        with tempfile.TemporaryDirectory() as tmp_dir:
            base_path = Path(tmp_dir)
            plugin_dir = base_path / '_internal' / 'PyQt6' / 'Qt6' / 'plugins'
            platforms_dir = plugin_dir / 'platforms'
            platforms_dir.mkdir(parents=True)

            os.environ['QT_PLUGIN_PATH'] = '/some/other/path'
            os.environ['QT_QPA_PLATFORM_PLUGIN_PATH'] = '/another/platform/path'
            sys._MEIPASS = str(base_path)

            qt_plugin_loader.configure_qt_plugin_path()

            self.assertEqual(
                os.environ['QT_PLUGIN_PATH'].split(os.pathsep)[0],
                str(plugin_dir),
            )
            self.assertIn('/some/other/path', os.environ['QT_PLUGIN_PATH'].split(os.pathsep))
            self.assertEqual(
                os.environ['QT_QPA_PLATFORM_PLUGIN_PATH'].split(os.pathsep)[0],
                str(platforms_dir),
            )
            self.assertIn(
                '/another/platform/path',
                os.environ['QT_QPA_PLATFORM_PLUGIN_PATH'].split(os.pathsep),
            )


if __name__ == '__main__':
    unittest.main()
