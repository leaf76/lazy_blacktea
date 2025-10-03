"""This is utils."""

import datetime
import logging
import os
import pathlib
import shlex
import subprocess
from typing import Optional


# Track whether log cleanup has already run for the current day.
_logs_cleaned_today = False


def _cleanup_old_logs(logs_dir: str):
  """Remove log files that do not belong to today (runs at most once per day)."""
  global _logs_cleaned_today

  # Skip if cleanup already ran today.
  if _logs_cleaned_today:
    return 0

  try:
    today = datetime.date.today().strftime('%Y%m%d')
    cleaned_count = 0

    for filename in os.listdir(logs_dir):
      if filename.startswith('lazy_blacktea_') and filename.endswith('.log'):
        # Extract date segment (lazy_blacktea_20250924_123456.log -> 20250924)
        try:
          date_part = filename[14:22]
          if len(date_part) == 8 and date_part.isdigit():
            if date_part != today:
              old_log_path = os.path.join(logs_dir, filename)
              os.remove(old_log_path)
              cleaned_count += 1
        except (IndexError, ValueError):
          # Skip unexpected filename formats.
          continue

    # Mark cleanup as done.
    _logs_cleaned_today = True

    return cleaned_count
  except Exception as e:
    # Cleanup failures should not interrupt the main application.
    return 0


def get_logger(name: str = 'my_logger') -> logging.Logger:
  """Set the logger with simplified output."""
  # Create logs directory in appropriate location based on platform
  import platform
  system = platform.system().lower()

  if system == 'darwin':  # macOS
    home_dir = os.path.expanduser('~')
    logs_dir = os.path.join(home_dir, '.lazy_blacktea_logs')
  elif system == 'linux':  # Linux
    # Use XDG Base Directory Specification
    xdg_data_home = os.environ.get('XDG_DATA_HOME')
    if xdg_data_home:
      logs_dir = os.path.join(xdg_data_home, 'lazy_blacktea', 'logs')
    else:
      home_dir = os.path.expanduser('~')
      logs_dir = os.path.join(home_dir, '.local', 'share', 'lazy_blacktea', 'logs')
  else:  # Fallback for other systems
    home_dir = os.path.expanduser('~')
    logs_dir = os.path.join(home_dir, '.lazy_blacktea_logs')
  pathlib.Path(logs_dir).mkdir(parents=True, exist_ok=True)

  # Clean up old log files (keep only today's logs)
  cleaned_count = _cleanup_old_logs(logs_dir)

  # Create log filename with timestamp
  current_time = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
  log_filename = f'lazy_blacktea_{current_time}.log'
  log_filepath = os.path.join(logs_dir, log_filename)

  # Configure logging with file handler only for detailed logs
  # Console handler only shows WARNING and above
  logger = logging.getLogger(name)

  # Avoid duplicate handlers
  if not logger.handlers:
    # File handler - detailed logging
    try:
      file_handler = logging.FileHandler(log_filepath, encoding='utf-8')
    except (OSError, PermissionError):
      fallback_dir = os.path.join(os.getcwd(), 'logs')
      pathlib.Path(fallback_dir).mkdir(parents=True, exist_ok=True)
      log_filepath = os.path.join(fallback_dir, log_filename)
      file_handler = logging.FileHandler(log_filepath, encoding='utf-8')
    file_handler.setLevel(logging.INFO)
    file_formatter = logging.Formatter(
        '%(asctime)s %(name)-12s %(levelname)-8s %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    file_handler.setFormatter(file_formatter)

    # Console handler - allow all levels for debugging
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)  # Changed from WARNING to INFO
    console_formatter = logging.Formatter('%(levelname)s: %(message)s')
    console_handler.setFormatter(console_formatter)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    logger.setLevel(logging.INFO)

    if cleaned_count > 0:
      logger.info('Removed %s old log file(s)', cleaned_count)

    # Only log file creation once
    if name == 'lazy_blacktea':
      logger.info(f"Log file created: {log_filepath}")

  return logger


_logger = get_logger('common')


def read_file(path) -> []:
  check_file = os.path.isfile(path)
  if not check_file:
    return ''
  result = []
  with open(path, encoding='utf-8') as f:
    read_data = f.readlines()
  for line in read_data:
    result.append(line.strip())
  return result


def timestamp_time() -> str:
  time_now = datetime.datetime.now().timestamp()
  return timestamp_to_format_time(time_now)


def timestamp_to_format_time(timestamp) -> str:
  """Convert the timestamp to format time.

  Args:
    timestamp: timestamp

  Returns:
    format time
  """
  try:
    timestamp = float(timestamp)
  except ValueError:
    return '0000000000'
  if len(str(timestamp)) > 10:
    timestamp = timestamp / 1000
  dt_object = datetime.datetime.fromtimestamp(timestamp)
  formatted_time = dt_object.strftime('%Y%m%d_%H%M%S')
  return formatted_time


def current_format_time_utc() -> str:
  # Get the current time with timestamp in utc
  current_utc_time = datetime.datetime.now()
  # utc_timestamp = current_utc_time.timestamp()
  # Format the time to 'yyyy_MM_dd_HH_mm_ss'
  formatted_time = current_utc_time.strftime('%Y%m%d_%H%M%S')
  return formatted_time


def make_gen_dir_path(folder_path: str) -> str:
  # process the path
  folder_path = folder_path.strip()
  if not folder_path:
    return ''

  # If the folder not exists that it to generate the full path folder.
  full_path = get_full_path(folder_path)
  pathlib.Path(full_path).mkdir(parents=True, exist_ok=True)
  # return folder full path
  return pathlib.Path(full_path).as_posix()


def check_exists_dir(path) -> bool:
  return os.path.exists(get_full_path(path))


def get_full_path(path):
  # Get the full path
  return os.path.expanduser(path)


def make_full_path(root_path: str, *paths: str) -> str:
  """Make the full path."""
  if not paths:
    return root_path
  return pathlib.Path(root_path).joinpath(*paths).as_posix()


def make_file_extension(file_path: str, extension: str) -> str:
  return pathlib.Path(file_path).with_suffix(extension)


def sp_run_command(command, ignore_index=0) -> list[str]:
  """This is for the sync process will be stuck the main process."""
  # start to run the command line
  _logger.debug('Run command: %s', command)
  listing_result = []

  # Convert string command to list for security
  if isinstance(command, str):
    command_list = shlex.split(command)
  else:
    command_list = command

  try:
    result = subprocess.run(
        command_list, check=True, capture_output=True, shell=False,
        text=True, encoding='utf-8'
    )
    if result.returncode == 0:
      output = result.stdout.splitlines()
      for line in output[ignore_index:]:
        listing_result.append(line)
    else:
      err_msg = result.stderr
      _logger.warning('Command error: %s', err_msg)
  except subprocess.CalledProcessError as e:
    _logger.warning('Command process error: %s', e.stderr if e.stderr else str(e))
  except Exception as e:
    _logger.error('Unexpected error running command: %s', str(e))
  _logger.debug('Command result: %s', listing_result)
  return listing_result


def validate_and_create_output_path(output_path: str) -> Optional[str]:
  """Validate and normalize output path, creating it if necessary.

  Args:
    output_path: Path to validate and potentially create

  Returns:
    Normalized path if valid, None if invalid
  """
  if not output_path or not output_path.strip():
    return None

  # Validate and normalize using common utilities
  if not check_exists_dir(output_path):
    normalized_path = make_gen_dir_path(output_path)
    if not normalized_path:
      return None
    return normalized_path

  return output_path


def run_command(command, ignore_index=0) -> list[str]:
  """This is for the sync process will be stuck the main process."""
  # start to run the command line
  _logger.debug('Run command: %s', command)
  return mp_run_command(command, ignore_index)


# This is for the non-sync process.
def mp_run_command(cmd: str, ignore_index=0) -> list[str]:
  """Run the command in non-sync process.

  Args:
    cmd: command
    ignore_index: ignore the first index

  Returns:
    list of string
  """
  # start to run the command line
  _logger.debug('Execute command: %s', cmd)
  listing_result = []
  # Convert string command to list for security
  if isinstance(cmd, str):
    command_list = shlex.split(cmd)
  else:
    command_list = cmd

  try:
    result = subprocess.Popen(
        command_list, shell=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, encoding='utf-8'
    )
    stdout, stderr = result.communicate()
    _logger.debug('Command stdout: %s', stdout)
    _logger.debug('Command stderr: %s', stderr)
    if result.returncode == 0:
      output = stdout.splitlines()
      for line in output[ignore_index:]:
        listing_result.append(line)
    else:
      if stderr and stderr.strip():  # Only log if there's actual error content
        _logger.warning('Command error: %s', stderr)
  except Exception as e:
    _logger.warning('Command process error: %s', str(e))
  _logger.debug('Command result: %s', listing_result)
  return listing_result

def create_cancellable_process(cmd: str) -> Optional[subprocess.Popen]:
    """Creates and returns a subprocess.Popen object for a command that can be cancelled.

    This function does not wait for the command to complete.

    Args:
        cmd: The command to execute.

    Returns:
        A subprocess.Popen object if successful, otherwise None.
    """
    _logger.debug('Creating cancellable process for command: %s', cmd)
    try:
        if isinstance(cmd, str):
            command_list = shlex.split(cmd)
        else:
            command_list = cmd

        process = subprocess.Popen(
            command_list,
            shell=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding='utf-8'
        )
        return process
    except Exception as e:
        _logger.error('Failed to create cancellable process: %s', str(e))
        return None
