import os
import sys
import types
import unittest
from unittest.mock import patch

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from PyQt6.QtCore import QTimer
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication, QWidget

from utils.task_dispatcher import TaskContext, TaskHandle


class _FakeSelectionManager:
    def __init__(self, serial: str) -> None:
        self._serial = serial

    def get_active_serial(self) -> str:
        return self._serial


class _ThreadDispatcher:
    """Execute submitted callables on a plain Python thread."""

    def submit(self, fn, *args, context: TaskContext | None = None, **kwargs) -> TaskHandle:
        ctx = context or TaskContext(name='test')
        handle = TaskHandle(ctx)

        def runner() -> None:
            try:
                result = fn(*args, **kwargs)
            except Exception as exc:  # pragma: no cover - defensive in test shim
                handle.failed.emit(exc)
            else:
                handle.completed.emit(result)
            finally:
                handle.finished.emit()

        QTimer.singleShot(0, runner)
        return handle


class AppListTabDeferredDetailsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        from ui.app_list_tab import AppListTab

        class _FakeWindow(QWidget):
            def __init__(self) -> None:
                super().__init__()

        self.window = _FakeWindow()
        self.window._task_dispatcher = _ThreadDispatcher()
        self.window._background_task_handles = []
        self.window.device_selection_manager = _FakeSelectionManager('serial-1')
        self.window.device_dict = {'serial-1': types.SimpleNamespace(device_model='Pixel X')}
        self.window.show_warning = lambda *args, **kwargs: None
        self.window.show_error = lambda *args, **kwargs: None
        self.window.show_info = lambda *args, **kwargs: None
        self.window.device_table = None

        self.tab = AppListTab(self.window)

    def tearDown(self) -> None:
        if hasattr(self.tab, '_active_watch') and self.tab._active_watch is not None:
            self.tab._active_watch.stop()
        self.tab.deleteLater()
        QTest.qWait(0)

    @patch('utils.adb_tools.list_installed_packages', return_value=[{'package': 'com.demo.app', 'apk_path': '/data/demo.apk', 'is_system': False}])
    @patch('utils.adb_tools.get_app_version_name')
    def test_refresh_populates_package_without_fetching_versions(self, mocked_get_version, mocked_list) -> None:
        self.tab.refresh_apps()
        QTest.qWait(50)

        self.assertEqual(mocked_get_version.call_count, 0)
        self.assertEqual(self.tab.tree.topLevelItemCount(), 1)
        item = self.tab.tree.topLevelItem(0)
        self.assertEqual(item.text(0), 'com.demo.app')
        self.assertEqual(item.text(1), 'User')
        self.assertEqual(item.text(2), '/data/demo.apk')

    @patch('PyQt6.QtWidgets.QMessageBox.information')
    @patch('utils.adb_tools.get_app_version_name', return_value='2.3.4')
    @patch('utils.adb_tools.list_installed_packages', return_value=[{'package': 'com.demo.app', 'apk_path': '/data/demo.apk', 'is_system': False}])
    def test_double_click_fetches_details_and_shows_dialog(self, mocked_list, mocked_get_version, mocked_info) -> None:
        self.tab.refresh_apps()
        QTest.qWait(50)

        item = self.tab.tree.topLevelItem(0)
        self.tab.tree.itemDoubleClicked.emit(item, 0)
        QTest.qWait(200)

        mocked_get_version.assert_called_once_with('serial-1', 'com.demo.app')
        # Table values remain unchanged
        self.assertEqual(item.text(0), 'com.demo.app')
        self.assertEqual(item.text(1), 'User')
        mocked_info.assert_called_once()
        args = mocked_info.call_args[0]
        # Title should include Package
        self.assertEqual(args[1], 'App Details - com.demo.app')
        # Body should contain Package and Version
        self.assertIn('com.demo.app', args[2])
        self.assertIn('2.3.4', args[2])


if __name__ == '__main__':  # pragma: no cover
    unittest.main()
