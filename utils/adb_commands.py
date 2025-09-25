"""Utility with commands functions for adb."""

## Scratch or grep the 'Test summary saved in ' with log

test_summary_grep_word = 'Test summary saved in '


def get_adb_command() -> str:
  """Get the appropriate ADB command path."""
  try:
    # Import here to avoid circular imports
    from utils import adb_tools
    return getattr(adb_tools, '_adb_command_prefix', 'adb')
  except:
    return 'adb'


def _build_adb_command(serial_num: str = None, *command_parts) -> str:
  """Build ADB command with proper prefix and device selection.

  Args:
    serial_num: Device serial number (optional)
    *command_parts: Command parts to join

  Returns:
    Complete ADB command string
  """
  adb_cmd = get_adb_command()
  parts = [adb_cmd]

  if serial_num:
    parts.extend(['-s', serial_num])

  parts.extend(command_parts)
  return ' '.join(parts)


def _build_adb_shell_command(serial_num: str, shell_command: str) -> str:
  """Build ADB shell command.

  Args:
    serial_num: Device serial number
    shell_command: Shell command to execute

  Returns:
    Complete ADB shell command string
  """
  return _build_adb_command(serial_num, 'shell', shell_command)


def _build_setting_getter_command(serial_num: str, setting_key: str) -> str:
  """Build command to get device setting.

  Args:
    serial_num: Device serial number
    setting_key: Setting key to retrieve

  Returns:
    Complete ADB command to get setting
  """
  return _build_adb_shell_command(serial_num, f'settings get global {setting_key}')


def _build_getprop_command(serial_num: str, property_key: str) -> str:
  """Build command to get device property.

  Args:
    serial_num: Device serial number
    property_key: Property key to retrieve

  Returns:
    Complete ADB command to get property
  """
  return _build_adb_shell_command(serial_num, f'getprop {property_key}')


def cmd_adb_shell(serial_num: str, command: str) -> str:
  return _build_adb_shell_command(serial_num, command)


def cmd_get_adb_devices() -> str:
  # adb devices -l
  # ['adb', 'devices', '-l']
  return _build_adb_command(None, 'devices', '-l')


def cmd_get_android_build_fingerprint(serial_num: str) -> str:
  return _build_getprop_command(serial_num, 'ro.build.fingerprint')


def cmd_kill_adb_server():
  return _build_adb_command(None, 'kill-server')


def cmd_start_adb_server():
  return _build_adb_command(None, 'start-server')


def cmd_get_dump_device_ui_detail(serial_num):
  # start to dump ui detail
  return f'adb -s {serial_num} shell uiautomator dump'


def cmd_pull_the_dump_device_ui_detail(serial_num, output_path):
  return f'adb -s {serial_num} pull /sdcard/window_dump.xml {output_path}'


def cmd_adb_root(serial_num):
  return _build_adb_command(serial_num, 'root')


def cmd_adb_reboot(serial_num: str):
  return _build_adb_command(serial_num, 'reboot')


def cmd_adb_install(serial_num: str, apk_path: str):
  return _build_adb_command(serial_num, 'install', '-d', '-r', '-g', f'"{apk_path}"')

def cmd_extact_discovery_service_info(serial_num, root_folder):
  return (
      f'adb -s {serial_num} shell dumpsys activity service DiscoveryService >'
      f' {root_folder}/{serial_num}_discovery_service_file.txt'
  )

def cmd_get_android_api_level(serial_num: str) -> str:
  """Gets android API level.

  Args:
    serial_num: Phone serial number.

  Returns:
  Command string.
  """
  return _build_getprop_command(serial_num, 'ro.build.version.sdk')


def cmd_get_android_version(serial_num):
  return _build_getprop_command(serial_num, 'ro.build.version.release')


def cmd_get_device_bluetooth(serial_num):
  # check the bluetooth is on/off
  return _build_setting_getter_command(serial_num, 'bluetooth_on')


def cmd_get_device_wifi(serial_num):
  # check the wifi is on/off
  return _build_setting_getter_command(serial_num, 'wifi_on')

def cmd_clear_device_logcat(serial_num) -> str:
  """Clears device logcat."""
  # adb -s $serial logcat -c
  # ['adb', '-s', serialNum, 'logcat', '-b', 'all', '-c']
  return _build_adb_command(serial_num, 'logcat', '-b', 'all', '-c')

def cmd_get_device_logcat(serial_num, output_path) -> str:
  """Gets device logcat.

  Args:
    serial_num:
    output_path:

  Returns:
    string

  ['adb', '-s', serialNum, 'logcat', '|', 'grep', '--line-buffered',
  serialNum, outputPath]
  """
  return (
      f'adb -s {serial_num} logcat | grep --line-buffered {serial_num} >'
      f' {output_path}'
  )

def cmd_output_device_bug_report(serial_num, output_path) -> str:
  """Gets device bug report using modern format.

  Args:
    serial_num: Device serial number
    output_path: Full path for the output zip file

  Returns:
    ADB command string for generating bug report
  """
  # Modern format: adb -s $serial bugreport $outputPath.zip
  # This creates a compressed zip file with complete bug report
  if not output_path.endswith('.zip'):
    output_path += '.zip'
  return f'adb -s {serial_num} bugreport "{output_path}"'

def cmd_get_app_version(serial_num, package_name) -> str:
  """Gets app version.

  ['adb', '-s', serialNum, 'shell', 'dumpsys', 'package', packageName, '|',
  'grep', 'versionName']

  Args:
    serial_num:
    package_name:

  Returns:
    string
  """
  # adb -s %serialNum shell dumpsys package $p | grep versionName
  adb_cmd = get_adb_command()
  return (
      f'{adb_cmd} -s {serial_num} shell dumpsys package {package_name} | grep'
      ' versionName'
  )

def cmd_get_apps_in_device(serial_num) -> str:
  """Gets apps in device.

  Args:
    serial_num:

  Returns:
    string
  """
  # adb -s $serialNum shell dumpsys package packages
  # ['adb', '-s', serialNum, 'shell', 'dumpsys', 'package', 'packages']
  return f'adb -s {serial_num} shell dumpsys package packages '


def cmd_cp_file(source, destination):
  return f'cp {source} {destination}'


def cmd_switch_enable_bluetooth(serial_num: str, enable: bool) -> str:
  if enable:
    result = 'enable'
  else:
    result = 'disable'
  return f'adb -s {serial_num} shell svc bluetooth {result}'

def cmd_pull_device_dcim(serial_num: str, output_path: str) -> str:
  return f'adb -s {serial_num} pull /sdcard/ dcims {output_path}'

def cmd_adb_screen_shot(
    serial_num: str, file_name: str, output_folder_path: str
) -> str:
  screen_shot_phone_path = f'/sdcard/{serial_num}_screenshot_{file_name}.png'
  return (
      f'adb -s {serial_num} shell screencap -p'
      f' {screen_shot_phone_path} && adb -s {serial_num} pull'
      f' {screen_shot_phone_path} {output_folder_path}'
  )


def cmd_android_screen_record(serial_num, name) -> str:
  return (
      f'adb -s {serial_num} shell screenrecord'
      f' /sdcard/screenrecord_{serial_num}_{name}.mp4'
  )

def cmd_android_screen_record_stop(serial_num) -> str:
  # -lINT
  # -SIGINT
  return f'adb -s {serial_num} shell pkill -SIGINT screenrecord'


def cmd_pull_android_screen_record(
    serial_num: str, name: str, output_folder_path: str
) -> str:
  return (
      f'adb -s {serial_num} pull /sdcard/screenrecord_{serial_num}_{name}.mp4'
      f' {output_folder_path}'
  )

def cmd_rm_android_screen_record(serial_num, name) -> str:
  return (
      f'adb -s {serial_num} shell rm'
      f' /sdcard/screenrecord_{serial_num}_{name}.mp4'
  )

def cmd_enlarge_log_buffer(serial_num: str, size: str) -> list[str]:
  """Adb command to enlarge the log buffer.

  Args:
    serial_num: Device serial number.
    size: The size of the log buffer (e.g., "1M", "16M").

  Returns:
    A list of command strings.
  """
  return [cmd_adb_shell(serial_num, f'logcat -b main -G {size}')]


