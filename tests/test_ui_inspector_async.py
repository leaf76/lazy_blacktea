"""UI Inspector 非同步載入行為測試。"""

import os
import sys
import tempfile
import threading
import time
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QImage
from PyQt6.QtWidgets import QApplication

from utils.ui_inspector_utils import elements_match


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

    @contextmanager
    def _mocked_inspector_dialog(self, *, image_size=(400, 800), elements=None):
        captured_threads: list[int] = []
        temp_dirs: list[str] = []

        if elements is None:
            elements_data = [{
                'class': 'android.view.View',
                'bounds': (0, 0, 100, 200),
                'clickable': True,
                'text': 'Test',
                'resource_id': 'id/test',
                'content_desc': 'desc',
            }]
        else:
            elements_data = [dict(item) for item in elements]

        def fake_create_temp_files():
            temp_dir = tempfile.mkdtemp()
            temp_dirs.append(temp_dir)
            screenshot_path = os.path.join(temp_dir, 'screen.png')
            xml_path = os.path.join(temp_dir, 'hierarchy.xml')
            return temp_dir, screenshot_path, xml_path

        def fake_capture(serial, path):
            captured_threads.append(threading.get_ident())
            width, height = image_size
            image = QImage(width, height, QImage.Format.Format_RGB32)
            image.fill(0xFFFFFFFF)
            image.save(path)
            return True

        def fake_dump(serial, path):
            captured_threads.append(threading.get_ident())
            Path(path).write_text('<hierarchy />')
            return True

        def fake_parse(path):
            captured_threads.append(threading.get_ident())
            return [dict(item) for item in elements_data]

        module_path = 'ui.ui_inspector_dialog'

        with patch(f'{module_path}.create_temp_files', side_effect=fake_create_temp_files), \
             patch(f'{module_path}.capture_device_screenshot', side_effect=fake_capture), \
             patch(f'{module_path}.dump_ui_hierarchy', side_effect=fake_dump), \
             patch(f'{module_path}.parse_ui_elements_cached', side_effect=fake_parse):

            from ui.ui_inspector_dialog import UIInspectorDialog

            dialog = UIInspectorDialog(None, 'SERIAL123', 'Pixel Test')

            try:
                yield dialog, captured_threads
            finally:
                dialog.close()
                for path in temp_dirs:
                    if os.path.isdir(path):
                        try:
                            import shutil
                            shutil.rmtree(path)
                        except OSError:
                            pass

    def _collect_tree_leaf_texts(self, tree_widget):
        root = tree_widget.invisibleRootItem()
        leaves: list[str] = []
        for i in range(root.childCount()):
            class_item = root.child(i)
            if class_item.childCount() == 0:
                leaves.append(class_item.text(0))
            else:
                for j in range(class_item.childCount()):
                    leaves.append(class_item.child(j).text(0))
        return leaves

    def test_refresh_executes_in_background_thread(self):
        main_thread_id = threading.get_ident()

        with self._mocked_inspector_dialog() as (dialog, captured_threads):
            first_progress = self._process_events_until(
                lambda: bool(captured_threads),
                timeout=4.0,
            )
            self.assertTrue(first_progress, '未偵測到背景執行緒的進度訊號')

            done = self._process_events_until(
                lambda: not dialog._worker_start_scheduled
                and getattr(dialog, '_worker_thread', None) is None,
                timeout=4.0,
            )
            self.assertTrue(done, 'UI Inspector worker 未在期限內完成')

            for thread_id in captured_threads:
                self.assertNotEqual(thread_id, main_thread_id, '耗時作業不應在主執行緒執行')

            pixmap = dialog.screenshot_label.pixmap()
            self.assertIsNotNone(pixmap)
            self.assertFalse(pixmap.isNull())

    def test_progress_bar_transitions_from_busy_to_determinate(self):
        with self._mocked_inspector_dialog() as (dialog, _):
            started_busy = self._process_events_until(
                lambda: dialog._progress_is_busy,
                timeout=1.0,
            )
            self.assertTrue(started_busy, '預期進度條在初始化時為忙碌模式')

            became_determinate = self._process_events_until(
                lambda: not dialog._progress_is_busy
                and dialog.progress_bar.value() >= 90,
                timeout=4.0,
            )
            self.assertTrue(became_determinate, '預期進度條應在取得進度後切換為可度量模式')

            self._process_events_until(
                lambda: not dialog._worker_start_scheduled
                and getattr(dialog, '_worker_thread', None) is None,
                timeout=4.0,
            )

    def test_zoom_controls_shrink_and_preserve_element_matching(self):
        with self._mocked_inspector_dialog(image_size=(640, 1280)) as (dialog, _):
            self.assertTrue(
                self._process_events_until(lambda: bool(dialog.ui_elements), timeout=4.0),
                'UI 元素應成功載入'
            )

            initial_pixmap = dialog.screenshot_label.pixmap()
            self.assertIsNotNone(initial_pixmap)
            initial_width = initial_pixmap.width()
            initial_scale = dialog.screenshot_label.scale_factor

            dialog.set_screenshot_zoom(0.5)

            self.assertTrue(
                self._process_events_until(
                    lambda: abs(dialog.screenshot_label.scale_factor - (initial_scale * 0.5)) < 0.05,
                    timeout=1.0,
                ),
                '縮放後應同步更新 scale factor'
            )

            updated_pixmap = dialog.screenshot_label.pixmap()
            self.assertIsNotNone(updated_pixmap)
            self.assertLess(updated_pixmap.width(), initial_width)

            element = dialog.ui_elements[0]
            final_scale = dialog.screenshot_label.scale_factor
            center_x = (element['bounds'][0] + element['bounds'][2]) / 2
            center_y = (element['bounds'][1] + element['bounds'][3]) / 2

            dialog.on_element_clicked(int(center_x), int(center_y))

            self.assertIsNotNone(
                dialog.screenshot_label.selected_element,
                '縮放後應仍可比對到對應的 UI 元件'
            )

            self.assertTrue(
                elements_match(dialog.screenshot_label.selected_element, element),
                '縮放後應仍可比對到對應的 UI 元件'
            )

            alignment = dialog.screenshot_label.alignment()
            self.assertTrue(bool(alignment & Qt.AlignmentFlag.AlignLeft))
            self.assertTrue(bool(alignment & Qt.AlignmentFlag.AlignTop))


    def test_hierarchy_search_filters_tree_items(self):
        elements = [
            {
                'class': 'android.widget.Button',
                'bounds': (0, 0, 100, 100),
                'clickable': True,
                'text': 'Login Button',
                'resource_id': 'com.example:id/login_button',
                'content_desc': '',
            },
            {
                'class': 'android.widget.Button',
                'bounds': (0, 100, 200, 200),
                'clickable': True,
                'text': 'Cancel',
                'resource_id': 'com.example:id/cancel_button',
                'content_desc': '',
            },
            {
                'class': 'android.widget.EditText',
                'bounds': (0, 200, 300, 260),
                'clickable': True,
                'text': '',
                'resource_id': 'com.example:id/username_input',
                'content_desc': '',
            },
        ]

        with self._mocked_inspector_dialog(elements=elements) as (dialog, _):
            self.assertTrue(
                self._process_events_until(
                    lambda: len(dialog.ui_elements) == len(elements),
                    timeout=2.0,
                ),
                'UI 元素應成功載入'
            )

            self.assertEqual(
                len(self._collect_tree_leaf_texts(dialog.hierarchy_tree)),
                len(elements),
            )

            dialog.hierarchy_search.setText('login')
            self.assertTrue(
                self._process_events_until(
                    lambda: self._collect_tree_leaf_texts(dialog.hierarchy_tree) == ['Login Button'],
                    timeout=1.0,
                ),
                '搜尋關鍵字應過濾出單一元素'
            )

            dialog.hierarchy_search.setText('username')
            self.assertTrue(
                self._process_events_until(
                    lambda: self._collect_tree_leaf_texts(dialog.hierarchy_tree) == ['com.example:id/username_input'],
                    timeout=1.0,
                ),
                '搜尋應支援 resource_id 關鍵字'
            )

            dialog.hierarchy_search.setText('nope')
            self.assertTrue(
                self._process_events_until(
                    lambda: dialog.hierarchy_tree.topLevelItemCount() == 1
                    and dialog.hierarchy_tree.topLevelItem(0).childCount() == 0
                    and dialog.hierarchy_tree.topLevelItem(0).text(0) == 'No matching elements',
                    timeout=1.0,
                ),
                '無符合搜尋結果時應顯示提示訊息'
            )

            dialog.hierarchy_search.clear()
            self.assertTrue(
                self._process_events_until(
                    lambda: len(self._collect_tree_leaf_texts(dialog.hierarchy_tree)) == len(elements),
                    timeout=1.0,
                ),
                '清除搜尋應恢復完整清單'
            )



if __name__ == '__main__':
    unittest.main()
