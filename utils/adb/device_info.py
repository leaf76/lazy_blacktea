"""Device discovery / info domain for the ADB layer (extracted from adb_tools, #63).

The module's central responsibility: enumerate devices and build DeviceInfo.
Depends only on ``_base``, ``common``, ``adb_commands`` and ``adb_models``.
``utils.adb_tools`` re-exports these names.
"""

from __future__ import annotations

import re
import subprocess
from typing import List, Optional

from config.constants import ADBConstants
from utils import adb_commands
from utils import adb_models
from utils import common
from utils.adb._base import (
    logger,
    adb_device_operation,
    _execute_functions_parallel,
)


## GMS app package name
gms_package_name = 'com.google.android.gms'

ACCEPTED_DEVICE_STATUSES = {
    ADBConstants.DEVICE_STATE_DEVICE,
    ADBConstants.DEVICE_STATE_UNAUTHORIZED,
    ADBConstants.DEVICE_STATE_RECOVERY,
    ADBConstants.DEVICE_STATE_BOOTLOADER,
    getattr(ADBConstants, 'DEVICE_STATE_SIDELOAD', 'sideload'),
    '',
}


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
    manufacturer_result = common.run_command(manufacturer_cmd, timeout=10)
    manufacturer = ''
    if manufacturer_result and isinstance(manufacturer_result, list):
      manufacturer = ' '.join(str(item) for item in manufacturer_result).strip()

    # Get model property for additional context
    model_cmd = adb_commands._build_getprop_command(serial_num, 'ro.product.model')
    model_result = common.run_command(model_cmd, timeout=10)
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
  """Return ro.build.version.release verbatim (e.g. '13', '13.0', '12L').

  Previously only integer releases were kept and everything else became 0
  ('Android 0'); the release is a free-form string, so return it as-is and fall
  back to 'Unknown' when unavailable (finding #34).
  """
  cmd = adb_commands.cmd_get_android_version(serial_num)
  result = common.run_command(cmd)
  if result:
    data = str(result[0]).strip()
    if data:
      return data
  return 'Unknown'

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


__all__ = [
    'get_device_serial_num_list',
    'get_devices_list',
    'get_devices_list_fast',
    'device_basic_info_entry',
    'get_device_detailed_info',
    'device_info_entry',
    '_is_device_available',
    '_get_device_manufacturer_info',
    'check_wifi_is_on',
    'check_bluetooth_is_on',
    'get_audio_state_summary',
    'get_bluetooth_manager_state_summary',
    'get_android_version',
    'get_android_api_level',
    'get_gms_version',
    'get_build_fingerprint',
    'get_device_properties',
    '_get_device_property',
    'get_additional_device_info',
]
