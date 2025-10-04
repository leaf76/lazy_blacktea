"""Device file browser orchestration extracted from WindowMain."""

from __future__ import annotations

import posixpath
from typing import Iterable, List, Optional, TYPE_CHECKING

from PyQt6.QtCore import QPoint, Qt
from PyQt6.QtWidgets import QMenu, QTreeWidget, QTreeWidgetItem

from config.constants import PanelText
from ui.constants import DEVICE_FILE_IS_DIR_ROLE, DEVICE_FILE_PATH_ROLE
from utils import adb_models, common

if TYPE_CHECKING:  # pragma: no cover
    from lazy_blacktea_pyqt import WindowMain
    from ui.device_file_preview_window import DeviceFilePreviewWindow


logger = common.get_logger("device_file_controller")


class DeviceFileController:
    """Encapsulates device file browser UI interactions."""

    def __init__(self, window: "WindowMain") -> None:
        self.window = window
        self._tree: Optional[QTreeWidget] = None
        self._path_edit = None
        self._status_label = None
        self._device_label = None
        self._preview_window: Optional["DeviceFilePreviewWindow"] = None
        self.current_serial: Optional[str] = None
        self.current_path: str = PanelText.PLACEHOLDER_DEVICE_FILE_PATH

    # ---- Widget registration -------------------------------------------------

    def register_widgets(
        self,
        *,
        tree: QTreeWidget,
        path_edit,
        status_label,
        device_label,
    ) -> None:
        self._tree = tree
        self._path_edit = path_edit
        self._status_label = status_label
        self._device_label = device_label

    # ---- Public API ----------------------------------------------------------

    def refresh_browser(self, path: Optional[str] = None) -> None:
        if not self._widgets_ready():
            self.window.show_error('Device Files', 'Device file browser UI is not ready yet.')
            return

        device = self.window.require_single_device_selection('Device file browser')
        if device is None:
            self._set_status('Select exactly one device to browse files.')
            self.current_serial = None
            return

        serial = device.device_serial_num
        raw_path = path if path is not None else self._path_edit.text()
        normalized_path = self._normalize_path(raw_path)

        self._path_edit.setText(normalized_path)
        if self._device_label is not None:
            self._device_label.setText(
                f'Browsing {device.device_model} ({serial}) — {normalized_path}'
            )

        self.current_serial = serial
        self.current_path = normalized_path
        self._set_status('Loading directory...')
        self.window.device_file_browser_manager.fetch_directory(serial, normalized_path)

    def navigate_up(self) -> None:
        if not self._widgets_ready():
            return
        current_path = self._normalize_path(self._path_edit.text())
        if current_path == '/':
            self.refresh_browser('/')
            return
        parent_path = posixpath.dirname(current_path.rstrip('/')) or '/'
        self.refresh_browser(parent_path)

    def navigate_to_path(self) -> None:
        if not self._widgets_ready():
            return
        self.refresh_browser(self._path_edit.text())

    def handle_item_double_clicked(self, item: QTreeWidgetItem, column: int) -> None:
        if item is None:
            return
        is_dir = bool(item.data(0, DEVICE_FILE_IS_DIR_ROLE))
        if is_dir:
            target_path = item.data(0, DEVICE_FILE_PATH_ROLE)
            self.refresh_browser(target_path)
            return
        self.preview_selected_file(item)

    def download_selected_files(self) -> None:
        if not self._widgets_ready():
            self.window.show_error('Device Files', 'Device file browser UI is not ready yet.')
            return

        device = self.window.require_single_device_selection('Device files download')
        if device is None:
            return

        serial = device.device_serial_num
        remote_paths: List[str] = []
        assert self._tree is not None  # for type checkers
        for index in range(self._tree.topLevelItemCount()):
            item = self._tree.topLevelItem(index)
            if item.checkState(0) == Qt.CheckState.Checked:
                path_value = item.data(0, DEVICE_FILE_PATH_ROLE)
                if path_value:
                    remote_paths.append(path_value)

        if not remote_paths:
            self.window.show_warning('Device Files', 'Select at least one file or folder to download.')
            return

        output_path = self.window._get_file_generation_output_path()
        if not output_path:
            return

        self._set_status(f'Downloading {len(remote_paths)} item(s)...')
        self.window.device_file_browser_manager.download_paths(serial, remote_paths, output_path)

    def preview_selected_file(self, item: Optional[QTreeWidgetItem] = None) -> None:
        if not self._widgets_ready():
            return

        if item is None and self._tree is not None:
            selected_items = self._tree.selectedItems()
            if not selected_items:
                self.window.show_warning('Preview File', 'Select a file to preview first.')
                return
            item = selected_items[0]

        if item is None:
            return

        is_dir = bool(item.data(0, DEVICE_FILE_IS_DIR_ROLE))
        if is_dir:
            self.window.show_warning('Preview File', 'Folder preview is not supported.')
            return

        remote_path = item.data(0, DEVICE_FILE_PATH_ROLE)
        if not remote_path:
            self.window.show_warning('Preview File', 'Unable to preview the selected item.')
            return

        if self.current_serial is None:
            self.window.show_warning('Preview File', 'No device selected.')
            return

        self.window.device_file_browser_manager.preview_file(self.current_serial, remote_path)
        self._set_status(f'Loading preview for {remote_path}...')

    def display_preview(self, local_path: str) -> None:
        window = self.ensure_preview_window()
        window.display_preview(local_path)
        self._set_status(f'Preview ready: {local_path}')

    def set_status(self, message: str) -> None:
        self._set_status(message)

    def clear_preview(self) -> None:
        if self._preview_window is not None:
            self._preview_window.clear()

    def hide_preview_loading(self) -> None:
        if self._preview_window is not None:
            self._preview_window.hide_loading()

    def copy_path(self, item: Optional[QTreeWidgetItem] = None) -> None:
        if not self._widgets_ready():
            return
        if item is None and self._tree is not None:
            selected_items = self._tree.selectedItems()
            if not selected_items:
                self.window.show_warning('Copy Path', 'Select a file to copy its path.')
                return
            item = selected_items[0]
        if item is None:
            return
        remote_path = item.data(0, DEVICE_FILE_PATH_ROLE)
        if not remote_path:
            self.window.show_warning('Copy Path', 'No path information available for the selected item.')
            return
        self.window.dialog_manager.copy_to_clipboard(remote_path)
        self.window.status_bar_manager.show_message(f'Copied path: {remote_path}', 2000)

    def download_item(self, item: Optional[QTreeWidgetItem] = None) -> None:
        if not self._widgets_ready():
            return
        if item is None and self._tree is not None:
            selected_items = self._tree.selectedItems()
            if not selected_items:
                self.window.show_warning('Download File', 'Select a file to download first.')
                return
            item = selected_items[0]
        if item is None:
            return
        remote_path = item.data(0, DEVICE_FILE_PATH_ROLE)
        if not remote_path:
            self.window.show_warning('Download File', 'No path information available for the selected item.')
            return
        if self.current_serial is None:
            self.window.show_warning('Download File', 'No device selected.')
            return
        output_path = self.window._get_file_generation_output_path()
        if not output_path:
            return
        item_name = posixpath.basename(remote_path)
        self._set_status(f'Downloading {item_name}...')
        self.window.device_file_browser_manager.download_paths(
            self.current_serial,
            [remote_path],
            output_path,
        )

    def show_context_menu(self, position: QPoint) -> None:
        if not self._widgets_ready() or self._tree is None:
            return
        item = self._tree.itemAt(position)
        menu = QMenu(self._tree)
        if item is not None:
            menu.addAction(PanelText.BUTTON_PREVIEW_SELECTED, lambda: self.preview_selected_file(item))
            menu.addAction(PanelText.BUTTON_COPY_PATH, lambda: self.copy_path(item))
            menu.addSeparator()
            menu.addAction(PanelText.BUTTON_DOWNLOAD_ITEM, lambda: self.download_item(item))
        menu.addSeparator()
        menu.addAction(PanelText.BUTTON_REFRESH, lambda: self.refresh_browser())
        global_pos = self._tree.viewport().mapToGlobal(position)
        menu.exec(global_pos)

    def ensure_preview_window(self):  # type: ignore[override]
        if self._preview_window is None:
            from ui.device_file_preview_window import DeviceFilePreviewWindow  # local import to avoid cycles

            self._preview_window = DeviceFilePreviewWindow(self.window)
        return self._preview_window

    def clear_preview_cache(self) -> None:
        self.window.device_file_browser_manager.cleanup_preview_cache()
        if self._preview_window is not None:
            self._preview_window.clear_cache()
            self._preview_window.clear()
        self._set_status('Preview cache cleared.')

    def open_preview_externally(self) -> None:
        if self._preview_window is None:
            self.window.show_warning('Preview File', 'Open a preview before launching an external viewer.')
            return
        self._preview_window.open_external_viewer()

    def handle_preview_cleanup(self, local_path: str) -> None:
        if not local_path:
            return
        success = self.window.device_file_browser_manager.cleanup_preview_path(local_path)
        if not success:
            warning = 'Some preview files could not be removed.'
            self._set_status(warning)
            self.window.show_warning('Preview Cache', warning)
        if self._preview_window is not None:
            self._preview_window.remove_preview_if_matches(local_path)

    def shutdown(self) -> None:
        """Release preview resources during application shutdown."""
        self.window.device_file_browser_manager.cleanup_preview_cache()
        if self._preview_window is not None:
            try:
                self._preview_window.close()
            except Exception:  # pragma: no cover - best effort
                pass

    # ---- Signal handlers -----------------------------------------------------

    def on_directory_listing(
        self,
        serial: str,
        path: str,
        listing: adb_models.DeviceDirectoryListing,
    ) -> None:
        if self.current_serial and serial != self.current_serial:
            logger.debug(
                'Ignoring directory listing for %s; current device is %s',
                serial,
                self.current_serial,
            )
            return

        if not self._widgets_ready():
            return

        error_message = getattr(listing, 'error_message', None) or getattr(listing, 'error', None)
        if error_message:
            self._set_status(f'Failed to load directory: {error_message}')
            return

        if self._path_edit is not None:
            self._path_edit.setText(path)
        self.current_path = path

        assert self._tree is not None
        self._tree.clear()
        directories = self._extract_entries(listing, 'directories')
        files = self._extract_entries(listing, 'files')
        for entry in directories:
            item = QTreeWidgetItem([entry.name, 'Directory'])
            item.setData(0, DEVICE_FILE_PATH_ROLE, entry.path)
            item.setData(0, DEVICE_FILE_IS_DIR_ROLE, True)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(0, Qt.CheckState.Unchecked)
            self._tree.addTopLevelItem(item)
        for entry in files:
            item = QTreeWidgetItem([entry.name, 'File'])
            item.setData(0, DEVICE_FILE_PATH_ROLE, entry.path)
            item.setData(0, DEVICE_FILE_IS_DIR_ROLE, False)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(0, Qt.CheckState.Unchecked)
            self._tree.addTopLevelItem(item)
        self._tree.sortItems(0, Qt.SortOrder.AscendingOrder)
        self._set_status(f'Loaded {len(directories)} folders and {len(files)} files.')

    def on_download_completed(
        self,
        serial: str,
        output_path: str,
        remote_paths: List[str],
        results: List[str],
    ) -> None:
        if serial != self.current_serial:
            return
        success_count = sum(1 for item in results if item == 'OK')
        self._set_status(f'Downloaded {success_count}/{len(remote_paths)} item(s) to {output_path}.')
        self.window.show_info('Download Complete', f'Downloaded {len(remote_paths)} item(s) to:\n{output_path}')
        if self.current_path:
            self.window.refresh_device_file_browser(self.current_path)

    def on_operation_failed(self, message: str) -> None:
        self._set_status(message)
        self.hide_preview_loading()
        self.window.show_error('Device Files', message)

    def on_preview_ready(self, serial: str, remote_path: str, local_path: str) -> None:
        if serial != self.current_serial:
            logger.debug('Preview belongs to %s but active device is %s', serial, self.current_serial)
            return
        self.display_preview(local_path)

    # ---- Internal helpers ----------------------------------------------------

    def _set_status(self, message: str) -> None:
        if self._status_label is not None:
            self._status_label.setText(message)

    def _widgets_ready(self) -> bool:
        if self._tree is None or self._path_edit is None:
            logger.debug('Device file browser widgets are not initialized yet.')
            return False
        return True

    @staticmethod
    def _extract_entries(listing: adb_models.DeviceDirectoryListing, attr_name: str) -> list[adb_models.DeviceFileEntry]:
        attr = getattr(listing, attr_name, None)
        if callable(attr):
            try:
                entries = attr()
            except TypeError:
                entries = attr
        else:
            entries = attr
        if entries is None:
            return []
        return list(entries)

    @staticmethod
    def _normalize_path(path: str) -> str:
        default_path = PanelText.PLACEHOLDER_DEVICE_FILE_PATH
        normalized = (path or default_path).strip()
        if not normalized:
            return default_path
        if not normalized.startswith('/'):
            normalized = f'/{normalized}'
        if normalized != '/' and normalized.endswith('/'):
            normalized = normalized.rstrip('/')
        return normalized or default_path
