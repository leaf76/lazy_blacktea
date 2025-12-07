"""Lightweight non-blocking toast notification widget.

Provides temporary, auto-dismissing notification overlays similar to
Android toasts or macOS notification banners.
"""

from typing import Optional
import logging

from PyQt6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve
from PyQt6.QtWidgets import QLabel, QWidget, QVBoxLayout, QGraphicsOpacityEffect

logger = logging.getLogger(__name__)


class ToastNotification(QWidget):
    """Non-blocking toast notification overlay.

    Displays a temporary message at the bottom of the parent widget
    that automatically fades out after a configurable duration.

    Usage:
        toast = ToastNotification(parent=self)
        toast.show_toast("Operation completed!", style=ToastNotification.STYLE_INFO)
    """

    STYLE_INFO = "info"
    STYLE_WARNING = "warning"
    STYLE_ERROR = "error"
    STYLE_SUCCESS = "success"

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        duration_ms: int = 3000,
    ) -> None:
        super().__init__(parent)
        self._duration_ms = duration_ms
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._fade_out)
        self._anim: Optional[QPropertyAnimation] = None
        self._init_ui()

    def _init_ui(self) -> None:
        """Initialize the toast UI components."""
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._label = QLabel()
        self._label.setWordWrap(True)
        self._label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._label.setMinimumWidth(200)
        self._label.setMaximumWidth(500)
        layout.addWidget(self._label)

        self._opacity = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self._opacity)

        self.hide()

    def show_toast(
        self,
        message: str,
        style: str = STYLE_INFO,
        duration_ms: Optional[int] = None,
    ) -> None:
        """Display the toast notification.

        Args:
            message: Text to display
            style: Visual style (STYLE_INFO, STYLE_WARNING, STYLE_ERROR, STYLE_SUCCESS)
            duration_ms: Override default duration, or None for default
        """
        # Cancel any ongoing animation
        if self._anim is not None:
            self._anim.stop()
            self._anim = None

        self._timer.stop()
        self._apply_style(style)
        self._label.setText(message)
        self._position_toast()

        self._opacity.setOpacity(1.0)
        self.show()
        self.raise_()

        timeout = duration_ms if duration_ms is not None else self._duration_ms
        self._timer.start(timeout)

    def _apply_style(self, style: str) -> None:
        """Apply visual style to the toast."""
        colors = {
            self.STYLE_INFO: ("#1f618d", "#d4e6f1"),
            self.STYLE_WARNING: ("#9a7d0a", "#fcf3cf"),
            self.STYLE_ERROR: ("#922b21", "#f5b7b1"),
            self.STYLE_SUCCESS: ("#1d8348", "#d4efdf"),
        }
        fg, bg = colors.get(style, colors[self.STYLE_INFO])

        self._label.setStyleSheet(f"""
            QLabel {{
                background-color: {bg};
                color: {fg};
                padding: 12px 20px;
                border-radius: 8px;
                font-size: 13px;
                font-weight: 500;
            }}
        """)

    def _position_toast(self) -> None:
        """Position toast at bottom center of parent widget."""
        parent = self.parentWidget()
        if parent is None:
            return

        self.adjustSize()
        parent_rect = parent.rect()
        x = (parent_rect.width() - self.width()) // 2
        y = parent_rect.height() - self.height() - 40
        self.move(max(10, x), max(10, y))

    def _fade_out(self) -> None:
        """Animate fade-out before hiding."""
        self._anim = QPropertyAnimation(self._opacity, b"opacity")
        self._anim.setDuration(300)
        self._anim.setStartValue(1.0)
        self._anim.setEndValue(0.0)
        self._anim.setEasingCurve(QEasingCurve.Type.OutQuad)
        self._anim.finished.connect(self._on_fade_complete)
        self._anim.start()

    def _on_fade_complete(self) -> None:
        """Hide widget after fade animation completes."""
        self.hide()
        self._anim = None

    def dismiss(self) -> None:
        """Immediately dismiss the toast."""
        self._timer.stop()
        if self._anim is not None:
            self._anim.stop()
            self._anim = None
        self.hide()
