"""Modern notification system with toast-style messages."""

from __future__ import annotations

from typing import Optional
from enum import Enum

from PyQt6.QtWidgets import QLabel, QGraphicsOpacityEffect, QWidget
from PyQt6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve, QPoint
from PyQt6.QtGui import QFont


class NotificationType(Enum):
    """Types of notifications."""
    SUCCESS = "success"
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


class ToastNotification(QLabel):
    """A toast-style notification widget."""

    # Color schemes for different notification types
    STYLES = {
        NotificationType.SUCCESS: {
            'bg': '#10b981',
            'fg': '#ffffff',
            'border': '#059669',
            'icon': '✓'
        },
        NotificationType.ERROR: {
            'bg': '#ef4444',
            'fg': '#ffffff',
            'border': '#dc2626',
            'icon': '✕'
        },
        NotificationType.WARNING: {
            'bg': '#f59e0b',
            'fg': '#ffffff',
            'border': '#d97706',
            'icon': '⚠'
        },
        NotificationType.INFO: {
            'bg': '#3b82f6',
            'fg': '#ffffff',
            'border': '#2563eb',
            'icon': 'ℹ'
        },
    }

    def __init__(
        self,
        parent: QWidget,
        message: str,
        notification_type: NotificationType = NotificationType.INFO,
        duration: int = 3000
    ):
        """
        Initialize a toast notification.

        Args:
            parent: Parent widget
            message: Message to display
            notification_type: Type of notification
            duration: Display duration in milliseconds
        """
        super().__init__(parent)

        self.notification_type = notification_type
        self.duration = duration
        self.is_visible = False

        # Set up the label
        style = self.STYLES[notification_type]
        icon = style['icon']

        self.setText(f"{icon}  {message}")
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setWordWrap(True)
        self.setMaximumWidth(400)
        self.setMinimumWidth(250)

        # Apply styling
        self.setStyleSheet(f"""
            QLabel {{
                background-color: {style['bg']};
                color: {style['fg']};
                border: 2px solid {style['border']};
                border-radius: 12px;
                padding: 16px 24px;
                font-size: 14px;
                font-weight: 600;
                box-shadow: 0 10px 25px rgba(0, 0, 0, 0.3);
            }}
        """)

        # Set up font
        font = QFont()
        font.setPointSize(11)
        font.setBold(True)
        self.setFont(font)

        # Set up opacity effect
        self.opacity_effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self.opacity_effect)
        self.opacity_effect.setOpacity(0.0)

        # Set up animations
        self.fade_in_animation = QPropertyAnimation(self.opacity_effect, b"opacity")
        self.fade_in_animation.setDuration(300)
        self.fade_in_animation.setStartValue(0.0)
        self.fade_in_animation.setEndValue(1.0)
        self.fade_in_animation.setEasingCurve(QEasingCurve.Type.OutCubic)

        self.fade_out_animation = QPropertyAnimation(self.opacity_effect, b"opacity")
        self.fade_out_animation.setDuration(300)
        self.fade_out_animation.setStartValue(1.0)
        self.fade_out_animation.setEndValue(0.0)
        self.fade_out_animation.setEasingCurve(QEasingCurve.Type.InCubic)
        self.fade_out_animation.finished.connect(self._on_fade_out_finished)

        # Set up auto-hide timer
        self.hide_timer = QTimer(self)
        self.hide_timer.timeout.connect(self.start_fade_out)
        self.hide_timer.setSingleShot(True)

        # Make it always on top
        self.setWindowFlags(Qt.WindowType.ToolTip | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        # Enable mouse interaction to dismiss
        self.mousePressEvent = lambda e: self.start_fade_out()

    def show_notification(self) -> None:
        """Show the notification with fade-in animation."""
        if self.is_visible:
            return

        self.is_visible = True

        # Position at top-center of parent
        self.adjustSize()
        parent_rect = self.parent().rect()
        x = (parent_rect.width() - self.width()) // 2
        y = 20  # 20px from top

        self.move(x, y)
        self.show()
        self.raise_()

        # Start fade-in animation
        self.fade_in_animation.start()

        # Start auto-hide timer
        self.hide_timer.start(self.duration)

    def start_fade_out(self) -> None:
        """Start fade-out animation."""
        if not self.is_visible:
            return

        self.hide_timer.stop()
        self.fade_out_animation.start()

    def _on_fade_out_finished(self) -> None:
        """Handle fade-out animation completion."""
        self.is_visible = False
        self.hide()
        self.deleteLater()


class NotificationManager:
    """Manages toast notifications for a window."""

    def __init__(self, parent_widget: QWidget):
        """
        Initialize the notification manager.

        Args:
            parent_widget: The parent widget (usually main window)
        """
        self.parent_widget = parent_widget
        self.active_notifications: list[ToastNotification] = []

    def show_success(self, message: str, duration: int = 3000) -> None:
        """Show a success notification."""
        self._show_notification(message, NotificationType.SUCCESS, duration)

    def show_error(self, message: str, duration: int = 4000) -> None:
        """Show an error notification."""
        self._show_notification(message, NotificationType.ERROR, duration)

    def show_warning(self, message: str, duration: int = 3500) -> None:
        """Show a warning notification."""
        self._show_notification(message, NotificationType.WARNING, duration)

    def show_info(self, message: str, duration: int = 3000) -> None:
        """Show an info notification."""
        self._show_notification(message, NotificationType.INFO, duration)

    def _show_notification(
        self,
        message: str,
        notification_type: NotificationType,
        duration: int
    ) -> None:
        """Internal method to create and show a notification."""
        # Clean up finished notifications
        self.active_notifications = [n for n in self.active_notifications if n.is_visible]

        # Calculate vertical offset for stacking
        y_offset = sum(n.height() + 10 for n in self.active_notifications)

        notification = ToastNotification(
            self.parent_widget,
            message,
            notification_type,
            duration
        )

        # Adjust position for stacking
        notification.show_notification()
        if y_offset > 0:
            current_pos = notification.pos()
            notification.move(current_pos.x(), current_pos.y() + y_offset)

        self.active_notifications.append(notification)

    def clear_all(self) -> None:
        """Clear all active notifications."""
        for notification in self.active_notifications:
            notification.start_fade_out()
        self.active_notifications.clear()


__all__ = ['NotificationManager', 'NotificationType', 'ToastNotification']
