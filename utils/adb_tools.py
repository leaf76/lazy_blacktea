"""Get devices list and use the device info to set object."""

import concurrent.futures
import os
import pathlib
import platform
import subprocess
import time

from utils import adb_commands
from utils import adb_models
from utils import common
from utils import dump_device_ui


## GMS app package name
gms_package_name = 'com.google.android.gms'

logger = common.get_logger('adb_tools')


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
    except:
      pass

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
      import glob
      matches = glob.glob(adb_path)
      for match in matches:
        if os.path.isfile(match) and os.access(match, os.X_OK):
          try:
            result = common.run_command(f'"{match}" version')
            if result:
              # Update the global PATH or set a global ADB path
              _set_adb_path(match)
              return True
          except:
            continue
    else:
      if os.path.isfile(adb_path) and os.access(adb_path, os.X_OK):
        try:
          result = common.run_command(f'"{adb_path}" version')
          if result:
            # Update the global PATH or set a global ADB path
            _set_adb_path(adb_path)
            return True
        except:
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
  all_devices_info = [item for item in init_devices if item]
  logger.info(all_devices_info)
  if not any(all_devices_info):
    logger.warning('Not found device')
    return result

  with concurrent.futures.ThreadPoolExecutor(
      max_workers=len(all_devices_info)
  ) as executor:
    futures = []
    for i in all_devices_info:
      info = [x for x in i.split() if x]
      furture = executor.submit(device_info_entry, info)
      futures.append(furture)

    concurrent.futures.as_completed(futures)
    for f in futures:
      device_info = f.result()
      result.append(device_info)

    return result


def device_info_entry(info: adb_models.DeviceInfo) -> adb_models.DeviceInfo:
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
  gms_verison_str = get_gms_version(serial_num)
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
      gms_verison_str,
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
  with concurrent.futures.ThreadPoolExecutor(
      max_workers=len(command_list)
  ) as executor:
    results = executor.map(common.run_command, command_list)
    for r in results:
      logger.info('Get generate result %s', r)
    callback(results)

  logger.info('----------End generate bug report finished.----------')


def generate_bug_report_device(serial_num: str, output_path: str) -> None:
  """Generate bug report for a single device.

  Args:
    serial_num: Device serial number.
    output_path: Full path where to save the bug report.
  """
  try:
    cmd = adb_commands.cmd_output_device_bug_report(serial_num, output_path)
    result = common.run_command(cmd)
    logger.info(f'Bug report generated for {serial_num}: {output_path}')
    return result
  except Exception as e:
    logger.error(f'Failed to generate bug report for {serial_num}: {e}')
    raise


def clear_device_logcat(serial_num) -> bool:
  logger.info('Start to clear logcat')
  if not serial_num:
    logger.warning('Serial number cannot be empty')
    return False
  common.run_command(adb_commands.cmd_clear_device_logcat(serial_num))
  logger.info('Clear logcat Ok.')
  return True


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

  with concurrent.futures.ThreadPoolExecutor(
      max_workers=len(commands)
  ) as executor:
    results = list(executor.map(common.run_command, commands))

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
    cmd = adb_commands.cmd_extact_discovery_service_info(s, root_folder)
    commands.append(cmd)

  with concurrent.futures.ThreadPoolExecutor(
      max_workers=len(serial_nums)
  ) as executor:
    results = executor.map(common.run_command, commands)
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
  cmd = adb_commands.cmd_extact_discovery_service_info(serial_num, root_folder)
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


def run_as_root(serial_nums: list[str]):
  """Run as root.

  Args:
    serial_nums: Device serial numbers
  """
  commands: list[str] = []
  for s in serial_nums:
    cmd = adb_commands.cmd_adb_root(s)
    commands.append(cmd)

  with concurrent.futures.ThreadPoolExecutor(
      max_workers=len(serial_nums)
  ) as executor:
    results = executor.map(common.run_command, commands)
    logger.info('Run root results: %s', results)


def start_reboot(serial_nums: list[str]):
  commands = []
  for s in serial_nums:
    cmd = adb_commands.cmd_adb_reboot(s)
    commands.append(cmd)

  with concurrent.futures.ThreadPoolExecutor(
      max_workers=len(serial_nums)
  ) as executor:
    results = executor.map(common.run_command, commands)
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

  with concurrent.futures.ThreadPoolExecutor(
      max_workers=len(serial_nums)
  ) as executor:
    results = executor.map(common.run_command, commands)
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

  with concurrent.futures.ThreadPoolExecutor(
      max_workers=len(commands)
  ) as executor:
    results = executor.map(common.run_command, commands)
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

  with concurrent.futures.ThreadPoolExecutor(
      max_workers=len(serial_nums)
  ) as executor:
    results = executor.map(common.run_command, commands)
    logger.info('Pull device dcim folder results: %s', results)
    return results


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


def start_to_screen_shot(
    serial_nums: list[str], file_name: str, output_path: str
) -> None:
  """Start to screen shot.

  Args:
    serial_nums: Phones serial number.
    file_name: Photo file name
    output_path: The output folder path.
  """
  logger.info('Start to screen shot.')

  output_path = common.make_gen_dir_path(output_path)
  commands = []
  for s in serial_nums:
    cmd = adb_commands.cmd_adb_screen_shot(s, file_name, output_path)
    commands.append(cmd)

  with concurrent.futures.ThreadPoolExecutor(
      max_workers=len(serial_nums)
  ) as executor:
    results = executor.map(common.run_command, commands)
    # Consume the generator to actually execute the commands
    result_list = list(results)
    logger.info('Start to screen shot results: %s', result_list)


def start_to_record_android_devices(
    serial_nums: list[str], file_name: str
) -> None:
  """Start to record android device.

  Args:
    serial_nums: Phones serial number.
    file_name: screen record file name.
  """
  logger.info('🎬 [START DEBUG] Starting recording for devices')
  logger.info(f'🎬 [START DEBUG] Serial numbers: {serial_nums}')
  logger.info(f'🎬 [START DEBUG] File name: {file_name}')

  commands = []
  for s in serial_nums:
    cmd = adb_commands.cmd_android_screen_record(s, file_name)
    logger.info(f'🎬 [START DEBUG] Command for {s}: {cmd}')
    commands.append(cmd)

  logger.info(f'🎬 [START DEBUG] All commands: {commands}')

  try:
    with concurrent.futures.ThreadPoolExecutor(
        max_workers=len(serial_nums)
    ) as executor:
      logger.info(f'🎬 [START DEBUG] Created ThreadPoolExecutor with {len(serial_nums)} workers')
      results = executor.map(common.mp_run_command, commands)
      # Keep the video must be recorded and exists.
      result_list = list(results)  # Force consumption
      logger.info(f'🎬 [START DEBUG] Recording commands completed. Results: {result_list}')
      time.sleep(0.5)

  except Exception as e:
    logger.error(f'❌ [START DEBUG] Error starting recording: {e}')
    import traceback
    logger.error(f'❌ [START DEBUG] Traceback: {traceback.format_exc()}')
    raise e

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
    with concurrent.futures.ThreadPoolExecutor(
        max_workers=len(serial_nums)
    ) as executor:
      logger.info(f'🔴 [MULTI-STOP DEBUG] Created ThreadPoolExecutor with {len(serial_nums)} max workers')

      results = executor.map(
          lambda x: stop_to_screen_record_android_device(
              x, file_name, output_path
          ),
          serial_nums,
      )
      logger.info('🔴 [MULTI-STOP DEBUG] executor.map called, consuming results...')

      # Force consumption of the generator to ensure all tasks complete
      result_list = list(results)
      logger.info(f'🔴 [MULTI-STOP DEBUG] All stop tasks completed. Results: {result_list}')

  except Exception as e:
    logger.error(f'❌ [MULTI-STOP DEBUG] Error in ThreadPoolExecutor: {e}')
    import traceback
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
    time.sleep(1.0)  # Give more time for process to stop

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
    time.sleep(0.5)

    # Step 3: Remove the file from device
    logger.info(f'🔴 [SINGLE-STOP DEBUG] STEP 3: Removing screen record file from device {serial_num}')
    rm_cmd = adb_commands.cmd_rm_android_screen_record(serial_num, name)
    logger.info(f'🔴 [SINGLE-STOP DEBUG] Remove command: {rm_cmd}')
    rm_result = common.run_command(rm_cmd)
    logger.info(f'🔴 [SINGLE-STOP DEBUG] Remove command result: {rm_result}')

    logger.info(f'✅ [SINGLE-STOP DEBUG] === Stop completed successfully for device {serial_num} ===')

  except Exception as e:
    logger.error(f'❌ [SINGLE-STOP DEBUG] Error stopping device {serial_num}: {e}')
    import traceback
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

  with concurrent.futures.ThreadPoolExecutor(
      max_workers=len(serial_nums)
  ) as executor:
    results = executor.map(common.run_command, all_commands)
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


def get_additional_device_info(serial_num: str) -> dict:
  """Get additional device information for enhanced display.

  Args:
    serial_num: Device serial number.

  Returns:
    Dictionary containing additional device information.
  """
  additional_info = {}

  # Screen density
  try:
    cmd = adb_commands.cmd_adb_shell(serial_num, 'wm density')
    result = common.run_command(cmd)
    if result and result[0]:
      density = result[0].strip()
      additional_info['screen_density'] = density
  except Exception:
    additional_info['screen_density'] = 'Unknown'

  # Screen size
  try:
    cmd = adb_commands.cmd_adb_shell(serial_num, 'wm size')
    result = common.run_command(cmd)
    if result and result[0]:
      size = result[0].strip()
      additional_info['screen_size'] = size
  except Exception:
    additional_info['screen_size'] = 'Unknown'

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
        except:
          pass

      # Calculate Battery mAs (milliamp seconds) - theoretical
      try:
        if 'battery_capacity_mah' in additional_info:
          mah_str = additional_info['battery_capacity_mah'].replace(' mAh', '')
          if mah_str.isdigit():
            mah = int(mah_str)
            mas = mah * 3600  # Convert mAh to mAs (1 hour = 3600 seconds)
            additional_info['battery_mas'] = f'{mas:,} mAs'
      except:
        pass

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
      except:
        pass

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

  # CPU architecture
  try:
    cmd = adb_commands.cmd_adb_shell(serial_num, 'getprop ro.product.cpu.abi')
    result = common.run_command(cmd)
    if result and result[0]:
      cpu = result[0].strip()
      additional_info['cpu_arch'] = cpu
  except Exception:
    additional_info['cpu_arch'] = 'Unknown'

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
      import subprocess
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
        import glob
        matches = glob.glob(scrcpy_path)
        for match in matches:
          if os.path.isfile(match) and os.access(match, os.X_OK):
            try:
              import subprocess
              result = subprocess.run([match, '--version'],
                                    capture_output=True, text=True, timeout=5)
              if result.returncode == 0:
                # Update global scrcpy path for future use
                _scrcpy_command_path = match
                return True, result.stdout.strip()
            except:
              continue
      else:
        if os.path.isfile(scrcpy_path) and os.access(scrcpy_path, os.X_OK):
          try:
            import subprocess
            result = subprocess.run([scrcpy_path, '--version'],
                                  capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
              # Update global scrcpy path for future use
              _scrcpy_command_path = scrcpy_path
              return True, result.stdout.strip()
          except:
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

  # Store the recording info for later use in stop function
  _active_recordings[serial] = {
    'filename': filename,
    'output_path': output_path
  }

  # Extract just the base name without extension for the start function
  # The start function expects just the base name, not the full filename
  base_name = filename.replace('.mp4', '') if filename.endswith('.mp4') else filename
  start_to_record_android_devices([serial], base_name)


def stop_screen_record_device(serial: str) -> None:
  """Stop screen recording for a single device (wrapper function).

  Args:
    serial: Device serial number
  """
  logger.info(f'🔴 [WRAPPER] Stopping screen recording for device {serial}')

  if serial in _active_recordings:
    recording_info = _active_recordings[serial]
    filename = recording_info['filename']
    output_path = recording_info['output_path']

    # Extract base name for the stop function
    base_name = filename.replace('.mp4', '') if filename.endswith('.mp4') else filename

    logger.info(f'🔴 [WRAPPER] Using stored info - filename: {filename}, base_name: {base_name}, output_path: {output_path}')

    try:
      # Use the existing stop function which handles the complete workflow
      stop_to_screen_record_android_device(serial, base_name, output_path)

      # Clean up the tracking info
      del _active_recordings[serial]
      logger.info(f'✅ [WRAPPER] Screen recording stopped successfully for device {serial}')

    except Exception as e:
      logger.error(f'❌ [WRAPPER] Error stopping screen recording for {serial}: {e}')
      # Clean up even on error
      if serial in _active_recordings:
        del _active_recordings[serial]
      raise
  else:
    logger.warning(f'⚠️ [WRAPPER] No active recording found for device {serial}, attempting simple stop')
    try:
      # Fallback to simple stop command
      stop_cmd = f'adb -s {serial} shell pkill -f screenrecord'
      common.run_command(stop_cmd)
      logger.info(f'📱 [WRAPPER] Simple stop command executed for device {serial}')
    except Exception as e:
      logger.error(f'❌ [WRAPPER] Error with simple stop for {serial}: {e}')
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
