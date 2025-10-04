"""Common utilities for Lazy Blacktea.

This module centralises logging setup, filesystem helpers, timestamp helpers,
command execution helpers, and trace identifier management used across the
application.
"""

from __future__ import annotations

import datetime as dt
import logging
import os
import platform
import shlex
import subprocess
import uuid
from contextlib import contextmanager
from contextvars import ContextVar, Token
from pathlib import Path
from typing import Iterator, List, Optional, Sequence, Union


_TRACE_ID_DEFAULT = "-"
_TRACE_ID_VAR: ContextVar[str] = ContextVar("lazy_blacktea_trace_id", default=_TRACE_ID_DEFAULT)

# Track whether log cleanup has already run for the current day.
_logs_cleaned_today = False


class TraceIdFilter(logging.Filter):
    """Augment log records with their active trace identifier."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.trace_id = get_trace_id()
        return True


def generate_trace_id() -> str:
    """Return a new random trace identifier."""
    return uuid.uuid4().hex


def get_trace_id() -> str:
    """Return the current trace identifier ("-" when unset)."""
    return _TRACE_ID_VAR.get()


def set_trace_id(trace_id: Optional[str]) -> Token[str]:
    """Set the active trace identifier and return the context token."""
    value = trace_id or _TRACE_ID_DEFAULT
    return _TRACE_ID_VAR.set(value)


def reset_trace_id(token: Token[str]) -> None:
    """Reset the trace identifier to the previous context."""
    _TRACE_ID_VAR.reset(token)


@contextmanager
def trace_id_scope(trace_id: Optional[str]) -> Iterator[None]:
    """Context manager that temporarily sets the trace identifier."""
    token = set_trace_id(trace_id)
    try:
        yield
    finally:
        reset_trace_id(token)


def _resolve_logs_dir() -> Path:
    """Return the directory path where log files should be stored."""
    system = platform.system().lower()
    home_dir = Path.home()

    if system == "darwin":
        return home_dir / ".lazy_blacktea_logs"

    if system == "linux":
        xdg_data_home = os.environ.get("XDG_DATA_HOME")
        if xdg_data_home:
            return Path(xdg_data_home) / "lazy_blacktea" / "logs"
        return home_dir / ".local" / "share" / "lazy_blacktea" / "logs"

    return home_dir / ".lazy_blacktea_logs"


def _cleanup_old_logs(logs_dir: Path, bootstrap_logger: logging.Logger) -> int:
    """Remove log files that do not belong to today (runs at most once per day)."""
    global _logs_cleaned_today

    if _logs_cleaned_today:
        return 0

    try:
        today = dt.date.today().strftime("%Y%m%d")
        cleaned_count = 0

        for filename in os.listdir(logs_dir):
            if not (filename.startswith("lazy_blacktea_") and filename.endswith(".log")):
                continue

            date_part = filename[14:22]
            if len(date_part) != 8 or not date_part.isdigit():
                continue

            if date_part == today:
                continue

            old_log_path = logs_dir / filename
            try:
                old_log_path.unlink()
                cleaned_count += 1
            except OSError:
                bootstrap_logger.exception("Error removing stale log file", extra={"stale_log": str(old_log_path)})

        _logs_cleaned_today = True
        return cleaned_count
    except Exception:  # pragma: no cover - defensive safeguard
        bootstrap_logger.exception(
            "Unexpected failure while cleaning logs directory", extra={"logs_dir": str(logs_dir)}
        )
        return 0


def _ensure_logger_filters(logger: logging.Logger) -> None:
    """Attach the TraceIdFilter to the logger if not already present."""
    if any(isinstance(item, TraceIdFilter) for item in logger.filters):
        return
    logger.addFilter(TraceIdFilter())


def get_logger(name: str = "lazy_blacktea") -> logging.Logger:
    """Return a configured logger augmented with trace identifiers."""
    logs_dir = _resolve_logs_dir()
    logs_dir.mkdir(parents=True, exist_ok=True)

    bootstrap_logger = logging.getLogger("lazy_blacktea.bootstrap")
    if not any(isinstance(handler, logging.NullHandler) for handler in bootstrap_logger.handlers):
        bootstrap_logger.addHandler(logging.NullHandler())

    cleaned_count = _cleanup_old_logs(logs_dir, bootstrap_logger)

    current_time = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    log_filename = f"lazy_blacktea_{current_time}.log"
    log_filepath = logs_dir / log_filename

    logger = logging.getLogger(name)
    _ensure_logger_filters(logger)

    if logger.handlers:
        return logger

    try:
        file_handler = logging.FileHandler(log_filepath, encoding="utf-8")
    except (OSError, PermissionError):
        fallback_dir = Path.cwd() / "logs"
        fallback_dir.mkdir(parents=True, exist_ok=True)
        log_filepath = fallback_dir / log_filename
        file_handler = logging.FileHandler(log_filepath, encoding="utf-8")

    file_formatter = logging.Formatter(
        "%(asctime)s %(trace_id)s %(name)-20s %(levelname)-8s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(file_formatter)
    file_handler.addFilter(TraceIdFilter())

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_formatter = logging.Formatter("%(levelname)s [%(trace_id)s] %(message)s")
    console_handler.setFormatter(console_formatter)
    console_handler.addFilter(TraceIdFilter())

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    logger.setLevel(logging.INFO)

    if cleaned_count > 0:
        logger.info("Removed %s old log file(s)", cleaned_count)

    if name == "lazy_blacktea":
        logger.info("Log file created: %s", log_filepath)

    return logger


# Module-level logger for common utilities (defined after get_logger).
_LOGGER = get_logger("common")


def read_file(path: str) -> List[str]:
    """Return a list of stripped lines from the given file path."""
    file_path = Path(path).expanduser()
    if not file_path.is_file():
        _LOGGER.warning("Requested file does not exist", extra={"path": str(file_path)})
        return []

    try:
        with file_path.open(encoding="utf-8") as handle:
            return [line.strip() for line in handle.readlines()]
    except Exception:  # pragma: no cover - defensive path
        _LOGGER.exception("Failed to read file", extra={"path": str(file_path)})
        return []


def timestamp_time() -> str:
    """Return the current time formatted as YYYYMMDD_HHMMSS."""
    return timestamp_to_format_time(dt.datetime.now().timestamp())


def timestamp_to_format_time(timestamp: Union[int, float, str]) -> str:
    """Convert the timestamp to a formatted string (YYYYMMDD_HHMMSS)."""
    try:
        ts_float = float(timestamp)
    except (TypeError, ValueError):
        _LOGGER.error("Invalid timestamp provided", extra={"timestamp": timestamp})
        return "0000000000"

    if len(str(int(ts_float))) > 10:
        ts_float = ts_float / 1000

    dt_object = dt.datetime.fromtimestamp(ts_float)
    return dt_object.strftime("%Y%m%d_%H%M%S")


def current_format_time_utc() -> str:
    """Return the current UTC time formatted as YYYYMMDD_HHMMSS."""
    return dt.datetime.now().strftime("%Y%m%d_%H%M%S")


def make_gen_dir_path(folder_path: str) -> str:
    """Create the directory (including parents) and return its POSIX path."""
    cleaned = folder_path.strip()
    if not cleaned:
        _LOGGER.error("Empty folder path provided to make_gen_dir_path")
        return ""

    full_path = Path(get_full_path(cleaned))
    full_path.mkdir(parents=True, exist_ok=True)
    return full_path.as_posix()


def check_exists_dir(path: str) -> bool:
    """Return True when the given path (expanded) exists."""
    return Path(get_full_path(path)).exists()


def get_full_path(path: str) -> str:
    """Return the expanded absolute path for the given path string."""
    return os.path.expanduser(path)


def make_full_path(root_path: str, *paths: str) -> str:
    """Join paths and return the POSIX representation."""
    if not paths:
        return root_path
    return Path(root_path).joinpath(*paths).as_posix()


def make_file_extension(file_path: str, extension: str) -> str:
    """Return the file path with the given extension."""
    return str(Path(file_path).with_suffix(extension))


CommandType = Union[str, Sequence[str]]


def sp_run_command(command: CommandType, ignore_index: int = 0) -> List[str]:
    """Run a synchronous subprocess command and return its output lines."""
    _LOGGER.debug("Run command synchronously", extra={"command": command})
    listing_result: List[str] = []

    command_list: Sequence[str]
    if isinstance(command, str):
        command_list = shlex.split(command)
    else:
        command_list = command

    try:
        result = subprocess.run(
            command_list,
            check=True,
            capture_output=True,
            shell=False,
            text=True,
            encoding="utf-8",
        )
        if result.returncode == 0:
            output = result.stdout.splitlines()
            listing_result.extend(output[ignore_index:])
        else:
            _LOGGER.error("Command returned non-zero exit", extra={"stderr": result.stderr})
    except subprocess.CalledProcessError as exc:  # pragma: no cover - defensive path
        _LOGGER.exception("Command process error", extra={"stderr": exc.stderr})
    except Exception:  # pragma: no cover - defensive path
        _LOGGER.exception("Unexpected error running command", extra={"command": command_list})

    _LOGGER.debug("Command result", extra={"result": listing_result})
    return listing_result


def validate_and_create_output_path(output_path: str) -> Optional[str]:
    """Validate and normalize output path, creating it if necessary."""
    if not output_path or not output_path.strip():
        return None

    if not check_exists_dir(output_path):
        normalized_path = make_gen_dir_path(output_path)
        if not normalized_path:
            return None
        return normalized_path

    return output_path


def run_command(command: CommandType, ignore_index: int = 0) -> List[str]:
    """Backwards compatible alias that delegates to mp_run_command."""
    _LOGGER.debug("Run command (alias)", extra={"command": command})
    return mp_run_command(command, ignore_index)


def mp_run_command(cmd: CommandType, ignore_index: int = 0) -> List[str]:
    """Run the command using subprocess.Popen and return its output lines."""
    _LOGGER.debug("Execute command asynchronously", extra={"command": cmd})
    listing_result: List[str] = []

    if isinstance(cmd, str):
        command_list: Sequence[str] = shlex.split(cmd)
    else:
        command_list = cmd

    try:
        process = subprocess.Popen(
            command_list,
            shell=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
        )
        stdout, stderr = process.communicate()
        _LOGGER.debug("Command stdout", extra={"stdout": stdout})
        _LOGGER.debug("Command stderr", extra={"stderr": stderr})
        if process.returncode == 0:
            output = stdout.splitlines()
            listing_result.extend(output[ignore_index:])
        elif stderr and stderr.strip():
            _LOGGER.error("Command error", extra={"stderr": stderr})
    except Exception:  # pragma: no cover - defensive path
        _LOGGER.exception("Command process error", extra={"command": command_list})

    _LOGGER.debug("Command result", extra={"result": listing_result})
    return listing_result


def create_cancellable_process(cmd: CommandType) -> Optional[subprocess.Popen]:
    """Create and return a subprocess.Popen object for a cancellable command."""
    _LOGGER.debug("Creating cancellable process", extra={"command": cmd})
    try:
        if isinstance(cmd, str):
            command_list: Sequence[str] = shlex.split(cmd)
        else:
            command_list = cmd

        process = subprocess.Popen(
            command_list,
            shell=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
        )
        return process
    except Exception:  # pragma: no cover - defensive path
        _LOGGER.exception("Failed to create cancellable process", extra={"command": cmd})
        return None


__all__ = [
    "TraceIdFilter",
    "create_cancellable_process",
    "current_format_time_utc",
    "generate_trace_id",
    "get_full_path",
    "get_logger",
    "get_trace_id",
    "make_file_extension",
    "make_full_path",
    "make_gen_dir_path",
    "mp_run_command",
    "read_file",
    "reset_trace_id",
    "run_command",
    "set_trace_id",
    "sp_run_command",
    "timestamp_time",
    "timestamp_to_format_time",
    "trace_id_scope",
    "validate_and_create_output_path",
]
