"""File-transfer / pull domain for the ADB layer (extracted from adb_tools, #63).

Depends only on ``_base`` (logger + parallel-exec), ``common``, ``adb_commands``,
``adb_models``, ``dump_device_ui`` and the stdlib. ``utils.adb_tools`` re-exports
these names.
"""

from __future__ import annotations

import concurrent.futures
import os
import posixpath
import tempfile

from utils import adb_commands
from utils import adb_models
from utils import common
from utils import dump_device_ui
from utils.adb._base import (
    logger,
    _execute_commands_parallel,
    _execute_commands_parallel_native,
)


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


def pull_device_paths(serial_num: str, remote_paths: list[str], output_path: str) -> list[dict]:
  """Pull multiple remote paths from a device into a local output directory.

  Returns one result dict per requested path:
  ``{'remote_path': str, 'success': bool, 'output': str}``. ``success`` is
  determined by whether the file/directory was actually written to the host,
  not by the adb output text (which is unreliable: ``adb pull`` writes its
  summary to stderr and the runner returns no output on a non-zero exit). This
  lets callers report partial/failed downloads instead of always claiming
  success.
  """

  if not remote_paths:
    logger.info('No remote paths supplied for pull_device_paths')
    return []

  base_output = common.make_full_path(output_path, f'device_{serial_num}')
  final_output = common.make_gen_dir_path(base_output)

  commands: list[str] = []
  normalized_remotes: list[str] = []
  for remote_path in remote_paths:
    normalized_remote = _normalize_remote_path(remote_path)
    normalized_remotes.append(normalized_remote)
    commands.append(
        adb_commands.cmd_pull_device_file(serial_num, normalized_remote, final_output)
    )

  logger.info('Pulling %d paths for device %s into %s', len(commands), serial_num, final_output)
  native_results = _execute_commands_parallel_native(commands, 'pull_device_paths')

  results: list[dict] = []
  for remote_path, normalized_remote, native_result in zip(
      remote_paths, normalized_remotes, native_results
  ):
    output_text = '\n'.join(native_result) if native_result else ''
    local_target = os.path.join(final_output, os.path.basename(normalized_remote.rstrip('/')))
    success = os.path.exists(local_target)
    if not success:
      logger.error(
          'Download verification failed for %s (expected %s)', remote_path, local_target
      )
    results.append(
        {'remote_path': remote_path, 'success': success, 'output': output_text}
    )
  return results


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
