"""UI Inspector 非同步載入行為測試。"""

import os
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from PyQt6.QtGui import QImage
from PyQt6.QtWidgets import QApplication


class UIInspectorAsyncTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._app = QApplication.instance() or QApplication([])

    def _process_events_until(self, condition, timeout=2.0):
        deadline = time.time() + timeout
        while time.time() < deadline:
            self._app.processEvents()
            if condition():
                return True
            time.sleep(0.01)
        return False

    def test_refresh_executes_in_background_thread(self):
        captured_threads: list[int] = []
        main_thread_id = threading.get_ident()

        temp_dirs: list[str] = []

        def fake_create_temp_files():
            temp_dir = tempfile.mkdtemp()
            temp_dirs.append(temp_dir)
            screenshot_path = os.path.join(temp_dir, 'screen.png')
            xml_path = os.path.join(temp_dir, 'hierarchy.xml')
            return temp_dir, screenshot_path, xml_path

        def fake_capture(serial, path):
            captured_threads.append(threading.get_ident())
            image = QImage(1, 1, QImage.Format.Format_RGB32)
            image.fill(0xFFFFFFFF)
            image.save(path)
            return True

        def fake_dump(serial, path):
            captured_threads.append(threading.get_ident())
            Path(path).write_text('<hierarchy />')
            return True

        def fake_parse(path):
            captured_threads.append(threading.get_ident())
            return [{
                'class': 'android.view.View',
                'bounds': (0, 0, 100, 200),
                'clickable': True,
                'text': 'Test',
                'resource_id': 'id/test',
                'content_desc': 'desc',
            }]

        module_path = 'ui.ui_inspector_dialog'

        with patch(f'{module_path}.create_temp_files', side_effect=fake_create_temp_files), \
             patch(f'{module_path}.capture_device_screenshot', side_effect=fake_capture), \
             patch(f'{module_path}.dump_ui_hierarchy', side_effect=fake_dump), \
             patch(f'{module_path}.parse_ui_elements_cached', side_effect=fake_parse):

            from ui.ui_inspector_dialog import UIInspectorDialog

            dialog = UIInspectorDialog(None, 'SERIAL123', 'Pixel Test')

            try:
                finished = self._process_events_until(
                    lambda: getattr(dialog, '_worker_thread', None) is None,
                    timeout=4.0,
                )
                self.assertTrue(finished, 'UI Inspector worker 未在期限內完成')

                self.assertTrue(captured_threads, '預期背景執行緒應該執行耗時作業')
                for thread_id in captured_threads:
                    self.assertNotEqual(thread_id, main_thread_id, '耗時作業不應在主執行緒執行')

                pixmap = dialog.screenshot_label.pixmap()
                self.assertIsNotNone(pixmap)
                self.assertFalse(pixmap.isNull())

            finally:
                dialog.close()
                for path in temp_dirs:
                    if os.path.isdir(path):
                        try:
                            import shutil
                            shutil.rmtree(path)
                        except OSError:
                            pass


if __name__ == '__main__':
    unittest.main()
