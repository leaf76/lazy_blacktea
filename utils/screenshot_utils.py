"""Screenshot utilities for device screenshot operations."""

import os
import threading
from typing import List, Callable, Optional
from utils import adb_models, adb_tools, common


def take_screenshots_batch(devices: List[adb_models.DeviceInfo],
                          output_path: str,
                          callback: Optional[Callable] = None) -> None:
    """Take screenshots from multiple devices simultaneously.

    Args:
        devices: List of device info objects
        output_path: Directory to save screenshots
        callback: Optional callback function called when complete
    """

    def screenshot_worker():
        try:
            serials = [d.device_serial_num for d in devices]
            device_count = len(devices)
            device_models = [d.device_model for d in devices]

            # Generate timestamp filename
            filename = common.current_format_time_utc()

            # Call the original working function directly instead of the wrapper
            logger = common.get_logger('screenshot')
            logger.info(f'🔧 [SCREENSHOT] About to call start_to_screen_shot with serials={serials}, filename={filename}, output_path={output_path}')
            adb_tools.start_to_screen_shot(serials, filename, output_path)
            logger.info(f'🔧 [SCREENSHOT] start_to_screen_shot completed successfully')

            # Call callback if provided
            logger.info(f'🔧 [CALLBACK] About to call callback, callback exists: {callback is not None}, callback type: {type(callback)}')
            if callback:
                logger.info(f'🔧 [CALLBACK] Calling callback with params: output_path={output_path}, device_count={device_count}, device_models={device_models}')
                logger.info(f'🔧 [CALLBACK] Callback object: {callback}')
                try:
                    result = callback(output_path, device_count, device_models)
                    logger.info(f'🔧 [CALLBACK] Callback execution completed successfully, result: {result}')
                except Exception as callback_error:
                    logger.error(f'🔧 [CALLBACK] Callback execution failed: {callback_error}')
                    import traceback
                    logger.error(f'🔧 [CALLBACK] Traceback: {traceback.format_exc()}')
            else:
                logger.warning(f'🔧 [CALLBACK] No callback provided')

        except Exception as e:
            common.get_logger('screenshot').error(f'Screenshot batch operation failed: {e}')

    # Run in background thread
    thread = threading.Thread(target=screenshot_worker, daemon=True)
    thread.start()


def validate_screenshot_path(output_path: str) -> Optional[str]:
    """Validate and normalize screenshot output path.

    Args:
        output_path: Path to validate

    Returns:
        Normalized path if valid, None if invalid
    """
    return common.validate_and_create_output_path(output_path)


def generate_screenshot_filename() -> str:
    """Generate timestamp-based filename for screenshots.

    Returns:
        Formatted timestamp string
    """
    return common.current_format_time_utc()


def take_single_screenshot(device_serial: str, output_path: str,
                          filename: Optional[str] = None) -> bool:
    """Take screenshot from a single device.

    Args:
        device_serial: Device serial number
        output_path: Directory to save screenshot
        filename: Optional custom filename (uses timestamp if None)

    Returns:
        True if successful, False otherwise
    """
    try:
        if not filename:
            filename = generate_screenshot_filename()

        return adb_tools.take_screenshot_single_device(device_serial, output_path, filename)
    except Exception as e:
        common.get_logger('screenshot').error(
            f'Single screenshot failed for {device_serial}: {e}'
        )
        return False


def get_screenshot_quick_actions() -> List[dict]:
    """Get list of quick actions available for screenshots.

    Returns:
        List of action dictionaries with 'name' and 'description'
    """
    return [
        {
            'name': 'Open Folder',
            'description': 'Open the screenshots folder in file manager',
            'icon': '📁'
        },
        {
            'name': 'Copy Path',
            'description': 'Copy the output path to clipboard',
            'icon': '📋'
        },
        {
            'name': 'Take Another',
            'description': 'Take another screenshot with same settings',
            'icon': '📷'
        }
    ]