"""Apps tab widget to display and manage installed apps per device."""

from __future__ import annotations

from typing import Dict, List, Optional

from PyQt6.QtCore import Qt, QTimer
from PyQt6 import sip
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGroupBox,
    QLabel,
    QLineEdit,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QMessageBox,
    QGridLayout,
    QSizePolicy,
)

from config.constants import PanelText
from ui.style_manager import LabelStyle, PanelButtonVariant, StyleManager
from utils import common, adb_tools
from utils.task_dispatcher import TaskContext, TaskHandle


logger = common.get_logger('apps_tab')


class AppListTab(QWidget):
    """Apps tab that lists installed packages with actions."""

    def __init__(self, main_window) -> None:
        super().__init__(parent=main_window)
        self.window = main_window
        self._apps: List[dict] = []
        self._detail_handles: Dict[str, TaskHandle] = {}
        self._destroyed = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(14)

        header = QLabel(PanelText.GROUP_APPS)
        StyleManager.apply_label_style(header, LabelStyle.SUBHEADER)
        layout.addWidget(header)
        layout.addSpacing(6)

        # Device indicator and refresh/search controls
        controls_group = QGroupBox()
        controls_layout = QHBoxLayout(controls_group)
        controls_layout.setContentsMargins(10, 8, 10, 8)
        controls_layout.setSpacing(8)
        self.device_label = QLabel('Active: None')
        StyleManager.apply_label_style(self.device_label, LabelStyle.STATUS)
        controls_layout.addWidget(self.device_label)

        controls_layout.addStretch(1)

        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText(PanelText.PLACEHOLDER_APP_SEARCH)
        self.search_edit.textChanged.connect(self._apply_search_filter)
        controls_layout.addWidget(self.search_edit)

        refresh_btn = QPushButton(PanelText.BUTTON_REFRESH_APPS)
        refresh_btn.setToolTip('Reload installed apps from active device')
        refresh_btn.clicked.connect(self.refresh_apps)
        StyleManager.apply_panel_button_style(refresh_btn, PanelButtonVariant.SECONDARY, fixed_height=34, min_width=120)
        controls_layout.addWidget(refresh_btn)

        layout.addWidget(controls_group)

        # Apps list
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(['Package', 'Type', 'Path'])
        self.tree.setRootIsDecorated(False)
        self.tree.setSortingEnabled(True)
        self.tree.setColumnWidth(0, 360)
        self.tree.setColumnWidth(1, 120)
        # Default sort: Type column with 'User' first (descending alphabetical)
        try:
            header = self.tree.header()
            header.setSortIndicatorShown(True)
            header.setSortIndicator(2, Qt.SortOrder.DescendingOrder)
            self.tree.sortItems(2, Qt.SortOrder.DescendingOrder)
        except Exception:
            pass
        layout.addWidget(self.tree)
        try:
            self.tree.itemDoubleClicked.connect(self._on_item_double_clicked)
        except Exception:
            pass

        # Actions (grid layout with 3 columns)
        actions_group = QGroupBox(PanelText.GROUP_APPS_ACTIONS)
        actions_layout = QGridLayout(actions_group)
        actions_layout.setContentsMargins(12, 24, 12, 12)
        actions_layout.setHorizontalSpacing(14)
        actions_layout.setVerticalSpacing(10)

        perm_btn = QPushButton(PanelText.BUTTON_SHOW_PERMISSIONS)
        perm_btn.setToolTip('Show requested and granted permissions for the selected app')
        perm_btn.clicked.connect(self._on_show_permissions)
        StyleManager.apply_panel_button_style(perm_btn, PanelButtonVariant.SECONDARY, fixed_height=34, min_width=160)

        info_btn = QPushButton(PanelText.BUTTON_OPEN_APP_INFO)
        info_btn.setToolTip('Open system app info page on device')
        info_btn.clicked.connect(self._on_open_app_info)
        StyleManager.apply_panel_button_style(info_btn, PanelButtonVariant.NEUTRAL, fixed_height=34, min_width=140)

        force_btn = QPushButton(PanelText.BUTTON_FORCE_STOP)
        force_btn.setToolTip('Force stop the selected app process')
        force_btn.clicked.connect(self._on_force_stop)
        StyleManager.apply_panel_button_style(force_btn, PanelButtonVariant.SECONDARY, fixed_height=34, min_width=140)

        enable_btn = QPushButton(PanelText.BUTTON_ENABLE_APP)
        enable_btn.setToolTip('Enable the selected app (pm enable)')
        enable_btn.clicked.connect(lambda: self._on_set_enabled(True))
        StyleManager.apply_panel_button_style(enable_btn, PanelButtonVariant.SECONDARY, fixed_height=34, min_width=120)

        disable_btn = QPushButton(PanelText.BUTTON_DISABLE_APP)
        disable_btn.setToolTip('Disable the selected app for the current user')
        disable_btn.clicked.connect(lambda: self._on_set_enabled(False))
        StyleManager.apply_panel_button_style(disable_btn, PanelButtonVariant.SECONDARY, fixed_height=34, min_width=120)

        clear_btn = QPushButton(PanelText.BUTTON_CLEAR_DATA)
        clear_btn.setToolTip('Clear app data (pm clear). Warning: This cannot be undone.')
        clear_btn.clicked.connect(self._on_clear_data)
        StyleManager.apply_panel_button_style(clear_btn, PanelButtonVariant.SECONDARY, fixed_height=34, min_width=140)

        uninstall_btn = QPushButton(PanelText.BUTTON_UNINSTALL_APP)
        uninstall_btn.setToolTip('Uninstall the selected app from the device. Warning: This cannot be undone.')
        uninstall_btn.clicked.connect(self._on_uninstall)
        StyleManager.apply_panel_button_style(uninstall_btn, PanelButtonVariant.SECONDARY, fixed_height=34, min_width=140)

        # Place buttons in a 3-column grid
        buttons = [
            perm_btn, info_btn, force_btn, enable_btn,
            disable_btn, clear_btn, uninstall_btn,
        ]
        columns = 4
        for idx, btn in enumerate(buttons):
            row, col = divmod(idx, columns)
            actions_layout.addWidget(btn, row, col)

        # Balance 4 columns for consistent spacing
        for c in range(columns):
            actions_layout.setColumnStretch(c, 1)

        layout.addSpacing(10)
        layout.addWidget(actions_group)

        self._sync_active_device_label()

        # Track active device changes and auto-refresh when it changes
        self._last_active_serial: Optional[str] = self.window.device_selection_manager.get_active_serial()
        self._connect_selection_watch()
        try:
            self.destroyed.connect(self._on_destroyed)  # type: ignore[arg-type]
        except Exception:
            pass
        
        

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def refresh_apps(self) -> None:
        # Cancel previous detail tasks before reloading
        self._cancel_detail_tasks()

        serial = self.window.device_selection_manager.get_active_serial()
        if not serial:
            self.window.show_warning('Device Selection', 'Select a device to load installed apps.')
            return

        device = self.window.device_dict.get(serial)
        if device is None:
            self.window.show_error('Device Not Available', f'Device {serial} is not available.')
            return

        self._sync_active_device_label()
        logger.info('Loading installed apps for %s', serial)
        try:
            self._apps = adb_tools.list_installed_packages(serial)
        except Exception as exc:  # pragma: no cover - defensive
            logger.error('Failed to list packages: %s', exc)
            self.window.show_error('List Apps Failed', str(exc))
            return

        # Populate rows; versions resolved on demand
        self._populate_tree(self._apps)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _sync_active_device_label(self) -> None:
        serial = self.window.device_selection_manager.get_active_serial()
        if serial and serial in self.window.device_dict:
            model = self.window.device_dict[serial].device_model
            self.device_label.setText(f'Active: {model} ({serial})')
        else:
            self.device_label.setText('Active: None')

    def _populate_tree(self, apps: List[dict]) -> None:
        self.tree.setSortingEnabled(False)
        self.tree.clear()
        for app in apps:
            pkg = app.get('package', '')
            path = app.get('apk_path', '')
            app_type = 'System' if app.get('is_system') else 'User'
            item = QTreeWidgetItem([pkg, app_type, path])
            # store pkg to retrieve later
            item.setData(0, Qt.ItemDataRole.UserRole, pkg)
            item.setData(0, Qt.ItemDataRole.UserRole + 1, app)
            self.tree.addTopLevelItem(item)

        # Auto-resize columns except path
        self.tree.header().resizeSection(0, 360)
        self.tree.header().resizeSection(1, 120)
        self.tree.setSortingEnabled(True)
        try:
            self.tree.sortItems(2, Qt.SortOrder.DescendingOrder)
        except Exception:
            pass

    def _apply_search_filter(self) -> None:
        query = (self.search_edit.text() or '').strip().lower()
        for i in range(self.tree.topLevelItemCount()):
            item = self.tree.topLevelItem(i)
            pkg = (item.text(0) or '').lower()
            visible = query in pkg
            # QTreeWidget supports per-item visibility via setHidden; avoid setRowHidden
            item.setHidden(not visible if query else False)

    def _get_selected_package(self) -> Optional[str]:
        item = self.tree.currentItem()
        if item is None:
            return None
        pkg = item.data(0, Qt.ItemDataRole.UserRole)
        return str(pkg) if pkg else None

    def _connect_selection_watch(self) -> None:
        # Connect to direct table toggles (user actions)
        device_table = getattr(self.window, 'device_table', None)
        try:
            if device_table is not None and hasattr(device_table, 'selection_toggled'):
                device_table.selection_toggled.connect(lambda *_: self._maybe_refresh_on_active_change())
        except Exception:
            pass

        # Fallback: periodic check to catch programmatic selection changes
        self._active_watch = QTimer(self)
        self._active_watch.setInterval(700)
        self._active_watch.timeout.connect(self._maybe_refresh_on_active_change)
        self._active_watch.start()

    def _maybe_refresh_on_active_change(self) -> None:
        current = self.window.device_selection_manager.get_active_serial()
        if current != self._last_active_serial:
            self._last_active_serial = current
            self._sync_active_device_label()
            if current:
                # Cancel previous detail loaders for old device before refresh
                self._cancel_detail_tasks()
                self.refresh_apps()
            else:
                self.tree.clear()

    # ------------------------------------------------------------------
    # Cleanup and safety helpers
    # ------------------------------------------------------------------
    def _on_destroyed(self) -> None:
        self._destroyed = True
        try:
            if getattr(self, '_active_watch', None) is not None:
                self._active_watch.stop()
        except Exception:
            pass
        self._cancel_detail_tasks()

    def _cancel_detail_tasks(self) -> None:
        handles = list(self._detail_handles.values())
        for handle in handles:
            try:
                handle.cancel()
            except Exception:
                pass
        self._detail_handles.clear()

    def _on_item_double_clicked(self, item: QTreeWidgetItem, _column: int) -> None:
        if item is None:
            return
        serial = self.window.device_selection_manager.get_active_serial()
        if not serial:
            self.window.show_warning('Device Selection', 'Select a device first.')
            return
        pkg = item.data(0, Qt.ItemDataRole.UserRole)
        if not pkg:
            return
        pkg_str = str(pkg)
        cached_version = item.data(1, Qt.ItemDataRole.UserRole)
        app_data = item.data(0, Qt.ItemDataRole.UserRole + 1) or {}
        if cached_version:
            self._show_details_dialog(pkg_str, str(cached_version), app_data)
            return
        if pkg_str in self._detail_handles:
            self.window.show_info('App Details', 'Loading app details, please wait.')
            return
        self._load_app_details(serial, pkg_str, item, app_data)

    def _load_app_details(self, serial: str, package: str, item: QTreeWidgetItem, app_data: dict) -> None:
        dispatcher = self.window._task_dispatcher

        def resolve_details(task_handle=None, progress_callback=None):  # pragma: no cover - runs in thread pool
            try:
                version = adb_tools.get_app_version_name(serial, package)
            except Exception as exc:  # pragma: no cover - defensive
                logger.error('Failed to fetch version for %s: %s', package, exc)
                version = ''
            return version or 'N/A'

        handle = dispatcher.submit(resolve_details, context=TaskContext(name='resolve_app_details', device_serial=serial))
        self._detail_handles[package] = handle
        self.window._background_task_handles.append(handle)
        try:
            handle.completed.connect(lambda version, it=item, data=app_data, pkg=package: self._on_details_ready(it, data, pkg, version))
            handle.failed.connect(lambda exc, pkg=package: self._on_details_failed(pkg, exc))
            handle.finished.connect(lambda pkg=package: self._detail_handles.pop(pkg, None))
        except Exception:
            pass

    def _on_details_ready(self, item: QTreeWidgetItem, app_data: dict, package: str, version: str) -> None:
        if item is None:
            return
        # Avoid UI updates if the widget is gone
        try:
            if self._destroyed or sip.isdeleted(self) or sip.isdeleted(self.tree):
                return
        except Exception:
            return
        # cache version in hidden role
        item.setData(1, Qt.ItemDataRole.UserRole, version)
        app_data = dict(app_data or {})
        app_data['version'] = version
        item.setData(0, Qt.ItemDataRole.UserRole + 1, app_data)
        self._show_details_dialog(package, version, app_data)

    def _on_details_failed(self, package: str, exc: Exception) -> None:
        logger.error('Failed to resolve app details for %s: %s', package, exc)
        self.window.show_error('App Details', f'Failed to load details for {package}.')

    def _show_details_dialog(self, package: str, version: str, app_data: dict) -> None:
        app_type = 'System' if app_data.get('is_system') else 'User'
        path = app_data.get('apk_path') or '(unknown)'
        message = (
            f'Package: {package}\n'
            f'Version: {version}\n'
            f'Type: {app_type}\n'
            f'Path: {path}'
        )
        title = f'App Details - {package}'
        QMessageBox.information(self, title, message)

    def _on_uninstall(self) -> None:
        serial = self.window.device_selection_manager.get_active_serial()
        if not serial:
            self.window.show_warning('Device Selection', 'Select a device first.')
            return
        pkg = self._get_selected_package()
        if not pkg:
            self.window.show_warning('Uninstall App', 'Select an app from the list.')
            return

        reply = QMessageBox.question(
            self,
            'Confirm Uninstall',
            f'Uninstall {pkg} from the active device?',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        ok = False
        try:
            ok = adb_tools.uninstall_app(serial, pkg)
        except Exception as exc:  # pragma: no cover - defensive
            logger.error('Uninstall failed: %s', exc)
        if ok:
            self.window.show_info('Uninstall', f'Successfully uninstalled {pkg}.')
            self.refresh_apps()
        else:
            self.window.show_error('Uninstall', f'Failed to uninstall {pkg}.')

    def _on_show_permissions(self) -> None:
        serial = self.window.device_selection_manager.get_active_serial()
        if not serial:
            self.window.show_warning('Device Selection', 'Select a device first.')
            return
        pkg = self._get_selected_package()
        if not pkg:
            self.window.show_warning('Permissions', 'Select an app from the list.')
            return
        try:
            perms = adb_tools.get_package_permissions(serial, pkg)
        except Exception as exc:  # pragma: no cover - defensive
            logger.error('Permission query failed: %s', exc)
            self.window.show_error('Permissions', str(exc))
            return

        requested = '\n'.join(perms.get('requested', [])) or '(none)'
        granted = '\n'.join(perms.get('granted', [])) or '(none)'
        text = (
            f'Requested permissions:\n{requested}\n\n'
            f'Granted permissions:\n{granted}'
        )
        QMessageBox.information(self, 'App Permissions', text)

    def _on_force_stop(self) -> None:
        serial = self.window.device_selection_manager.get_active_serial()
        if not serial:
            self.window.show_warning('Device Selection', 'Select a device first.')
            return
        pkg = self._get_selected_package()
        if not pkg:
            self.window.show_warning('Force Stop', 'Select an app from the list.')
            return
        try:
            ok = adb_tools.force_stop_app(serial, pkg)
        except Exception as exc:  # pragma: no cover
            logger.error('Force stop failed: %s', exc)
            ok = False
        if ok:
            self.window.show_info('Force Stop', f'Force-stopped {pkg}.')
        else:
            self.window.show_error('Force Stop', f'Failed to force-stop {pkg}.')

    def _on_clear_data(self) -> None:
        serial = self.window.device_selection_manager.get_active_serial()
        if not serial:
            self.window.show_warning('Device Selection', 'Select a device first.')
            return
        pkg = self._get_selected_package()
        if not pkg:
            self.window.show_warning('Clear Data', 'Select an app from the list.')
            return

        reply = QMessageBox.question(
            self,
            'Confirm Clear Data',
            f'Clear all data for {pkg}? This action cannot be undone.',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        try:
            ok = adb_tools.clear_app_data(serial, pkg)
        except Exception as exc:  # pragma: no cover
            logger.error('Clear data failed: %s', exc)
            ok = False
        if ok:
            self.window.show_info('Clear Data', f'Data cleared for {pkg}.')
        else:
            self.window.show_error('Clear Data', f'Failed to clear data for {pkg}.')

    def _on_set_enabled(self, enable: bool) -> None:
        serial = self.window.device_selection_manager.get_active_serial()
        if not serial:
            self.window.show_warning('Device Selection', 'Select a device first.')
            return
        pkg = self._get_selected_package()
        if not pkg:
            self.window.show_warning('App Enable/Disable', 'Select an app from the list.')
            return
        try:
            ok = adb_tools.set_app_enabled(serial, pkg, enable)
        except Exception as exc:  # pragma: no cover
            logger.error('Set enabled failed: %s', exc)
            ok = False
        if ok:
            state = 'enabled' if enable else 'disabled'
            self.window.show_info('App State', f'{pkg} {state}.')
        else:
            self.window.show_error('App State', f'Failed to change state for {pkg}.')

    def _on_open_app_info(self) -> None:
        serial = self.window.device_selection_manager.get_active_serial()
        if not serial:
            self.window.show_warning('Device Selection', 'Select a device first.')
            return
        pkg = self._get_selected_package()
        if not pkg:
            self.window.show_warning('Open App Info', 'Select an app from the list.')
            return
        try:
            ok = adb_tools.open_app_info(serial, pkg)
        except Exception as exc:  # pragma: no cover
            logger.error('Open app info failed: %s', exc)
            ok = False
        if ok:
            self.window.show_info('App Info', f'Opening settings for {pkg} on device.')
        else:
            self.window.show_error('App Info', f'Failed to open settings for {pkg}.')


__all__ = ['AppListTab']
