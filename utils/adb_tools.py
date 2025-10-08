"""Get devices list and use the device info to set object."""

import concurrent.futures
import glob
import os
import posixpath
import pathlib
import platform
import re
import shutil
import subprocess
import shlex
import signal
import tempfile
import threading
import time
import traceback
from typing import List, Callable, Any, Optional
from functools import wraps

from config.constants import ADBConstants

from utils import adb_commands
from utils import adb_models
from utils import common
from utils import dump_device_ui
from utils import native_bridge


## GMS app package name
gms_package_name = 'com.google.android.gms'

logger = common.get_logger('adb_tools')

ACCEPTED_DEVICE_STATUSES = {
    ADBConstants.DEVICE_STATE_DEVICE,
    ADBConstants.DEVICE_STATE_UNAUTHORIZED,
    ADBConstants.DEVICE_STATE_RECOVERY,
    ADBConstants.DEVICE_STATE_BOOTLOADER,
    getattr(ADBConstants, 'DEVICE_STATE_SIDELOAD', 'sideload'),
    '',
}


def adb_operation(operation_name: str = None, default_return=None, log_errors: bool = True):
  """Decorator for ADB operations with standardized error handling.

  Args:
    operation_name: Name of the operation for logging (defaults to function name)
    default_return: Value to return on error
    log_errors: Whether to log errors or suppress them

  Returns:
    Decorated function with error handling
  """
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
  """Decorator specifically for device operations that take serial_num as first arg.

  Args:
    default_return: Value to return on error
    log_errors: Whether to log errors

  Returns:
    Decorated function with device-specific error handling
  """
  def decorator(func):
    @wraps(func)
    def wrapper(serial_num, *args, **kwargs):
      try:
        return func(serial_num, *args, **kwargs)
      except Exception as e:
        if log_errors:
          logger.error(f'Error in {func.__name__} for device {serial_num}: {e}')
          logger.debug(f'Traceback for {func.__name__} (device {serial_num}): {traceback.format_exc()}')
        return default_return
    return wrapper
  return decorator


def _execute_commands_parallel(commands: List[str], operation_name: str) -> List[str]:
  """Execute multiple ADB commands in parallel.

  Args:
    commands: List of command strings to execute
    operation_name: Name of the operation for logging

  Returns:
    List of command results
  """
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
  """Execute multiple functions in parallel.

  Args:
    functions: List of functions to execute
    args_list: List of arguments for each function
    operation_name: Name of the operation for logging

  Returns:
    List of function results
  """
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


def is_adb_installed() -> bool:
  """Checks if ADB is installed and available in the system's PATH or common locations.

  Returns:
    True if ADB is installed, False otherwise.
  """
  import os
  import shutil

  # First try to find adb in PATH
  if shutil.which('adb'):
    try:
      result = common.run_command('adb version')
      return bool(result)
    except (subprocess.SubprocessError, OSError) as e:
      logger.debug(f'ADB availability check failed: {e}')
    except Exception as e:
      logger.warning(f'Unexpected error checking ADB availability: {e}')

  # If not in PATH, try common locations based on platform
  import platform
  system = platform.system().lower()

  if system == 'darwin':  # macOS
    common_paths = [
      '/opt/homebrew/bin/adb',
      '/usr/local/bin/adb',
      '/opt/homebrew/Caskroom/android-platform-tools/*/platform-tools/adb',
      os.path.expanduser('~/Library/Android/sdk/platform-tools/adb'),
      os.path.expanduser('~/Android/sdk/platform-tools/adb'),
      '/Applications/Android Studio.app/Contents/plugins/android/lib/android.jar/../../../platform-tools/adb'
    ]
  elif system == 'linux':  # Linux
    common_paths = [
      '/usr/bin/adb',
      '/usr/local/bin/adb',
      '/opt/android-sdk/platform-tools/adb',
      '/snap/bin/adb',
      os.path.expanduser('~/Android/Sdk/platform-tools/adb'),
      os.path.expanduser('~/android-sdk/platform-tools/adb'),
      os.path.expanduser('~/.android-sdk/platform-tools/adb'),
      '/opt/android-studio/bin/studio.sh/../../../platform-tools/adb',
      os.path.expanduser('~/android-studio/platform-tools/adb'),
      '/flatpak/exports/bin/adb'  # Flatpak installs
    ]
  else:  # Fallback for other systems
    common_paths = [
      '/usr/bin/adb',
      '/usr/local/bin/adb',
      os.path.expanduser('~/Android/Sdk/platform-tools/adb'),
      os.path.expanduser('~/android-sdk/platform-tools/adb')
    ]

  for adb_path in common_paths:
    # Handle wildcard paths
    if '*' in adb_path:
      matches = glob.glob(adb_path)
      for match in matches:
        if os.path.isfile(match) and os.access(match, os.X_OK):
          try:
            result = common.run_command(f'"{match}" version')
            if result:
              # Update the global PATH or set a global ADB path
              _set_adb_path(match)
              return True
          except (subprocess.SubprocessError, OSError) as e:
            logger.debug(f'Failed to test ADB at {match}: {e}')
            continue
          except Exception as e:
            logger.warning(f'Unexpected error testing ADB at {match}: {e}')
            continue
    else:
      if os.path.isfile(adb_path) and os.access(adb_path, os.X_OK):
        try:
          result = common.run_command(f'"{adb_path}" version')
          if result:
            # Update the global PATH or set a global ADB path
            _set_adb_path(adb_path)
            return True
        except (subprocess.SubprocessError, OSError) as e:
          logger.debug(f'Failed to test ADB at {adb_path}: {e}')
          continue
        except Exception as e:
          logger.warning(f'Unexpected error testing ADB at {adb_path}: {e}')
          continue

  return False


def _set_adb_path(adb_path: str):
  """Set the ADB path for use in other functions."""
  import os
  global _adb_command_prefix
  _adb_command_prefix = f'"{adb_path}"'
  # Also add to PATH for subprocess calls
  adb_dir = os.path.dirname(adb_path)
  current_path = os.environ.get('PATH', '')
  if adb_dir not in current_path:
    os.environ['PATH'] = f"{adb_dir}:{current_path}"


# Global variable to store custom ADB path
_adb_command_prefix = 'adb'

# Global variable to store custom scrcpy path
_scrcpy_command_path = 'scrcpy'


def _determine_worker_count(task_count: int) -> int:
  """Select a sensible worker count for per-device parallelism.

  Args:
    task_count: Number of tasks to execute.

  Returns:
    Number of threads to schedule.
  """
  if task_count <= 0:
    return 0
  cpu_count = os.cpu_count() or 1
  return max(1, min(task_count, cpu_count))


def get_device_serial_num_list():
  return [l.device_serial_num for l in get_devices_list()]


def get_devices_list() -> list[adb_models.DeviceInfo]:
  """Get devices list and use the device info to set object.

  Returns:
    device_infos: the device info list.
  """
  result = []
  init_devices = common.run_command(adb_commands.cmd_get_adb_devices(), 1)
  logger.info('Get init devices: %s', init_devices)

  parsed_devices: list[list[str]] = []
  for raw_line in init_devices:
    if not raw_line:
      continue

    parts = [x for x in raw_line.split() if x]
    if not parts:
      continue

    status = parts[1].lower() if len(parts) > 1 else ''
    if status and status not in ACCEPTED_DEVICE_STATUSES:
      logger.debug('Skipping device %s due to status %s', parts[0], status)
      continue

    parsed_devices.append(parts)

  if not parsed_devices:
    logger.warning('Not found device')
    return result

  # Prepare function calls for parallel execution
  functions = [device_info_entry] * len(parsed_devices)
  # Each device_info_entry expects a single list argument, not multiple args
  args_list = [(parts,) for parts in parsed_devices]

  # Execute device info collection in parallel
  results = _execute_functions_parallel(functions, args_list, 'get_devices_list')

  # Filter out None results and return
  result = [device_info for device_info in results if device_info is not None]
  return result


def get_devices_list_fast() -> list[adb_models.DeviceInfo]:
  """Get devices list with basic info only (fast version for immediate UI display).

  Returns:
    device_infos: the device info list with basic information only.
  """
  result = []
  init_devices = common.run_command(adb_commands.cmd_get_adb_devices(), 1)
  logger.info('Get init devices (fast): %s', init_devices)
  filtered_devices: list[list[str]] = []
  for raw_line in init_devices:
    if not raw_line:
      continue

    parts = [x for x in raw_line.split() if x]
    if not parts:
      continue

    status = parts[1].lower() if len(parts) > 1 else ''
    if status and status not in ACCEPTED_DEVICE_STATUSES:
      logger.debug('Skipping device %s due to status %s', parts[0], status)
      continue

    filtered_devices.append(parts)

  if not filtered_devices:
    logger.warning('Not found device')
    return result

  # Prepare function calls for parallel execution (basic info only)
  functions = [device_basic_info_entry] * len(filtered_devices)
  args_list = [(info,) for info in filtered_devices]

  # Execute basic device info collection in parallel
  results = _execute_functions_parallel(functions, args_list, 'get_devices_list_fast')

  # Filter out None results and return
  result = [device_info for device_info in results if device_info is not None]
  logger.info(f'Fast device discovery completed: {len(result)} devices')
  return result


def device_basic_info_entry(info: List[str]) -> Optional[adb_models.DeviceInfo]:
  """Organize basic device info only (fast version without detailed checks).

  Args:
    info: device info from the adb

  Returns:
    Basic device info with placeholders for detailed information.
  """
  logger.info(f'Getting basic info for: {info}')
  serial_num = info[0]

  if len(info) > 1:
    device_status = info[1].lower()
    if device_status and device_status not in ACCEPTED_DEVICE_STATUSES:
      logger.debug('Filtered out %s during basic device entry (status=%s)', serial_num, device_status)
      return None

  # usb: ?#
  device_usb = 'None'
  if len(info) > 2 and ':' in info[2]:
    device_usb = info[2].split(':')[1]

  # product: ?#
  device_prod = 'None'
  if len(info) > 3 and ':' in info[3]:
    device_prod = info[3].split(':')[1]

  # model: ?#
  device_model = 'None'
  if len(info) > 4 and ':' in info[4]:
    device_model = info[4].split(':')[1]

  logger.info(f'Basic phone info: {serial_num}, {device_usb}, {device_prod}, {device_model}')

  # 創建基本設備信息，詳細信息初始為 None，稍後根據加載結果更新
  return adb_models.DeviceInfo(
      serial_num,
      device_usb,
      device_prod,
      device_model,
      None,  # WiFi狀態稍後加載
      None,  # 藍牙狀態稍後加載
      None,  # Android版本稍後加載，加載失敗時設為Unknown
      None,  # API等級稍後加載，加載失敗時設為Unknown
      None,  # GMS版本稍後加載，加載失敗時設為Unknown
      None,  # Build fingerprint稍後加載，加載失敗時設為Unknown
  )


def get_device_detailed_info(serial_num: str) -> dict:
  """Get detailed information for a specific device (async operation).

  Args:
    serial_num: Device serial number

  Returns:
    Dictionary with detailed device information
  """
  logger.info('Fetching detailed information for device %s', serial_num)

  try:
    detailed_info = {
      'wifi_status': check_wifi_is_on(serial_num),
      'bluetooth_status': check_bluetooth_is_on(serial_num),
      'android_version': get_android_version(serial_num),
      'android_api_level': get_android_api_level(serial_num),
      'gms_version': get_gms_version(serial_num),
      'build_fingerprint': get_build_fingerprint(serial_num),
      'audio_state': get_audio_state_summary(serial_num),
      'bluetooth_manager_state': get_bluetooth_manager_state_summary(serial_num),
    }
    logger.info('Detailed information retrieved for device %s', serial_num)
    return detailed_info
  except Exception as e:
    logger.error('Failed to retrieve detailed information for device %s: %s', serial_num, e)
    return {
      'wifi_status': None,
      'bluetooth_status': None,
      'android_version': 'Unknown',
      'android_api_level': 'Unknown',
      'gms_version': 'Unknown',
      'build_fingerprint': 'Unknown',
      'audio_state': 'Unknown',
      'bluetooth_manager_state': 'Unknown',
    }


def device_info_entry(info: List[str]) -> adb_models.DeviceInfo:
  """Organize device info.

  Args:
    info: device info from the adb

  Returns:
    Organize new device info.
  """
  logger.info(info)
  serial_num = info[0]
  # usb: ?#
  device_usb = 'None'
  if len(info) > 2 and ':' in info[2]:
    device_usb = info[2].split(':')[1]
  # product: ?#
  device_prod = 'None'
  if len(info) > 3 and ':' in info[3]:
    device_prod = info[3].split(':')[1]
  # model: ?#
  device_model = 'None'
  if len(info) > 4 and ':' in info[4]:
    device_model = info[4].split(':')[1]
  logger.info(
      'Get phone info %s, %s, %s, %s',
      serial_num,
      device_usb,
      device_prod,
      device_model,
  )
  check_wifi = check_wifi_is_on(serial_num)
  check_bt = check_bluetooth_is_on(serial_num)
  android_ver = get_android_version(serial_num)
  android_api_level = get_android_api_level(serial_num)
  gms_version_str = get_gms_version(serial_num)
  build_fingerprint = get_build_fingerprint(serial_num)
  return adb_models.DeviceInfo(
      serial_num,
      device_usb,
      device_prod,
      device_model,
      check_wifi,
      check_bt,
      android_ver,
      android_api_level,
      gms_version_str,
      build_fingerprint,
  )


def generate_the_android_bug_report(
    root_folder: str,
    device_infos: list[adb_models.DeviceInfo],
    callback=None,
) -> None:
  """Generate the android bug report.

  Args:
    root_folder: the root folder to store the extracted info.
    device_infos: the device info list.
    callback: Call back foreach result
  """

  logger.info('----------Start to generate bug report----------')
  if not device_infos:
    logger.warning('Device info list cannot be empty.')
    return
  command_list: list[str] = []
  root_folder = common.make_gen_dir_path(root_folder)

  for l in device_infos:
    s = l.device_serial_num
    phone = l.device_model
    ver = get_gms_version(s)
    phone_sign = l.device_model
    output_path = common.make_full_path(
        root_folder, f'{phone}_{phone_sign}_{s}_gms_ver_{ver}'
    )
    output_path = common.make_gen_dir_path(output_path)
    cmd = adb_commands.cmd_output_device_bug_report(s, output_path)
    command_list.append(cmd)
  if not command_list:
    logger.warning(
        '----------Failed to generate the bug report, the command list is'
        ' empty.----------'
    )
    return

  logger.info('Start concurrent generate bug reports.')
  results = _execute_commands_parallel(command_list, 'generate_bug_report')
  for r in results:
    logger.info('Get generate result %s', r)
    callback(results)

  logger.info('----------End generate bug report finished.----------')


@adb_device_operation(default_return=None)
def generate_bug_report_device(
    serial_num: str,
    output_path: str,
    timeout: int = 300,
    *,
    cancel_event: Optional[threading.Event] = None,
) -> dict:
  """Generate bug report for a single device with enhanced error handling.

  Args:
    serial_num: Device serial number
    output_path: Full path where to save the bug report (will add .zip if needed)
    timeout: Command timeout in seconds (default: 5 minutes)

  Returns:
    dict: Result with success status, output path, and any error information
  """
  result = {
    'success': False,
    'serial': serial_num,
    'output_path': output_path,
    'error': None,
    'file_size': 0,
    'details': ''
  }

  executed_command = ''
  command_output: List[str] = []

  try:
    # Ensure output path has .zip extension
    if not output_path.endswith('.zip'):
      output_path += '.zip'
      result['output_path'] = output_path

    logger.info(f'Generating bug report for device {serial_num}...')
    logger.debug(f'Output path: {output_path}')

    # Check if device is available
    if not _is_device_available(serial_num):
      result['error'] = f'Device {serial_num} is not available or not responding'
      logger.warning(result['error'])
      result['details'] = f'Command not executed because device {serial_num} was unavailable'
      return result

    # Check device manufacturer for known issues
    device_info = _get_device_manufacturer_info(serial_num)
    manufacturer = device_info.get('manufacturer', '').lower()

    # Check if device requires special handling for bug reports
    if manufacturer in ['samsung', 'huawei', 'xiaomi', 'oppo', 'vivo', 'oneplus']:
      logger.info(f'Detected {manufacturer} device, checking bug report permissions...')
      if not _check_bug_report_permissions(serial_num):
        result['error'] = f'{manufacturer.title()} device may require developer options or USB debugging permissions for bug reports'
        logger.warning(result['error'])
        logger.info('Try: 1) Enable Developer Options 2) Enable USB Debugging 3) Grant computer authorization')
        result['details'] = 'Command not executed because prerequisite permissions are missing'
        return result

    # Generate the command
    cmd = adb_commands.cmd_output_device_bug_report(serial_num, output_path)
    executed_command = cmd

    logger.info(f'Executing: {cmd}')

    # Launch cancellable subprocess for better cancellation responsiveness
    popen_kwargs: dict = {
      'stdout': subprocess.PIPE,
      'stderr': subprocess.PIPE,
      'text': True,
      'encoding': 'utf-8',
      'shell': False,
    }

    system = platform.system().lower()
    if system == 'windows':  # Create a new process group for CTRL_BREAK
      popen_kwargs['creationflags'] = getattr(subprocess, 'CREATE_NEW_PROCESS_GROUP', 0)
    else:  # Start a new session for group signalling
      popen_kwargs['preexec_fn'] = os.setsid

    proc = subprocess.Popen(shlex.split(cmd), **popen_kwargs)

    stdout_chunks: list[str] = []
    stderr_chunks: list[str] = []

    start_time = time.time()
    cancelled = False
    while True:
      try:
        out, err = proc.communicate(timeout=0.5)
        if out:
          stdout_chunks.append(out)
        if err:
          stderr_chunks.append(err)
        break
      except subprocess.TimeoutExpired:
        # Check timeout
        if timeout and (time.time() - start_time) > timeout:
          try:
            if system == 'windows':
              proc.terminate()
            else:
              os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
          except Exception:
            pass
          result['error'] = f'Bug report generation timed out after {timeout} seconds'
          logger.error(result['error'])
          break

        # Check cancellation
        if cancel_event is not None and cancel_event.is_set():
          cancelled = True
          try:
            if system == 'windows':
              # Try to gracefully break; fall back to terminate/kill
              try:
                proc.send_signal(getattr(signal, 'CTRL_BREAK_EVENT', signal.SIGTERM))
              except Exception:
                proc.terminate()
              time.sleep(0.5)
              if proc.poll() is None:
                proc.kill()
            else:
              try:
                os.killpg(os.getpgid(proc.pid), signal.SIGINT)
              except Exception:
                proc.terminate()
              time.sleep(0.5)
              if proc.poll() is None:
                proc.kill()
          except Exception:
            pass
          try:
            out, err = proc.communicate(timeout=2)
            if out:
              stdout_chunks.append(out)
            if err:
              stderr_chunks.append(err)
          except Exception:
            pass
          result['error'] = 'Cancelled by user'
          logger.info('Bug report generation for %s cancelled by user', serial_num)
          break

    command_output = (''.join(stdout_chunks) + '\n' + ''.join(stderr_chunks)).splitlines()
    result['details'] = f'Command: {cmd}'
    if command_output:
      joined_output = ' '.join(command_output)
      result['details'] += f'\nOutput: {joined_output}'

    # Check command output for common Samsung/manufacturer errors
    if command_output:
      output_str = ' '.join(str(item) for item in command_output).lower()
      if any(error in output_str for error in ['permission denied', 'access denied', 'not allowed', 'unauthorized']):
        result['error'] = f'Permission denied - {manufacturer.title()} device requires additional authorization'
        logger.error(result['error'])
        logger.debug(f'Bug report command output for {serial_num}: {output_str}')
        return result

    # Check if file was created and has reasonable size
    if os.path.exists(output_path):
      file_size = os.path.getsize(output_path)
      result['file_size'] = file_size

      if file_size > 1024 and not cancelled:  # At least 1KB and not cancelled
        result['success'] = True
        logger.info(f'✅ Bug report generated successfully for {serial_num}')
        logger.info(f'   File: {output_path} ({file_size:,} bytes)')
        result['details'] = f'Command: {cmd}\nFile saved to {output_path} ({file_size} bytes)'
      else:
        if cancelled:
          result['error'] = 'Cancelled by user'
          # Clean up tiny partial files to avoid user confusion
          try:
            if file_size < 1024:
              os.remove(output_path)
              logger.info('Removed partial bug report file after cancellation: %s', output_path)
          except Exception:
            pass
        else:
          result['error'] = f'Bug report file too small ({file_size} bytes), likely incomplete'
          logger.warning(result['error'])
          result['details'] = f'Command: {cmd}\nFile size only {file_size} bytes'
    else:
      result['error'] = 'Bug report file was not created'
      logger.error(f'Bug report file not found: {output_path}')
      result['details'] = f'Command: {cmd}\nNo bug report generated at {output_path}'

  except subprocess.TimeoutExpired:
    result['error'] = f'Bug report generation timed out after {timeout} seconds'
    logger.error(result['error'])
    result['details'] = f'Command: {executed_command or "<unavailable>"}\nTimeout after {timeout} seconds'
  except Exception as e:
    result['error'] = f'Bug report generation failed: {str(e)}'
    logger.error(result['error'])
    logger.debug(f'Full error details: {e}', exc_info=True)
    result['details'] = f'Command: {executed_command or "<unavailable>"}\nError: {str(e)}'

  return result


def generate_bug_report_device_streaming(
    serial_num: str,
    output_path: str,
    timeout: int = 300,
    *,
    cancel_event: Optional[threading.Event] = None,
    progress_cb: Optional[Callable[[int], None]] = None,
) -> dict:
  """Generate bug report using bugreportz -p to report streaming progress.

  Falls back to non-streaming when unsupported.

  Returns dict similar to generate_bug_report_device, with extra key:
    'stream_supported': bool
  """
  result = {
    'success': False,
    'serial': serial_num,
    'output_path': output_path if output_path.endswith('.zip') else output_path + '.zip',
    'error': None,
    'file_size': 0,
    'details': '',
    'stream_supported': False,
  }

  try:
    logger.info('Attempting streaming bugreport for %s', serial_num)

    # Ensure output path suffix
    if not output_path.endswith('.zip'):
      output_path += '.zip'

    system = platform.system().lower()
    popen_kwargs: dict = {
      'stdout': subprocess.PIPE,
      'stderr': subprocess.STDOUT,
      'text': True,
      'encoding': 'utf-8',
      'shell': False,
    }
    if system == 'windows':
      popen_kwargs['creationflags'] = getattr(subprocess, 'CREATE_NEW_PROCESS_GROUP', 0)
    else:
      popen_kwargs['preexec_fn'] = os.setsid

    # Start streaming progress
    cmd = [
      'adb', '-s', serial_num,
      'shell', 'bugreportz', '-p'
    ]
    proc = subprocess.Popen(cmd, **popen_kwargs)
    result['stream_supported'] = True

    start_time = time.time()
    remote_path = ''
    last_percent = -1

    while True:
      # Check cancel
      if cancel_event is not None and cancel_event.is_set():
        try:
          if system == 'windows':
            try:
              proc.send_signal(getattr(signal, 'CTRL_BREAK_EVENT', signal.SIGTERM))
            except Exception:
              proc.terminate()
            time.sleep(0.5)
            if proc.poll() is None:
              proc.kill()
          else:
            try:
              os.killpg(os.getpgid(proc.pid), signal.SIGINT)
            except Exception:
              proc.terminate()
            time.sleep(0.5)
            if proc.poll() is None:
              proc.kill()
        except Exception:
          pass
        result['error'] = 'Cancelled by user'
        logger.info('Streaming bugreport cancelled for %s', serial_num)
        break

      # Timeout
      if timeout and (time.time() - start_time) > timeout:
        try:
          if system == 'windows':
            proc.terminate()
          else:
            os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
        except Exception:
          pass
        result['error'] = f'Streaming bugreport timed out after {timeout} seconds'
        logger.error(result['error'])
        break

      line = proc.stdout.readline() if proc.stdout else ''
      if not line:
        if proc.poll() is not None:
          break
        time.sleep(0.05)
        continue

      payload = parse_bugreportz_line(line)
      logger.debug('bugreportz -p parsed: %s', payload)

      if payload.get('type') == 'progress':
        percent = int(payload.get('percent', 0))
        if percent != last_percent:
          last_percent = percent
          if progress_cb:
            try:
              progress_cb(percent)
            except Exception:
              pass
      elif payload.get('type') == 'ok':
        remote_path = payload.get('path', '')
      elif payload.get('type') == 'fail':
        result['error'] = payload.get('reason', 'FAIL')

    # Process ended
    code = proc.poll()
    if code not in (0, None) and not remote_path and not result['error']:
      result['error'] = f'bugreportz returned non-zero code {code}'

    if result['error']:
      return result

    if not remote_path:
      # Streaming not available or no path returned
      result['stream_supported'] = False
      result['error'] = 'Streaming unsupported or did not return path'
      return result

    # Pull the generated zip
    pull_cmd = ['adb', '-s', serial_num, 'pull', remote_path, output_path]
    try:
      pull_proc = subprocess.run(pull_cmd, check=False, capture_output=True, text=True)
      if pull_proc.returncode != 0:
        result['error'] = f'Failed to pull bugreport: {pull_proc.stderr.strip()}'
        return result
    except Exception as exc:
      result['error'] = f'Failed to pull bugreport: {exc}'
      return result

    if os.path.exists(output_path):
      file_size = os.path.getsize(output_path)
      result['file_size'] = file_size
      if file_size > 1024:
        result['success'] = True
        result['output_path'] = output_path
      else:
        result['error'] = f'Bug report file too small ({file_size} bytes), likely incomplete'

    return result
  except Exception as exc:
    logger.debug('Streaming bugreport path failed, will fallback: %s', exc)
    result['stream_supported'] = False
    result['error'] = str(exc)
    return result

def _is_device_available(serial_num: str) -> bool:
  """Check if device is available and responding.

  Args:
    serial_num: Device serial number

  Returns:
    bool: True if device is available
  """
  try:
    cmd = f'adb -s {serial_num} get-state'
    result = common.run_command(cmd)

    if isinstance(result, list):
      normalized = ' '.join(str(item).lower() for item in result)
    else:
      normalized = str(result).lower()

    return 'device' in normalized
  except (subprocess.SubprocessError, subprocess.TimeoutExpired) as e:
    logger.debug(f'Device {serial_num} availability check failed: {e}')
    return False
  except Exception as e:
    logger.warning(f'Unexpected error checking device {serial_num}: {e}')
    return False


def _get_device_manufacturer_info(serial_num: str) -> dict:
  """Get device manufacturer information.

  Args:
    serial_num: Device serial number

  Returns:
    dict: Device manufacturer info
  """
  try:
    # Get manufacturer property
    manufacturer_cmd = adb_commands._build_getprop_command(serial_num, 'ro.product.manufacturer')
    manufacturer_result = common.run_command(manufacturer_cmd, 10)
    manufacturer = ''
    if manufacturer_result and isinstance(manufacturer_result, list):
      manufacturer = ' '.join(str(item) for item in manufacturer_result).strip()

    # Get model property for additional context
    model_cmd = adb_commands._build_getprop_command(serial_num, 'ro.product.model')
    model_result = common.run_command(model_cmd, 10)
    model = ''
    if model_result and isinstance(model_result, list):
      model = ' '.join(str(item) for item in model_result).strip()

    return {
      'manufacturer': manufacturer,
      'model': model
    }
  except Exception as e:
    logger.debug(f'Could not get manufacturer info for {serial_num}: {e}')
    return {'manufacturer': '', 'model': ''}


def _check_bug_report_permissions(serial_num: str) -> bool:
  """Check if device has permissions for bug report generation.

  Args:
    serial_num: Device serial number

  Returns:
    bool: True if permissions are likely sufficient
  """
  try:
    # Test with a simple shell command that requires similar permissions
    test_cmd = adb_commands._build_adb_shell_command(serial_num, 'echo "permission_test"')
    result = common.run_command(test_cmd, 5)

    if result and 'permission_test' in str(result):
      # Try to access a system service that bug reports need
      service_cmd = adb_commands._build_adb_shell_command(serial_num, 'service list | head -1')
      service_result = common.run_command(service_cmd, 10)

      if service_result and len(service_result) > 0:
        return True

    return False
  except Exception as e:
    logger.debug(f'Permission check failed for {serial_num}: {e}')
    return False


def clear_device_logcat(serial_num) -> bool:
  logger.info('Start to clear logcat')
  if not serial_num:
    logger.warning('Serial number cannot be empty')
    return False
  common.run_command(adb_commands.cmd_clear_device_logcat(serial_num))
  logger.info('Clear logcat Ok.')
  return True


@adb_device_operation(default_return=[])
def get_package_pids(serial_num: str, package_name: str) -> List[str]:
  """Return running process IDs for the given package."""
  if not package_name:
    return []

  command = adb_commands.cmd_adb_shell(serial_num, f'pidof {package_name}')
  output_lines = common.run_command(command)

  if not output_lines:
    return []

  pids: List[str] = []
  for line in output_lines:
    pids.extend(pid.strip() for pid in line.split() if pid.strip())
  return pids


def run_adb_shell_command(
    serial_nums: list[str],
    command_str: str,
    callback=None,
) -> None:
  """Run adb custom command."""
  commands = []
  for s in serial_nums:
    cmd = adb_commands.cmd_adb_shell(s, command_str)
    commands.append(cmd)

  # Execute per-device shell commands in parallel with accurate operation label
  results = _execute_commands_parallel(commands, 'run_adb_shell_command')

  # Log detailed results for each device
  for i, (serial, cmd, result) in enumerate(zip(serial_nums, commands, results)):
    logger.info(f'[{serial}] Command: {command_str}')
    if result:
      # Show first few lines of output
      output_lines = result[:5] if len(result) > 5 else result
      for line in output_lines:
        logger.info(f'[{serial}] Output: {line}')
      if len(result) > 5:
        logger.info(f'[{serial}] ... and {len(result) - 5} more lines')
    else:
      logger.info(f'[{serial}] No output or command failed')

  logger.info(f'Run adb custom command completed on {len(serial_nums)} device(s)')
  if callback:
    callback(results)


def run_cancellable_adb_shell_command(
    serial_nums: list[str],
    command_str: str,
) -> list[subprocess.Popen]:
    """Run adb shell command on multiple devices and return the process objects."""
    processes = []
    for s in serial_nums:
        cmd = adb_commands.cmd_adb_shell(s, command_str)
        process = common.create_cancellable_process(cmd)
        if process:
            processes.append(process)
    return processes


def extract_all_discovery_service_info(
    root_folder: str,
    serial_nums: list[str],
    callback=None,
):
  """Extract the discovery service info from the device.

  Args:
    root_folder: the root folder to store the extracted info.
    serial_nums: list of device serial numbers.
    callback: Call back foreach result.
  """

  logger.info('Start to extract discovery info.')
  root_folder = common.make_gen_dir_path(root_folder)
  commands = []
  for s in serial_nums:
    cmd = adb_commands.cmd_extract_discovery_service_info(s, root_folder)
    commands.append(cmd)

  results = _execute_commands_parallel(commands, 'extract_to_android_device')
  for r in results:
    logger.info('Get extract result %s', r)
    callback(results)

  logger.info('Extract done.')


def extract_single_discovery_service_info(root_folder: str, serial_num: str):
  """Extract the discovery service info from the device.

  Args:
    root_folder: the root folder to store the extracted info.
    serial_num: device serial numbers.
  """
  logger.info('Start to extract discovery info.')

  root_folder = common.get_full_path(root_folder)
  cmd = adb_commands.cmd_extract_discovery_service_info(serial_num, root_folder)
  common.run_command(cmd)
  logger.info('Extract done.')


def check_wifi_is_on(serial_num):
  cmd = adb_commands.cmd_get_device_wifi(serial_num)
  result = common.run_command(cmd)
  if result:
    data = str(result[0])
    if data.isnumeric():
      return int(data)
  return 0


def check_bluetooth_is_on(serial_num):
  cmd = adb_commands.cmd_get_device_bluetooth(serial_num)
  result = common.run_command(cmd)
  if result:
    data = str(result[0])
    if data.isnumeric():
      return int(data)
  return 0


def get_audio_state_summary(serial_num: str) -> str:
  """Return a concise summary for dumpsys audio."""
  lines = common.run_command(adb_commands.cmd_get_audio_dump(serial_num))
  if not lines:
    return 'Unknown'

  mode_pattern = re.compile(r'\bmode\s*[:=]\s*([A-Za-z_]+)', re.IGNORECASE)
  ringer_pattern = re.compile(r'\bringer\s+mode\s*[:=]\s*([A-Za-z_]+)', re.IGNORECASE)
  music_pattern = re.compile(r'music\s+active\s*[:=]\s*([A-Za-z_]+)', re.IGNORECASE)
  device_pattern = re.compile(r'device\s+(?:current\s+)?state\s*[:=]\s*(.+)', re.IGNORECASE)
  sco_pattern = re.compile(r'sco\s+state\s*[:=]\s*(.+)', re.IGNORECASE)

  summary: dict[str, str] = {}
  for raw_line in lines:
    stripped = raw_line.strip()
    if not stripped:
      continue

    if 'mode' not in summary:
      match = mode_pattern.search(stripped)
      if match:
        summary['mode'] = match.group(1).upper()
        continue

    if 'ringer' not in summary:
      match = ringer_pattern.search(stripped)
      if match:
        summary['ringer'] = match.group(1).upper()
        continue

    if 'music_active' not in summary:
      match = music_pattern.search(stripped)
      if match:
        summary['music_active'] = match.group(1).lower()
        continue

    if 'device_state' not in summary:
      match = device_pattern.search(stripped)
      if match:
        summary['device_state'] = match.group(1).strip()
        continue

    if 'sco_state' not in summary:
      match = sco_pattern.search(stripped)
      if match:
        summary['sco_state'] = match.group(1).strip()

    if len(summary) >= 5:
      break

  parts = []
  if 'mode' in summary:
    parts.append(f"mode={summary['mode']}")
  if 'ringer' in summary:
    parts.append(f"ringer={summary['ringer']}")
  if 'music_active' in summary:
    parts.append(f"music_active={summary['music_active']}")
  if 'device_state' in summary:
    parts.append(f"device_state={summary['device_state']}")
  if 'sco_state' in summary:
    parts.append(f"sco_state={summary['sco_state']}")

  if parts:
    return ' | '.join(parts)

  snippet = ' '.join(line.strip() for line in lines[:5] if line.strip())
  return snippet[:200] if snippet else 'Unknown'


def get_bluetooth_manager_state_summary(serial_num: str) -> str:
  """Return bluetooth manager high-level state."""
  lines = common.run_command(adb_commands.cmd_get_bluetooth_manager_state(serial_num))
  if not lines:
    return 'Unknown'

  state_pattern = re.compile(r'state\s*[:=]\s*([A-Za-z_]+)', re.IGNORECASE)
  for raw_line in lines:
    stripped = raw_line.strip()
    if not stripped:
      continue
    match = state_pattern.search(stripped)
    if match:
      return match.group(1).upper()

  first_line = lines[0].strip()
  return first_line if first_line else 'Unknown'


def get_android_version(serial_num):
  cmd = adb_commands.cmd_get_android_version(serial_num)
  result = common.run_command(cmd)
  if result:
    data = str(result[0])
    if data.isnumeric():
      return int(data)
  return 0


def get_android_api_level(serial_num):
  cmd = adb_commands.cmd_get_android_api_level(serial_num)
  result = common.run_command(cmd)
  if result:
    data = str(result[0])
    if data.isnumeric():
      return int(data)
  return 0


def get_gms_version(serial_num):
  data = common.run_command(
      adb_commands.cmd_get_app_version(serial_num, gms_package_name)
  )
  version_list = [item.strip() for item in data]
  logger.info(version_list)
  result = 'None'
  if len(version_list) > 1:
    result = version_list[0].split('=')[1].split()[0]
  logger.info('Get gms app version is %s', result)
  return result


def get_build_fingerprint(serial_num):
  cmd = adb_commands.cmd_get_android_build_fingerprint(serial_num)
  result = common.run_command(cmd)
  if result:
    data = str(result[0])
    return data
  return 'None'


@adb_device_operation(default_return={})
def get_device_properties(serial_num: str) -> dict[str, str]:
  """Retrieve device properties via `adb shell getprop`.

  Args:
    serial_num: Device serial number.

  Returns:
    Dictionary mapping property keys to values.
  """
  cmd = adb_commands.cmd_adb_shell(serial_num, 'getprop')
  lines = common.run_command(cmd)
  if not lines:
    return {}

  properties: dict[str, str] = {}
  pattern = re.compile(r'^\[(?P<key>[^\]]+)\]\s*:\s*\[(?P<value>[^\]]*)\]')
  for line in lines:
    if not line:
      continue
    match = pattern.match(str(line).strip())
    if not match:
      continue
    key = match.group('key').strip()
    value = match.group('value').strip()
    properties[key] = value

  return properties


def run_as_root(serial_nums: list[str]):
  """Run as root.

  Args:
    serial_nums: Device serial numbers
  """
  commands: list[str] = []
  for s in serial_nums:
    cmd = adb_commands.cmd_adb_root(s)
    commands.append(cmd)

  results = _execute_commands_parallel(commands, 'root_android_devices')
  logger.info('Run root results: %s', results)


def start_reboot(serial_nums: list[str]):
  commands = []
  for s in serial_nums:
    cmd = adb_commands.cmd_adb_reboot(s)
    commands.append(cmd)

  results = _execute_commands_parallel(commands, 'start_reboot')
  logger.info('Start reboot results: %s', results)


def kill_adb_server():
  result = common.run_command(adb_commands.cmd_kill_adb_server())
  logger.info('Kill adb service result: %s', result)


def start_adb_server():
  result = common.run_command(adb_commands.cmd_start_adb_server())
  logger.info('Start adb service result: %s', result)


def install_the_apk(serial_nums: list[str], apk_path: str) -> list[str]:
  """Install the apk.

  Args:
    serial_nums: phone serial numbers
    apk_path: apk file path in device.

  Returns:
    Return the results.
  """
  commands: list[str] = []

  if not apk_path:
    logger.warning('Apk file path is empty')
    return ['Apk file path is empty']

  apk_path = common.get_full_path(apk_path)

  if not pathlib.Path(apk_path).exists():
    logger.warning('Apk file %s is not exists', apk_path)
    return ['Apk file %s is not exists' % apk_path]

  # check the apk is exists
  if not pathlib.Path(apk_path).is_file():
    logger.warning('Apk file %s is not exists', apk_path)
    return ['Apk file %s is not exists' % apk_path]

  logger.info('Install the apk %s', apk_path)
  for s in serial_nums:
    cmd = adb_commands.cmd_adb_install(s, apk_path)
    commands.append(cmd)

  results = _execute_commands_parallel(commands, 'install_to_android_device')
  logger.info('Install the apk results: %s', results)
  return results


def copy_file(source: str, destination: str):
  # copy file to destination
  logger.info('Start to copy file')
  common.run_command(adb_commands.cmd_cp_file(source, destination))
  logger.info('Copy file finished')


def switch_bluetooth_enable(serial_nums: list[str], enable: bool) -> list[str]:
  """Switch bluetooth enable.

  Args:
    serial_nums: Phones serial numbers.
    enable: Enable the bluetooth.

  Returns:
    result the results.
  """

  commands = []
  for s in serial_nums:
    cmd = adb_commands.cmd_switch_enable_bluetooth(s, enable)
    commands.append(cmd)

  results = _execute_commands_parallel(commands, 'switch_bluetooth_enable')
  logger.info('Switch bluetooth enable results: %s', results)
  return results

def pull_device_dcim(serial_nums: list[str], output_path: str) -> list[str]:
  """Pull device dcim folder.

  Args:
    serial_nums: Phones serial number.
    output_path: The output path.

  Returns:
  Result list string.
  """

  commands = []

  for s in serial_nums:
    output_path_combined = common.make_full_path(output_path, f'dcims_{s}')
    new_output_path = common.make_gen_dir_path(output_path_combined)
    cmd = adb_commands.cmd_pull_device_dcim(s, new_output_path)
    commands.append(cmd)

  results = _execute_commands_parallel(commands, 'pull_device_dcim')
  logger.info('Pull device dcim folder results: %s', results)
  return results


def _normalize_remote_path(path: str) -> str:
  normalized = (path or '/').strip()
  if not normalized:
    return '/'
  if not normalized.startswith('/'):
    normalized = f'/{normalized}'
  if normalized != '/' and normalized.endswith('/'):
    normalized = normalized.rstrip('/')
  return normalized or '/'


def list_device_directory(serial_num: str, remote_path: str) -> adb_models.DeviceDirectoryListing:
  """List contents of a directory on the device.

  Args:
    serial_num: Device serial.
    remote_path: Path on the device to inspect.

  Returns:
    DeviceDirectoryListing with parsed entries.
  """

  normalized_path = _normalize_remote_path(remote_path)
  command = adb_commands.cmd_list_device_directory(serial_num, normalized_path)
  raw_entries = common.run_command(command)

  entries: list[adb_models.DeviceFileEntry] = []
  for raw_entry in raw_entries:
    if not raw_entry:
      continue

    is_dir = raw_entry.endswith('/')
    name = raw_entry[:-1] if is_dir else raw_entry
    if not name:
      continue

    full_path = posixpath.normpath(posixpath.join(normalized_path, name))
    entries.append(adb_models.DeviceFileEntry(name=name, path=full_path, is_dir=is_dir))

  entries.sort(key=lambda entry: (not entry.is_dir, entry.name.lower()))
  listing = adb_models.DeviceDirectoryListing(serial=serial_num, path=normalized_path, entries=entries)
  logger.info('Listed %d entries for %s:%s', len(entries), serial_num, normalized_path)
  return listing


def pull_device_paths(serial_num: str, remote_paths: list[str], output_path: str) -> list[str]:
  """Pull multiple remote paths from a device into a local output directory."""

  if not remote_paths:
    logger.info('No remote paths supplied for pull_device_paths')
    return []

  base_output = common.make_full_path(output_path, f'device_{serial_num}')
  final_output = common.make_gen_dir_path(base_output)

  commands: list[str] = []
  for remote_path in remote_paths:
    normalized_remote = _normalize_remote_path(remote_path)
    commands.append(
        adb_commands.cmd_pull_device_file(serial_num, normalized_remote, final_output)
    )

  logger.info('Pulling %d paths for device %s into %s', len(commands), serial_num, final_output)
  native_results = _execute_commands_parallel_native(commands, 'pull_device_paths')
  return ['\n'.join(result) if result else '' for result in native_results]


def pull_device_file_preview(serial_num: str, remote_path: str) -> str:
  """Pull a single remote file into a temporary directory for previewing.

  Args:
    serial_num: Device serial number.
    remote_path: Remote file path to preview.

  Returns:
    Local path to the preview file.

  Raises:
    ValueError: If the remote path is invalid or points to a directory.
  """

  stripped_input = (remote_path or '').strip()
  if stripped_input.endswith('/') and stripped_input not in ('/', ''):
    raise ValueError(f'Remote path appears to be a directory: {stripped_input}')

  normalized_remote = _normalize_remote_path(remote_path)
  if normalized_remote in ('/', ''):
    raise ValueError('Remote path must reference a file, not the device root.')

  file_name = posixpath.basename(normalized_remote)
  if not file_name or file_name in ('.', '..'):
    raise ValueError(f'Unable to determine file name for {normalized_remote}')

  preview_dir = tempfile.mkdtemp(prefix=f'lazy_blacktea_preview_{serial_num}_')
  local_path = os.path.join(preview_dir, file_name)

  command = adb_commands.cmd_pull_device_file(serial_num, normalized_remote, local_path)
  logger.info('Pulling preview file %s:%s into %s', serial_num, normalized_remote, local_path)
  result = common.run_command(command)
  logger.debug('Preview pull result for %s:%s -> %s', serial_num, normalized_remote, result)
  return local_path


def pull_device_dcim_folders_with_device_folder(serial_nums: list[str], output_path: str) -> list[str]:
  """Backward-compatible wrapper for refactored DCIM pull workflow.

  The PyQt file operations manager expects a helper that keeps each device's
  assets within its own subdirectory. The legacy ``pull_device_dcim`` already
  applies that structure, so this wrapper simply delegates while providing a
  clear extension point for future enhancements.

  Args:
    serial_nums: Devices to pull DCIM contents from.
    output_path: Base directory for all exported media.

  Returns:
    Results from the underlying ``pull_device_dcim`` execution.
  """
  if not serial_nums:
    logger.info('No devices supplied for pull_device_dcim_folders_with_device_folder')
    return []

  return pull_device_dcim(serial_nums, output_path)


def pull_devices_hsv(serial_nums: list[str], output_path: str) -> list[str]:
  """Pull devices Hierarchy Snapshot Viewer.

  Args:
    serial_nums: Phones serial number.
    output_path: The output path.

  Returns:
    Result list string.
  """
  result = []
  with concurrent.futures.ThreadPoolExecutor(
      max_workers=len(serial_nums)
  ) as executor:
    futures = []
    for s in serial_nums:
      output_path_combined = common.make_full_path(output_path, f'hsv_{s}')
      new_output_path = common.make_gen_dir_path(output_path_combined)
      future = executor.submit(
          dump_device_ui.generate_process, s, new_output_path
      )
      futures.append(future)

    concurrent.futures.as_completed(futures)
    for f in futures:
      device_info = f.result()
      result.append(device_info)

    return result


def _capture_screenshot_for_device(serial: str, file_name: str, output_path: str) -> None:
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


def start_to_screen_shot(
    serial_nums: list[str], file_name: str, output_path: str
) -> None:
  """Capture screenshots for the provided devices."""

  if not serial_nums:
    logger.info('No devices supplied for start_to_screen_shot')
    return

  logger.info('Start to screen shot.')
  output_path = common.make_gen_dir_path(output_path)
  worker_count = _determine_worker_count(len(serial_nums))

  if worker_count <= 0:
    logger.info('No workers scheduled for screenshot capture (worker_count=%s)', worker_count)
    return

  futures: dict[concurrent.futures.Future, str] = {}
  with concurrent.futures.ThreadPoolExecutor(max_workers=worker_count) as executor:
    for serial in serial_nums:
      future = executor.submit(_capture_screenshot_for_device, serial, file_name, output_path)
      futures[future] = serial

    for future in concurrent.futures.as_completed(futures):
      serial = futures[future]
      try:
        future.result()
      except Exception as exc:
        logger.error('Error capturing screenshot for %s: %s', serial, exc)

  logger.info('Start to screen shot completed for %s device(s)', len(serial_nums))


def start_to_record_android_devices(
    serial_nums: list[str], file_name: str
) -> None:
  """Start to record android device.

  Args:
    serial_nums: Phones serial number.
    file_name: screen record file name.
  """
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
  """Stop the screen record process.

  Args:
   serial_nums: Phone serial numbers.
   file_name: Screen record file name.
   output_path: Screen record folder output path.
  """

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
  """Stop the screen record process."""

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

def _run_multiple_adb_commands(serial_nums: list[str], command_func) -> None:
  """Runs multiple ADB commands across multiple devices.

  Args:
    serial_nums: List of device serial numbers.
    command_func: A function from adb_commands.py that returns a list of
      commands for a single serial number.
  """
  if not serial_nums:
    logger.warning('No devices provided to run commands.')
    return

  all_commands = []
  for s in serial_nums:
    all_commands.extend(command_func(s))

  results = _execute_commands_parallel(all_commands, 'run_enlarge_log_buffer')
  logger.info('Command execution results: %s', results)




def run_enlarge_log_buffer(serial_nums: list[str], size: str = '16M') -> None:
  """Enlarges the log buffer on selected devices.

  Args:
    serial_nums: List of device serial numbers.
    size: The size of the log buffer (e.g., "1M", "16M").
  """
  run_as_root(serial_nums)
  _run_multiple_adb_commands(
      serial_nums, lambda s: adb_commands.cmd_enlarge_log_buffer(s, size)
  )
  logger.info(f'Enlarged log buffer to {size}.')


def _get_device_property(serial_num: str, shell_command: str, default_value: str = 'Unknown') -> str:
  """Get a single device property via ADB shell command.

  Args:
    serial_num: Device serial number
    shell_command: Shell command to execute
    default_value: Value to return on error

  Returns:
    Property value or default_value on error
  """
  try:
    cmd = adb_commands.cmd_adb_shell(serial_num, shell_command)
    result = common.run_command(cmd)
    if result and result[0]:
      return result[0].strip()
  except Exception:
    pass
  return default_value


@adb_device_operation(default_return={})
def get_additional_device_info(serial_num: str) -> dict:
  """Get additional device information for enhanced display.

  Args:
    serial_num: Device serial number.

  Returns:
    Dictionary containing additional device information.
  """
  additional_info = {}

  # Screen density and size using unified property getter
  additional_info['screen_density'] = _get_device_property(serial_num, 'wm density')
  additional_info['screen_size'] = _get_device_property(serial_num, 'wm size')

  # Battery information - comprehensive battery data
  try:
    # Get full battery information
    cmd = adb_commands.cmd_adb_shell(serial_num, 'dumpsys battery')
    result = common.run_command(cmd)
    if result:
      # result is a list of lines, not a single string
      # Parse battery level (specifically look for "level:" but not "Capacity level:")
      for line in result:
        line = line.strip()
        if line.startswith('level:') and 'Capacity level' not in line:
          battery_level = line.split(':')[-1].strip()
          if battery_level.isdigit():
            additional_info['battery_level'] = f'{battery_level}%'
            break  # Stop after finding the first (correct) battery level
        elif 'scale:' in line and 'level:' not in line:
          # Battery capacity in mAh (sometimes available in scale)
          scale_value = line.split(':')[-1].strip()
          if scale_value.isdigit() and int(scale_value) > 100:
            additional_info['battery_capacity_mah'] = f'{scale_value} mAh'

      # Try to get battery capacity from other sources
      if 'battery_capacity_mah' not in additional_info:
        try:
          capacity_cmd = adb_commands.cmd_adb_shell(serial_num, 'cat /sys/class/power_supply/battery/capacity')
          capacity_result = common.run_command(capacity_cmd)
          if capacity_result and capacity_result[0]:
            # Try to get actual mAh capacity
            mah_cmd = adb_commands.cmd_adb_shell(serial_num, 'cat /sys/class/power_supply/battery/charge_full_design')
            mah_result = common.run_command(mah_cmd)
            if mah_result and mah_result[0]:
              mah_value = int(mah_result[0].strip()) // 1000  # Convert from μAh to mAh
              additional_info['battery_capacity_mah'] = f'{mah_value} mAh'
        except (ValueError, IndexError, subprocess.SubprocessError) as e:
          logger.debug(f'Failed to get battery capacity: {e}')

      # Calculate Battery mAs (milliamp seconds) - theoretical
      try:
        if 'battery_capacity_mah' in additional_info:
          mah_str = additional_info['battery_capacity_mah'].replace(' mAh', '')
          if mah_str.isdigit():
            mah = int(mah_str)
            mas = mah * 3600  # Convert mAh to mAs (1 hour = 3600 seconds)
            additional_info['battery_mas'] = f'{mas:,} mAs'
      except (ValueError, KeyError) as e:
        logger.debug(f'Failed to calculate battery mAs: {e}')

      # Calculate DOU (Days Of Use) hours - estimated based on typical usage
      try:
        if 'battery_capacity_mah' in additional_info and additional_info['battery_level'] != 'Unknown':
          mah_str = additional_info['battery_capacity_mah'].replace(' mAh', '')
          level_str = additional_info['battery_level'].replace('%', '')
          if mah_str.isdigit() and level_str.isdigit():
            mah = int(mah_str)
            level = int(level_str)
            current_charge = (mah * level) / 100
            # Estimate usage time based on average 200mA consumption (typical smartphone usage)
            estimated_hours = current_charge / 200
            additional_info['battery_dou_hours'] = f'{estimated_hours:.1f} hours'
      except (ValueError, KeyError, ZeroDivisionError) as e:
        logger.debug(f'Failed to calculate battery DOU hours: {e}')

  except Exception:
    additional_info['battery_level'] = 'Unknown'

  # Set defaults for missing battery info
  if 'battery_level' not in additional_info:
    additional_info['battery_level'] = 'Unknown'
  if 'battery_capacity_mah' not in additional_info:
    additional_info['battery_capacity_mah'] = 'Unknown'
  if 'battery_mas' not in additional_info:
    additional_info['battery_mas'] = 'Unknown'
  if 'battery_dou_hours' not in additional_info:
    additional_info['battery_dou_hours'] = 'Unknown'

  # CPU architecture using unified property getter
  additional_info['cpu_arch'] = _get_device_property(serial_num, 'getprop ro.product.cpu.abi')

  return additional_info


def check_tool_availability(tool_name: str) -> tuple[bool, str]:
  """Check if a tool is available in the system with smart path detection.

  Args:
    tool_name: Name of the tool to check.

  Returns:
    Tuple of (is_available, version_info)
  """
  global _scrcpy_command_path
  import platform
  import shutil

  # First try to find tool in PATH
  if shutil.which(tool_name):
    try:
      result = subprocess.run([tool_name, '--version'],
                            capture_output=True, text=True, timeout=5)
      if result.returncode == 0:
        return True, result.stdout.strip()
    except (FileNotFoundError, subprocess.TimeoutExpired, Exception):
      pass

  # If not in PATH, try common locations based on platform
  system = platform.system().lower()
  common_paths = []

  if tool_name == 'scrcpy':
    if system == 'darwin':  # macOS
      common_paths = [
        '/opt/homebrew/bin/scrcpy',
        '/usr/local/bin/scrcpy',
        '/opt/homebrew/Caskroom/scrcpy/*/scrcpy',
        os.path.expanduser('~/Applications/scrcpy.app/Contents/MacOS/scrcpy')
      ]
    elif system == 'linux':  # Linux
      common_paths = [
        '/usr/bin/scrcpy',
        '/usr/local/bin/scrcpy',
        '/snap/bin/scrcpy',
        '/flatpak/exports/bin/scrcpy',
        os.path.expanduser('~/snap/scrcpy/current/bin/scrcpy'),
        os.path.expanduser('~/.local/bin/scrcpy'),
        '/opt/scrcpy/scrcpy'
      ]

    for scrcpy_path in common_paths:
      # Handle wildcard paths
      if '*' in scrcpy_path:
        matches = glob.glob(scrcpy_path)
        for match in matches:
          if os.path.isfile(match) and os.access(match, os.X_OK):
            try:
              result = subprocess.run([match, '--version'],
                                    capture_output=True, text=True, timeout=5)
              if result.returncode == 0:
                # Update global scrcpy path for future use
                _scrcpy_command_path = match
                return True, result.stdout.strip()
            except (subprocess.SubprocessError, subprocess.TimeoutExpired, OSError) as e:
              logger.debug(f'Failed to check scrcpy version at {match}: {e}')
              continue
      else:
        if os.path.isfile(scrcpy_path) and os.access(scrcpy_path, os.X_OK):
          try:
            result = subprocess.run([scrcpy_path, '--version'],
                                  capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
              # Update global scrcpy path for future use
              _scrcpy_command_path = scrcpy_path
              return True, result.stdout.strip()
          except (subprocess.SubprocessError, subprocess.TimeoutExpired, OSError) as e:
            logger.debug(f'Failed to check scrcpy version at {scrcpy_path}: {e}')
            continue

  return False, ""


def get_scrcpy_command() -> str:
  """Get the appropriate scrcpy command path."""
  global _scrcpy_command_path
  return _scrcpy_command_path


# Global dict to track active recordings for wrapper functions
_active_recordings = {}

# Wrapper functions for compatibility with recording_utils.py
def start_screen_record_device(serial: str, output_path: str, filename: str) -> None:
  """Start screen recording for a single device (wrapper function).

  Args:
    serial: Device serial number
    output_path: Output directory path
    filename: Recording filename
  """
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
  """Stop screen recording for a single device (wrapper function).

  Args:
    serial: Device serial number
  """
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


def take_screenshot_single_device(serial: str, output_path: str, filename: str) -> bool:
  """Take screenshot for a single device (wrapper function).

  Args:
    serial: Device serial number
    output_path: Output directory path
    filename: Screenshot filename

  Returns:
    True if screenshot was taken successfully
  """
  try:
    logger.info(f'Taking screenshot for device {serial}, file: {filename}')
    start_to_screen_shot([serial], filename, output_path)
    return True
  except Exception as e:
    logger.error(f'Error taking screenshot for {serial}: {e}')
    return False


def _verify_recording_started(serial_nums: List[str]) -> bool:
  """Verify that screen recording has started on devices.

  Args:
    serial_nums: List of device serial numbers

  Returns:
    bool: True if recording verified on all devices
  """
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
    result = common.run_command(cmd, 3)
    if result and any(str(line).strip() for line in result):
      return True

  # Fallback to ps listing
  cmd = adb_commands._build_adb_shell_command(serial, 'ps -A')
  result = common.run_command(cmd, 3)
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
  """Verify that screen recording file was pulled successfully.

  Args:
    output_path: Output directory path
    serial_num: Device serial number
    name: Recording name

  Returns:
    bool: True if file exists locally
  """
  import os
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
    time.sleep(0.01)  # Reduced from 0.1s to 0.01s

  logger.warning(f'Could not verify file was pulled: {local_file_path}')
  return False
def parse_bugreportz_line(line: str) -> dict:
  """Parse a single bugreportz output line into a structured payload.

  Supports common OEM variations:
    - "PROGRESS: N/M"
    - "PROGRESS: N%" or "PROGRESS: N"
    - optional spaces around colon and slashes
    - "OK: <path>" or "OK:filename=<path>"
    - "FAIL: <reason>"
  """
  try:
    raw = (line or '').strip()
    if not raw:
      return {'type': 'unknown', 'raw': line}

    upper = raw.upper()
    if upper.startswith('PROGRESS'):
      # Normalize separators
      try:
        payload = raw.split(':', 1)[1].strip()
      except Exception:
        payload = ''
      # Try fraction form
      m = re.match(r"^(\d+)\s*/\s*(\d+)$", payload)
      if m:
        num = int(m.group(1))
        den = max(1, int(m.group(2)))
        pct = int(min(100, max(0, round(100 * num / den))))
        return {'type': 'progress', 'percent': pct, 'raw': line}
      # Try percentage or integer
      m = re.match(r"^(\d+)\s*%?$", payload)
      if m:
        pct = int(m.group(1))
        pct = int(min(100, max(0, pct)))
        return {'type': 'progress', 'percent': pct, 'raw': line}
      return {'type': 'unknown', 'raw': line}

    if upper.startswith('OK'):
      try:
        payload = raw.split(':', 1)[1].strip()
      except Exception:
        payload = ''
      # Handle optional key=value
      if '=' in payload:
        _, val = payload.split('=', 1)
        path_val = val.strip()
      else:
        path_val = payload
      return {'type': 'ok', 'path': path_val, 'raw': line}

    if upper.startswith('FAIL'):
      try:
        payload = raw.split(':', 1)[1].strip()
      except Exception:
        payload = raw
      return {'type': 'fail', 'reason': payload, 'raw': line}

    return {'type': 'unknown', 'raw': line}
  except Exception:
    return {'type': 'unknown', 'raw': line}
