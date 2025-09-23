"""Common utils."""

import json
import os
from typing import Any

from utils import common

logger = common.get_logger('json_utils')


def save_json_to_file(file_path: str, data: dict[str, Any]) -> None:
  """Save dict to json file.

  Args:
    file_path: The file path to save.
    data: The dict data to save.
  """
  expanded_path = os.path.expanduser(file_path)
  try:
    with open(expanded_path, 'w', encoding='utf-8') as f:
      json.dump(data, f, indent=4)
  except IOError as e:
    logger.error('Error saving json file: %s', e)


def load_json_from_file(file_path: str) -> dict[str, Any]:
  """Load json file to dict.

  Args:
    file_path: The file path to load.

  Returns:
    The dict data from json file.
  """
  expanded_path = os.path.expanduser(file_path)
  try:
    with open(expanded_path, 'r', encoding='utf-8') as f:
      return json.load(f)
  except (IOError, json.JSONDecodeError) as e:
    logger.error('Error loading json file: %s', e)
    return {}


# Config file constants
CONFIG_FILE_PATH = '~/.lazy_blacktea_config.json'


def read_config_json() -> dict[str, Any]:
  """Read config data from the default config file.

  Returns:
    The config data as dict.
  """
  return load_json_from_file(CONFIG_FILE_PATH)


def save_config_json(data: dict[str, Any]) -> None:
  """Save config data to the default config file.

  Args:
    data: The config data to save.
  """
  save_json_to_file(CONFIG_FILE_PATH, data)
