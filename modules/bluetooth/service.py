"""Coordinator service wiring parsers, collectors, and the state machine."""

from __future__ import annotations

import threading
import time
from typing import Callable, Iterable, List, Optional

from PyQt6.QtCore import QObject, pyqtSignal

from utils import common

from .models import ParsedEvent, ParsedSnapshot, StateSummary
from .parser import BluetoothParser
from .state_machine import BluetoothStateMachine


logger = common.get_logger('bluetooth_service')


SnapshotRunner = Callable[[], str]
LogcatRunner = Callable[[], Iterable[str]]

# Adaptive polling interval constants for Bluetooth monitoring.
# The service dynamically adjusts polling frequency based on activity:
# - When Bluetooth state changes are detected, polling speeds up to MIN_INTERVAL_S
# - After IDLE_THRESHOLD_S without changes, polling gradually slows to MAX_INTERVAL_S
# - This balances responsiveness with resource efficiency
DEFAULT_INTERVAL_S = 5.0   # Starting interval for new monitoring sessions
MIN_INTERVAL_S = 2.0       # Fastest polling when activity is detected
MAX_INTERVAL_S = 10.0      # Slowest polling after extended idle period
IDLE_THRESHOLD_S = 30.0    # Seconds without state change before slowing down


class BluetoothMonitorService(QObject):
    """Coordinates snapshot polling, log monitoring, and the state machine."""

    snapshot_parsed = pyqtSignal(ParsedSnapshot)
    event_parsed = pyqtSignal(ParsedEvent)
    state_updated = pyqtSignal(StateSummary)
    error_occurred = pyqtSignal(str)

    def __init__(
        self,
        serial: str,
        snapshot_runner: Optional[SnapshotRunner] = None,
        logcat_runner: Optional[LogcatRunner] = None,
        snapshot_interval_s: float = DEFAULT_INTERVAL_S,
        parser: Optional[BluetoothParser] = None,
        state_machine: Optional[BluetoothStateMachine] = None,
    ) -> None:
        super().__init__()
        self._serial = serial
        self._snapshot_runner = snapshot_runner
        self._logcat_runner = logcat_runner
        self._base_interval_s = snapshot_interval_s
        self._current_interval_s = snapshot_interval_s
        self._parser = parser or BluetoothParser()
        self._state_machine = state_machine or BluetoothStateMachine()

        self._stop_event = threading.Event()
        self._threads: List[threading.Thread] = []

        # Adaptive polling state
        self._last_activity_time: Optional[float] = None
        self._last_snapshot_hash: Optional[int] = None

    # ------------------------------------------------------------------
    # Lifecycle management
    # ------------------------------------------------------------------
    def start(self) -> None:
        logger.info('Starting Bluetooth monitor service for %s', self._serial)
        self._stop_event.clear()
        if self._snapshot_runner is not None:
            thread = threading.Thread(target=self._snapshot_loop, name=f'{self._serial}-snapshot', daemon=True)
            self._threads.append(thread)
            thread.start()
        if self._logcat_runner is not None:
            thread = threading.Thread(target=self._logcat_loop, name=f'{self._serial}-logcat', daemon=True)
            self._threads.append(thread)
            thread.start()

    def stop(self, wait: bool = True) -> None:
        logger.info('Stopping Bluetooth monitor service for %s', self._serial)
        self._stop_event.set()
        if wait:
            for thread in list(self._threads):
                thread.join(timeout=2.0)
        self._threads.clear()

    # ------------------------------------------------------------------
    # Loops
    # ------------------------------------------------------------------
    def _snapshot_loop(self) -> None:
        while not self._stop_event.is_set():
            start_ts = time.time()
            try:
                raw_snapshot = self._snapshot_runner()
                if raw_snapshot:
                    # Check if snapshot changed (for adaptive polling)
                    snapshot_hash = hash(raw_snapshot)
                    changed = snapshot_hash != self._last_snapshot_hash
                    self._last_snapshot_hash = snapshot_hash

                    if changed:
                        self._last_activity_time = start_ts

                    snapshot = self._parser.parse_snapshot(self._serial, raw_snapshot, timestamp=start_ts)
                    self.snapshot_parsed.emit(snapshot)
                    update = self._state_machine.apply_snapshot(snapshot)
                    self._emit_state(update)

                    # Adjust polling interval based on activity
                    self._adjust_polling_interval(start_ts)
            except Exception as exc:  # pragma: no cover - safety net
                logger.error('Snapshot loop failure: %s', exc)
                self.error_occurred.emit(f'Snapshot collector error: {exc}')

            remaining = self._current_interval_s - (time.time() - start_ts)
            if remaining > 0:
                self._stop_event.wait(remaining)

    def _adjust_polling_interval(self, current_time: float) -> None:
        """Adjust polling interval based on recent activity."""
        if self._last_activity_time is None:
            self._current_interval_s = self._base_interval_s
            return

        idle_time = current_time - self._last_activity_time
        if idle_time < IDLE_THRESHOLD_S:
            # Active: use faster polling
            self._current_interval_s = max(MIN_INTERVAL_S, self._base_interval_s)
        else:
            # Idle: gradually slow down polling
            slowdown_factor = min(2.0, 1.0 + (idle_time - IDLE_THRESHOLD_S) / 60.0)
            self._current_interval_s = min(MAX_INTERVAL_S, self._base_interval_s * slowdown_factor)

    def _logcat_loop(self) -> None:
        try:
            for line in self._logcat_runner():
                if self._stop_event.is_set():
                    break
                try:
                    event = self._parser.parse_log_line(self._serial, line)
                except Exception as exc:  # pragma: no cover - guard rails
                    logger.error('Failed to parse log line: %s', exc)
                    continue
                if not event:
                    continue
                self.event_parsed.emit(event)
                update = self._state_machine.apply_event(event)
                self._emit_state(update)
        except Exception as exc:  # pragma: no cover - guard rails
            logger.error('Logcat loop failure: %s', exc)
            self.error_occurred.emit(f'Log monitor error: {exc}')

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _emit_state(self, update) -> None:
        summary: StateSummary = update.summary if hasattr(update, 'summary') else update
        emit = True
        if hasattr(update, 'changed'):
            emit = bool(update.changed)
        if emit:
            self.state_updated.emit(summary)
