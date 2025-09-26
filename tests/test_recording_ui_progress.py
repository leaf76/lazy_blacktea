#!/usr/bin/env python3
"""Unit tests for recording progress integration in WindowMain."""

from types import SimpleNamespace
import unittest
import datetime

from lazy_blacktea_pyqt import WindowMain


class RecordingProgressUITest(unittest.TestCase):
    """Validate recording progress callbacks update UI state."""

    def setUp(self):
        self.window = WindowMain.__new__(WindowMain)
        self.window.device_recordings = {}
        self.window.device_operations = {}
        self.console_messages = []
        self.warning_messages = []
        self.status_updates = 0

        self.window.write_to_console = lambda message: self.console_messages.append(message)
        self.window.error_handler = SimpleNamespace(
            show_warning=lambda title, message: self.warning_messages.append((title, message))
        )
        self.window.update_recording_status = lambda: setattr(self, 'status_updates', self.status_updates + 1)

    def test_segment_completed_event_updates_records(self):
        event_payload = {
            'type': 'segment_completed',
            'device_serial': 'ABC123',
            'device_name': 'PixelTest',
            'segment_index': 2,
            'segment_filename': 'record_part02.mp4',
            'duration_seconds': 12.5,
            'total_duration_seconds': 25.0,
            'output_path': '/tmp/output',
        }

        self.window._on_recording_progress_event(event_payload)

        self.assertIn('ABC123', self.window.device_recordings)
        record = self.window.device_recordings['ABC123']
        self.assertTrue(record['active'])
        self.assertEqual(record['device_name'], 'PixelTest')
        self.assertEqual(record['output_path'], '/tmp/output')
        self.assertIn('Recording', self.window.device_operations.values())
        self.assertEqual(len(record['segments']), 1)
        segment = record['segments'][0]
        self.assertEqual(segment['index'], 2)
        self.assertAlmostEqual(segment['duration_seconds'], 12.5)
        self.assertAlmostEqual(segment['total_duration_seconds'], 25.0)
        self.assertEqual(record['elapsed_before_current'], 25.0)
        self.assertIsNotNone(record['ongoing_start'])
        self.assertIsInstance(record['ongoing_start'], datetime.datetime)
        self.assertEqual(record['display_seconds'], 25)
        self.assertEqual(self.status_updates, 1)
        self.assertEqual(len(self.console_messages), 1)
        self.assertEqual(self.warning_messages, [])

    def test_error_event_marks_recording_inactive(self):
        self.window.device_recordings['XYZ789'] = {
            'active': True,
            'segments': [],
            'output_path': '/tmp/output',
            'device_name': 'GalaxyTest',
            'elapsed_before_current': 10.0,
            'ongoing_start': datetime.datetime.now(),
        }
        self.window.device_operations['XYZ789'] = 'Recording'

        event_payload = {
            'type': 'error',
            'device_serial': 'XYZ789',
            'device_name': 'GalaxyTest',
            'message': 'ADB disconnected',
        }

        self.window._on_recording_progress_event(event_payload)

        record = self.window.device_recordings['XYZ789']
        self.assertFalse(record['active'])
        self.assertIsNone(record['ongoing_start'])
        self.assertEqual(record['display_seconds'], 10)
        self.assertNotIn('XYZ789', self.window.device_operations)
        self.assertEqual(self.status_updates, 1)
        self.assertEqual(len(self.warning_messages), 1)
        self.assertIn('ADB disconnected', self.warning_messages[0][1])


if __name__ == '__main__':
    unittest.main()
