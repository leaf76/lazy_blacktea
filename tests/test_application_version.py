import importlib
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


class ApplicationVersionResolutionTests(unittest.TestCase):
    def setUp(self):
        # Ensure the constants module is imported for shared helper access
        self.constants = importlib.import_module('config.constants')

    def tearDown(self):
        # Reload constants so other tests observe the original app version
        importlib.reload(self.constants)

    def test_read_version_strips_prefixed_v(self):
        target_path = Path(self.constants.__file__).resolve().parent.parent / 'VERSION'

        original_read_text = Path.read_text

        def fake_read_text(self, *args, **kwargs):  # noqa: ANN001
            if self == target_path:
                return 'v1.2.3\n'
            return original_read_text(self, *args, **kwargs)

        with patch('pathlib.Path.read_text', new=fake_read_text), patch('pathlib.Path.exists',
                                                                        new=lambda self: self == target_path):
            version = self.constants._read_version()

        self.assertEqual(version, '1.2.3')

    def test_read_version_falls_back_to_meipass_location(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            version_file = Path(temp_dir) / 'VERSION'
            version_file.write_text('v4.5.6')

            primary_path = Path(self.constants.__file__).resolve().parent.parent / 'VERSION'
            original_read_text = Path.read_text

            def fake_read_text(self, *args, **kwargs):  # noqa: ANN001
                if self == primary_path:
                    raise FileNotFoundError
                return original_read_text(self, *args, **kwargs)

            original_exists = Path.exists

            def fake_exists(self):  # noqa: ANN001
                if self == primary_path:
                    return False
                return original_exists(self)

            original_meipass = getattr(sys, '_MEIPASS', None)
            sys._MEIPASS = temp_dir
            try:
                with patch('pathlib.Path.read_text', new=fake_read_text), patch('pathlib.Path.exists', new=fake_exists):
                    version = self.constants._read_version()
            finally:
                if original_meipass is None and hasattr(sys, '_MEIPASS'):
                    delattr(sys, '_MEIPASS')
                elif original_meipass is not None:
                    sys._MEIPASS = original_meipass

        self.assertEqual(version, '4.5.6')

    def test_environment_variable_overrides_version(self):
        with patch.dict(os.environ, {'LAZY_BLACKTEA_VERSION': 'v7.8.9'}, clear=False), patch(
            'pathlib.Path.exists', return_value=False
        ):
            version = self.constants._read_version()

        self.assertEqual(version, '7.8.9')


if __name__ == '__main__':
    unittest.main()
