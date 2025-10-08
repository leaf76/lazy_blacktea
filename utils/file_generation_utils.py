"""File generation utilities for creating device reports and files."""

import asyncio
import concurrent.futures
import os
import re
import threading
from typing import List, Callable, Optional, Dict, Any

from utils import adb_models, adb_tools, common


class BugReportInProgressError(RuntimeError):
    """Raised when a bug report generation request overlaps an active run."""


_bug_report_state_lock = threading.Lock()
_bug_report_in_progress = False
_active_bug_report_serials: set[str] = set()


def is_bug_report_generation_active() -> bool:
    """Return True when a bug report batch run is currently active."""
    with _bug_report_state_lock:
        return _bug_report_in_progress


def get_active_bug_report_serials() -> list[str]:
    """Return the serial numbers participating in the active bug report run."""
    with _bug_report_state_lock:
        return list(_active_bug_report_serials)


def _claim_bug_report_run(serials: list[str]) -> None:
    """Atomically mark bug report generation as active or raise if already busy."""
    with _bug_report_state_lock:
        global _bug_report_in_progress
        if _bug_report_in_progress:
            overlapping = sorted(set(serials) & _active_bug_report_serials)
            if overlapping:
                devices_text = ', '.join(overlapping)
                raise BugReportInProgressError(
                    f'Bug report generation already running for: {devices_text}'
                )
            raise BugReportInProgressError('Bug report generation already in progress')

        _bug_report_in_progress = True
        _active_bug_report_serials.clear()
        _active_bug_report_serials.update(serials)


def _release_bug_report_run() -> None:
    """Clear the active bug report generation marker."""
    with _bug_report_state_lock:
        global _bug_report_in_progress
        _bug_report_in_progress = False
        _active_bug_report_serials.clear()


def _sanitize_fragment(value: str) -> str:
    """Sanitize a string for safe filesystem usage."""
    if not value:
        return 'unknown'
    sanitized = re.sub(r'[^A-Za-z0-9._-]+', '_', value)
    return sanitized.strip('_') or 'unknown'




def _parallel_fetch(devices: List[adb_models.DeviceInfo], fetcher, logger, error_message: str) -> dict[str, Any]:
    """Execute device-bound fetchers concurrently and collect results."""
    if not devices:
        return {}

    worker_count = min(len(devices), max(1, os.cpu_count() or 1))
    results: dict[str, Any] = {}

    with concurrent.futures.ThreadPoolExecutor(max_workers=worker_count) as executor:
        future_map = {
            executor.submit(fetcher, device): device
            for device in devices
        }

        for future in concurrent.futures.as_completed(future_map):
            device = future_map[future]
            try:
                results[device.device_serial_num] = future.result()
            except Exception as exc:  # pragma: no cover - defensive
                logger.warning(f"{error_message} for {device.device_serial_num}: {exc}")

    return results


def generate_bug_report_batch(
    devices: List[adb_models.DeviceInfo],
    output_path: str,
    callback: Optional[Callable] = None,
    progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
    completion_event: Optional[threading.Event] = None,
    cancel_event: Optional[threading.Event] = None,
) -> None:
    """Generate Android bug reports for multiple devices.

    Args:
        devices: List of device info objects
        output_path: Directory to save bug reports
        callback: Optional callback function called when complete
    """

    serials = [device.device_serial_num for device in devices]
    logger = common.get_logger('file_generation')

    try:
        _claim_bug_report_run(serials)
    except BugReportInProgressError as exc:
        logger.warning(f'Bug report generation request rejected: {exc}')
        raise


    async def _run_bug_report_batch() -> None:
        try:
            timestamp = common.current_format_time_utc()
            device_count = len(devices)

            logger.info('Starting bug report generation for %s devices', device_count)

            os.makedirs(output_path, exist_ok=True)

            successes = 0
            failures: List[Dict[str, str]] = []
            # For smooth progress: each device contributes 0..100 units
            device_percent: Dict[str, int] = {d.device_serial_num: 0 for d in devices}
            total_steps = max(1, device_count * 100)
            progress_lock = asyncio.Lock()

            def _emit_progress(payload: Dict[str, Any]) -> None:
                if progress_callback:
                    try:
                        progress_callback(payload)
                    except Exception as callback_error:  # pragma: no cover - defensive
                        logger.warning('Progress callback failed: %s', callback_error)

            def _record_failure(device, error_message: str) -> Dict[str, str]:
                return {
                    'device_serial': device.device_serial_num,
                    'device_model': device.device_model,
                    'error': error_message,
                }

            def _log_manufacturer_guidance(device_model: str) -> None:
                device_model_lower = (device_model or '').lower()
                if 'samsung' in device_model_lower:
                    logger.warning('Samsung device %s may require additional permissions', device_model)
                elif any(brand in device_model_lower for brand in ['huawei', 'honor']):
                    logger.warning('Huawei device %s may require HiSuite permissions', device_model)
                elif 'xiaomi' in device_model_lower or 'redmi' in device_model_lower:
                    logger.warning('Xiaomi device %s may require MIUI developer options', device_model)
                elif any(brand in device_model_lower for brand in ['oppo', 'realme', 'oneplus']):
                    logger.warning('OPPO/OnePlus device %s may require ColorOS/OxygenOS developer settings', device_model)
                elif 'vivo' in device_model_lower:
                    logger.warning('Vivo device %s may require FunTouch OS developer permissions', device_model)

            async def _process_device(index: int, device: adb_models.DeviceInfo) -> None:
                nonlocal successes

                sanitized_model = _sanitize_fragment(device.device_model)
                sanitized_serial = _sanitize_fragment(device.device_serial_num)
                filename = f"bug_report_{sanitized_model}_{sanitized_serial}_{timestamp}"
                filepath = os.path.join(output_path, filename)

                logger.info(
                    'Generating bug report %s/%s for %s (%s)',
                    index,
                    device_count,
                    device.device_model,
                    device.device_serial_num,
                )

                success = False
                failure_entry: Optional[Dict[str, str]] = None
                payload_output_path = f'{filepath}.zip'
                error_message = ''
                details = ''

                try:
                    # 若已取消，快速退出
                    if cancel_event is not None and cancel_event.is_set():
                        raise RuntimeError('operation cancelled')

                    # Emit initial 0% for this device
                    async with progress_lock:
                        device_percent[device.device_serial_num] = 0
                        overall_current = sum(device_percent.values())
                        _emit_progress({
                            'success': True,
                            'current': overall_current,
                            'total': total_steps,
                            'device_serial': device.device_serial_num,
                            'device_model': device.device_model,
                            'output_path': payload_output_path,
                            'details': 'Starting bug report...',
                        })

                    # Try streaming progress first
                    def _on_device_percent(p: int) -> None:
                        # Note: running in background thread
                        async def _update():
                            async with progress_lock:
                                device_percent[device.device_serial_num] = max(0, min(100, int(p)))
                                overall_current = sum(device_percent.values())
                                _emit_progress({
                                    'success': True,
                                    'current': overall_current,
                                    'total': total_steps,
                                    'device_serial': device.device_serial_num,
                                    'device_model': device.device_model,
                                    'output_path': payload_output_path,
                                    'details': f'Progress {p}%',
                                    'percent': int(p),
                                })
                        try:
                            loop = asyncio.get_event_loop()
                            if loop.is_running():
                                asyncio.run_coroutine_threadsafe(_update(), loop)
                        except Exception:
                            pass

                    stream_result = await asyncio.to_thread(
                        adb_tools.generate_bug_report_device_streaming,
                        device.device_serial_num,
                        filepath,
                        300,
                        cancel_event=cancel_event,
                        progress_cb=_on_device_percent,
                    )

                    if stream_result.get('stream_supported') and not stream_result.get('error'):
                        result = stream_result
                    else:
                        # Fallback to non-streaming; set to busy and complete as 100 when done
                        result = await asyncio.to_thread(
                            adb_tools.generate_bug_report_device,
                            device.device_serial_num,
                            filepath,
                            300,
                            cancel_event=cancel_event,
                        )
                    success = bool(result.get('success'))
                    payload_output_path = result.get('output_path', payload_output_path)
                    error_message = result.get('error', '')
                    details = result.get('details', '')
                    file_size = result.get('file_size', 'unknown')
                except Exception as exc:  # pragma: no cover - defensive logging
                    error_message = str(exc)
                    _log_manufacturer_guidance(device.device_model)
                    failure_entry = _record_failure(device, error_message)
                else:
                    if success:
                        logger.info(
                            'Bug report generated for %s (%s): %s bytes',
                            device.device_model,
                            device.device_serial_num,
                            file_size,
                        )
                    else:
                        if not error_message:
                            error_message = 'Unknown error'
                        logger.error(
                            'Bug report failed for %s (%s): %s',
                            device.device_model,
                            device.device_serial_num,
                            error_message,
                        )
                        failure_entry = _record_failure(device, error_message)

                payload = {
                    'success': success,
                    'total': total_steps,
                    'device_serial': device.device_serial_num,
                    'device_model': device.device_model,
                    'output_path': payload_output_path,
                    'error_message': error_message,
                    'details': details,
                }

                async with progress_lock:
                    # Mark this device as finished (100) regardless of success/failure to reflect completion
                    device_percent[device.device_serial_num] = 100
                    overall_current = sum(device_percent.values())
                    payload['current'] = overall_current
                    if success:
                        successes += 1
                    elif failure_entry is not None:
                        failures.append(failure_entry)

                _emit_progress(payload)

            if device_count > 0:
                await asyncio.gather(
                    *(_process_device(index, device) for index, device in enumerate(devices, 1))
                )

            if callback:
                failure_count = len(failures)
                summary_lines = [
                    f'Bug report generation completed for {device_count} device(s).',
                    f'📁 Output directory: {output_path}',
                    '',
                    f'✅ Success: {successes} device(s)',
                    f'❌ Failed: {failure_count} device(s)',
                ]

                if failures:
                    summary_lines.append('')
                    summary_lines.append('Failed devices:')
                    for failure in failures:
                        summary_lines.append(
                            f"• {failure['device_model']} ({failure['device_serial']}) — {failure['error']}"
                        )

                completion_message = '\n'.join(summary_lines)
                completion_payload = {
                    'summary': completion_message,
                    'output_path': output_path,
                    'successes': successes,
                    'failures': failures,
                    'timestamp': timestamp,
                }

                try:
                    callback('Bug Report Complete', completion_payload, successes, '🐛')
                except Exception as callback_error:
                    logger.warning('Completion callback failed: %s', callback_error)

        except Exception as exc:
            logger.error('Bug report batch operation failed: %s', exc)
        finally:
            _release_bug_report_run()

    # Run in background thread with asyncio event loop
    try:
        def _thread_target() -> None:
            try:
                asyncio.run(_run_bug_report_batch())
            finally:
                if completion_event is not None:
                    completion_event.set()

        thread = threading.Thread(target=_thread_target, daemon=True)
        thread.start()
    except Exception:
        _release_bug_report_run()
        if completion_event is not None:
            completion_event.set()
        raise

def generate_device_discovery_file(devices: List[adb_models.DeviceInfo],
                                  output_path: str,
                                  callback: Optional[Callable] = None) -> None:
    """Generate device discovery file with device information.

    Args:
        devices: List of device info objects
        output_path: Directory to save discovery file
        callback: Optional callback function called when complete
    """

    def discovery_worker():
        try:
            timestamp = common.current_format_time_utc()
            filename = f"device_discovery_{timestamp}.txt"
            filepath = os.path.join(output_path, filename)

            logger = common.get_logger('file_generation')
            logger.info(f'Generating device discovery file for {len(devices)} devices')

            # Create device discovery content
            content_lines = [
                "# Device Discovery Report",
                f"# Generated: {common.timestamp_time()}",
                f"# Total Devices: {len(devices)}",
                "",
                "# Device Information:",
                ""
            ]

            properties_map = _parallel_fetch(
                devices,
                lambda device: adb_tools.get_device_properties(device.device_serial_num),
                logger,
                'Could not get properties'
            )

            for i, device in enumerate(devices, 1):
                content_lines.extend([
                    f"## Device {i}: {device.device_model}",
                    f"Serial: {device.device_serial_num}",
                    f"Model: {device.device_model}",
                    f"Status: {device.device_status}",
                    f"Transport: {device.transport_id}",
                    ""
                ])

                properties = properties_map.get(device.device_serial_num, {})
                if properties:
                    content_lines.append("### Device Properties:")
                    for key, value in properties.items():
                        content_lines.append(f"{key}: {value}")
                    content_lines.append("")

            # Write to file
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write('\n'.join(content_lines))

            logger.info(f'Device discovery file generated: {filename}')

            # Call callback if provided
            if callback:
                callback('Device Discovery', output_path, len(devices), '🔍')

        except Exception as e:
            common.get_logger('file_generation').error(f'Device discovery generation failed: {e}')

    # Run in background thread
    thread = threading.Thread(target=discovery_worker, daemon=True)
    thread.start()


def generate_device_info_batch(devices: List[adb_models.DeviceInfo],
                              output_path: str,
                              callback: Optional[Callable] = None) -> None:
    """Generate detailed device information files for multiple devices.

    Args:
        devices: List of device info objects
        output_path: Directory to save info files
        callback: Optional callback function called when complete
    """

    def info_worker():
        try:
            timestamp = common.current_format_time_utc()
            device_count = len(devices)

            logger = common.get_logger('file_generation')
            logger.info(f'Generating device info files for {device_count} devices')

            version_map = _parallel_fetch(
                devices,
                lambda device: adb_tools.get_android_version(device.device_serial_num),
                logger,
                'Could not get Android version'
            )
            properties_map = _parallel_fetch(
                devices,
                lambda device: adb_tools.get_device_properties(device.device_serial_num),
                logger,
                'Could not get properties'
            )

            for device in devices:
                try:
                    filename = f"device_info_{device.device_model}_{device.device_serial_num}_{timestamp}.txt"
                    filepath = os.path.join(output_path, filename)

                    # Collect device information
                    content_lines = [
                        f"# Device Information Report",
                        f"# Generated: {common.timestamp_time()}",
                        f"# Device: {device.device_model}",
                        "",
                        "## Basic Information:",
                        f"Serial Number: {device.device_serial_num}",
                        f"Model: {device.device_model}",
                        f"Status: {device.device_status}",
                        f"Transport ID: {device.transport_id}",
                        ""
                    ]

                    # Add system information
                    android_version = version_map.get(device.device_serial_num)
                    if android_version:
                        content_lines.extend([
                            "## System Information:",
                            f"Android Version: {android_version}",
                            ""
                        ])

                    properties = properties_map.get(device.device_serial_num, {})
                    if properties:
                        content_lines.append("## Device Properties:")
                        for key, value in sorted(properties.items()):
                            content_lines.append(f"{key}: {value}")
                        content_lines.append("")

                    # Write to file
                    with open(filepath, 'w', encoding='utf-8') as f:
                        f.write('\n'.join(content_lines))

                    logger.info(f'Device info file generated: {filename}')

                except Exception as e:
                    logger.error(f'Device info generation failed for {device.device_serial_num}: {e}')

            # Call callback if provided
            if callback:
                callback('Device Info', output_path, device_count, '📋')

        except Exception as e:
            common.get_logger('file_generation').error(f'Device info batch operation failed: {e}')

    # Run in background thread
    thread = threading.Thread(target=info_worker, daemon=True)
    thread.start()


def validate_file_output_path(output_path: str) -> Optional[str]:
    """Validate and normalize file output path.

    Args:
        output_path: Path to validate

    Returns:
        Normalized path if valid, None if invalid
    """
    if not output_path or not output_path.strip():
        return None

    # Validate and normalize using common utilities
    if not common.check_exists_dir(output_path):
        normalized_path = common.make_gen_dir_path(output_path)
        if not normalized_path:
            return None
        return normalized_path

    return output_path


def get_file_generation_operations() -> List[dict]:
    """Get list of available file generation operations.

    Returns:
        List of operation dictionaries with 'name', 'description', and 'icon'
    """
    return [
        {
            'name': 'Bug Report',
            'description': 'Generate Android bug reports for debugging',
            'icon': '🐛',
            'function': 'generate_bug_report_batch'
        },
        {
            'name': 'Device Discovery',
            'description': 'Generate device discovery file with basic info',
            'icon': '🔍',
            'function': 'generate_device_discovery_file'
        },
        {
            'name': 'Device Info',
            'description': 'Generate detailed device information files',
            'icon': '📋',
            'function': 'generate_device_info_batch'
        }
    ]
