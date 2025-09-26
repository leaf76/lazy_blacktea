"""File generation utilities for creating device reports and files."""

import os
import re
import threading
from typing import List, Callable, Optional, Dict, Any

from utils import adb_models, adb_tools, common


def _sanitize_fragment(value: str) -> str:
    """Sanitize a string for safe filesystem usage."""
    if not value:
        return 'unknown'
    sanitized = re.sub(r'[^A-Za-z0-9._-]+', '_', value)
    return sanitized.strip('_') or 'unknown'


def generate_bug_report_batch(devices: List[adb_models.DeviceInfo],
                             output_path: str,
                             callback: Optional[Callable] = None,
                             progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None) -> None:
    """Generate Android bug reports for multiple devices.

    Args:
        devices: List of device info objects
        output_path: Directory to save bug reports
        callback: Optional callback function called when complete
    """

    def report_worker():
        try:
            timestamp = common.current_format_time_utc()
            device_count = len(devices)

            logger = common.get_logger('file_generation')
            logger.info(f'Starting bug report generation for {device_count} devices')

            os.makedirs(output_path, exist_ok=True)

            successes = 0
            failures: List[Dict[str, str]] = []

            # Generate reports for each device with progress
            for index, device in enumerate(devices, 1):
                try:
                    sanitized_model = _sanitize_fragment(device.device_model)
                    sanitized_serial = _sanitize_fragment(device.device_serial_num)
                    filename = f"bug_report_{sanitized_model}_{sanitized_serial}_{timestamp}"
                    filepath = os.path.join(output_path, filename)

                    logger.info(
                        f'Generating bug report {index}/{device_count} for '
                        f'{device.device_model} ({device.device_serial_num})'
                    )

                    result = adb_tools.generate_bug_report_device(
                        device.device_serial_num,
                        filepath,
                        timeout=300
                    )

                    success = bool(result.get('success'))
                    if success:
                        successes += 1
                        logger.info(
                            'Bug report generated for %s (%s): %s bytes',
                            device.device_model,
                            device.device_serial_num,
                            result.get('file_size', 'unknown')
                        )
                    else:
                        error_msg = result.get('error', 'Unknown error')
                        failures.append({
                            'device_serial': device.device_serial_num,
                            'device_model': device.device_model,
                            'error': error_msg
                        })
                        logger.error(
                            'Bug report failed for %s (%s): %s',
                            device.device_model,
                            device.device_serial_num,
                            error_msg
                        )

                    progress_payload = {
                        'success': success,
                        'current': index,
                        'total': device_count,
                        'device_serial': device.device_serial_num,
                        'device_model': device.device_model,
                        'output_path': result.get('output_path', f'{filepath}.zip'),
                        'error_message': result.get('error', ''),
                        'details': result.get('details', '')
                    }

                    if progress_callback:
                        try:
                            progress_callback(progress_payload)
                        except Exception as callback_error:
                            logger.warning(f'Progress callback failed: {callback_error}')

                except Exception as e:
                    logger.error(f'Bug report failed for {device.device_model} ({device.device_serial_num}): {e}')
                    failures.append({
                        'device_serial': device.device_serial_num,
                        'device_model': device.device_model,
                        'error': str(e)
                    })

                    if progress_callback:
                        failure_payload = {
                            'success': False,
                            'current': index,
                            'total': device_count,
                            'device_serial': device.device_serial_num,
                            'device_model': device.device_model,
                            'output_path': f'{filepath}.zip',
                            'error_message': str(e),
                            'details': ''
                        }
                        try:
                            progress_callback(failure_payload)
                        except Exception as callback_error:
                            logger.warning(f'Progress callback failed: {callback_error}')

                    # Log manufacturer-specific guidance
                    device_model_lower = device.device_model.lower()
                    if 'samsung' in device_model_lower:
                        logger.warning(f'Samsung device {device.device_model} may require:')
                        logger.info('  - Developer options enabled')
                        logger.info('  - USB debugging authorized for this computer')
                        logger.info('  - "Disable permission monitoring" enabled (if available)')
                    elif any(brand in device_model_lower for brand in ['huawei', 'honor']):
                        logger.warning(f'Huawei device {device.device_model} may require HiSuite permissions')
                    elif 'xiaomi' in device_model_lower or 'redmi' in device_model_lower:
                        logger.warning(f'Xiaomi device {device.device_model} may require MIUI developer options')
                    elif any(brand in device_model_lower for brand in ['oppo', 'realme', 'oneplus']):
                        logger.warning(f'OPPO/OnePlus device {device.device_model} may require ColorOS/OxygenOS developer settings')
                    elif 'vivo' in device_model_lower:
                        logger.warning(f'Vivo device {device.device_model} may require FunTouch OS developer permissions')

                    # Don't break the loop, continue with other devices

            # Single completion callback to avoid multiple dialogs
            if callback:
                failure_count = len(failures)
                summary_lines = [
                    f'Bug report generation completed for {device_count} device(s).',
                    f'📁 Output directory: {output_path}',
                    '',
                    f'✅ Success: {successes} device(s)',
                    f'❌ Failed: {failure_count} device(s)'
                ]

                if failures:
                    summary_lines.append('')
                    summary_lines.append('Failed devices:')
                    for failure in failures:
                        summary_lines.append(
                            f'• {failure["device_model"]} ({failure["device_serial"]}) — {failure["error"]}'
                        )

                completion_message = '\n'.join(summary_lines)
                completion_payload = {
                    'summary': completion_message,
                    'output_path': output_path,
                    'successes': successes,
                    'failures': failures,
                    'timestamp': timestamp
                }

                try:
                    callback('Bug Report Complete', completion_payload, successes, '🐛')
                except Exception as callback_error:
                    logger.warning(f'Completion callback failed: {callback_error}')

        except Exception as e:
            common.get_logger('file_generation').error(f'Bug report batch operation failed: {e}')

    # Run in background thread
    thread = threading.Thread(target=report_worker, daemon=True)
    thread.start()


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

            for i, device in enumerate(devices, 1):
                content_lines.extend([
                    f"## Device {i}: {device.device_model}",
                    f"Serial: {device.device_serial_num}",
                    f"Model: {device.device_model}",
                    f"Status: {device.device_status}",
                    f"Transport: {device.transport_id}",
                    ""
                ])

                # Add device properties if available
                try:
                    properties = adb_tools.get_device_properties(device.device_serial_num)
                    if properties:
                        content_lines.append("### Device Properties:")
                        for key, value in properties.items():
                            content_lines.append(f"{key}: {value}")
                        content_lines.append("")
                except Exception as e:
                    logger.warning(f'Could not get properties for {device.device_serial_num}: {e}')

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
                    try:
                        # Get Android version
                        android_version = adb_tools.get_android_version(device.device_serial_num)
                        if android_version:
                            content_lines.extend([
                                "## System Information:",
                                f"Android Version: {android_version}",
                                ""
                            ])

                        # Get device properties
                        properties = adb_tools.get_device_properties(device.device_serial_num)
                        if properties:
                            content_lines.append("## Device Properties:")
                            for key, value in sorted(properties.items()):
                                content_lines.append(f"{key}: {value}")
                            content_lines.append("")

                    except Exception as e:
                        logger.warning(f'Could not get detailed info for {device.device_serial_num}: {e}')

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
