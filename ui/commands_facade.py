"""Facade for shell and batch command interactions in the main window."""

from __future__ import annotations

from typing import List, Optional, TYPE_CHECKING, Any

from PyQt6.QtGui import QTextCursor

if TYPE_CHECKING:  # pragma: no cover
    from ui.main_window import WindowMain
    from utils import adb_models


class CommandsFacade:
    """Encapsulates shell command execution and history operations."""

    def __init__(self, window: "WindowMain") -> None:
        self.window = window

    # Shell commands
    def run_shell_command(self) -> None:
        command = self.window.shell_cmd_edit.text().strip()
        devices = self.window.get_checked_devices()
        self.window.command_execution_manager.run_shell_command(command, devices)

    def add_template_command(self, command: str) -> None:
        self.window.command_execution_manager.add_template_command(command)

    def run_single_command(self) -> None:
        text = self.window.batch_commands_edit.toPlainText().strip()
        if not text:
            self.window.show_error('Error', 'Please enter commands in the batch area.')
            return

        cursor = self.window.batch_commands_edit.textCursor()
        current_line = cursor.blockNumber()

        lines = text.split('\n')
        if current_line < len(lines):
            command = lines[current_line].strip()
        else:
            command = lines[0].strip()

        if not command or command.startswith('#'):
            self.window.show_error('Error', 'Selected line is empty or a comment.')
            return

        self.execute_single_command(command)

    def run_batch_commands(self) -> None:
        commands = self.get_valid_commands()
        devices = self.window.get_checked_devices()
        self.window.command_execution_manager.execute_batch_commands(commands, devices)

    def execute_single_command(self, command: str) -> None:
        devices = self.window.get_checked_devices()
        self.window.command_execution_manager.execute_single_command(command, devices)

    # History
    def get_valid_commands(self) -> List[str]:
        text = self.window.batch_commands_edit.toPlainText().strip()
        return self.window.command_execution_manager.get_valid_commands_from_text(text)

    def add_to_history(self, command: str) -> None:
        self.window.command_history_manager.add_to_history(command)
        self.update_history_display()

    def update_history_display(self) -> None:
        self.window.command_history_list.clear()
        for command in reversed(self.window.command_history_manager.command_history):
            self.window.command_history_list.addItem(command)

    def load_from_history(self, item: Any) -> None:
        command = item.text()
        current_text = self.window.batch_commands_edit.toPlainText()
        new_text = (current_text + '\n' + command) if current_text else command
        self.window.batch_commands_edit.setPlainText(new_text)

    def clear_command_history(self) -> None:
        self.window.command_history_manager.clear_history()

    def export_command_history(self) -> None:
        self.window.command_history_manager.export_command_history()

    def import_command_history(self) -> None:
        self.window.command_history_manager.import_command_history()


__all__ = ["CommandsFacade"]
