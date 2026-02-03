import os
import sys
import time
import unittest
from pathlib import Path
from unittest.mock import Mock, patch, ANY

from PyQt6.QtWidgets import QApplication, QPlainTextEdit
from PyQt6.QtCore import Qt

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ui.logcat_viewer import (
    LogLine,
    LogcatListModel,
    LogcatFilterProxyModel,
    LogcatWindow,
    PerformanceSettingsDialog,
    PERFORMANCE_PRESETS,
)


class _DummyDevice:
    """Lightweight stand-in for adb_models.DeviceInfo used in tests."""

    def __init__(self):
        self.device_model = 'TestDevice'
        self.device_serial_num = 'TESTSERIAL'


class LogLineParsingTest(unittest.TestCase):
    """Validate threadtime parsing and graceful fallbacks."""

    def test_threadtime_line_is_parsed(self):
        raw = '09-25 12:34:56.789  123  456 D MyTag: Something happened'
        line = LogLine.from_string(raw)

        self.assertEqual(line.timestamp, '09-25 12:34:56.789')
        self.assertEqual(line.pid, '123')
        self.assertEqual(line.tid, '456')
        self.assertEqual(line.level, 'D')
        self.assertEqual(line.tag, 'MyTag')
        self.assertEqual(line.message, 'Something happened')
        self.assertEqual(line.raw, raw)

    def test_unstructured_line_defaults_to_info(self):
        raw = 'completely unstructured line that should pass through'
        line = LogLine.from_string(raw)

        self.assertEqual(line.level, 'I')
        self.assertEqual(line.tag, 'Logcat')
        self.assertEqual(line.message, raw)
        self.assertEqual(line.raw, raw)


class LogcatListModelTest(unittest.TestCase):
    """Ensure the custom list model stores and trims log lines correctly."""

    def setUp(self):
        self.model = LogcatListModel()
        self.lines = [
            LogLine(
                timestamp=f'09-25 00:00:0{idx}.000',
                pid=str(idx),
                tid=str(idx),
                level='I',
                tag='Tag',
                message=f'message {idx}',
                raw=f'line {idx}'
            )
            for idx in range(5)
        ]

    def test_append_lines_exposes_raw_and_object(self):
        self.model.append_lines(self.lines)

        self.assertEqual(self.model.rowCount(), len(self.lines))
        index = self.model.index(0)
        self.assertEqual(self.model.data(index, Qt.ItemDataRole.DisplayRole), 'line 0')
        stored = self.model.data(index, Qt.ItemDataRole.UserRole)
        self.assertIsInstance(stored, LogLine)
        self.assertEqual(stored.raw, 'line 0')

    def test_trim_discards_oldest_entries_first(self):
        self.model.append_lines(self.lines)
        self.model.trim(2)

        self.assertEqual(self.model.rowCount(), 2)
        index = self.model.index(0)
        self.assertEqual(self.model.data(index, Qt.ItemDataRole.DisplayRole), 'line 3')


class LogcatFilterProxyModelTest(unittest.TestCase):
    """Verify regex-based filtering with live and saved filters."""

    def setUp(self):
        self.model = LogcatListModel()
        self.proxy = LogcatFilterProxyModel()
        self.proxy.setSourceModel(self.model)

        lines = [
            LogLine(timestamp='', pid='', tid='', level='I', tag='Alpha', message='alpha event', raw='alpha event ready'),
            LogLine(timestamp='', pid='', tid='', level='W', tag='Beta', message='beta warning', raw='beta warning happened'),
            LogLine(timestamp='', pid='', tid='', level='E', tag='Gamma', message='gamma failure', raw='gamma failure detected'),
        ]
        self.model.append_lines(lines)

    def test_live_pattern_filters_case_insensitively(self):
        self.proxy.set_live_pattern('ALPHA')
        self.proxy.invalidateFilter()

        self.assertEqual(self.proxy.rowCount(), 1)
        index = self.proxy.index(0, 0)
        line = self.proxy.data(index, Qt.ItemDataRole.UserRole)
        self.assertEqual(line.tag, 'Alpha')

    def test_combined_patterns_match_union(self):
        self.proxy.set_live_pattern('warning')
        self.proxy.set_saved_patterns(['alpha', 'does_not_match'])
        self.proxy.invalidateFilter()

        results = [
            self.proxy.data(self.proxy.index(row, 0), Qt.ItemDataRole.DisplayRole)
            for row in range(self.proxy.rowCount())
        ]
        self.assertIn('alpha event ready', results)
        self.assertIn('beta warning happened', results)
        self.assertEqual(len(results), 2)

    def test_invalid_regex_is_ignored(self):
        self.proxy.set_live_pattern('[')
        self.proxy.invalidateFilter()

        self.assertEqual(self.proxy.rowCount(), 3)


class LogcatWindowBehaviourTest(unittest.TestCase):
    """Integration-level checks for the logcat window."""

    @classmethod
    def setUpClass(cls):
        os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.window = LogcatWindow(_DummyDevice())
        self.window.max_lines = 5

    def tearDown(self):
        self.window.close()

    def _emit_stream_batch(self, lines):
        """Simulate a background worker batch arriving in the UI thread."""
        from ui.logcat_viewer import _filter_log_lines_snapshot

        matched = []
        if self.window._has_active_filters():
            patterns = []
            if self.window.live_filter_pattern:
                patterns.append(self.window.live_filter_pattern)
            patterns.extend(self.window.active_filters)
            matched = _filter_log_lines_snapshot(lines, patterns, capacity=len(lines))

        self.window._on_stream_batch_ready(lines, matched, self.window._filter_revision)
        QApplication.processEvents()

    def _wait_for(self, predicate, *, timeout_s=5.0):
        start = time.time()
        while time.time() - start < timeout_s:
            QApplication.processEvents()
            if predicate():
                return
            time.sleep(0.01)
        raise AssertionError('Condition not met within timeout')

    def test_log_display_is_plain_text_edit(self):
        self.assertIsInstance(self.window.log_display, QPlainTextEdit)

    def test_limit_log_lines_trims_model(self):
        self.window.history_multiplier = 1
        lines = [
            LogLine(timestamp='', pid='', tid='', level='I', tag='Tag', message=f'msg {idx}', raw=f'line {idx}')
            for idx in range(10)
        ]
        self.window.log_model.append_lines(lines)
        self.window.limit_log_lines()

        self.assertEqual(self.window.log_model.rowCount(), self.window.max_lines)
        first_visible = self.window.log_model.data(self.window.log_model.index(0), Qt.ItemDataRole.DisplayRole)
        self.assertEqual(first_visible, 'line 5')

    def test_live_and_saved_filters_feed_proxy(self):
        lines = [
            LogLine(timestamp='', pid='', tid='', level='I', tag='Alpha', message='alpha ready', raw='alpha event ready'),
            LogLine(timestamp='', pid='', tid='', level='I', tag='Beta', message='beta ready', raw='beta event ready'),
            LogLine(timestamp='', pid='', tid='', level='I', tag='Gamma', message='gamma ready', raw='gamma event ready'),
        ]
        self.window.log_model.append_lines(lines)

        # Use the FilterPanelWidget public API
        filter_panel = self.window._filter_panel_widget

        # Add active pattern through public method
        filter_panel.add_active_pattern('alpha')

        # Set live filter through filter panel
        filter_panel.set_live_filter('beta')

        self._wait_for(lambda: self.window.filtered_model.rowCount() == 2)
        results = [
            self.window.filtered_model.data(self.window.filtered_model.index(row, 0), Qt.ItemDataRole.DisplayRole)
            for row in range(self.window.filtered_model.rowCount())
        ]
        self.assertEqual(results, ['alpha event ready', 'beta event ready'])

        # Removing the active filter should shrink the proxy results
        filter_panel.remove_active_pattern('alpha')

        self._wait_for(lambda: self.window.filtered_model.rowCount() == 1)
        results = [
            self.window.filtered_model.data(self.window.filtered_model.index(row, 0), Qt.ItemDataRole.DisplayRole)
            for row in range(self.window.filtered_model.rowCount())
        ]
        self.assertEqual(results, ['beta event ready'])

    def test_persisted_settings_apply_on_init(self):
        settings = {
            'max_lines': 2048,
            'history_multiplier': 9,
            'update_interval_ms': 180,
            'max_lines_per_update': 120,
            'max_buffer_size': 220,
        }

        window = LogcatWindow(_DummyDevice(), settings=settings)
        try:
            self.assertEqual(window.max_lines, 2048)
            self.assertEqual(window.history_multiplier, 9)
            self.assertEqual(window.update_interval_ms, 180)
            self.assertEqual(window.max_lines_per_update, 120)
            self.assertEqual(window.max_buffer_size, 220)
            self.assertEqual(window.log_proxy._visible_limit, 2048)
        finally:
            window.close()

    def test_performance_settings_updates_notify_callback(self):
        captured = {}

        def record(settings):
            captured.update(settings)

        window = LogcatWindow(_DummyDevice(), on_settings_changed=record)
        try:
            window.max_lines = 1500
            window.history_multiplier = 6
            window.update_interval_ms = 175
            window.max_lines_per_update = 90
            window.max_buffer_size = 180

            window.on_performance_settings_updated()

            self.assertEqual(captured,
                             {
                                 'max_lines': 1500,
                                 'history_multiplier': 6,
                                 'update_interval_ms': 175,
                                 'max_lines_per_update': 90,
                                 'max_buffer_size': 180,
                             })
        finally:
            window.close()

    def test_filtered_history_retains_until_capacity(self):
        self.window.max_lines = 3
        self.window.history_multiplier = 1

        matching_lines = [
            LogLine.from_string(f'09-30 12:00:0{i}.000  123  456 I Tag: match {i}')
            for i in range(3)
        ]
        self._emit_stream_batch(matching_lines)

        self.window.apply_live_filter('match')
        self._wait_for(lambda: self.window.filtered_model.rowCount() == 3)

        for i in range(20):
            self._emit_stream_batch([
                LogLine.from_string(f'09-30 12:01:{i:02d}.000  123  456 I Tag: other {i}')
            ])

        visible = [
            self.window.filtered_model.data(
                self.window.filtered_model.index(row, 0),
                Qt.ItemDataRole.DisplayRole,
            )
            for row in range(self.window.filtered_model.rowCount())
        ]
        self.assertEqual(
            visible,
            [line.raw for line in matching_lines],
        )

        for i in range(3):
            self._emit_stream_batch([
                LogLine.from_string(f'09-30 12:02:0{i}.000  123  456 I Tag: match-new {i}')
            ])

        self._wait_for(lambda: self.window.filtered_model.rowCount() == 3)
        latest = [
            self.window.filtered_model.data(
                self.window.filtered_model.index(row, 0),
                Qt.ItemDataRole.DisplayRole,
            )
            for row in range(self.window.filtered_model.rowCount())
        ]
        self.assertEqual(
            latest,
            [
                '09-30 12:02:00.000  123  456 I Tag: match-new 0',
                '09-30 12:02:01.000  123  456 I Tag: match-new 1',
                '09-30 12:02:02.000  123  456 I Tag: match-new 2',
            ],
        )

    def test_clearing_logs_does_not_disable_live_filters(self):
        initial_lines = [
            LogLine.from_string(f'09-30 12:10:0{i}.000  123  456 I Tag: match {i}')
            for i in range(2)
        ]
        self._emit_stream_batch(initial_lines)

        self.window.apply_live_filter('match')
        self._wait_for(lambda: self.window.filtered_model.rowCount() == 2)

        self.window.clear_logs()
        self.assertTrue(self.window._has_active_filters())
        self.assertEqual(self.window.log_model.rowCount(), 0)

        self._emit_stream_batch([
            LogLine.from_string('09-30 12:11:00.000  123  456 I Tag: match new')
        ])

        visible_text = self.window.log_display.toPlainText()
        self.assertIn('match new', visible_text)

    def test_scroll_up_disables_auto_follow_and_preserves_position(self):
        self.window.max_lines = 200
        seed_lines = [
            LogLine.from_string(f'09-30 12:20:{i:02d}.000  123  456 I Tag: seed {i}')
            for i in range(120)
        ]
        self._emit_stream_batch(seed_lines)

        scroll_bar = self.window.log_display.verticalScrollBar()
        self.window._scroll_to_bottom()
        initial_max = scroll_bar.maximum()
        self.assertGreater(initial_max, 0)

        scroll_bar.setValue(scroll_bar.minimum())
        self.assertFalse(self.window._auto_scroll_enabled)
        self.assertFalse(self.window.follow_latest_checkbox.isChecked())
        position_before = scroll_bar.value()

        self._emit_stream_batch([
            LogLine.from_string('09-30 12:21:00.000  123  456 I Tag: latest new')
        ])

        self.assertEqual(scroll_bar.value(), position_before)
        self.assertLess(scroll_bar.value(), scroll_bar.maximum())

    def test_scrolling_back_to_bottom_resumes_auto_follow(self):
        self.window.max_lines = 200
        seed_lines = [
            LogLine.from_string(f'09-30 12:30:{i:02d}.000  123  456 I Tag: follow {i}')
            for i in range(400)
        ]
        self._emit_stream_batch(seed_lines)

        scroll_bar = self.window.log_display.verticalScrollBar()
        self.window._scroll_to_bottom()
        self.assertGreater(scroll_bar.maximum(), 0)
        self.window.set_auto_scroll_enabled(False, from_scroll=True)
        scroll_bar.setValue(scroll_bar.minimum())
        self.assertFalse(self.window._auto_scroll_enabled)

        scroll_bar.setValue(scroll_bar.maximum())
        self.assertTrue(self.window._auto_scroll_enabled)
        self.assertTrue(self.window.follow_latest_checkbox.isChecked())

        self._emit_stream_batch([
            LogLine.from_string('09-30 12:31:00.000  123  456 I Tag: follow latest')
        ])

        self.assertEqual(scroll_bar.value(), scroll_bar.maximum())

    def test_stop_logcat_resets_state(self):
        fake_process = Mock()
        fake_process.kill = Mock()
        fake_process.waitForFinished = Mock()
        self.window.logcat_process = fake_process
        self.window.is_running = True
        self.window.start_btn.setEnabled(False)
        self.window.stop_btn.setEnabled(True)

        self.window.stop_logcat()

        fake_process.kill.assert_called_once()
        fake_process.waitForFinished.assert_called_once()
        self.assertFalse(self.window.is_running)
        self.assertIsNone(self.window.logcat_process)
        self.assertTrue(self.window.start_btn.isEnabled())
        self.assertFalse(self.window.stop_btn.isEnabled())

    def test_partial_line_buffering_merges_chunks(self):
        from ui.logcat_viewer import _split_logcat_chunk

        lines, partial = _split_logcat_chunk('', b'First line part')
        self.assertEqual(lines, [])
        self.assertEqual(partial, 'First line part')

        lines, partial = _split_logcat_chunk(partial, b' two\nSecond line\n')
        self.assertEqual(lines, ['First line part two', 'Second line'])
        self.assertEqual(partial, '')

    def test_close_event_triggers_stop(self):
        from PyQt6.QtGui import QCloseEvent

        self.window.is_running = True
        self.window.logcat_process = Mock()

        with patch.object(self.window, 'stop_logcat') as mock_stop:
            event = QCloseEvent()
            self.window.closeEvent(event)
            mock_stop.assert_called_once_with()

    def test_window_enables_min_max_buttons(self):
        flags = self.window.windowFlags()
        self.assertTrue(flags & Qt.WindowType.WindowMaximizeButtonHint)
        self.assertTrue(flags & Qt.WindowType.WindowMinimizeButtonHint)

    @patch('ui.logcat_viewer.QApplication.clipboard')
    def test_copy_selected_logs_copies_to_clipboard(self, clipboard_factory):
        lines = [
            LogLine(timestamp='', pid='', tid='', level='I', tag='Tag', message=f'msg {idx}', raw=f'line {idx}')
            for idx in range(3)
        ]
        self.window.log_model.append_lines(lines)
        self.window._rebuild_log_display_from_model()

        cursor = self.window.log_display.textCursor()
        cursor.movePosition(cursor.MoveOperation.Start)
        cursor.movePosition(cursor.MoveOperation.EndOfBlock, cursor.MoveMode.KeepAnchor)
        self.window.log_display.setTextCursor(cursor)

        clipboard = Mock()
        clipboard_factory.return_value = clipboard

        copied_text = self.window.copy_selected_logs()

        self.assertEqual(copied_text, 'line 0')
        clipboard.setText.assert_called_once_with('line 0')

    def test_log_context_menu_has_copy_actions(self):
        menu = self.window._build_log_context_menu()
        action_texts = [action.text() for action in menu.actions()]

        self.assertIn('Copy Selected', action_texts)
        self.assertIn('Copy All', action_texts)
        self.assertIn('Select All', action_texts)

    def test_ctrl_f_shortcut_opens_floating_search_bar(self):
        """Ctrl+F should open the floating search bar and focus its input."""
        self.window.show()
        QApplication.processEvents()

        # Search bar should be hidden initially
        self.assertFalse(self.window._search_bar.isVisible())

        self.window._handle_find_shortcut()
        QApplication.processEvents()

        # After Ctrl+F, search bar should be visible
        self.assertTrue(self.window._search_bar.isVisible())
        # Focus should be on the search input
        self.assertTrue(self.window._search_bar._search_input.hasFocus())

    def test_search_finds_matching_rows(self):
        """Search should find and count matching log rows."""
        # Add some log lines
        from ui.logcat_viewer import LogLine
        lines = [
            LogLine.from_string('01-01 00:00:01.000 1 2 I TestTag: error message'),
            LogLine.from_string('01-01 00:00:02.000 1 2 I TestTag: normal message'),
            LogLine.from_string('01-01 00:00:03.000 1 2 I TestTag: another error here'),
        ]
        self.window.log_model.append_lines(lines)
        self.window._rebuild_log_display_from_model()
        QApplication.processEvents()

        # Perform search
        self.window._search_bar.set_search_text('error')
        self.window._on_search_changed('error')
        self._wait_for(lambda: len(self.window._search_match_rows) == 2)

        # Should find 2 matches
        self.assertEqual(len(self.window._search_match_rows), 2)
        self.assertIn(0, self.window._search_match_rows)  # First line
        self.assertIn(2, self.window._search_match_rows)  # Third line

    def test_search_navigation_cycles_through_matches(self):
        """F3 and Shift+F3 should cycle through matches."""
        from ui.logcat_viewer import LogLine
        lines = [
            LogLine.from_string('01-01 00:00:01.000 1 2 I Tag: findme one'),
            LogLine.from_string('01-01 00:00:02.000 1 2 I Tag: nothing here'),
            LogLine.from_string('01-01 00:00:03.000 1 2 I Tag: findme two'),
            LogLine.from_string('01-01 00:00:04.000 1 2 I Tag: findme three'),
        ]
        self.window.log_model.append_lines(lines)
        self.window._rebuild_log_display_from_model()
        QApplication.processEvents()

        # Search for "findme"
        self.window._search_bar.set_search_text('findme')
        self.window._on_search_changed('findme')
        self._wait_for(lambda: len(self.window._search_match_rows) == 3)

        # Should find 3 matches (rows 0, 2, 3)
        self.assertEqual(len(self.window._search_match_rows), 3)
        initial_index = self.window._current_match_index

        # Navigate next
        self.window._navigate_to_next_match()
        self.assertEqual(self.window._current_match_index, (initial_index + 1) % 3)

        # Navigate previous
        self.window._navigate_to_prev_match()
        self.assertEqual(self.window._current_match_index, initial_index)

    def test_search_close_clears_highlight(self):
        """Closing search bar should clear all highlights."""
        from ui.logcat_viewer import LogLine
        lines = [
            LogLine.from_string('01-01 00:00:01.000 1 2 I Tag: test line'),
        ]
        self.window.log_model.append_lines(lines)
        self.window._rebuild_log_display_from_model()
        self.window._search_bar.set_search_text('test')
        self.window._on_search_changed('test')
        self._wait_for(lambda: self.window._search_pattern is not None and len(self.window._search_match_rows) > 0)

        # Verify search is active
        self.assertIsNotNone(self.window._search_pattern)
        self.assertTrue(len(self.window._search_match_rows) > 0)

        # Close search
        self.window._on_search_closed()
        QApplication.processEvents()

        # Verify search state is cleared
        self.assertIsNone(self.window._search_pattern)
        self.assertEqual(len(self.window._search_match_rows), 0)
        self.assertEqual(self.window._current_match_index, -1)

    def test_search_delegate_receives_pattern(self):
        """Search should populate match spans for highlighting."""
        from ui.logcat_viewer import LogLine
        lines = [
            LogLine.from_string('01-01 00:00:01.000 1 2 I Tag: highlight me'),
        ]
        self.window.log_model.append_lines(lines)
        self.window._rebuild_log_display_from_model()
        QApplication.processEvents()

        self.window._search_bar.set_search_text('highlight')
        self.window._on_search_changed('highlight')
        self._wait_for(lambda: len(self.window._search_match_spans) > 0)
        self.assertTrue(any(span[0] == 0 for span in self.window._search_match_spans))


class FakeSignal:
    """Minimal signal stub for intercepting connections in tests."""

    def __init__(self):
        self.callback = None

    def connect(self, callback):
        self.callback = callback

    def emit(self, *args, **kwargs):
        if self.callback:
            self.callback(*args, **kwargs)


class FakeProcess:
    """Stand-in for QProcess capturing start parameters."""

    def __init__(self, parent=None):
        self.readyReadStandardOutput = FakeSignal()
        self.finished = FakeSignal()
        self.started = FakeSignal()
        self.errorOccurred = FakeSignal()
        self.program = None
        self.arguments = None
        self.killed = False
        self.wait_finished_called = False
        self.deleted = False
        self.waitForStarted_called = False
        self.parent = parent

    def start(self, program, arguments):
        self.program = program
        self.arguments = arguments

    def waitForStarted(self):
        self.waitForStarted_called = True
        return True

    def kill(self):
        self.killed = True

    def waitForFinished(self, _msec):
        self.wait_finished_called = True

    def deleteLater(self):
        self.deleted = True

    def setParent(self, parent):
        self.parent = parent


class LogcatWindowStartCommandTest(unittest.TestCase):
    """Ensure the logcat process is launched with proper arguments."""

    @classmethod
    def setUpClass(cls):
        os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.window = LogcatWindow(_DummyDevice())

    def tearDown(self):
        self.window.close()

    def test_all_log_levels_selected_by_default(self):
        checked_levels = [level for level, checkbox in self.window.log_levels.items() if checkbox.isChecked()]
        self.assertEqual(checked_levels, ['V', 'D', 'I', 'W', 'E', 'F'])

    @patch('ui.logcat_viewer.subprocess.run')
    @patch('ui.logcat_viewer.QProcess', new=FakeProcess)
    def test_start_logcat_uses_all_levels(self, mock_run):
        self.window.start_logcat()

        fake_process = self.window.logcat_process
        self.assertIsNotNone(fake_process)
        self.assertEqual(fake_process.program, 'adb')
        self.assertEqual(
            fake_process.arguments,
            ['-s', 'TESTSERIAL', 'logcat', '-v', 'threadtime', '*:V']
        )
        self.assertFalse(fake_process.waitForStarted_called)
        mock_run.assert_called_once_with(
            ['adb', '-s', 'TESTSERIAL', 'logcat', '-c'],
            check=False,
            stdout=ANY,
            stderr=ANY,
        )

    @patch('ui.logcat_viewer.subprocess.run')
    @patch('ui.logcat_viewer.QProcess', new=FakeProcess)
    def test_start_logcat_applies_tag_filter(self, mock_run):
        self.window.log_source_mode.setCurrentText('Tag')
        self.window.log_source_input.setText('MyTag')
        self.window.log_levels['V'].setChecked(False)

        self.window.start_logcat()

        args = self.window.logcat_process.arguments
        self.assertIn('MyTag:D', args)
        self.assertIn('*:S', args)
        self.assertFalse(self.window.logcat_process.waitForStarted_called)
        mock_run.assert_called_once_with(
            ['adb', '-s', 'TESTSERIAL', 'logcat', '-c'],
            check=False,
            stdout=ANY,
            stderr=ANY,
        )

    @patch('ui.logcat_viewer.subprocess.run')
    @patch('ui.logcat_viewer.adb_tools.get_package_pids', return_value=['123', '456'])
    @patch('ui.logcat_viewer.QProcess', new=FakeProcess)
    def test_start_logcat_applies_package_filter(self, mock_get_pids, mock_run):
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
        self.assertFalse(self.window.logcat_process.waitForStarted_called)
        mock_run.assert_called_once_with(
            ['adb', '-s', 'TESTSERIAL', 'logcat', '-c'],
            check=False,
            stdout=ANY,
            stderr=ANY,
        )

    @patch('ui.logcat_viewer.subprocess.run')
    @patch('ui.logcat_viewer.adb_tools.get_package_pids', return_value=[])
    @patch('ui.logcat_viewer.QProcess', new=FakeProcess)
    def test_start_logcat_package_filter_requires_running_process(self, mock_get_pids, mock_run):
        self.window.log_source_mode.setCurrentText('Package')
        self.window.log_source_input.setText('missing.app')
        self.window.show_error = Mock()

        self.window.start_logcat()

        self.window.show_error.assert_called_once()
        self.assertFalse(self.window.is_running)
        self.assertIsNone(self.window.logcat_process)
        mock_run.assert_not_called()
        # Buffer clearing should not occur when start aborts early
        # (using getattr to avoid import just for test)
        from ui import logcat_viewer
        self.assertFalse(logcat_viewer.subprocess.run.called)

    @patch('ui.logcat_viewer.subprocess.run')
    @patch('ui.logcat_viewer.QProcess', new=FakeProcess)
    def test_start_logcat_does_not_block_wait(self, mock_run):
        self.window.start_logcat()

        process = self.window.logcat_process
        self.assertIsNotNone(process)
        self.assertFalse(process.waitForStarted_called)
        mock_run.assert_called_once_with(
            ['adb', '-s', 'TESTSERIAL', 'logcat', '-c'],
            check=False,
            stdout=ANY,
            stderr=ANY,
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
        lines = [
            LogLine(timestamp='', pid='', tid='', level='I', tag='Tag', message=f'msg {idx}', raw=f'line {idx}')
            for idx in range(500)
        ]
        self.window.log_model.append_lines(lines)

        dialog = PerformanceSettingsDialog(self.window)
        dialog.max_lines_spin.setValue(400)
        dialog.history_multiplier_spin.setValue(3)
        dialog.update_interval_spin.setValue(180)
        dialog.lines_per_update_spin.setValue(40)
        dialog.buffer_size_spin.setValue(90)

        dialog.apply_settings()

        self.assertEqual(self.window.max_lines, 400)
        self.assertEqual(self.window.history_multiplier, 3)
        self.assertEqual(self.window.update_interval_ms, 180)
        self.assertEqual(self.window.max_lines_per_update, 40)
        self.assertEqual(self.window.max_buffer_size, 90)

        self.assertLessEqual(self.window.log_model.rowCount(), 1200)

    def test_selecting_preset_updates_controls(self):
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
