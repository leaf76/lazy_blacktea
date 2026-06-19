"""Package / app management domain for the ADB layer (extracted from adb_tools, #63).

Depends only on ``_base`` (logger), ``common`` and ``adb_commands``.
``utils.adb_tools`` re-exports these names.
"""

from __future__ import annotations

from typing import List

from utils import adb_commands
from utils import common
from utils.adb._base import logger


def parse_pm_list_packages_output(lines: List[str]) -> List[dict]:
  """Parse lines from `pm list packages -f`.

  Each input line typically looks like one of:
    - 'package:/data/app/.../base.apk=com.example.app'
    - 'package:/system/app/.../Sys.apk=com.android.sys'

  Returns a list of dicts with keys: package, apk_path, is_system.
  """
  apps: List[dict] = []
  for raw in lines or []:
    line = (raw or '').strip()
    if not line:
      continue
    if not line.startswith('package:'):
      # Some Android builds omit prefix in rare cases; tolerate pure 'com.pkg'
      if '=' not in line:
        pkg = line
        apk_path = ''
      else:
        # Fallback generic parse
        try:
          apk_path, pkg = line.split('=', 1)
        except ValueError:
          continue
      is_system = apk_path.startswith(('/system/', '/product/', '/vendor/', '/system_ext/'))
      apps.append({'package': pkg, 'apk_path': apk_path, 'is_system': is_system})
      continue

    # Normal form: package:<path>=<pkg>
    try:
      payload = line[len('package:'):]
      # Some paths may contain '=' (e.g., modern base paths encode with '=='),
      # so split from the rightmost '='
      apk_path, pkg = payload.rsplit('=', 1)
    except ValueError:
      continue
    apk_path = apk_path.strip()
    pkg = pkg.strip()
    is_system = apk_path.startswith(('/system/', '/product/', '/vendor/', '/system_ext/'))
    apps.append({'package': pkg, 'apk_path': apk_path, 'is_system': is_system})
  return apps


def parse_dumpsys_package_permissions(lines: List[str]) -> dict:
  """Parse permissions from `dumpsys package <pkg>` output.

  Extracts two sets:
    - requested: permissions listed under 'requested permissions:'
    - granted: permissions with 'granted=true' under install/runtime sections
  """
  requested: set[str] = set()
  granted: set[str] = set()

  section = None
  for raw in lines or []:
    line = (raw or '').strip()
    if not line:
      continue
    lower = line.lower()
    if lower.endswith('requested permissions:'):
      section = 'requested'
      continue
    if lower.endswith('install permissions:') or lower.endswith('runtime permissions:'):
      section = 'grants'
      continue

    if section == 'requested':
      # Lines are permission names (possibly indented)
      # Filter obviously invalid tokens
      if ' ' not in line and '.' in line:
        requested.add(line)
      continue

    if section == 'grants':
      # Format: <perm>: granted=true/false
      # Accept variations like '<perm>: granted=true, flags=0xX'
      if ':' in line:
        perm, _, tail = line.partition(':')
        perm = perm.strip()
        if perm:
          if 'granted=true' in tail.replace(' ', '').lower():
            granted.add(perm)
      continue

  return {'requested': sorted(requested), 'granted': sorted(granted)}


def list_installed_packages(
    serial_num: str,
    *,
    include_path: bool = True,
    third_party_only: bool | None = None,
    user_id: int | None = None,
) -> List[dict]:
  """Return parsed package list for the given device.

  See `parse_pm_list_packages_output` for the returned item format.
  """
  cmd = adb_commands.cmd_list_packages(
      serial_num,
      include_path=include_path,
      third_party_only=third_party_only,
      user_id=user_id,
  )
  lines = common.run_command(cmd)
  return parse_pm_list_packages_output(lines)


def get_app_version_name(serial_num: str, package_name: str) -> str:
  """Return versionName for the package or empty string if unavailable.

  Use dumpsys output and parse in Python for better cross-device compatibility
  (avoid relying on device-side grep/cut).
  """
  cmd = adb_commands.cmd_dumpsys_package(serial_num, package_name)
  lines = common.run_command(cmd)
  version = ''
  for raw in lines:
    line = (raw or '').strip()
    if not line:
      continue
    if 'versionName' in line:
      # Accept both 'versionName=1.2.3' and 'versionName: 1.2.3'
      if '=' in line:
        version = line.split('=', 1)[1].strip()
      elif ':' in line:
        version = line.split(':', 1)[1].strip()
      # Trim any surrounding quotes
      version = version.strip('"\'')
      if version:
        return version
  return version


def get_package_permissions(serial_num: str, package_name: str) -> dict:
  """Return requested/granted permissions for the given package."""
  cmd = adb_commands.cmd_dumpsys_package(serial_num, package_name)
  lines = common.run_command(cmd)
  return parse_dumpsys_package_permissions(lines)


def uninstall_app(serial_num: str, package_name: str, *, keep_data: bool = False) -> bool:
  """Uninstall the given package. Returns True on success."""
  cmd = adb_commands.cmd_adb_uninstall(serial_num, package_name, keep_data=keep_data)
  lines = common.run_command(cmd)
  normalized = '\n'.join((l or '').strip() for l in lines)
  return 'success' in normalized.lower()


def force_stop_app(serial_num: str, package_name: str) -> bool:
  """Force stop a running app. Returns True only if adb exited successfully.

  ``am force-stop`` produces no stdout on success, so we rely on the exit code
  (via run_command_with_status) instead of output presence to avoid reporting
  success when the device is offline or the package is invalid.
  """
  cmd = adb_commands.cmd_am_force_stop(serial_num, package_name)
  returncode, _stdout, stderr = common.run_command_with_status(cmd)
  if returncode != 0:
    logger.error(
        'force_stop_app failed for %s/%s (exit %s): %s',
        serial_num,
        package_name,
        returncode,
        ' '.join(stderr).strip(),
    )
    return False
  return True


def clear_app_data(serial_num: str, package_name: str) -> bool:
  """Clear app data; returns True if 'Success' was reported."""
  cmd = adb_commands.cmd_pm_clear(serial_num, package_name)
  lines = common.run_command(cmd)
  normalized = '\n'.join((l or '').strip() for l in lines)
  return 'success' in normalized.lower()


def set_app_enabled(serial_num: str, package_name: str, enable: bool, *, user_id: int | None = None) -> bool:
  """Enable or disable a package. Returns True on apparent success."""
  cmd = adb_commands.cmd_pm_set_enabled(serial_num, package_name, enable, user_id)
  lines = common.run_command(cmd)
  text = '\n'.join((l or '').lower() for l in lines)
  if 'error' in text:
    return False
  # Typical outputs include 'new state: enabled/disabled' or nothing
  if enable:
    return 'enabled' in text or text.strip() == ''
  return 'disabled' in text or text.strip() == ''


def _am_start_reported_error(returncode: int, stdout: list[str], stderr: list[str]) -> bool:
  """Heuristic for whether an ``am start`` invocation failed.

  ``am start`` exit codes are unreliable across Android versions, so we treat the
  command as failed when it could not run at all or its output contains an error
  marker (``Error:`` / ``unable to``).
  """
  if returncode == -1:
    return True
  text = '\n'.join(list(stdout) + list(stderr)).lower()
  return 'error' in text or 'unable to' in text


def open_app_info(serial_num: str, package_name: str) -> bool:
  """Open the app details settings page for the package with fallbacks.

  Returns True when either the primary or the legacy ``am start`` is accepted.
  Only returns False when both invocations report an error.
  """
  primary = adb_commands.cmd_open_app_info(serial_num, package_name)
  returncode, stdout, stderr = common.run_command_with_status(primary)
  if not _am_start_reported_error(returncode, stdout, stderr):
    return True

  legacy = adb_commands.cmd_open_app_info_legacy(serial_num, package_name)
  returncode, stdout, stderr = common.run_command_with_status(legacy)
  if _am_start_reported_error(returncode, stdout, stderr):
    logger.error('open_app_info failed for %s/%s', serial_num, package_name)
    return False
  return True


__all__ = [
    "parse_pm_list_packages_output",
    "parse_dumpsys_package_permissions",
    "list_installed_packages",
    "get_app_version_name",
    "get_package_permissions",
    "uninstall_app",
    "force_stop_app",
    "clear_app_data",
    "set_app_enabled",
    "_am_start_reported_error",
    "open_app_info",
]
