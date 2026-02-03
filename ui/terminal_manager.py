#!/usr/bin/env python3
"""
Terminal Manager - Handles ADB command parsing, execution, and result display.

This module is responsible for:
1. Parsing user-entered ADB commands
2. Executing commands on selected devices in parallel
3. Routing output to the TerminalWidget
4. Managing command history
"""

import re
import shlex
import subprocess
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple
from PyQt6.QtCore import QObject, pyqtSignal, QTimer

from utils import adb_models, adb_tools, common
from utils.task_dispatcher import TaskCancelledError, TaskContext, TaskHandle, get_task_dispatcher

logger = common.get_logger("terminal_manager")


@dataclass
class ParsedCommand:
    """Represents a parsed ADB command."""

    original: str
    command_type: str  # 'shell', 'push', 'pull', 'install', 'other'
    shell_command: Optional[str] = None  # The actual shell command to run
    target_serial: Optional[str] = None  # -s specified serial (if any)
    args: List[str] = None  # Additional arguments

    def __post_init__(self):
        if self.args is None:
            self.args = []


class ADBCommandParser:
    """Parses ADB commands to extract the shell command portion."""

    # Regex to match various ADB command patterns
    # Examples:
    #   adb shell pm list packages
    #   adb -s SERIAL shell getprop
    #   adb -s SERIAL shell "complex command with spaces"
    ADB_PATTERN = re.compile(
        r"^(?:adb\s+)?"  # Optional 'adb ' prefix
        r"(?:-s\s+(\S+)\s+)?"  # Optional -s SERIAL
        r"(shell|push|pull|install|uninstall|logcat|forward|reverse|devices|"
        r"connect|disconnect|reboot|root|unroot|remount|bugreport|"
        r"get-state|get-serialno|wait-for-device)\s*"  # ADB subcommand
        r"(.*)$",  # Rest of the command
        re.IGNORECASE,
    )

    @classmethod
    def parse(cls, command: str) -> ParsedCommand:
        """Parse an ADB command string.

        Args:
            command: Raw command string from user input

        Returns:
            ParsedCommand with parsed components
        """
        command = command.strip()

        # Try to match ADB pattern
        match = cls.ADB_PATTERN.match(command)

        if match:
            serial = match.group(1)
            cmd_type = match.group(2).lower()
            rest = match.group(3).strip()

            return ParsedCommand(
                original=command,
                command_type=cmd_type,
                shell_command=rest if cmd_type == "shell" else None,
                target_serial=serial,
                args=shlex.split(rest) if rest and cmd_type != "shell" else [],
            )

        # If no match, treat the entire command as a shell command
        # (user might have entered just "pm list packages")
        return ParsedCommand(
            original=command,
            command_type="shell",
            shell_command=command,
            target_serial=None,
            args=[],
        )

    @classmethod
    def is_shell_command(cls, parsed: ParsedCommand) -> bool:
        """Check if the command should be executed via adb shell."""
        return parsed.command_type == "shell" and parsed.shell_command


class TerminalManager(QObject):
    """Manages terminal command execution and output routing."""

    # Signals
    output_ready = pyqtSignal(str, str, list, bool)  # serial, name, lines, is_error
    system_message = pyqtSignal(str)  # message
    execution_started = pyqtSignal()
    execution_finished = pyqtSignal()
    device_count_changed = pyqtSignal(int)  # count

    def __init__(self, parent_window):
        super().__init__()
        self.parent_window = parent_window
        self._dispatcher = get_task_dispatcher()
        self._active_handles: List[TaskHandle] = []
        self._run_seq: int = 0
        self._active_run_id: Optional[int] = None
        self._command_history: List[str] = []
        self._history_index: int = -1
        self._max_history: int = 100
        self._parser = ADBCommandParser()
        self._is_executing: bool = False

    @property
    def is_executing(self) -> bool:
        return self._is_executing

    def execute_command(self, raw_command: str) -> None:
        """Execute a command on all selected devices.

        Args:
            raw_command: The raw command string from user input
        """
        if not raw_command.strip():
            return

        if self._is_executing:
            self.system_message.emit(
                "A command is already executing. Cancel it before starting a new one."
            )
            return

        # Get selected devices
        devices = self._get_selected_devices()
        if not devices:
            self.system_message.emit(
                "No devices selected. Please select at least one device."
            )
            return

        # Add to history
        self._add_to_history(raw_command)

        # Parse the command
        parsed = self._parser.parse(raw_command)

        if not ADBCommandParser.is_shell_command(parsed):
            self.system_message.emit(
                f"Command type '{parsed.command_type}' is not yet supported in terminal mode. "
                f"Please use shell commands (e.g., 'adb shell pm list packages')."
            )
            return

        shell_cmd = parsed.shell_command
        if not shell_cmd:
            self.system_message.emit("Empty shell command. Nothing to execute.")
            return

        # Log execution start
        device_count = len(devices)
        serials = [d.device_serial_num for d in devices]
        logger.info(
            f'Terminal executing "{shell_cmd}" on {device_count} device(s): {serials}'
        )

        self.system_message.emit(f"Executing on {device_count} device(s): {shell_cmd}")
        self._is_executing = True
        self.execution_started.emit()

        self._run_seq += 1
        run_id = self._run_seq
        self._active_run_id = run_id

        # Execute on each device
        context = TaskContext(name="terminal_shell", category="terminal")
        handle = self._dispatcher.submit(
            self._execute_shell_on_devices,
            devices,
            shell_cmd,
            context=context,
        )

        handle.completed.connect(
            lambda payload, rid=run_id: self._on_execution_completed(shell_cmd, payload, rid)
        )
        handle.failed.connect(lambda exc, rid=run_id: self._on_execution_failed(shell_cmd, exc, rid))
        handle.finished.connect(lambda h=handle: self._cleanup_handle(h))
        self._active_handles.append(handle)

    def _execute_shell_on_devices(
        self,
        devices: List[adb_models.DeviceInfo],
        shell_cmd: str,
        *,
        task_handle: Optional[TaskHandle] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute shell command on devices and collect results.

        This runs in a background thread.
        """
        results: Dict[str, Any] = {}
        serials = [d.device_serial_num for d in devices]

        # Use the cancellable command runner
        processes_by_serial = adb_tools.run_cancellable_adb_shell_command(serials, shell_cmd)
        processes = [p for p in processes_by_serial.values() if p is not None]

        if task_handle and task_handle.is_cancelled():
            self._terminate_processes(processes)
            raise TaskCancelledError("Operation cancelled")

        for device in devices:
            serial = device.device_serial_num
            name = device.device_model or serial
            process = processes_by_serial.get(serial)

            if process is None:
                results[serial] = {
                    "name": name,
                    "lines": ["Failed to start adb process"],
                    "is_error": True,
                }
                continue

            try:
                stdout, stderr = self._collect_process_output(
                    process,
                    task_handle,
                    overall_timeout=60.0,
                )

                lines = []
                is_error = False

                if stdout:
                    if isinstance(stdout, bytes):
                        lines.extend(
                            stdout.decode("utf-8", errors="replace").splitlines()
                        )
                    else:
                        lines.extend(str(stdout).splitlines())

                if stderr:
                    is_error = True
                    if isinstance(stderr, bytes):
                        lines.extend(
                            stderr.decode("utf-8", errors="replace").splitlines()
                        )
                    else:
                        lines.extend(str(stderr).splitlines())

                if process.returncode != 0 and not lines:
                    lines = [f"Command exited with code {process.returncode}"]
                    is_error = True

                results[serial] = {
                    "name": name,
                    "lines": lines if lines else ["(no output)"],
                    "is_error": is_error,
                }

            except TaskCancelledError:
                self._terminate_processes(processes)
                raise
            except subprocess.TimeoutExpired:
                results[serial] = {
                    "name": name,
                    "lines": ["Error: command timed out"],
                    "is_error": True,
                }
            except OSError as exc:
                results[serial] = {
                    "name": name,
                    "lines": [f"Error: {str(exc)}"],
                    "is_error": True,
                }
            except Exception as exc:
                logger.exception("Terminal command error on %s: %s", serial, exc)
                results[serial] = {
                    "name": name,
                    "lines": [f"Error: {str(exc)}"],
                    "is_error": True,
                }

        return {"results": results}

    def _on_execution_completed(self, shell_cmd: str, payload: Any, run_id: int) -> None:
        """Handle successful command execution."""
        if self._active_run_id != run_id:
            return

        results = payload.get("results", {}) if isinstance(payload, dict) else {}

        for serial, data in results.items():
            # Emit signal to update terminal output
            QTimer.singleShot(
                0,
                lambda s=serial, d=data: self.output_ready.emit(
                    s, d["name"], d["lines"], d["is_error"]
                ),
            )

        QTimer.singleShot(
            0, lambda: self.system_message.emit(f"Completed: {shell_cmd}")
        )
        self._active_run_id = None
        self._is_executing = False
        QTimer.singleShot(0, self.execution_finished.emit)

    def _on_execution_failed(self, shell_cmd: str, exc: Exception, run_id: int) -> None:
        if self._active_run_id != run_id:
            return

        if isinstance(exc, TaskCancelledError):
            logger.info('Terminal command cancelled: %s', shell_cmd)
            error_msg = f"Cancelled: {shell_cmd}"
        else:
            error_msg = f"Execution failed: {str(exc)}"
            logger.error(f"Terminal command failed: {shell_cmd} - {exc}")

        QTimer.singleShot(0, lambda: self.system_message.emit(error_msg))
        self._active_run_id = None
        self._is_executing = False
        QTimer.singleShot(0, self.execution_finished.emit)

    def cancel_all(self) -> None:
        if not self._active_handles:
            return

        for handle in list(self._active_handles):
            handle.cancel()

        self._active_run_id = None
        self._is_executing = False
        self.system_message.emit("Cancellation requested.")
        self.execution_finished.emit()

    def _cleanup_handle(self, handle: TaskHandle) -> None:
        try:
            self._active_handles.remove(handle)
        except ValueError:
            return

    @staticmethod
    def _request_process_termination(process: subprocess.Popen) -> None:
        if process.poll() is not None:
            return
        try:
            process.terminate()
        except Exception as exc:
            logger.debug("Failed to terminate process %s: %s", getattr(process, "pid", "?"), exc)

    @staticmethod
    def _force_kill_process(process: subprocess.Popen, *, timeout: float) -> None:
        if process.poll() is not None:
            return
        TerminalManager._request_process_termination(process)
        try:
            process.wait(timeout=timeout)
            return
        except subprocess.TimeoutExpired:
            pass

        try:
            process.kill()
        except Exception as exc:
            logger.debug("Failed to kill process %s: %s", getattr(process, "pid", "?"), exc)

    @staticmethod
    def _terminate_processes(processes: List[subprocess.Popen]) -> None:
        for proc in processes:
            TerminalManager._request_process_termination(proc)
        for proc in processes:
            TerminalManager._force_kill_process(proc, timeout=0.5)

    def _collect_process_output(
        self,
        process: subprocess.Popen,
        task_handle: Optional[TaskHandle],
        *,
        poll_interval: float = 0.2,
        kill_timeout: float = 0.5,
        overall_timeout: float = 60.0,
    ) -> tuple[Any, Any]:
        """Wait for process completion while honouring task cancellation."""
        deadline = time.time() + overall_timeout

        while True:
            if task_handle and task_handle.is_cancelled():
                self._request_process_termination(process)

            remaining = max(0.0, deadline - time.time())
            if remaining <= 0.0:
                self._force_kill_process(process, timeout=kill_timeout)
                raise subprocess.TimeoutExpired(cmd="adb shell", timeout=overall_timeout)

            timeout = min(poll_interval, remaining)
            try:
                return process.communicate(timeout=timeout)
            except subprocess.TimeoutExpired:
                if task_handle and task_handle.is_cancelled():
                    self._force_kill_process(process, timeout=kill_timeout)
                    raise TaskCancelledError("Operation cancelled")
                continue

    def _get_selected_devices(self) -> List[adb_models.DeviceInfo]:
        """Get the list of currently selected devices."""
        if hasattr(self.parent_window, "get_checked_devices"):
            return self.parent_window.get_checked_devices()
        return []

    def update_device_count(self) -> None:
        """Emit current device count."""
        devices = self._get_selected_devices()
        self.device_count_changed.emit(len(devices))

    # Command history management
    def _add_to_history(self, command: str) -> None:
        """Add command to history."""
        command = command.strip()
        # Don't add duplicates of the last command
        if self._command_history and self._command_history[-1] == command:
            return

        self._command_history.append(command)
        if len(self._command_history) > self._max_history:
            self._command_history = self._command_history[-self._max_history :]

        # Reset history navigation index
        self._history_index = -1

    def get_previous_command(self) -> Optional[str]:
        """Get previous command from history (up arrow behavior)."""
        if not self._command_history:
            return None

        if self._history_index == -1:
            self._history_index = len(self._command_history) - 1
        elif self._history_index > 0:
            self._history_index -= 1

        return self._command_history[self._history_index]

    def get_next_command(self) -> Optional[str]:
        """Get next command from history (down arrow behavior)."""
        if not self._command_history or self._history_index == -1:
            return None

        if self._history_index < len(self._command_history) - 1:
            self._history_index += 1
            return self._command_history[self._history_index]
        else:
            self._history_index = -1
            return ""

    def get_command_history(self) -> List[str]:
        """Get full command history."""
        return self._command_history.copy()

    def set_command_history(self, history: List[str]) -> None:
        """Set command history (for persistence)."""
        self._command_history = history[-self._max_history :] if history else []
        self._history_index = -1
