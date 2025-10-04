import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication, QLabel

from ui.device_file_controller import DeviceFileController
from config.constants import PanelText
from utils import adb_models


class DummyTree:
    def __init__(self) -> None:
        self.items = []

    def clear(self) -> None:
        self.items.clear()

    def addTopLevelItem(self, item) -> None:
        self.items.append(item)

    def sortItems(self, column, order) -> None:  # pragma: no cover - no-op for tests
        pass

    def selectedItems(self):  # pragma: no cover - unused in tests
        return []

    def topLevelItemCount(self):  # pragma: no cover - compatibility helper
        return len(self.items)

    def topLevelItem(self, index):  # pragma: no cover
        return self.items[index]

    def itemAt(self, position):  # pragma: no cover - context menu helper
        return None

    def viewport(self):  # pragma: no cover - context menu helper
        return SimpleNamespace(mapToGlobal=lambda pos: pos)


class DummyTreeItem:
    def __init__(self, columns):
        self.columns = columns
        self._data = {}
        self._flags = Qt.ItemFlag(0)

    def setData(self, column, role, value):
        self._data[(column, role)] = value

    def data(self, column, role):  # pragma: no cover - debug helper
        return self._data.get((column, role))

    def setFlags(self, flags):
        self._flags = flags

    def flags(self):  # pragma: no cover - debug helper
        return self._flags

    def setCheckState(self, column, state):
        self._data[(column, 'check_state')] = state


class DeviceFileControllerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.browser_manager = MagicMock()
        self.status_label = QLabel('Ready to browse device files.')
        self.status_label.setFixedWidth(420)
        self.status_label.resize(420, self.status_label.sizeHint().height())
        self.device_label = MagicMock()
        self.path_edit = MagicMock()
        self.path_edit.text.return_value = PanelText.PLACEHOLDER_DEVICE_FILE_PATH
        self.tree = DummyTree()

        self.window = SimpleNamespace(
            require_single_device_selection=MagicMock(return_value=None),
            show_error=MagicMock(),
            device_file_browser_manager=self.browser_manager,
            device_file_controller=None,
        )

        self.tree_item_patch = patch('ui.device_file_controller.QTreeWidgetItem', DummyTreeItem)
        self.tree_item_patch.start()

        self.controller = DeviceFileController(window=self.window)
        self.controller.register_widgets(
            tree=self.tree,
            path_edit=self.path_edit,
            status_label=self.status_label,
            device_label=self.device_label,
        )
        self.window.device_file_controller = self.controller

    def tearDown(self) -> None:
        self.tree_item_patch.stop()

    def test_refresh_browser_without_device_updates_status_and_skips_fetch(self) -> None:
        self.controller.refresh_browser()
        self._app.processEvents()

        self.assertEqual(self.status_label.text(), 'Select exactly one device to browse files.')
        self.assertEqual(self.status_label.toolTip(), '')
        self.browser_manager.fetch_directory.assert_not_called()

    def test_refresh_browser_fetches_directory_with_normalized_path(self) -> None:
        device = SimpleNamespace(device_serial_num='ABC123', device_model='Pixel 7')
        self.window.require_single_device_selection.return_value = device
        self.path_edit.text.return_value = 'sdcard/Download/'

        self.controller.refresh_browser()
        self._app.processEvents()

        self.path_edit.setText.assert_called_once_with('/sdcard/Download')
        self.device_label.setText.assert_called_once()
        self.assertEqual(self.status_label.text(), 'Loading directory...')
        self.browser_manager.fetch_directory.assert_called_once_with('ABC123', '/sdcard/Download')

    def test_display_preview_uses_preview_window(self) -> None:
        preview_window = MagicMock()
        self.controller.ensure_preview_window = MagicMock(return_value=preview_window)

        self.controller.display_preview('/tmp/preview.png')
        self._app.processEvents()

        preview_window.display_preview.assert_called_once_with('/tmp/preview.png')
        self.assertEqual(self.status_label.text(), 'Preview ready: /tmp/preview.png')

    def test_on_directory_listing_handles_dataclass_without_error_attribute(self) -> None:
        self.controller.current_serial = 'SER123'
        listing = adb_models.DeviceDirectoryListing(
            serial='SER123',
            path='/sdcard',
            entries=[
                adb_models.DeviceFileEntry(name='DCIM', path='/sdcard/DCIM', is_dir=True),
                adb_models.DeviceFileEntry(name='note.txt', path='/sdcard/note.txt', is_dir=False),
            ],
        )

        self.controller.on_directory_listing('SER123', '/sdcard', listing)
        self._app.processEvents()

        self.assertEqual(len(self.tree.items), 2)
        self.assertEqual(self.status_label.text(), 'Loaded 1 folders and 1 files.')
        self.path_edit.setText.assert_called_with('/sdcard')

    def test_status_label_elides_long_messages_and_provides_tooltip(self) -> None:
        self.status_label.setFixedWidth(180)
        self.status_label.resize(180, self.status_label.sizeHint().height())
        long_message = 'Loaded 12 folders and 345 files from /a/really/long/path/that/does/not/fit'

        self.controller.set_status(long_message)
        self._app.processEvents()

        label_text = self.status_label.text()
        self.assertNotEqual(label_text, long_message)
        self.assertTrue(label_text.endswith('…'), 'Expected elided text to end with ellipsis')
        self.assertEqual(self.status_label.toolTip(), long_message)


if __name__ == '__main__':
    unittest.main()
