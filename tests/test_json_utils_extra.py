#!/usr/bin/env python3
"""Extra unit tests for utils.json_utils covering error and path-expansion flows."""

import os
import sys
import json
import tempfile
import unittest
from unittest.mock import patch, mock_open

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils import json_utils


class TestJsonUtilsExtra(unittest.TestCase):
    def test_save_and_load_ok(self) -> None:
        """save_json_to_file/load_json_from_file roundtrip via patched expanduser."""
        with tempfile.TemporaryDirectory() as td:
            target = os.path.join(td, "data.json")
            data = {"a": 1, "b": "ok"}

            with patch("utils.json_utils.os.path.expanduser", return_value=target):
                json_utils.save_json_to_file("~/fake.json", data)
                loaded = json_utils.load_json_from_file("~/fake.json")

            self.assertEqual(loaded, data)

    def test_save_handles_io_error(self) -> None:
        """save_json_to_file should log on IOError and not raise."""
        data = {"k": "v"}
        with patch("utils.json_utils.os.path.expanduser", return_value="/no/such/dir/x.json"), \
             patch("builtins.open", side_effect=IOError("boom")):
            # Should not raise
            json_utils.save_json_to_file("~/x.json", data)

    def test_load_handles_io_and_decode_error(self) -> None:
        """load_json_from_file returns {} for IO/JSON errors."""
        # IOError path
        with patch("utils.json_utils.os.path.expanduser", return_value="/nope.json"), \
             patch("builtins.open", side_effect=IOError("nope")):
            self.assertEqual(json_utils.load_json_from_file("~/nope.json"), {})

        # JSON decode error path
        m = mock_open(read_data="{invalid json}")
        with patch("utils.json_utils.os.path.expanduser", return_value="/tmp/invalid.json"), \
             patch("builtins.open", m):
            self.assertEqual(json_utils.load_json_from_file("~/invalid.json"), {})

    def test_config_read_write_uses_config_path(self) -> None:
        """read_config_json/save_config_json should respect CONFIG_FILE_PATH when patched."""
        with tempfile.TemporaryDirectory() as td:
            cfg = os.path.join(td, "config.json")
            payload = {"ui": {"scale": 1.25}}

            with patch("utils.json_utils.CONFIG_FILE_PATH", cfg):
                json_utils.save_config_json(payload)
                loaded = json_utils.read_config_json()
                self.assertEqual(loaded, payload)


if __name__ == "__main__":
    unittest.main()

