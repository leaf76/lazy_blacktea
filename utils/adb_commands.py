"""Utility with commands functions for adb."""

import shlex

## Scratch or grep the 'Test summary saved in ' with log

test_summary_grep_word = 'Test summary saved in '


def get_adb_command() -> str:
  """Get the appropriate ADB command path."""
  try:
    # Import here to avoid circular imports
    from utils import adb_tools
    return getattr(adb_tools, '_adb_command_prefix', 'adb')
  except (ImportError, AttributeError):
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


def cmd_screencap_capture(serial_num: str, remote_path: str) -> str:
  """Build screencap capture command, honoring screenshot settings."""
  extra_tokens: list[str] = []
  try:
    from config.config_manager import ConfigManager
    ss = ConfigManager().get_screenshot_settings()
    extra = getattr(ss, 'extra_args', '') or ''
    if extra.strip():
      try:
        extra_tokens = [tok for tok in shlex.split(extra) if tok]
      except Exception:
        extra_tokens = [extra.strip()]
    # display id
    did = int(getattr(ss, 'display_id', -1) or -1)
    if did >= 0:
      extra_tokens = ['-d', str(did)] + extra_tokens
  except Exception:
    pass

  return _build_adb_command(
      serial_num,
      'shell',
      'screencap',
      '-p',
      *extra_tokens,
      shlex.quote(remote_path)
  )


def cmd_pull_device_file(serial_num: str, remote_path: str, local_path: str) -> str:
  return _build_adb_command(
      serial_num,
      'pull',
      shlex.quote(remote_path),
      shlex.quote(local_path)
  )


def cmd_remove_device_file(serial_num: str, remote_path: str) -> str:
  return _build_adb_command(
      serial_num,
      'shell',
      'rm',
      shlex.quote(remote_path)
  )


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
  """Build adb install command using persisted settings.

  The default flags remain: -d -r -g (plus optional -t), unless changed in settings.
  """
  try:
    # Lazy import to avoid any potential circular import issues
    from config.config_manager import ConfigManager
    settings = ConfigManager().get_apk_install_settings()
  except Exception:
    # Fallback to defaults if config cannot be loaded
    class _F:
      replace_existing = True
      allow_downgrade = True
      grant_permissions = True
      allow_test_packages = False
      extra_args = ''
    settings = _F()

  parts = ['install']
  if getattr(settings, 'allow_downgrade', True):
    parts.append('-d')
  if getattr(settings, 'replace_existing', True):
    parts.append('-r')
  if getattr(settings, 'grant_permissions', True):
    parts.append('-g')
  if getattr(settings, 'allow_test_packages', False):
    parts.append('-t')

  extra = getattr(settings, 'extra_args', '') or ''
  if extra.strip():
    try:
      parts.extend(shlex.split(extra))
    except Exception:
      # If parsing fails, append raw extra args to preserve behavior
      parts.append(extra.strip())

  parts.append(f'"{apk_path}"')
  return _build_adb_command(serial_num, *parts)

def cmd_extract_discovery_service_info(serial_num, root_folder):
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


def cmd_get_audio_dump(serial_num: str) -> str:
  return _build_adb_command(serial_num, 'shell', 'dumpsys', 'audio')


def cmd_get_bluetooth_manager_state(serial_num: str) -> str:
  return _build_adb_command(serial_num, 'shell', 'cmd', 'bluetooth_manager', 'get-state')


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


def cmd_list_packages(
    serial_num: str,
    *,
    include_path: bool = True,
    third_party_only: bool | None = None,
    user_id: int | None = None,
) -> str:
  """Build command for `pm list packages` with common flags.

  Args:
    serial_num: Device serial number
    include_path: Include APK path via `-f`
    third_party_only: True for `-3` (third-party), False for `-s` (system), None for all
    user_id: Android user id (when provided, adds `--user <id>`)

  Returns:
    Command string to execute on the device.
  """
  parts: list[str] = ['pm', 'list', 'packages']
  if include_path:
    parts.append('-f')
  if third_party_only is True:
    parts.append('-3')
  elif third_party_only is False:
    parts.append('-s')
  if user_id is not None:
    parts.extend(['--user', str(user_id)])
  return _build_adb_shell_command(serial_num, ' '.join(parts))


def cmd_dumpsys_package(serial_num: str, package_name: str) -> str:
  """Build command to dump package details for a specific app."""
  return _build_adb_shell_command(serial_num, f'dumpsys package {shlex.quote(package_name)}')


def cmd_adb_uninstall(serial_num: str, package_name: str, *, keep_data: bool = False) -> str:
  """Build command to uninstall a package from the device.

  Uses `adb uninstall` rather than shell pm to leverage host-side handling.
  """
  parts: list[str] = ['uninstall']
  if keep_data:
    parts.append('-k')
  parts.append(package_name)
  return _build_adb_command(serial_num, *parts)


def cmd_am_force_stop(serial_num: str, package_name: str) -> str:
  """Build command to force-stop an application."""
  return _build_adb_shell_command(serial_num, f'am force-stop {shlex.quote(package_name)}')


def cmd_pm_clear(serial_num: str, package_name: str) -> str:
  """Build command to clear app userdata (equivalent to factory reset for the app)."""
  return _build_adb_shell_command(serial_num, f'pm clear {shlex.quote(package_name)}')


def cmd_pm_set_enabled(serial_num: str, package_name: str, enable: bool, user_id: int | None = None) -> str:
  """Build command to enable or disable a package for a given user (if provided)."""
  if enable:
    base = f'pm enable {shlex.quote(package_name)}'
  else:
    # Prefer disable-user when possible to avoid requiring root
    if user_id is not None:
      base = f'pm disable-user --user {user_id} {shlex.quote(package_name)}'
    else:
      base = f'pm disable-user {shlex.quote(package_name)}'
  return _build_adb_shell_command(serial_num, base)


def cmd_open_app_info(serial_num: str, package_name: str) -> str:
  """Build command to open the app info settings page for a package."""
  uri = f'package:{package_name}'
  return _build_adb_shell_command(
      serial_num,
      f'am start -a android.settings.APPLICATION_DETAILS_SETTINGS -d {shlex.quote(uri)}'
  )


def cmd_open_app_info_legacy(serial_num: str, package_name: str) -> str:
  """Fallback: directly start the InstalledAppDetails activity with extras.

  Some OEM builds are picky with the ACTION + data URI approach. This legacy
  fallback targets the known Settings component and passes the package extra.
  """
  pkg = shlex.quote(package_name)
  return _build_adb_shell_command(
      serial_num,
      f'am start -n com.android.settings/.applications.InstalledAppDetails -e package {pkg}'
  )


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


def cmd_list_device_directory(serial_num: str, remote_path: str) -> str:
  """Build command to list a directory on the device."""
  sanitized_path = remote_path if remote_path else '/'
  return _build_adb_command(
      serial_num,
      'shell',
      'ls',
      '-a',
      '-p',
      '-1',
      shlex.quote(sanitized_path)
  )

def cmd_adb_screen_shot(
    serial_num: str, file_name: str, output_folder_path: str
) -> str:
  """One-line screenshot capture+pull command; applies screenshot settings when present."""
  screen_shot_phone_path = f'/sdcard/{serial_num}_screenshot_{file_name}.png'
  quoted_phone_path = shlex.quote(screen_shot_phone_path)
  quoted_output_path = shlex.quote(output_folder_path)

  extra_tokens: list[str] = []
  try:
    from config.config_manager import ConfigManager
    ss = ConfigManager().get_screenshot_settings()
    extra = getattr(ss, 'extra_args', '') or ''
    if extra.strip():
      try:
        extra_tokens = [tok for tok in shlex.split(extra) if tok]
      except Exception:
        extra_tokens = [extra.strip()]
  except Exception:
    pass

  extra_str = (" " + " ".join(extra_tokens)) if extra_tokens else ""
  return (
      f'adb -s {serial_num} shell screencap -p{extra_str} {quoted_phone_path} && '
      f'adb -s {serial_num} pull {quoted_phone_path} {quoted_output_path}'
  )


def cmd_android_screen_record(serial_num, name) -> str:
  """Build screenrecord start command using persisted settings when available."""
  opts: list[str] = []
  try:
    from config.config_manager import ConfigManager
    rs = ConfigManager().get_screen_record_settings()
    br = (getattr(rs, 'bit_rate', '') or '').strip()
    if br:
      opts.extend(['--bit-rate', br])
    tl = int(getattr(rs, 'time_limit_sec', 0) or 0)
    if tl > 0:
      opts.extend(['--time-limit', str(tl)])
    sz = (getattr(rs, 'size', '') or '').strip()
    if sz:
      opts.extend(['--size', sz])
    did = int(getattr(rs, 'display_id', -1) or -1)
    if did >= 0:
      opts.extend(['--display-id', str(did)])
    if bool(getattr(rs, 'use_hevc', False)):
      opts.extend(['--codec', 'hevc'])
    if bool(getattr(rs, 'bugreport', False)):
      opts.append('--bugreport')
    if bool(getattr(rs, 'verbose', False)):
      opts.append('--verbose')
    extra = (getattr(rs, 'extra_args', '') or '').strip()
    if extra:
      try:
        opts.extend([tok for tok in shlex.split(extra) if tok])
      except Exception:
        opts.append(extra)
  except Exception:
    pass

  return (
      f'adb -s {serial_num} shell screenrecord'
      + (" " + " ".join(opts) if opts else "")
      + f' /sdcard/screenrecord_{serial_num}_{name}.mp4'
  )

def cmd_android_screen_record_stop(serial_num) -> str:
  # -lINT
  # -SIGINT
  return f'adb -s {serial_num} shell pkill -SIGINT screenrecord'


def cmd_pull_android_screen_record(
    serial_num: str, name: str, output_folder_path: str
) -> str:
  device_path = f'/sdcard/screenrecord_{serial_num}_{name}.mp4'
  return (
      f'adb -s {serial_num} pull {shlex.quote(device_path)} '
      f'{shlex.quote(output_folder_path)}'
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
