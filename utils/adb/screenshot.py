"""Screenshot capture domain for the ADB layer (extracted from adb_tools, #63).

Self-contained: depends only on ``_base`` (worker-count helper), ``common`` and
``adb_commands``. ``utils.adb_tools`` re-exports these names.
"""

from __future__ import annotations

import concurrent.futures
import os

from utils import adb_commands
from utils import common
from utils.adb._base import logger, _determine_worker_count


def _capture_screenshot_for_device(serial: str, file_name: str, output_path: str) -> bool:
    """Capture, pull and clean up a screenshot for one device.

    Returns ``True`` only when the screenshot was actually pulled to the host. We
    verify by checking that the expected local PNG exists and is non-empty rather
    than trusting the adb output, so a failed capture/pull is reported as failure
    instead of a misleading "saved".
    """
    remote_path = f'/sdcard/{serial}_screenshot_{file_name}.png'
    logger.info('📸 [SCREENSHOT] Processing device %s -> %s', serial, remote_path)

    capture_cmd = adb_commands.cmd_screencap_capture(serial, remote_path)
    pull_cmd = adb_commands.cmd_pull_device_file(serial, remote_path, output_path)
    cleanup_cmd = adb_commands.cmd_remove_device_file(serial, remote_path)

    for stage, command in (
        ('capture', capture_cmd),
        ('pull', pull_cmd),
        ('cleanup', cleanup_cmd),
    ):
        logger.debug('📸 [SCREENSHOT] %s command for %s: %s', stage, serial, command)
        result = common.run_command(command)
        logger.debug('📸 [SCREENSHOT] %s result for %s: %s', stage, serial, result)

    local_path = os.path.join(output_path, f'{serial}_screenshot_{file_name}.png')
    success = os.path.exists(local_path) and os.path.getsize(local_path) > 0
    if not success:
        logger.error(
            '📸 [SCREENSHOT] Screenshot was not saved for %s (expected %s)',
            serial,
            local_path,
        )
    return success


def start_to_screen_shot(
    serial_nums: list[str], file_name: str, output_path: str
) -> dict[str, bool]:
    """Capture screenshots for the provided devices.

    Returns a mapping of ``device_serial -> success`` so callers can report which
    devices actually produced a screenshot instead of assuming every device
    succeeded.
    """
    results: dict[str, bool] = {}
    if not serial_nums:
        logger.info('No devices supplied for start_to_screen_shot')
        return results

    logger.info('Start to screen shot.')
    output_path = common.make_gen_dir_path(output_path)
    worker_count = _determine_worker_count(len(serial_nums))

    if worker_count <= 0:
        logger.info('No workers scheduled for screenshot capture (worker_count=%s)', worker_count)
        return results

    futures: dict[concurrent.futures.Future, str] = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=worker_count) as executor:
        for serial in serial_nums:
            future = executor.submit(_capture_screenshot_for_device, serial, file_name, output_path)
            futures[future] = serial

        for future in concurrent.futures.as_completed(futures):
            serial = futures[future]
            try:
                results[serial] = bool(future.result())
            except Exception as exc:
                logger.error('Error capturing screenshot for %s: %s', serial, exc)
                results[serial] = False

    succeeded = sum(1 for ok in results.values() if ok)
    logger.info(
        'Start to screen shot completed: %s/%s device(s) saved',
        succeeded,
        len(serial_nums),
    )
    return results


def take_screenshot_single_device(serial: str, output_path: str, filename: str) -> bool:
    """Take screenshot for a single device (wrapper function)."""
    try:
        logger.info(f'Taking screenshot for device {serial}, file: {filename}')
        results = start_to_screen_shot([serial], filename, output_path)
        return bool(results.get(serial, False))
    except Exception as e:
        logger.error(f'Error taking screenshot for {serial}: {e}')
        return False


__all__ = [
    "_capture_screenshot_for_device",
    "start_to_screen_shot",
    "take_screenshot_single_device",
]
