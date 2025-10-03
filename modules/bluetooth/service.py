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
        snapshot_interval_s: float = 2.0,
        parser: Optional[BluetoothParser] = None,
        state_machine: Optional[BluetoothStateMachine] = None,
    ) -> None:
        super().__init__()
        self._serial = serial
        self._snapshot_runner = snapshot_runner
        self._logcat_runner = logcat_runner
        self._snapshot_interval_s = snapshot_interval_s
        self._parser = parser or BluetoothParser()
        self._state_machine = state_machine or BluetoothStateMachine()

        self._stop_event = threading.Event()
        self._threads: List[threading.Thread] = []

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
                    snapshot = self._parser.parse_snapshot(self._serial, raw_snapshot, timestamp=start_ts)
                    self.snapshot_parsed.emit(snapshot)
                    update = self._state_machine.apply_snapshot(snapshot)
                    self._emit_state(update)
            except Exception as exc:  # pragma: no cover - safety net
                logger.error('Snapshot loop failure: %s', exc)
                self.error_occurred.emit(f'Snapshot collector error: {exc}')

            remaining = self._snapshot_interval_s - (time.time() - start_ts)
            if remaining > 0:
                self._stop_event.wait(remaining)

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
