"""APK install domain for the ADB layer (extracted from adb_tools, #63).

Self-contained: imports only ``_base`` (logger + parallel-exec), ``common``,
``adb_commands``, ``adb_models`` and the stdlib. ``utils.adb_tools`` re-exports
these names so existing references keep resolving.
"""

from __future__ import annotations

import concurrent.futures
import os
import pathlib
import platform
import re
import shutil
import subprocess
import tempfile
import time
import zipfile
from typing import List, Optional

from config.constants import ADBConstants
from utils import adb_commands
from utils import adb_models
from utils import common
from utils.adb._base import logger, _execute_commands_parallel


def get_apk_info(apk_path: str) -> adb_models.ApkInfo:
  """Extract information from an APK file.

  Uses aapt/aapt2 if available, otherwise performs basic validation.

  Args:
    apk_path: Path to the APK file.

  Returns:
    ApkInfo with extracted metadata or error information.
  """
  apk_path = common.get_full_path(apk_path)
  info = adb_models.ApkInfo(path=apk_path)

  # Check file exists
  path_obj = pathlib.Path(apk_path)
  if not path_obj.exists():
    info.error = f'File not found: {apk_path}'
    return info

  if not path_obj.is_file():
    info.error = f'Not a file: {apk_path}'
    return info

  info.file_size_bytes = path_obj.stat().st_size

  # Check if it's a split APK bundle (.apks or .xapk)
  lower_path = apk_path.lower()
  if lower_path.endswith('.apks') or lower_path.endswith('.xapk'):
    info.is_split_apk = True
    # For split APKs, we'd need to extract and parse - mark as valid for now
    info.package_name = path_obj.stem  # Use filename as placeholder
    return info

  # Validate ZIP structure (APK is a ZIP file)
  try:
    with zipfile.ZipFile(apk_path, 'r') as zf:
      namelist = zf.namelist()
      if 'AndroidManifest.xml' not in namelist:
        info.error = 'Invalid APK: missing AndroidManifest.xml'
        return info
      if 'classes.dex' not in namelist and not any(n.startswith('classes') and n.endswith('.dex') for n in namelist):
        # Some APKs might use different dex naming
        pass  # Not a critical error
  except zipfile.BadZipFile:
    info.error = 'Invalid APK: not a valid ZIP file'
    return info
  except Exception as e:
    info.error = f'Error reading APK: {e}'
    return info

  # Try aapt2 first, then aapt
  aapt_cmd = _find_aapt_command()
  if aapt_cmd:
    try:
      result = subprocess.run(
          [aapt_cmd, 'dump', 'badging', apk_path],
          capture_output=True,
          text=True,
          timeout=30
      )
      if result.returncode == 0:
        _parse_aapt_output(info, result.stdout)
        return info
    except Exception as e:
      logger.debug('aapt parsing failed: %s', e)

  # Fallback: use filename as package name hint
  if not info.package_name:
    info.package_name = path_obj.stem

  return info


def _find_aapt_command() -> Optional[str]:
  """Find aapt or aapt2 command on the system."""
  for cmd in ['aapt2', 'aapt']:
    if shutil.which(cmd):
      return cmd

  # Check common Android SDK locations
  android_home = os.environ.get('ANDROID_HOME') or os.environ.get('ANDROID_SDK_ROOT')
  if android_home:
    build_tools = pathlib.Path(android_home) / 'build-tools'
    if build_tools.exists():
      # Sort by version number (handle "30.0.0" > "9.0.0" correctly)
      def version_key(path: pathlib.Path) -> tuple:
        try:
          parts = path.name.split('.')
          return tuple(int(p) for p in parts if p.isdigit())
        except (ValueError, AttributeError):
          return (0,)

      versions = sorted(build_tools.iterdir(), key=version_key, reverse=True)
      for version_dir in versions:
        for cmd in ['aapt2', 'aapt']:
          aapt_path = version_dir / cmd
          if platform.system() == 'Windows':
            aapt_path = version_dir / f'{cmd}.exe'
          if aapt_path.exists():
            return str(aapt_path)

  return None


def _parse_aapt_output(info: adb_models.ApkInfo, output: str) -> None:
  """Parse aapt dump badging output to extract APK info."""
  for line in output.split('\n'):
    if line.startswith('package:'):
      # package: name='com.example' versionCode='1' versionName='1.0'
      match = re.search(r"name='([^']+)'", line)
      if match:
        info.package_name = match.group(1)
      match = re.search(r"versionCode='(\d+)'", line)
      if match:
        info.version_code = int(match.group(1))
      match = re.search(r"versionName='([^']+)'", line)
      if match:
        info.version_name = match.group(1)
    elif line.startswith('sdkVersion:'):
      match = re.search(r"'(\d+)'", line)
      if match:
        info.min_sdk_version = int(match.group(1))
    elif line.startswith('targetSdkVersion:'):
      match = re.search(r"'(\d+)'", line)
      if match:
        info.target_sdk_version = int(match.group(1))


def validate_apk_for_device(
    apk_info: adb_models.ApkInfo,
    device_api_level: Optional[int] = None
) -> tuple[bool, str]:
  """Validate if an APK can be installed on a device.

  Args:
    apk_info: APK information from get_apk_info()
    device_api_level: Device's Android API level (optional)

  Returns:
    Tuple of (is_valid, error_message)
  """
  if not apk_info.is_valid:
    return False, apk_info.error or 'Invalid APK'

  if device_api_level and apk_info.min_sdk_version:
    if device_api_level < apk_info.min_sdk_version:
      return False, (
          f'Device API level {device_api_level} is below '
          f'minimum required {apk_info.min_sdk_version}'
      )

  return True, ''


def extract_split_apks(bundle_path: str, extract_dir: Optional[str] = None) -> List[str]:
  """Extract APKs from a split APK bundle (.apks or .xapk).

  Args:
    bundle_path: Path to .apks or .xapk file
    extract_dir: Optional directory for extraction. If None, uses temp dir.

  Returns:
    List of extracted APK file paths, or empty list on failure.
  """
  bundle_path = common.get_full_path(bundle_path)
  lower_path = bundle_path.lower()

  if not (lower_path.endswith('.apks') or lower_path.endswith('.xapk')):
    # Not a bundle, return as single APK
    return [bundle_path] if pathlib.Path(bundle_path).is_file() else []

  if not pathlib.Path(bundle_path).is_file():
    logger.warning('Split APK bundle not found: %s', bundle_path)
    return []

  # Create extraction directory
  if extract_dir is None:
    extract_dir = tempfile.mkdtemp(prefix='lazy_blacktea_apk_')

  extracted_apks = []

  try:
    with zipfile.ZipFile(bundle_path, 'r') as zf:
      for name in zf.namelist():
        # Extract only .apk files
        if name.lower().endswith('.apk'):
          # Handle nested paths (some bundles have apks in subdirs)
          apk_name = pathlib.Path(name).name
          extract_path = pathlib.Path(extract_dir) / apk_name

          with zf.open(name) as src, open(extract_path, 'wb') as dst:
            dst.write(src.read())

          extracted_apks.append(str(extract_path))
          logger.debug('Extracted split APK: %s', apk_name)

  except zipfile.BadZipFile:
    logger.error('Invalid split APK bundle: %s', bundle_path)
    return []
  except Exception as e:
    logger.error('Error extracting split APK bundle: %s', e)
    return []

  # Sort to put base APK first (usually named base.apk or contains 'base')
  def sort_key(path: str) -> tuple:
    name = pathlib.Path(path).name.lower()
    if 'base' in name:
      return (0, name)
    return (1, name)

  extracted_apks.sort(key=sort_key)
  logger.info('Extracted %d APKs from bundle: %s', len(extracted_apks), bundle_path)

  return extracted_apks


def install_split_apk(
    serial: str,
    apk_paths: List[str],
    device_model: Optional[str] = None,
) -> adb_models.ApkInstallResult:
  """Install split APKs on a single device using install-multiple.

  Args:
    serial: Device serial number
    apk_paths: List of APK file paths (base + splits)
    device_model: Optional device model for better error messages

  Returns:
    ApkInstallResult with installation outcome
  """
  device_start = time.monotonic()

  if not apk_paths:
    return adb_models.ApkInstallResult(
        serial=serial,
        success=False,
        error_code=adb_models.ApkInstallErrorCode.INSTALL_FAILED_INVALID_APK,
        raw_output='No APK files provided',
        device_model=device_model,
    )

  try:
    cmd = adb_commands.cmd_adb_install_multiple(serial, apk_paths)
    output = common.run_command(cmd, timeout=ADBConstants.INSTALL_COMMAND_TIMEOUT)

    output_str = output if isinstance(output, str) else ('\n'.join(output) if output else '')
    error_code = adb_models.ApkInstallErrorCode.from_output(output_str)
    success = error_code == adb_models.ApkInstallErrorCode.SUCCESS

    return adb_models.ApkInstallResult(
        serial=serial,
        success=success,
        error_code=error_code,
        raw_output=output_str,
        duration_seconds=time.monotonic() - device_start,
        device_model=device_model,
    )
  except Exception as e:
    return adb_models.ApkInstallResult(
        serial=serial,
        success=False,
        error_code=adb_models.ApkInstallErrorCode.UNKNOWN_ERROR,
        raw_output=str(e),
        duration_seconds=time.monotonic() - device_start,
        device_model=device_model,
    )


def install_apk(
    serial_nums: List[str],
    apk_path: str,
    *,
    progress_callback: Optional[Callable[[str, int, int, bool], None]] = None,
    validate: bool = True,
    device_info_map: Optional[dict[str, adb_models.DeviceInfo]] = None,
) -> adb_models.ApkBatchInstallResult:
  """Install APK on multiple devices with structured results.

  This is the improved installation API with:
  - Structured error codes and messages
  - Optional pre-validation
  - Progress callbacks
  - True parallel execution
  - Automatic split APK (.apks/.xapk) support

  Args:
    serial_nums: List of device serial numbers
    apk_path: Path to APK file (.apk, .apks, or .xapk)
    progress_callback: Optional callback(serial, current, total, success)
    validate: Whether to validate APK before install
    device_info_map: Optional map of serial -> DeviceInfo for better messages

  Returns:
    ApkBatchInstallResult with per-device results
  """
  start_time = time.monotonic()
  apk_path = common.get_full_path(apk_path)

  result = adb_models.ApkBatchInstallResult(apk_path=apk_path)

  # Check if this is a split APK bundle
  lower_path = apk_path.lower()
  is_split_bundle = lower_path.endswith('.apks') or lower_path.endswith('.xapk')
  split_apk_paths: List[str] = []
  temp_extract_dir: Optional[str] = None

  if is_split_bundle:
    # Extract split APKs to temp directory
    temp_extract_dir = tempfile.mkdtemp(prefix='lazy_blacktea_apk_')
    split_apk_paths = extract_split_apks(apk_path, temp_extract_dir)
    if not split_apk_paths:
      error_code = adb_models.ApkInstallErrorCode.INSTALL_FAILED_INVALID_APK
      for serial in serial_nums:
        result.results[serial] = adb_models.ApkInstallResult(
            serial=serial,
            success=False,
            error_code=error_code,
            raw_output=f'Failed to extract split APKs from: {apk_path}',
        )
      result.total_duration_seconds = time.monotonic() - start_time
      # Cleanup temp dir
      if temp_extract_dir:
        shutil.rmtree(temp_extract_dir, ignore_errors=True)
      return result
    logger.info('Split APK bundle detected, extracted %d APKs', len(split_apk_paths))

  # Get APK info (for regular APKs)
  if validate and not is_split_bundle:
    result.apk_info = get_apk_info(apk_path)
    if not result.apk_info.is_valid:
      error_code = adb_models.ApkInstallErrorCode.INSTALL_FAILED_INVALID_APK
      for serial in serial_nums:
        device_model = device_info_map[serial].device_model if device_info_map and serial in device_info_map else None
        result.results[serial] = adb_models.ApkInstallResult(
            serial=serial,
            success=False,
            error_code=error_code,
            raw_output=result.apk_info.error or '',
            device_model=device_model,
        )
      result.total_duration_seconds = time.monotonic() - start_time
      return result
  elif not is_split_bundle:
    # Basic path check for non-split APKs
    if not pathlib.Path(apk_path).is_file():
      for serial in serial_nums:
        result.results[serial] = adb_models.ApkInstallResult(
            serial=serial,
            success=False,
            error_code=adb_models.ApkInstallErrorCode.INSTALL_FAILED_INVALID_APK,
            raw_output=f'File not found: {apk_path}',
        )
      result.total_duration_seconds = time.monotonic() - start_time
      return result

  # Prepare install tasks
  def install_on_device(serial: str) -> adb_models.ApkInstallResult:
    device_start = time.monotonic()
    device_model = None
    if device_info_map and serial in device_info_map:
      device_model = device_info_map[serial].device_model

    try:
      if is_split_bundle:
        # Use install-multiple for split APKs
        cmd = adb_commands.cmd_adb_install_multiple(serial, split_apk_paths)
      else:
        cmd = adb_commands.cmd_adb_install(serial, apk_path)

      output = common.run_command(cmd, timeout=ADBConstants.INSTALL_COMMAND_TIMEOUT)

      # Parse result
      output_str = output if isinstance(output, str) else ('\n'.join(output) if output else '')
      error_code = adb_models.ApkInstallErrorCode.from_output(output_str)
      success = error_code == adb_models.ApkInstallErrorCode.SUCCESS

      return adb_models.ApkInstallResult(
          serial=serial,
          success=success,
          error_code=error_code,
          raw_output=output_str,
          duration_seconds=time.monotonic() - device_start,
          device_model=device_model,
      )
    except Exception as e:
      return adb_models.ApkInstallResult(
          serial=serial,
          success=False,
          error_code=adb_models.ApkInstallErrorCode.UNKNOWN_ERROR,
          raw_output=str(e),
          duration_seconds=time.monotonic() - device_start,
          device_model=device_model,
      )

  # Execute in parallel
  total = len(serial_nums)
  completed = 0

  try:
    with concurrent.futures.ThreadPoolExecutor(max_workers=min(total, 8)) as executor:
      future_to_serial = {
          executor.submit(install_on_device, serial): serial
          for serial in serial_nums
      }

      for future in concurrent.futures.as_completed(future_to_serial):
        serial = future_to_serial[future]
        try:
          install_result = future.result()
        except Exception as e:
          install_result = adb_models.ApkInstallResult(
              serial=serial,
              success=False,
              error_code=adb_models.ApkInstallErrorCode.UNKNOWN_ERROR,
              raw_output=str(e),
          )

        result.results[serial] = install_result
        completed += 1

        if progress_callback:
          try:
            progress_callback(serial, completed, total, install_result.success)
          except Exception:
            pass  # Don't let callback errors break installation

  finally:
    # Cleanup temp directory for split APKs
    if temp_extract_dir:
      shutil.rmtree(temp_extract_dir, ignore_errors=True)

  result.total_duration_seconds = time.monotonic() - start_time
  logger.info(
      'APK installation completed: %d/%d successful in %.2fs',
      result.successful_count, result.total_count, result.total_duration_seconds
  )

  return result


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
