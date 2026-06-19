"""Shared low-level helpers for the ADB layer (extracted from adb_tools, #63).

Holds the error-handling decorators and the parallel-execution primitives that
every ADB domain relies on. Depends only on ``common`` and ``native_bridge`` (no
domain modules), so domain submodules and ``utils.adb_tools`` can import from
here without an import cycle.
"""

from __future__ import annotations

import concurrent.futures
import os
import traceback
from functools import wraps
from typing import Any, Callable, List

from utils import common
from utils import native_bridge

logger = common.get_logger('adb_tools')


def adb_operation(operation_name: str = None, default_return=None, log_errors: bool = True):
    """Decorator for ADB operations with standardized error handling."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            op_name = operation_name or func.__name__
            try:
                return func(*args, **kwargs)
            except Exception as e:
                if log_errors:
                    logger.error(f'Error in {op_name}: {e}')
                    logger.debug(f'Traceback for {op_name}: {traceback.format_exc()}')
                return default_return
        return wrapper
    return decorator


def adb_device_operation(default_return=None, log_errors: bool = True):
    """Decorator for device operations that take ``serial_num`` as the first arg."""
    def decorator(func):
        @wraps(func)
        def wrapper(serial_num, *args, **kwargs):
            try:
                return func(serial_num, *args, **kwargs)
            except Exception as e:
                if log_errors:
                    logger.error(f'Error in {func.__name__} for device {serial_num}: {e}')
                    logger.debug(
                        f'Traceback for {func.__name__} (device {serial_num}): {traceback.format_exc()}'
                    )
                return default_return
        return wrapper
    return decorator


def _execute_commands_parallel(commands: List[str], operation_name: str) -> List[str]:
    """Execute multiple ADB commands in parallel."""
    if not commands:
        return []

    with concurrent.futures.ThreadPoolExecutor(max_workers=len(commands)) as executor:
        results = list(executor.map(common.run_command, commands))
        logger.info(f'{operation_name} completed - executed {len(commands)} commands')
        return results


def _normalize_parallel_results(raw_results: List[Any]) -> List[List[str]]:
    normalized: List[List[str]] = []
    for item in raw_results:
        if isinstance(item, list):
            normalized.append([str(line) for line in item])
        elif isinstance(item, tuple):
            normalized.append([str(line) for line in item])
        elif item is None:
            normalized.append([])
        else:
            normalized.append([str(item)])
    return normalized


def _execute_commands_parallel_native(commands: List[str], operation_name: str) -> List[List[str]]:
    """Execute commands in parallel using the native runner when available."""
    if not commands:
        return []

    if not native_bridge.is_available():
        fallback = _execute_commands_parallel(commands, operation_name)
        return _normalize_parallel_results(fallback)

    try:
        return native_bridge.run_commands_parallel(commands)
    except native_bridge.NativeBridgeError as exc:
        logger.warning('Native command runner failed for %s: %s', operation_name, exc)
        fallback = _execute_commands_parallel(commands, operation_name)
        return _normalize_parallel_results(fallback)


def _execute_functions_parallel(functions: List[Callable], args_list: List[Any], operation_name: str) -> List[Any]:
    """Execute multiple functions in parallel."""
    if not functions or not args_list:
        return []

    with concurrent.futures.ThreadPoolExecutor(max_workers=len(functions)) as executor:
        futures = []
        for func, args in zip(functions, args_list):
            future = executor.submit(func, *args if isinstance(args, (list, tuple)) else [args])
            futures.append(future)

        results = []
        for future in concurrent.futures.as_completed(futures):
            try:
                result = future.result()
                results.append(result)
            except Exception as e:
                logger.error(f'Error in {operation_name}: {e}')
                results.append(None)

        logger.info(f'{operation_name} completed - executed {len(functions)} functions')
        return results


def _determine_worker_count(task_count: int) -> int:
    """Select a sensible worker count for per-device parallelism."""
    if task_count <= 0:
        return 0
    cpu_count = os.cpu_count() or 1
    return max(1, min(task_count, cpu_count))


__all__ = [
    "logger",
    "adb_operation",
    "adb_device_operation",
    "_execute_commands_parallel",
    "_normalize_parallel_results",
    "_execute_commands_parallel_native",
    "_execute_functions_parallel",
    "_determine_worker_count",
]
