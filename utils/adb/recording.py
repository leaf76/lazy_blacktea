"""Screen-recording domain for the ADB layer (extracted from adb_tools, #63).

Depends only on ``_base`` (worker-count + parallel-exec), ``common``,
``adb_commands`` and ``native_bridge``. ``_active_recordings`` is recording-only
module state. ``utils.adb_tools`` re-exports these names.
"""

from __future__ import annotations

import concurrent.futures
import os
import time
import traceback
from typing import List

from utils import adb_commands
from utils import common
from utils import native_bridge
from utils.adb._base import (
    logger,
    _determine_worker_count,
    _execute_functions_parallel,
)

# Tracks single-device wrapper recordings (native vs adb fallback).
_active_recordings = {}


def start_to_record_android_devices(
    serial_nums: list[str], file_name: str
) -> None:
  """Start to record android device."""
  if not serial_nums:
    logger.info('No devices supplied for start_to_record_android_devices')
    return

  logger.info('🎬 [START DEBUG] Starting recording for devices')
  logger.info(f'🎬 [START DEBUG] Serial numbers: {serial_nums}')
  logger.info(f'🎬 [START DEBUG] File name: {file_name}')

  command_map: dict[str, str] = {}
  for serial in serial_nums:
    cmd = adb_commands.cmd_android_screen_record(serial, file_name)
    logger.info(f'🎬 [START DEBUG] Command for {serial}: {cmd}')
    command_map[serial] = cmd

  logger.info(f'🎬 [START DEBUG] All commands: {list(command_map.values())}')

  worker_count = _determine_worker_count(len(serial_nums))
  results: dict[str, list[str]] = {}

  try:
    logger.info(f'🎬 [START DEBUG] Executing recording commands on {len(serial_nums)} devices')
    with concurrent.futures.ThreadPoolExecutor(max_workers=worker_count) as executor:
      future_map = {
          executor.submit(common.mp_run_command, command_map[serial]): serial
          for serial in serial_nums
      }

      for future in concurrent.futures.as_completed(future_map):
        serial = future_map[future]
        try:
          results[serial] = future.result()
        except Exception as exc:  # pragma: no cover - defensive
          logger.error(f'❌ [START DEBUG] Recording command failed for {serial}: {exc}')
          raise

    ordered_results = [results.get(serial, []) for serial in serial_nums]
    logger.info(f'🎬 [START DEBUG] Recording commands completed. Results: {ordered_results}')

    _verify_recording_started(serial_nums)

  except Exception as e:
    logger.error(f'❌ [START DEBUG] Error starting recording: {e}')
    logger.error(f'❌ [START DEBUG] Traceback: {traceback.format_exc()}')
    raise

  logger.info('✅ [START DEBUG] Recording started successfully')


def stop_to_screen_record_android_devices(
    serial_nums: list[str], file_name: str, output_path: str
) -> None:
  """Stop the screen record process for multiple devices."""

  logger.info('🔴 [MULTI-STOP DEBUG] Starting stop_to_screen_record_android_devices')
  logger.info(f'🔴 [MULTI-STOP DEBUG] Serial numbers: {serial_nums}')
  logger.info(f'🔴 [MULTI-STOP DEBUG] File name: {file_name}')
  logger.info(f'🔴 [MULTI-STOP DEBUG] Output path before normalization: {output_path}')

  output_path = common.make_gen_dir_path(output_path)
  logger.info(f'🔴 [MULTI-STOP DEBUG] Output path after normalization: {output_path}')

  try:
    logger.info(f'🔴 [MULTI-STOP DEBUG] Executing stop commands on {len(serial_nums)} devices')

    # Prepare function calls for parallel execution
    functions = [stop_to_screen_record_android_device] * len(serial_nums)
    args_list = [(serial, file_name, output_path) for serial in serial_nums]

    # Execute stop operations in parallel
    results = _execute_functions_parallel(functions, args_list, 'stop_screen_record')
    logger.info(f'🔴 [MULTI-STOP DEBUG] All stop tasks completed. Results: {results}')

  except Exception as e:
    logger.error(f'❌ [MULTI-STOP DEBUG] Error stopping recording: {e}')
    logger.error(f'❌ [MULTI-STOP DEBUG] Traceback: {traceback.format_exc()}')
    raise e

  logger.info('✅ [MULTI-STOP DEBUG] stop_to_screen_record_android_devices completed successfully')


def stop_to_screen_record_android_device(
    serial_num: str, name: str, output_path: str
):
  """Stop the screen record process for a single device."""

  logger.info(f'🔴 [SINGLE-STOP DEBUG] === Starting stop for device {serial_num} ===')
  logger.info(f'🔴 [SINGLE-STOP DEBUG] Name parameter: {name}')
  logger.info(f'🔴 [SINGLE-STOP DEBUG] Output path parameter: {output_path}')

  output_path = common.make_gen_dir_path(output_path)
  logger.info(f'🔴 [SINGLE-STOP DEBUG] Normalized output path: {output_path}')

  try:
    # Step 1: Stop the screenrecord process
    logger.info(f'🔴 [SINGLE-STOP DEBUG] STEP 1: Stopping screenrecord process for {serial_num}')
    stop_cmd = adb_commands.cmd_android_screen_record_stop(serial_num)
    logger.info(f'🔴 [SINGLE-STOP DEBUG] Stop command: {stop_cmd}')
    stop_result = common.run_command(stop_cmd)
    logger.info(f'🔴 [SINGLE-STOP DEBUG] Stop command result: {stop_result}')
    # Verify the process has stopped
    _verify_recording_stopped(serial_num)

    # Step 2: Pull the screen record to output path
    logger.info(f'🔴 [SINGLE-STOP DEBUG] STEP 2: Pulling screen record from device {serial_num}')
    pull_cmd = adb_commands.cmd_pull_android_screen_record(serial_num, name, output_path)
    logger.info(f'🔴 [SINGLE-STOP DEBUG] Pull command: {pull_cmd}')

    # Check if the file exists on device before pulling
    check_cmd = f'adb -s {serial_num} shell ls -la /sdcard/screenrecord_{serial_num}_{name}.mp4'
    logger.info(f'🔴 [SINGLE-STOP DEBUG] Checking file existence: {check_cmd}')
    check_result = common.run_command(check_cmd)
    logger.info(f'🔴 [SINGLE-STOP DEBUG] File check result: {check_result}')

    pull_result = common.run_command(pull_cmd)
    logger.info(f'🔴 [SINGLE-STOP DEBUG] Pull command result: {pull_result}')

    # Verify file was pulled successfully
    _verify_file_pulled(output_path, serial_num, name)

    # Step 3: Remove the file from device
    logger.info(f'🔴 [SINGLE-STOP DEBUG] STEP 3: Removing screen record file from device {serial_num}')
    rm_cmd = adb_commands.cmd_rm_android_screen_record(serial_num, name)
    logger.info(f'🔴 [SINGLE-STOP DEBUG] Remove command: {rm_cmd}')
    rm_result = common.run_command(rm_cmd)
    logger.info(f'🔴 [SINGLE-STOP DEBUG] Remove command result: {rm_result}')

    logger.info(f'✅ [SINGLE-STOP DEBUG] === Stop completed successfully for device {serial_num} ===')

  except Exception as e:
    logger.error(f'❌ [SINGLE-STOP DEBUG] Error stopping device {serial_num}: {e}')
    logger.error(f'❌ [SINGLE-STOP DEBUG] Traceback: {traceback.format_exc()}')
    raise e


def start_screen_record_device(serial: str, output_path: str, filename: str) -> None:
  """Start screen recording for a single device (wrapper function)."""
  logger.info(f'🎬 [WRAPPER] Starting screen recording for device {serial}, file: {filename}, output: {output_path}')

  base_name = filename.replace('.mp4', '') if filename.endswith('.mp4') else filename
  remote_path = f'/sdcard/screenrecord_{serial}_{base_name}.mp4'

  entry = {
    'filename': filename,
    'output_path': output_path,
    'remote_path': remote_path,
  }

  if native_bridge.is_available():
    try:
      native_bridge.start_screen_record(serial, remote_path)
      entry['native'] = True
      _active_recordings[serial] = entry
      _verify_recording_started([serial])
      return
    except native_bridge.NativeBridgeError as exc:
      logger.warning('Native screen recording start failed for %s: %s', serial, exc)

  entry['native'] = False
  _active_recordings[serial] = entry
  start_to_record_android_devices([serial], base_name)


def stop_screen_record_device(serial: str) -> None:
  """Stop screen recording for a single device (wrapper function)."""
  logger.info(f'🔴 [WRAPPER] Stopping screen recording for device {serial}')

  recording_info = _active_recordings.get(serial)
  if recording_info is None:
    logger.warning(f'⚠️ [WRAPPER] No active recording found for device {serial}, attempting simple stop')
    try:
      stop_cmd = f'adb -s {serial} shell pkill -f screenrecord'
      common.run_command(stop_cmd)
      logger.info(f'📱 [WRAPPER] Simple stop command executed for device {serial}')
    except Exception as exc:
      logger.error(f'❌ [WRAPPER] Error executing simple stop for {serial}: {exc}')
    return

  filename = recording_info['filename']
  output_path = recording_info['output_path']
  base_name = filename.replace('.mp4', '') if filename.endswith('.mp4') else filename
  is_native = recording_info.get('native', False)

  if is_native and native_bridge.is_available():
    try:
      native_bridge.stop_screen_record(serial)
    except native_bridge.NativeBridgeError as exc:
      logger.warning('Native screen recording stop failed for %s: %s', serial, exc)

  try:
    stop_to_screen_record_android_device(serial, base_name, output_path)
    if serial in _active_recordings:
      del _active_recordings[serial]
    logger.info(f'✅ [WRAPPER] Screen recording stopped successfully for device {serial}')
  except Exception as exc:
    logger.error(f'❌ [WRAPPER] Error stopping screen recording for {serial}: {exc}')
    if serial in _active_recordings:
      del _active_recordings[serial]
    raise


def _verify_recording_started(serial_nums: List[str]) -> bool:
  """Verify that screen recording has started on devices."""
  max_attempts = 10
  for attempt in range(max_attempts):
    all_started = True
    for serial in serial_nums:
      try:
        if _is_screenrecord_running(serial):
          continue
        all_started = False
        break
      except Exception as e:
        logger.debug(f'Failed to verify recording on {serial}: {e}')
        all_started = False
        break

    if all_started:
      logger.info(f'Screen recording verified on all {len(serial_nums)} devices')
      return True

    time.sleep(0.05)

  logger.warning(f'Could not verify recording started on all devices after {max_attempts} attempts')
  return False


def _is_screenrecord_running(serial: str) -> bool:
  """Check if screenrecord process is running on the device."""
  pid_commands = [
      'pidof screenrecord',
      'pidof /system/bin/screenrecord',
  ]

  for command in pid_commands:
    cmd = adb_commands._build_adb_shell_command(serial, command)
    result = common.run_command(cmd, timeout=3)
    if result and any(str(line).strip() for line in result):
      return True

  # Fallback to ps listing
  cmd = adb_commands._build_adb_shell_command(serial, 'ps -A')
  result = common.run_command(cmd, timeout=3)
  if result and any('screenrecord' in str(line) for line in result):
    return True

  return False


def _verify_recording_stopped(serial_num: str) -> bool:
  """Verify that screen recording has stopped on a device."""

  max_attempts = 30  # Up to ~1.5s with 50ms polling
  for _ in range(max_attempts):
    try:
      if not _is_screenrecord_running(serial_num):
        logger.info(f'Screen recording stopped on device {serial_num}')
        return True
    except Exception as exc:
      logger.debug(f'Failed to verify recording stopped on {serial_num}: {exc}')

    time.sleep(0.05)

  logger.warning(f'Could not verify recording stopped on {serial_num} after {max_attempts} attempts')
  return False


def _verify_file_pulled(output_path: str, serial_num: str, name: str) -> bool:
  """Verify that screen recording file was pulled successfully."""
  expected_filename = f"screenrecord_{serial_num}_{name}.mp4"
  local_file_path = os.path.join(output_path, expected_filename)

  max_attempts = 20  # Up to 2 seconds
  for attempt in range(max_attempts):
    if os.path.exists(local_file_path):
      file_size = os.path.getsize(local_file_path)
      if file_size > 0:
        logger.info(f'Screen recording file pulled successfully: {local_file_path} ({file_size} bytes)')
        return True

    # Minimal wait before retry (non-blocking)
    time.sleep(0.01)

  logger.warning(f'Could not verify file was pulled: {local_file_path}')
  return False


__all__ = [
    "start_to_record_android_devices",
    "stop_to_screen_record_android_devices",
    "stop_to_screen_record_android_device",
    "start_screen_record_device",
    "stop_screen_record_device",
    "_verify_recording_started",
    "_is_screenrecord_running",
    "_verify_recording_stopped",
    "_verify_file_pulled",
]
