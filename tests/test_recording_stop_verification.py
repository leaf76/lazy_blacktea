import unittest
from unittest.mock import patch

from utils import adb_tools


class VerifyRecordingStoppedTests(unittest.TestCase):
    """Tests for adb_tools._verify_recording_stopped polling logic."""

    def setUp(self) -> None:
        sleep_patcher = patch('utils.adb_tools.time.sleep', side_effect=lambda *_args, **_kwargs: None)
        self.addCleanup(sleep_patcher.stop)
        sleep_patcher.start()

    def test_returns_true_when_only_grep_process_matches(self) -> None:
        """Should treat grep helper output as stopped and exit early."""

        def fake_run(command, *_args, **_kwargs):
            if 'screenrecord' in command and 'grep' in command:
                return ['shell         123   grep screenrecord']
            return []

        with patch('utils.adb_tools.common.run_command', side_effect=fake_run), \
             patch('utils.adb_tools._is_screenrecord_running', side_effect=[True, False]) as mock_running:
            result = adb_tools._verify_recording_stopped('SERIAL123')

        self.assertTrue(result)
        self.assertEqual(mock_running.call_count, 2)

    def test_returns_false_when_process_never_exits(self) -> None:
        """Should exhaust retries if screenrecord keeps running."""

        def fake_run(command, *_args, **_kwargs):
            if 'screenrecord' in command:
                return ['shell         321   screenrecord']
            return []

        with patch('utils.adb_tools.common.run_command', side_effect=fake_run), \
             patch('utils.adb_tools._is_screenrecord_running', return_value=True) as mock_running:
            result = adb_tools._verify_recording_stopped('SERIAL999')

        self.assertFalse(result)
        self.assertEqual(mock_running.call_count, 30)


if __name__ == '__main__':
    unittest.main()
