"""Command execution module for handling ADB commands."""

import logging
import threading
from typing import List, Callable, Dict
from PyQt6.QtCore import QTimer, pyqtSignal, QObject

from utils import adb_models, adb_tools, common

logger = common.get_logger('command_executor')


def ensure_devices_selected(func):
    """Decorator to ensure devices are selected before executing commands."""
    def wrapper(self, *args, **kwargs):
        if not hasattr(self, 'get_checked_devices') or not self.get_checked_devices():
            if hasattr(self, 'show_warning'):
                self.show_warning('No Devices Selected', 'Please select at least one device first.')
            return
        return func(self, *args, **kwargs)
    return wrapper


class CommandExecutor(QObject):
    """Handles command execution and management."""

    # Signals for thread-safe communication
    command_completed = pyqtSignal(str, list, object)  # command, serials, results
    command_failed = pyqtSignal(str, str)  # command, error_message

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        self.command_history: List[str] = []
        self.max_history_size = 50

    def execute_single_command(self, command: str, devices: List[adb_models.DeviceInfo],
                             callback: Callable = None):
        """Execute a single command on selected devices."""
        if not command.strip():
            logger.warning('Empty command provided')
            return

        serials = [d.device_serial_num for d in devices]
        device_count = len(devices)

        logger.info(f'🚀 Starting command execution: "{command}" on {device_count} device(s)')

        # Add to history
        self.add_to_history(command)

        def shell_wrapper():
            try:
                def log_results(results):
                    if callback:
                        callback(command, serials, results)
                    self.command_completed.emit(command, serials, results)

                adb_tools.run_adb_shell_command(serials, command, callback=log_results)
            except Exception as e:
                error_msg = f'Command failed: {command} - {e}'
                logger.error(error_msg)
                self.command_failed.emit(command, str(e))

        self.run_in_thread(shell_wrapper)

    def execute_batch_commands(self, commands: List[str], devices: List[adb_models.DeviceInfo],
                             callback: Callable = None):
        """Execute multiple commands simultaneously on selected devices."""
        if not commands:
            logger.warning('No commands provided for batch execution')
            return

        serials = [d.device_serial_num for d in devices]
        device_count = len(devices)

        logger.info(f'🚀 Starting batch execution: {len(commands)} commands on {device_count} device(s)')

        for command in commands:
            self.add_to_history(command)

            def shell_wrapper(cmd=command):
                try:
                    def log_results(results):
                        if callback:
                            callback(cmd, serials, results)
                        self.command_completed.emit(cmd, serials, results)

                    adb_tools.run_adb_shell_command(serials, cmd, callback=log_results)
                except Exception as e:
                    error_msg = f'Command failed: {cmd} - {e}'
                    logger.error(error_msg)
                    self.command_failed.emit(cmd, str(e))

            self.run_in_thread(shell_wrapper)

    def run_in_thread(self, func: Callable):
        """Execute function in a separate thread."""
        thread = threading.Thread(target=func, daemon=True)
        thread.start()

    def add_to_history(self, command: str):
        """Add command to history."""
        if command not in self.command_history:
            self.command_history.append(command)
            # Keep only last N commands
            if len(self.command_history) > self.max_history_size:
                self.command_history = self.command_history[-self.max_history_size:]
            logger.info(f'Added command to history: {command}')

    def get_command_history(self) -> List[str]:
        """Get command history."""
        return self.command_history.copy()

    def clear_command_history(self):
        """Clear command history."""
        self.command_history.clear()
        logger.info('Command history cleared')

    def set_command_history(self, history: List[str]):
        """Set command history."""
        self.command_history = history[-self.max_history_size:] if history else []
        logger.info(f'Command history set with {len(self.command_history)} commands')

    def get_valid_commands(self, text: str) -> List[str]:
        """Parse and validate commands from text input."""
        if not text.strip():
            return []

        commands = []
        lines = text.split('\n')

        for line in lines:
            line = line.strip()
            # Skip empty lines and comments
            if line and not line.startswith('#'):
                commands.append(line)

        return commands


class CommandHistoryManager:
    """Manages command history persistence."""

    def __init__(self, config_manager):
        self.config_manager = config_manager
        self.logger = common.get_logger('command_history')

    def save_history(self, history: List[str]):
        """Save command history to config."""
        try:
            config_data = self.config_manager.load_config()
            config_data['command_history'] = history
            self.config_manager.save_config(config_data)
            self.logger.info(f'Command history saved ({len(history)} commands)')
        except Exception as e:
            self.logger.warning(f'Failed to save command history: {e}')

    def load_history(self) -> List[str]:
        """Load command history from config."""
        try:
            config_data = self.config_manager.load_config()
            history = config_data.get('command_history', [])
            self.logger.info(f'Command history loaded ({len(history)} commands)')
            return history[-50:]  # Keep only last 50
        except Exception as e:
            self.logger.warning(f'Failed to load command history: {e}')
            return []

    def export_history(self, filepath: str, history: List[str]):
        """Export command history to file."""
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write('# ADB Command History\n')
                f.write(f'# Generated: {common.timestamp_time()}\n\n')
                for command in history:
                    f.write(f'{command}\n')
            self.logger.info(f'Command history exported to: {filepath}')
        except Exception as e:
            self.logger.error(f'Failed to export history: {e}')
            raise

    def import_history(self, filepath: str) -> List[str]:
        """Import command history from file."""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                lines = f.readlines()

            commands = []
            for line in lines:
                line = line.strip()
                # Skip empty lines and comments
                if line and not line.startswith('#'):
                    commands.append(line)

            self.logger.info(f'Command history imported from: {filepath} ({len(commands)} commands)')
            return commands
        except Exception as e:
            self.logger.error(f'Failed to import history: {e}')
            raise