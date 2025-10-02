"""Controller for device file preview widgets."""

from __future__ import annotations

import mimetypes
import os
from dataclasses import dataclass
from typing import Callable, Optional

from PyQt6.QtGui import QPixmap


@dataclass
class PreviewContent:
    mode: str
    payload: Optional[str] = None


class DeviceFilePreviewController:
    """Manage rendering of device file previews inside the UI."""

    PLACEHOLDER_MESSAGE = 'Select a file to preview.'
    UNSUPPORTED_MESSAGE = 'Preview not available for this file.'
    ERROR_MESSAGE = 'Failed to load preview.'
    TEXT_CHAR_LIMIT = 200_000

    def __init__(
        self,
        *,
        stack,
        text_widget,
        image_widget,
        message_widget,
        open_button,
        image_loader: Callable[[str], object] | None = None,
        image_label=None,
    ) -> None:
        self.stack = stack
        self.text_widget = text_widget
        self.image_widget = image_widget
        self.image_label = image_label or image_widget
        self.message_widget = message_widget
        self.open_button = open_button
        self.image_loader = image_loader or self._load_pixmap

        # Assign indices to allow tests and callers to inspect state.
        self.text_index = self.stack.addWidget(self.text_widget)
        self.image_index = self.stack.addWidget(self.image_widget)
        self.message_index = self.stack.addWidget(self.message_widget)

        self.current_path: Optional[str] = None
        self.last_mode: Optional[str] = None
        self.clear_preview()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def display_preview(self, local_path: str) -> None:
        """Render the supplied file inside the preview widgets."""
        self.current_path = local_path
        content = self._classify_content(local_path)

        self.last_mode = content.mode

        if content.mode == 'text' and content.payload is not None:
            self.text_widget.setPlainText(content.payload)
            self.stack.setCurrentWidget(self.text_widget)
            self.message_widget.setText('')
            self.open_button.setEnabled(True)
            return

        if content.mode == 'image':
            pixmap = self.image_loader(local_path)
            if hasattr(pixmap, 'isNull') and pixmap.isNull():
                self.show_message(self.ERROR_MESSAGE)
                self.open_button.setEnabled(bool(self.current_path))
                return
            self.image_label.setPixmap(pixmap)
            if hasattr(self.image_label, 'adjustSize'):
                self.image_label.adjustSize()
            self.stack.setCurrentWidget(self.image_widget)
            self.message_widget.setText('')
            self.open_button.setEnabled(True)
            return

        if content.mode == 'video':
            filename = os.path.basename(local_path)
            message = (
                f'Video detected: {filename}\n'
                'Use "Open Externally" to view playback.'
            )
            self.show_message(message)
            self.open_button.setEnabled(True)
            return

        # Unsupported fallback
        message = f'{self.UNSUPPORTED_MESSAGE}\n{os.path.basename(local_path)}'
        self.show_message(message)
        self.open_button.setEnabled(True if self.current_path else False)

    def clear_preview(self) -> None:
        """Reset the preview widgets to their default state."""
        self.text_widget.setPlainText('')
        if hasattr(self.image_label, 'clear'):
            self.image_label.clear()
        elif hasattr(self.image_label, 'setPixmap'):
            self.image_label.setPixmap(QPixmap())
        self.show_message(self.PLACEHOLDER_MESSAGE)
        self.open_button.setEnabled(False)
        self.current_path = None
        self.last_mode = None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def show_message(self, message: str) -> None:
        self.message_widget.setText(message)
        self.stack.setCurrentWidget(self.message_widget)

    def _load_pixmap(self, local_path: str) -> QPixmap:
        return QPixmap(local_path)

    def _classify_content(self, local_path: str) -> PreviewContent:
        # First handle obvious image types via mimetypes
        mime, _ = mimetypes.guess_type(local_path)
        if mime:
            if mime.startswith('image/'):
                return PreviewContent('image')
            if mime.startswith('video/'):
                return PreviewContent('video')

        # Attempt to read as UTF-8 text within the configured limit
        try:
            with open(local_path, 'rb') as fh:
                data = fh.read(self.TEXT_CHAR_LIMIT + 1)
        except OSError:
            return PreviewContent('unsupported')

        try:
            text = data.decode('utf-8')
        except UnicodeDecodeError:
            return PreviewContent('unsupported')

        if self._contains_binary_control_chars(text):
            return PreviewContent('unsupported')

        truncated = False
        if len(text) > self.TEXT_CHAR_LIMIT:
            text = text[: self.TEXT_CHAR_LIMIT]
            truncated = True

        if truncated:
            text = f"{text}\n… (truncated)"

        return PreviewContent('text', text)

    def _contains_binary_control_chars(self, text: str) -> bool:
        for char in text:
            if char in ('\n', '\r', '\t'):
                continue
            if ord(char) == 0 or ord(char) < 32:
                return True
        return False


__all__ = ['DeviceFilePreviewController']
