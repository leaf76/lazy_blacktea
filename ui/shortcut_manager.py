"""Keyboard Shortcut Manager - Centralized shortcut management for the application."""

from __future__ import annotations

from typing import TYPE_CHECKING, Dict, Callable, Optional
from PyQt6.QtGui import QKeySequence, QShortcut
from PyQt6.QtCore import Qt

if TYPE_CHECKING:  # pragma: no cover
    from PyQt6.QtWidgets import QWidget


class ShortcutManager:
    """Manages keyboard shortcuts for the application."""

    def __init__(self, parent_widget: QWidget):
        """
        Initialize the shortcut manager.

        Args:
            parent_widget: The parent widget (usually main window) to attach shortcuts to
        """
        self.parent_widget = parent_widget
        self.shortcuts: Dict[str, QShortcut] = {}
        self._enabled = True

    def register_shortcut(
        self,
        key_sequence: str,
        callback: Callable,
        description: str = "",
        context: Qt.ShortcutContext = Qt.ShortcutContext.WindowShortcut
    ) -> Optional[QShortcut]:
        """
        Register a keyboard shortcut.

        Args:
            key_sequence: The key sequence (e.g., 'Ctrl+S', 'Ctrl+Shift+R')
            callback: The function to call when the shortcut is activated
            description: Human-readable description of the shortcut
            context: The context in which the shortcut is active

        Returns:
            The created QShortcut object, or None if registration failed
        """
        try:
            shortcut = QShortcut(QKeySequence(key_sequence), self.parent_widget)
            shortcut.setContext(context)
            shortcut.activated.connect(callback)
            shortcut.setEnabled(self._enabled)

            # Store with description for documentation
            shortcut_id = f"{key_sequence}_{id(callback)}"
            self.shortcuts[shortcut_id] = shortcut

            # Store metadata as property
            shortcut.setProperty('description', description)
            shortcut.setProperty('key_sequence', key_sequence)

            return shortcut
        except Exception as e:
            print(f"Failed to register shortcut {key_sequence}: {e}")
            return None

    def unregister_shortcut(self, key_sequence: str, callback: Callable) -> bool:
        """
        Unregister a keyboard shortcut.

        Args:
            key_sequence: The key sequence to unregister
            callback: The callback function

        Returns:
            True if successfully unregistered, False otherwise
        """
        shortcut_id = f"{key_sequence}_{id(callback)}"
        if shortcut_id in self.shortcuts:
            shortcut = self.shortcuts[shortcut_id]
            shortcut.setEnabled(False)
            shortcut.activated.disconnect(callback)
            del self.shortcuts[shortcut_id]
            return True
        return False

    def enable_all(self) -> None:
        """Enable all registered shortcuts."""
        self._enabled = True
        for shortcut in self.shortcuts.values():
            shortcut.setEnabled(True)

    def disable_all(self) -> None:
        """Disable all registered shortcuts."""
        self._enabled = False
        for shortcut in self.shortcuts.values():
            shortcut.setEnabled(False)

    def get_shortcuts_help(self) -> str:
        """
        Get a formatted help string listing all registered shortcuts.

        Returns:
            Formatted string with all shortcuts and their descriptions
        """
        if not self.shortcuts:
            return "No keyboard shortcuts registered."

        lines = ["Keyboard Shortcuts:", "=" * 50]
        for shortcut in self.shortcuts.values():
            key_seq = shortcut.property('key_sequence')
            description = shortcut.property('description') or 'No description'
            lines.append(f"{key_seq:20} - {description}")

        return "\n".join(lines)

    def clear_all(self) -> None:
        """Remove all registered shortcuts."""
        for shortcut in self.shortcuts.values():
            shortcut.setEnabled(False)
            try:
                shortcut.activated.disconnect()
            except:
                pass
        self.shortcuts.clear()


def register_tool_shortcuts(shortcut_manager: ShortcutManager, window) -> None:
    """
    Register all tool-related keyboard shortcuts.

    Args:
        shortcut_manager: The ShortcutManager instance
        window: The main window instance with tool action handlers
    """
    # Screen Capture shortcuts
    shortcut_manager.register_shortcut(
        'Ctrl+S',
        lambda: window.handle_tool_action('screenshot'),
        'Take a screenshot of the device screen'
    )

    shortcut_manager.register_shortcut(
        'Ctrl+R',
        lambda: window.handle_tool_action('record_start'),
        'Start screen recording'
    )

    shortcut_manager.register_shortcut(
        'Ctrl+Shift+R',
        lambda: window.handle_tool_action('record_stop'),
        'Stop screen recording'
    )

    # Navigation shortcuts
    shortcut_manager.register_shortcut(
        'Ctrl+H',
        lambda: window.handle_tool_action('home'),
        'Navigate to device home screen'
    )

    # Installation shortcuts
    shortcut_manager.register_shortcut(
        'Ctrl+I',
        lambda: window.handle_tool_action('install_apk'),
        'Install APK file'
    )

    # Device mirroring
    shortcut_manager.register_shortcut(
        'Ctrl+M',
        lambda: window.handle_tool_action('launch_scrcpy'),
        'Launch scrcpy for device mirroring'
    )

    # Refresh device list
    shortcut_manager.register_shortcut(
        'F5',
        lambda: window.load_devices() if hasattr(window, 'load_devices') else None,
        'Refresh device list'
    )

    # Tab navigation
    shortcut_manager.register_shortcut(
        'Ctrl+1',
        lambda: _switch_to_tab(window, 0),
        'Switch to Device Overview tab'
    )

    shortcut_manager.register_shortcut(
        'Ctrl+2',
        lambda: _switch_to_tab(window, 1),
        'Switch to ADB Tools tab'
    )

    shortcut_manager.register_shortcut(
        'Ctrl+3',
        lambda: _switch_to_tab(window, 2),
        'Switch to Shell Commands tab'
    )

    shortcut_manager.register_shortcut(
        'Ctrl+4',
        lambda: _switch_to_tab(window, 3),
        'Switch to Device Files tab'
    )

    shortcut_manager.register_shortcut(
        'Ctrl+5',
        lambda: _switch_to_tab(window, 4),
        'Switch to Device Groups tab'
    )

    shortcut_manager.register_shortcut(
        'Ctrl+6',
        lambda: _switch_to_tab(window, 5),
        'Switch to Apps tab'
    )


def _switch_to_tab(window, tab_index: int) -> None:
    """Helper function to switch to a specific tab."""
    try:
        # Find the tab widget
        tab_widgets = window.findChildren(window.__class__.__bases__[0])
        for widget in window.findChildren(widget.__class__):
            if hasattr(widget, 'setCurrentIndex'):
                widget.setCurrentIndex(tab_index)
                break
    except Exception as e:
        print(f"Failed to switch to tab {tab_index}: {e}")


__all__ = ['ShortcutManager', 'register_tool_shortcuts']
