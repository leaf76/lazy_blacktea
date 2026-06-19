"""Regression tests for device file download success (audit finding #17).

``on_download_completed`` used to always show "Download Complete" and compute the
success count with a broken ``== 'OK'`` check. It now uses the structured
results from ``pull_device_paths`` and warns on partial/failed downloads.
"""

import os
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ui.device_file_controller import DeviceFileController


def _result(remote_path, success):
    return {'remote_path': remote_path, 'success': success, 'output': 'x'}


class DownloadSuccessTests(unittest.TestCase):
    def test_failed_download_paths_uses_success_flag(self):
        results = [_result('/a', True), _result('/b', False)]
        self.assertEqual(
            DeviceFileController._failed_download_paths(['/a', '/b'], results), ['/b']
        )

    def test_failed_download_paths_treats_missing_as_failed(self):
        # Legacy/empty results -> everything is considered failed (never over-report).
        self.assertEqual(
            DeviceFileController._failed_download_paths(['/a', '/b'], []), ['/a', '/b']
        )

    def _stub(self, current_path=None):
        window = SimpleNamespace(
            show_info=MagicMock(),
            show_warning=MagicMock(),
            refresh_device_file_browser=MagicMock(),
        )
        return SimpleNamespace(
            current_serial='S',
            current_path=current_path,
            _set_status=MagicMock(),
            _failed_download_paths=DeviceFileController._failed_download_paths,
            window=window,
        )

    def test_all_success_shows_info(self):
        stub = self._stub()
        DeviceFileController.on_download_completed(
            stub, 'S', '/out', ['/a', '/b'], [_result('/a', True), _result('/b', True)]
        )
        stub.window.show_info.assert_called_once()
        stub.window.show_warning.assert_not_called()

    def test_partial_failure_shows_warning(self):
        stub = self._stub()
        DeviceFileController.on_download_completed(
            stub, 'S', '/out', ['/a', '/b'], [_result('/a', True), _result('/b', False)]
        )
        stub.window.show_warning.assert_called_once()
        stub.window.show_info.assert_not_called()
        # The failed path is surfaced to the user.
        _, message = stub.window.show_warning.call_args[0]
        self.assertIn('/b', message)

    def test_ignores_stale_serial(self):
        stub = self._stub()
        DeviceFileController.on_download_completed(
            stub, 'OTHER', '/out', ['/a'], [_result('/a', True)]
        )
        stub.window.show_info.assert_not_called()
        stub.window.show_warning.assert_not_called()


if __name__ == '__main__':
    unittest.main()
