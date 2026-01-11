#!/usr/bin/env python3
"""
Terminal-like widget for executing ADB shell commands and viewing output.
"""

from typing import List, Optional
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QTextEdit,
    QLineEdit,
    QLabel,
    QPushButton,
    QFrame,
    QSizePolicy,
)
from PyQt6.QtCore import pyqtSignal, Qt, QSize
from PyQt6.QtGui import QFont, QTextCursor, QColor, QKeyEvent

from ui.style_manager import StyleManager, ButtonStyle


class TerminalWidget(QWidget):
    """
    A modern terminal/console widget for ADB commands.
    Features a REPL-style layout with output area and input line.
    """

    command_submitted = pyqtSignal(str)  # Emits the raw command string

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()
        self._apply_styles()
        self._show_welcome_message()

    def _show_welcome_message(self):
        """Show initial welcome message with instructions"""
        welcome_color = "#00d9ff"  # Cyan
        cursor = self.output_area.textCursor()

        banner = "═" * 50
        self._insert_text(cursor, banner + "\n", welcome_color)
        self._insert_text(
            cursor, " LAZY BLACKTEA ADB SHELL TERMINAL\n", welcome_color, bold=True
        )
        self._insert_text(cursor, banner + "\n", welcome_color)

        instructions = [
            "• Execution: Commands run on ALL selected devices",
            "• Shortcuts: Press Enter to execute, Ctrl+C to clear input",
            "• History: Use Up/Down arrows to navigate previous commands",
            "• Quick: Use buttons above for common templates",
        ]

        for line in instructions:
            self._insert_text(cursor, line + "\n", "#888")

        self._insert_text(cursor, "\nReady for commands...\n\n", "#555")

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 1. Output area
        self.output_area = QTextEdit()
        self.output_area.setObjectName("terminalOutput")
        self.output_area.setReadOnly(True)
        self.output_area.setUndoRedoEnabled(False)
        self.output_area.setAcceptRichText(True)
        self.output_area.setMinimumHeight(200)

        # Set monospace font
        font = QFont("Consolas", 10)
        if not font.fixedPitch():
            font = QFont("Monaco", 10)
        if not font.fixedPitch():
            font = QFont("Courier New", 10)
        font.setStyleHint(QFont.StyleHint.Monospace)
        self.output_area.setFont(font)

        layout.addWidget(self.output_area, stretch=1)

        # 2. Separator line
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setFrameShadow(QFrame.Shadow.Plain)
        separator.setLineWidth(1)
        separator.setObjectName("terminalSeparator")
        layout.addWidget(separator)

        # 3. Input area
        input_container = QWidget()
        input_container.setObjectName("inputContainer")
        input_layout = QHBoxLayout(input_container)
        input_layout.setContentsMargins(8, 4, 8, 4)
        input_layout.setSpacing(4)

        self.prompt_label = QLabel("> ")
        self.prompt_label.setObjectName("promptLabel")
        self.prompt_label.setFont(font)

        self.input_line = QLineEdit()
        self.input_line.setObjectName("terminalInput")
        self.input_line.setFont(font)
        self.input_line.setPlaceholderText(
            "Enter ADB command (e.g., adb shell pm list packages)"
        )
        self.input_line.setFrame(False)
        self.input_line.returnPressed.connect(self._on_command_entered)

        # Install event filter to catch Ctrl+C
        self.input_line.installEventFilter(self)

        input_layout.addWidget(self.prompt_label)
        input_layout.addWidget(self.input_line, stretch=1)
        layout.addWidget(input_container)

        # 4. Toolbar
        toolbar_container = QWidget()
        toolbar_container.setObjectName("toolbarContainer")
        toolbar_layout = QHBoxLayout(toolbar_container)
        toolbar_layout.setContentsMargins(8, 2, 8, 2)

        self.device_count_label = QLabel("0 devices ready")
        self.device_count_label.setObjectName("deviceCountLabel")

        self.clear_button = QPushButton("Clear")
        self.clear_button.setFixedWidth(60)
        self.clear_button.clicked.connect(self.clear_output)
        StyleManager.apply_button_style(
            self.clear_button,
            ButtonStyle.NEUTRAL,
            fixed_height=24,
        )
        # Re-apply some terminal-specific styling to the button if needed
        self.clear_button.setStyleSheet(
            self.clear_button.styleSheet()
            + """
            QPushButton {
                font-size: 10px;
                padding: 2px 4px;
            }
        """
        )

        toolbar_layout.addWidget(self.device_count_label)
        toolbar_layout.addStretch(1)
        toolbar_layout.addWidget(self.clear_button)
        layout.addWidget(toolbar_container)

    def _apply_styles(self):
        base_style = StyleManager.get_terminal_style()

        colors = StyleManager.COLORS
        bg = colors.get("terminal_background", "#1a1a2e")
        text = colors.get("terminal_text", "#e0e0e0")
        border = colors.get("terminal_border", "#3A4052")
        input_bg = colors.get("terminal_input_bg", "#22223b")
        prompt_color = colors.get("terminal_prompt", "#00d9ff")

        widget_style = f"""
            TerminalWidget {{
                background-color: {bg};
            }}
            QTextEdit#terminalOutput {{
                background-color: {bg};
                color: {text};
                border: none;
                padding: 12px;
                selection-background-color: #44475a;
                selection-color: #f8f8f2;
            }}
            #terminalSeparator {{
                background-color: {border};
                min-height: 1px;
                max-height: 1px;
            }}
            #inputContainer {{
                background-color: {input_bg};
                border-top: 1px solid {border};
                padding: 4px;
            }}
            #terminalInput {{
                background-color: transparent;
                color: {text};
                padding: 8px 4px;
            }}
            #promptLabel {{
                color: {prompt_color};
                font-weight: bold;
                padding-left: 8px;
            }}
            #toolbarContainer {{
                background-color: {bg};
                border-top: 1px solid {border};
            }}
        """
        self.setStyleSheet(base_style + widget_style)

    def eventFilter(self, obj, event):
        if obj is self.input_line and event.type() == event.Type.KeyPress:
            key_event = QKeyEvent(event)
            if (
                key_event.key() == Qt.Key.Key_C
                and key_event.modifiers() == Qt.KeyboardModifier.ControlModifier
            ):
                self.input_line.clear()
                return True
        return super().eventFilter(obj, event)

    def _on_command_entered(self):
        command = self.input_line.text().strip()
        if command:
            self.command_submitted.emit(command)
            self.input_line.clear()

    def append_output(
        self,
        device_serial: str,
        device_name: str,
        output_lines: List[str],
        is_error: bool = False,
    ):
        """Append output for a specific device in its own visual block"""
        header_color = "#4fc3f7"  # Cyan
        error_color = "#ff6b6b"  # Red/Orange

        # Build the block
        header = f"┌─ [Device: {device_name} ({device_serial})] "
        padding_len = max(0, 60 - len(header))
        header += "─" * padding_len

        footer = "└" + "─" * (len(header) - 1)

        cursor = self.output_area.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)

        # Insert Header
        self._insert_text(cursor, header + "\n", header_color, bold=True)

        # Insert Body
        text_color = error_color if is_error else "#e0e0e0"
        for line in output_lines:
            self._insert_text(cursor, f"│ {line}\n", text_color)

        # Insert Footer
        self._insert_text(cursor, footer + "\n\n", header_color)

        # Auto-scroll
        self.output_area.verticalScrollBar().setValue(
            self.output_area.verticalScrollBar().maximum()
        )

    def append_system_message(self, message: str):
        """Append a system/status message (not device-specific)"""
        system_color = StyleManager.COLORS.get("text_hint", "#888")
        cursor = self.output_area.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self._insert_text(cursor, f"[*] {message}\n", system_color, italic=True)

        self.output_area.verticalScrollBar().setValue(
            self.output_area.verticalScrollBar().maximum()
        )

    def _insert_text(
        self,
        cursor: QTextCursor,
        text: str,
        color: str,
        bold: bool = False,
        italic: bool = False,
    ):
        fmt = cursor.charFormat()
        fmt.setForeground(QColor(color))
        if bold:
            fmt.setFontWeight(QFont.Weight.Bold)
        else:
            fmt.setFontWeight(QFont.Weight.Normal)
        fmt.setFontItalic(italic)
        cursor.insertText(text, fmt)

    def clear_output(self):
        """Clear all output"""
        self.output_area.clear()

    def set_input_enabled(self, enabled: bool):
        """Enable/disable input while commands are running"""
        self.input_line.setEnabled(enabled)
        if enabled:
            self.input_line.setFocus()
            self.input_line.setPlaceholderText(
                "Enter ADB command (e.g., adb shell pm list packages)"
            )
        else:
            self.input_line.setPlaceholderText("Executing command...")

    def update_device_count(self, count: int):
        """Update the device count indicator in the toolbar"""
        self.device_count_label.setText(f"{count} devices ready")
