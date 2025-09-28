import os
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in os.sys.path:
    os.sys.path.insert(0, str(PROJECT_ROOT))

from build_scripts import spec_utils


class PrepareSpecContentTests(unittest.TestCase):
    def test_rewrites_native_libs_path_to_absolute(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            original = "('build/native-libs', 'native'),"

            rewritten = spec_utils.prepare_spec_content(original, tmp_dir)

            expected_prefix = f"('{os.path.join(tmp_dir, 'build', 'native-libs')}'"
            self.assertIn(expected_prefix, rewritten)
            self.assertNotIn("('build/native-libs'", rewritten)


if __name__ == '__main__':
    unittest.main()
