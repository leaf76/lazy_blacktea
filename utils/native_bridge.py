"""Native bridge loading for Rust-accelerated helpers."""

from __future__ import annotations

import ctypes
import os
import pathlib
import platform
import sys
import threading
from typing import Iterable, List, Optional

from utils import common

logger = common.get_logger('native_bridge')

_LIB_HANDLE: Optional[ctypes.CDLL] = None
_LIB_LOCK = threading.RLock()
_HAS_NATIVE = False

_RECORD_SEPARATOR = '\u001e'
_LINE_SEPARATOR = '\u001f'

_LIBRARY_NAME_BY_SYSTEM = {
    'Darwin': 'libnative_lbb.dylib',
    'Linux': 'libnative_lbb.so',
    'Windows': 'native_lbb.dll',
}

_LIBRARY_FILENAMES = tuple(dict.fromkeys(_LIBRARY_NAME_BY_SYSTEM.values()))


class NativeBridgeError(RuntimeError):
    """Raised when invoking the native library fails."""


def _default_library_name() -> str:
    return _LIBRARY_NAME_BY_SYSTEM.get(platform.system(), _LIBRARY_FILENAMES[0])


def _candidate_library_paths() -> Iterable[pathlib.Path]:
    env_override = os.environ.get('LAZY_BLACKTEA_NATIVE_LIB')
    if env_override:
        yield pathlib.Path(env_override)

    base_dir = pathlib.Path(__file__).resolve().parents[1]
    native_root = base_dir / 'native_lbb'
    build_variants = [native_root / 'target' / 'release', native_root / 'target' / 'debug']

    staged_dirs = [
        base_dir / 'build' / 'native-libs',
        base_dir / 'utils' / 'native',
    ]

    runtime_base = getattr(sys, '_MEIPASS', None)
    if runtime_base:
        staged_dirs.append(pathlib.Path(runtime_base) / 'native')

    search_dirs = build_variants + staged_dirs

    for directory in search_dirs:
        for name in _LIBRARY_FILENAMES:
            candidate = directory / name
            if candidate.exists():
                yield candidate


def _load_library() -> Optional[ctypes.CDLL]:
    global _LIB_HANDLE, _HAS_NATIVE
    if _LIB_HANDLE is not None:
        return _LIB_HANDLE

    with _LIB_LOCK:
        if _LIB_HANDLE is not None:
            return _LIB_HANDLE

        for path in _candidate_library_paths():
            try:
                handle = ctypes.CDLL(str(path))
            except OSError as exc:
                logger.debug('Failed to load native library at %s: %s', path, exc)
                continue

            handle.lb_render_device_ui_html.argtypes = [ctypes.c_char_p]
            handle.lb_render_device_ui_html.restype = ctypes.c_void_p
            handle.lb_run_commands_parallel.argtypes = [ctypes.c_char_p]
            handle.lb_run_commands_parallel.restype = ctypes.c_void_p
            handle.lb_start_screen_record.argtypes = [ctypes.c_char_p, ctypes.c_char_p]
            handle.lb_start_screen_record.restype = ctypes.c_int
            handle.lb_stop_screen_record.argtypes = [ctypes.c_char_p]
            handle.lb_stop_screen_record.restype = ctypes.c_int
            handle.lb_last_error.argtypes = []
            handle.lb_last_error.restype = ctypes.c_void_p
            handle.lb_free_string.argtypes = [ctypes.c_void_p]
            handle.lb_free_string.restype = None

            _LIB_HANDLE = handle
            _HAS_NATIVE = True
            logger.info('Native library loaded from %s', path)
            return _LIB_HANDLE

        logger.warning('Unable to locate native library; falling back to pure Python implementations')
        _HAS_NATIVE = False
        return None


def is_available() -> bool:
    """Return whether the native library is available."""
    _load_library()
    return bool(_HAS_NATIVE)


def _read_and_free_string(ptr: int) -> str:
    if ptr == 0:
        return ''
    handle = _load_library()
    if handle is None:
        return ''
    try:
        value = ctypes.string_at(ptr).decode('utf-8')
    finally:
        handle.lb_free_string(ctypes.c_void_p(ptr))
    return value


def _read_last_error() -> str:
    handle = _load_library()
    if handle is None:
        return ''
    err_ptr = handle.lb_last_error()
    return _read_and_free_string(err_ptr if err_ptr else 0)


def render_device_ui_html(xml_content: str) -> str:
    """Render XML device UI dump into HTML using the native helper."""
    handle = _load_library()
    if handle is None:
        raise NativeBridgeError('Native library not available')

    xml_bytes = xml_content.encode('utf-8')
    result_ptr = handle.lb_render_device_ui_html(ctypes.c_char_p(xml_bytes))
    if not result_ptr:
        error_message = _read_last_error() or 'Unknown native rendering error'
        raise NativeBridgeError(error_message)
    return _read_and_free_string(result_ptr)


def run_commands_parallel(commands: List[str]) -> List[List[str]]:
    """Execute commands in parallel through the native helper."""
    if not commands:
        return []

    handle = _load_library()
    if handle is None:
        raise NativeBridgeError('Native library not available')

    payload_lines = [str(len(commands))]
    payload_lines.extend(commands)
    payload = '\n'.join(payload_lines).encode('utf-8')

    result_ptr = handle.lb_run_commands_parallel(ctypes.c_char_p(payload))
    if not result_ptr:
        error_message = _read_last_error() or 'Unknown native command error'
        raise NativeBridgeError(error_message)

    raw_result = _read_and_free_string(result_ptr)
    if not raw_result:
        return [[] for _ in commands]

    command_chunks = raw_result.split(_RECORD_SEPARATOR)
    results: List[List[str]] = []
    for chunk in command_chunks:
        if chunk == '':
            results.append([])
            continue
        lines = chunk.split(_LINE_SEPARATOR)
        results.append(lines)
    return results


def start_screen_record(serial: str, remote_path: str) -> None:
    """Start an adb screenrecord session using the native helper."""
    handle = _load_library()
    if handle is None:
        raise NativeBridgeError('Native library not available')

    serial_bytes = serial.encode('utf-8')
    remote_bytes = remote_path.encode('utf-8')
    result = handle.lb_start_screen_record(ctypes.c_char_p(serial_bytes), ctypes.c_char_p(remote_bytes))
    if result != 1:
        error_message = _read_last_error() or f'Failed to start screenrecord for {serial}'
        raise NativeBridgeError(error_message)


def stop_screen_record(serial: str) -> None:
    """Stop an adb screenrecord session using the native helper."""
    handle = _load_library()
    if handle is None:
        raise NativeBridgeError('Native library not available')

    serial_bytes = serial.encode('utf-8')
    result = handle.lb_stop_screen_record(ctypes.c_char_p(serial_bytes))
    if result != 1:
        error_message = _read_last_error() or f'Failed to stop screenrecord for {serial}'
        raise NativeBridgeError(error_message)


__all__ = ['NativeBridgeError', 'is_available', 'render_device_ui_html', 'run_commands_parallel', 'start_screen_record', 'stop_screen_record']
