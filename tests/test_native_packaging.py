import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


class NativeBuildSupportTests(unittest.TestCase):
    def test_prepare_native_library_copies_release_artifact(self) -> None:
        from build_scripts import native_support

        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            native_dir = project_root / 'native_lbb'
            release_dir = native_dir / 'target' / 'release'
            release_dir.mkdir(parents=True)

            lib_name = native_support.library_filename()
            source_path = release_dir / lib_name
            source_path.write_bytes(b'native-bin')

            build_dir = project_root / 'build' / 'native-libs'

            with mock.patch('subprocess.run') as mocked_run:
                mocked_run.return_value = mock.Mock(returncode=0, stdout='', stderr='')
                result = native_support.prepare_native_library(project_root, build_dir)

            self.assertTrue(result.exists())
            self.assertEqual(result.read_bytes(), b'native-bin')
            mocked_run.assert_called()
            self.assertTrue((build_dir / lib_name).exists())


class NativeBridgePathResolutionTests(unittest.TestCase):
    def test_candidate_paths_include_packaged_native_dir(self) -> None:
        if not sys.platform.startswith(('darwin', 'linux')):
            self.skipTest('Packaged path resolution only validated on macOS/Linux')

        from utils import native_bridge

        lib_name = native_bridge._default_library_name()

        previous_meipass = getattr(sys, '_MEIPASS', None)
        try:
            with tempfile.TemporaryDirectory() as tmp:
                native_dir = Path(tmp) / 'native'
                native_dir.mkdir()
                candidate_path = native_dir / lib_name
                candidate_path.write_bytes(b'placeholder')

                sys._MEIPASS = tmp

                paths = list(native_bridge._candidate_library_paths())

            self.assertIn(candidate_path, paths)
        finally:
            if previous_meipass is not None:
                sys._MEIPASS = previous_meipass
            elif hasattr(sys, '_MEIPASS'):
                del sys._MEIPASS


if __name__ == '__main__':
    unittest.main()
