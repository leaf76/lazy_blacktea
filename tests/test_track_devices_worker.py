#!/usr/bin/env python3
"""Tests for TrackDevicesWorker length-prefixed parsing."""

import io
import os
import sys
import tempfile
import threading
import unittest
from collections import OrderedDict

# Redirect HOME so logger writes inside workspace-friendly location before imports
TEST_HOME = tempfile.mkdtemp(prefix='lazy_blacktea_test_home_')
os.environ['HOME'] = TEST_HOME

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ui.async_device_manager import TrackDevicesWorker  # noqa: E402


def _build_chunk(payload: str) -> bytes:
    encoded = payload.encode('utf-8')
    return f"{len(encoded):04x}".encode('ascii') + encoded


class TrackDevicesWorkerParsingTests(unittest.TestCase):
    """Ensure adb track-devices stream parsing handles length prefixes."""

    def test_consume_track_stream_parses_length_prefixed_messages(self):
        payload_online = "35151FDJH000GQ\tdevice\n"
        payload_offline = "35151FDJH000GQ\toffline\n"
        stream = io.BytesIO(
            _build_chunk(payload_online)
            + _build_chunk(payload_offline)
            + b"0000"
        )

        stop_event = threading.Event()
        updates = list(TrackDevicesWorker._consume_track_stream(stream, stop_event))

        expected = [
            OrderedDict({"35151FDJH000GQ": "device"}),
            OrderedDict({"35151FDJH000GQ": "offline"}),
            OrderedDict(),
        ]
        self.assertEqual(expected, updates)


if __name__ == "__main__":
    unittest.main()
