import os
import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from PyQt6.QtWidgets import QApplication

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ui.logcat_viewer import LogcatWindow, PerformanceSettingsDialog, PERFORMANCE_PRESETS


class _DummyDevice:
    """Lightweight stand-in for adb_models.DeviceInfo used in tests."""

    def __init__(self):
        self.device_model = 'TestDevice'
        self.device_serial_num = 'TESTSERIAL'


class LogcatWindowLimitLinesTest(unittest.TestCase):
    """Tests for log trimming behaviour in LogcatWindow."""

    @classmethod
    def setUpClass(cls):
        os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.window = LogcatWindow(_DummyDevice())
        self.window.max_lines = 5

    def tearDown(self):
        self.window.close()

    def test_limit_log_lines_retains_recent_entries(self):
        """Ensure older log entries are discarded while recent ones remain."""
        logs = [f'line {idx}' for idx in range(10)]
        self.window.log_display.setPlainText('\n'.join(logs))

        self.window.limit_log_lines()

        remaining = [line for line in self.window.log_display.toPlainText().splitlines() if line]

        self.assertEqual(len(remaining), self.window.max_lines)
        self.assertEqual(remaining[0], 'line 5')
        self.assertEqual(remaining[-1], 'line 9')

    def test_stop_logcat_resets_process_state(self):
        """Stopping logcat should clean up process and reset UI state."""
        fake_process = Mock()
        self.window.logcat_process = fake_process
        self.window.is_running = True
        self.window.log_buffer = ['old']
        self.window.raw_logs = ['line 1']
        self.window.update_timer = Mock()
        self.window.start_btn.setEnabled(False)
        self.window.stop_btn.setEnabled(True)

        self.window.stop_logcat()

        fake_process.kill.assert_called_once()
        fake_process.waitForFinished.assert_called_once()
        self.window.update_timer.stop.assert_called_once()
        self.assertFalse(self.window.is_running)
        self.assertIsNone(self.window.logcat_process)
        self.assertEqual(self.window.log_buffer, [])
        self.assertTrue(self.window.start_btn.isEnabled())
        self.assertFalse(self.window.stop_btn.isEnabled())


class FakeSignal:
    """Minimal signal stub for intercepting connections in tests."""

    def __init__(self):
        self.callback = None

    def connect(self, callback):
        self.callback = callback


class FakeProcess:
    """Stand-in for QProcess capturing start parameters."""

    def __init__(self):
        self.readyReadStandardOutput = FakeSignal()
        self.finished = FakeSignal()
        self.program = None
        self.arguments = None
        self.killed = False
        self.wait_finished_called = False
        self.deleted = False

    def start(self, program, arguments):
        self.program = program
        self.arguments = arguments

    def waitForStarted(self):
        return True

    def kill(self):
        self.killed = True

    def waitForFinished(self, msec):
        self.wait_finished_called = True

    def deleteLater(self):
        self.deleted = True


class LogcatWindowStartCommandTest(unittest.TestCase):
    """Tests around building the logcat start command."""

    @classmethod
    def setUpClass(cls):
        os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.window = LogcatWindow(_DummyDevice())

    def tearDown(self):
        self.window.close()

    def test_all_log_levels_selected_by_default(self):
        """Every log level checkbox should be on initially."""
        checked_levels = [level for level, checkbox in self.window.log_levels.items() if checkbox.isChecked()]
        self.assertEqual(checked_levels, ['V', 'D', 'I', 'W', 'E', 'F'])

    @patch('ui.logcat_viewer.QProcess', new=FakeProcess)
    def test_start_logcat_uses_all_levels(self):
        """Starting logcat should include all level filters when none are deselected."""
        self.window.start_logcat()

        fake_process = self.window.logcat_process
        self.assertIsNotNone(fake_process)
        self.assertEqual(fake_process.program, 'adb')

        self.assertEqual(
            fake_process.arguments,
            ['-s', 'TESTSERIAL', 'logcat', '-v', 'threadtime', '*:V']
        )

    @patch('ui.logcat_viewer.QProcess', new=FakeProcess)
    def test_start_logcat_applies_tag_filter(self):
        """Tag filters should translate into TAG:LEVEL specs with silence."""
        self.window.log_source_mode.setCurrentText('Tag')
        self.window.log_source_input.setText('MyTag')
        # Exclude Verbose so we can verify the level resolution logic
        self.window.log_levels['V'].setChecked(False)

        self.window.start_logcat()

        args = self.window.logcat_process.arguments
        self.assertIn('MyTag:D', args)
        self.assertIn('*:S', args)

    @patch('ui.logcat_viewer.adb_tools.get_package_pids', return_value=['123', '456'])
    @patch('ui.logcat_viewer.QProcess', new=FakeProcess)
    def test_start_logcat_applies_package_filter(self, mock_get_pids):
        """Package filters should resolve to --pid arguments plus level filters."""
        self.window.log_source_mode.setCurrentText('Package')
        self.window.log_source_input.setText('com.example.app')

        self.window.start_logcat()

        args = self.window.logcat_process.arguments
        self.assertTrue(mock_get_pids.called)
        self.assertEqual(
            [args[idx + 1] for idx, value in enumerate(args) if value == '--pid'],
            ['123', '456']
        )
        self.assertEqual(args[-1], '*:V')

    @patch('ui.logcat_viewer.adb_tools.get_package_pids', return_value=[])
    @patch('ui.logcat_viewer.QProcess', new=FakeProcess)
    def test_start_logcat_package_filter_requires_running_process(self, mock_get_pids):
        """Starting logcat with a package filter should validate pid resolution."""
        self.window.log_source_mode.setCurrentText('Package')
        self.window.log_source_input.setText('missing.app')
        self.window.show_error = Mock()

        self.window.start_logcat()

        self.window.show_error.assert_called_once()
        self.assertFalse(self.window.is_running)
        self.assertIsNone(self.window.logcat_process)

    def test_live_and_saved_filters_combine(self):
        """Live filter input should combine with active saved filters."""
        self.window.raw_logs = [
            'alpha event ready',
            'beta event ready',
            'alpha beta combined'
        ]

        self.window.add_active_filter('AlphaFilter', 'alpha')
        self.window.apply_live_filter('beta')

        self.assertEqual(self.window.filtered_logs, ['alpha beta combined'])

        # Removing the active filter should update list and results
        self.window.active_filters_list.setCurrentRow(0)
        self.window.remove_selected_active_filters()
        self.assertFalse(self.window.active_filters)

        self.assertEqual(
            self.window.filtered_logs,
            ['beta event ready', 'alpha beta combined']
        )


class PerformanceSettingsDialogTest(unittest.TestCase):
    """Verify performance settings dialog interactions."""

    @classmethod
    def setUpClass(cls):
        os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.window = LogcatWindow(_DummyDevice())

    def tearDown(self):
        self.window.close()

    def test_apply_custom_settings_updates_window(self):
        """Applying settings should update window attributes and trim buffers."""
        self.window.raw_logs = [f'line {idx}' for idx in range(5000)]
        self.window.add_active_filter('contains-1', '1')

        dialog = PerformanceSettingsDialog(self.window)
        dialog.max_lines_spin.setValue(400)
        dialog.history_multiplier_spin.setValue(6)
        dialog.update_interval_spin.setValue(180)
        dialog.lines_per_update_spin.setValue(40)
        dialog.buffer_size_spin.setValue(90)

        dialog.apply_settings()

        self.assertEqual(self.window.max_lines, 400)
        self.assertEqual(self.window.history_multiplier, 6)
        self.assertEqual(self.window.update_interval_ms, 180)
        self.assertEqual(self.window.max_lines_per_update, 40)
        self.assertEqual(self.window.max_buffer_size, 90)

        capacity = self.window.max_lines * self.window.history_multiplier
        self.assertLessEqual(len(self.window.raw_logs), capacity)
        self.assertLessEqual(len(self.window.filtered_logs), capacity)

    def test_selecting_preset_updates_controls(self):
        """Preset selection should populate spin boxes with preset values."""
        dialog = PerformanceSettingsDialog(self.window)
        dialog.preset_combo.setCurrentText('Extended history')

        preset = PERFORMANCE_PRESETS['Extended history']
        self.assertEqual(dialog.max_lines_spin.value(), preset['max_lines'])
        self.assertEqual(dialog.history_multiplier_spin.value(), preset['history_multiplier'])
        self.assertEqual(dialog.update_interval_spin.value(), preset['update_interval_ms'])
        self.assertEqual(dialog.lines_per_update_spin.value(), preset['lines_per_update'])
        self.assertEqual(dialog.buffer_size_spin.value(), preset['max_buffer_size'])


if __name__ == '__main__':
    unittest.main()
