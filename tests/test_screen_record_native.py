import unittest
from unittest.mock import patch

from utils import adb_tools, native_bridge


class ScreenRecordingNativeTests(unittest.TestCase):
    def setUp(self) -> None:
        adb_tools._active_recordings.clear()

    def tearDown(self) -> None:
        adb_tools._active_recordings.clear()

    def test_start_screen_record_prefers_native_runner(self) -> None:
        with patch('utils.native_bridge.is_available', return_value=True), \
             patch('utils.native_bridge.start_screen_record') as mock_start, \
             patch('utils.adb_tools._verify_recording_started', return_value=True), \
             patch('utils.adb_tools.start_to_record_android_devices') as mock_fallback:
            adb_tools.start_screen_record_device('SERIAL123', '/tmp/out', 'clip001.mp4')

        expected_remote = '/sdcard/screenrecord_SERIAL123_clip001.mp4'
        mock_start.assert_called_once_with('SERIAL123', expected_remote)
        mock_fallback.assert_not_called()
        self.assertIn('SERIAL123', adb_tools._active_recordings)
        self.assertTrue(adb_tools._active_recordings['SERIAL123'].get('native'))

    def test_start_screen_record_falls_back_on_native_failure(self) -> None:
        with patch('utils.native_bridge.is_available', return_value=True), \
             patch('utils.native_bridge.start_screen_record', side_effect=native_bridge.NativeBridgeError('boom')), \
             patch('utils.adb_tools._verify_recording_started', return_value=True), \
             patch('utils.adb_tools.start_to_record_android_devices') as mock_fallback:
            adb_tools.start_screen_record_device('SERIAL999', '/tmp/out', 'clip002.mp4')

        mock_fallback.assert_called_once()
        self.assertIn('SERIAL999', adb_tools._active_recordings)
        self.assertFalse(adb_tools._active_recordings['SERIAL999'].get('native'))

    def test_stop_screen_record_uses_native_handle(self) -> None:
        adb_tools._active_recordings['SER555'] = {
            'filename': 'clip003.mp4',
            'output_path': '/tmp/out',
            'native': True,
        }

        with patch('utils.native_bridge.is_available', return_value=True), \
             patch('utils.native_bridge.stop_screen_record') as mock_stop, \
             patch('utils.adb_tools.stop_to_screen_record_android_device') as mock_stop_fallback:
            adb_tools.stop_screen_record_device('SER555')

        mock_stop.assert_called_once_with('SER555')
        mock_stop_fallback.assert_called_once()


if __name__ == '__main__':
    unittest.main()
