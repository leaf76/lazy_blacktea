"""Standalone window for device file previews."""

from __future__ import annotations

import os
from typing import Optional

from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtGui import QDesktopServices, QPixmap, QPainter
from PyQt6.QtWidgets import (
    QDialog,
    QFrame,
    QGraphicsPixmapItem,
    QGraphicsScene,
    QGraphicsView,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QPlainTextEdit,
)

from config.constants import PanelText
from ui.device_file_preview_controller import DeviceFilePreviewController


class _GraphicsImageAdapter:
    """Adapter that exposes QLabel-like API backed by QGraphicsView."""

    def __init__(self, view: QGraphicsView, item: QGraphicsPixmapItem) -> None:
        self._view = view
        self._item = item

    def setPixmap(self, pixmap: QPixmap) -> None:
        self._item.setPixmap(pixmap)
        self._view.scene().setSceneRect(pixmap.rect())
        self._view.resetTransform()
        self._view.centerOn(self._item)

    def clear(self) -> None:
        self._item.setPixmap(QPixmap())
        self._view.scene().setSceneRect(0, 0, 0, 0)

    def adjustSize(self) -> None:  # pragma: no cover - no-op for adapter
        pass


class DeviceFilePreviewWindow(QDialog):
    """Dialog that renders device file previews with multiple content types."""

    LAST_GEOMETRY = None

    def __init__(self, parent=None, *, cleanup_callback=None) -> None:
        super().__init__(parent)
        self.setWindowTitle('Device File Preview')
        self.setMinimumSize(720, 520)
        self._cleanup_callback = cleanup_callback
        self._current_zoom = 1.0

        layout = QVBoxLayout(self)

        self.status_label = QLabel('', self)
        self.status_label.setObjectName('device_file_preview_status')
        layout.addWidget(self.status_label)

        self.stack = QStackedWidget(self)
        layout.addWidget(self.stack, stretch=1)

        self.text_widget = QPlainTextEdit(self)
        self.text_widget.setObjectName('device_file_preview_text')
        self.text_widget.setReadOnly(True)
        self.text_widget.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)

        image_container = QVBoxLayout()
        image_frame = QFrame(self)
        image_frame.setLayout(image_container)

        self.graphics_view = QGraphicsView(self)
        self.graphics_view.setRenderHints(
            self.graphics_view.renderHints() | QPainter.RenderHint.Antialiasing
        )
        self.graphics_view.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.graphics_view.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.graphics_scene = QGraphicsScene(self)
        self.graphics_view.setScene(self.graphics_scene)
        self.graphics_item = QGraphicsPixmapItem()
        self.graphics_scene.addItem(self.graphics_item)
        image_container.addWidget(self.graphics_view)

        self.message_widget = QLabel(self)
        self.message_widget.setObjectName('device_file_preview_message')
        self.message_widget.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.message_widget.setWordWrap(True)

        button_row = QHBoxLayout()

        self.zoom_in_button = QPushButton('Zoom In', self)
        self.zoom_in_button.clicked.connect(lambda: self.adjust_zoom(1.2))
        button_row.addWidget(self.zoom_in_button)

        self.zoom_out_button = QPushButton('Zoom Out', self)
        self.zoom_out_button.clicked.connect(lambda: self.adjust_zoom(1 / 1.2))
        button_row.addWidget(self.zoom_out_button)

        self.reset_zoom_button = QPushButton('Reset Zoom', self)
        self.reset_zoom_button.clicked.connect(self.reset_zoom)
        button_row.addWidget(self.reset_zoom_button)

        self.fit_button = QPushButton('Fit to Window', self)
        self.fit_button.clicked.connect(self.fit_to_window)
        button_row.addWidget(self.fit_button)

        self.open_button = QPushButton(PanelText.BUTTON_OPEN_EXTERNALLY, self)
        self.open_button.clicked.connect(self._open_externally)
        self.open_button.setEnabled(False)
        button_row.addWidget(self.open_button)

        clear_button = QPushButton(PanelText.BUTTON_CLEAR_PREVIEW_CACHE, self)
        clear_button.clicked.connect(self._handle_clear_clicked)
        button_row.addWidget(clear_button)

        button_row.addStretch(1)
        layout.addLayout(button_row)

        self.loading_overlay = QLabel('Loading...', self)
        self.loading_overlay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.loading_overlay.setStyleSheet(
            'background-color: rgba(0, 0, 0, 180); color: white; font-size: 16px;'
        )
        self.loading_overlay.hide()

        adapter = _GraphicsImageAdapter(self.graphics_view, self.graphics_item)
        self.controller = DeviceFilePreviewController(
            stack=self.stack,
            text_widget=self.text_widget,
            image_widget=image_frame,
            message_widget=self.message_widget,
            open_button=self.open_button,
            image_label=adapter,
        )

        if DeviceFilePreviewWindow.LAST_GEOMETRY:
            self.restoreGeometry(DeviceFilePreviewWindow.LAST_GEOMETRY)

        self._update_controls_enabled(False)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    @property
    def current_path(self) -> Optional[str]:
        return self.controller.current_path

    def set_metadata(self, *, device_label: str, remote_path: str) -> None:
        self.status_label.setText(f'{device_label} — {remote_path}')
        self.setWindowTitle(f'Device File Preview — {os.path.basename(remote_path)}')

    def display_preview(self, local_path: str) -> None:
        mode = self.controller.display_preview(local_path)
        self._current_zoom = 1.0
        self._update_controls_enabled(mode == 'image')
        if mode == 'image':
            self.fit_to_window()
        self.hide_loading()
        self.show()
        self.raise_()
        self.activateWindow()

    def clear_preview(self, *, cleanup: bool = True) -> None:
        path = self.controller.current_path
        self.controller.clear_preview()
        self._update_controls_enabled(False)
        if cleanup and self._cleanup_callback and path:
            self._cleanup_callback(path)
        self.hide_loading()

    def show_loading(self, message: str = 'Preparing preview...') -> None:
        self.loading_overlay.setText(message)
        self.loading_overlay.show()
        self.loading_overlay.raise_()
        self._update_overlay_geometry()

    def hide_loading(self) -> None:
        self.loading_overlay.hide()

    # ------------------------------------------------------------------
    # Zoom helpers
    # ------------------------------------------------------------------
    def adjust_zoom(self, factor: float) -> None:
        self._current_zoom *= factor
        self.graphics_view.scale(factor, factor)

    def reset_zoom(self) -> None:
        self.graphics_view.resetTransform()
        self._current_zoom = 1.0

    def fit_to_window(self) -> None:
        pixmap = self.graphics_item.pixmap()
        if pixmap.isNull():
            return
        self.graphics_view.fitInView(self.graphics_item, Qt.AspectRatioMode.KeepAspectRatio)
        self._current_zoom = 1.0

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _open_externally(self) -> None:
        path = self.controller.current_path
        if not path or not os.path.exists(path):
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(path))

    def _handle_clear_clicked(self) -> None:
        self.clear_preview()
        self.hide()

    def _update_controls_enabled(self, image_mode: bool) -> None:
        for button in (self.zoom_in_button, self.zoom_out_button, self.reset_zoom_button, self.fit_button):
            button.setEnabled(image_mode)

    def _update_overlay_geometry(self) -> None:
        if not self.loading_overlay.isVisible():
            return
        self.loading_overlay.setGeometry(0, 0, self.width(), self.height())

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._update_overlay_geometry()

    def moveEvent(self, event) -> None:  # pragma: no cover - updates geometry persistence
        super().moveEvent(event)
        DeviceFilePreviewWindow.LAST_GEOMETRY = self.saveGeometry()

    def closeEvent(self, event) -> None:  # pragma: no cover
        DeviceFilePreviewWindow.LAST_GEOMETRY = self.saveGeometry()
        path = self.controller.current_path
        super().closeEvent(event)
        if self._cleanup_callback and path:
            self._cleanup_callback(path)
        self.clear_preview(cleanup=False)


__all__ = ['DeviceFilePreviewWindow']
