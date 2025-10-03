"""State machine for consolidating Bluetooth activity signals."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional, Set

from .models import (
    AdvertisingState,
    BluetoothEventType,
    BluetoothState,
    ParsedEvent,
    ParsedSnapshot,
    ScanningState,
    StateSummary,
)


@dataclass
class StateUpdate:
    """Return payload for state machine transitions."""

    summary: StateSummary
    changed: bool


class BluetoothStateMachine:
    """Combines snapshot and event feeds into a debounced state summary."""

    def __init__(
        self,
        advertising_timeout_s: float = 3.0,
        scanning_timeout_s: float = 3.0,
    ) -> None:
        self._serial: Optional[str] = None
        self._adapter_enabled: bool = True
        self._advertising_active: bool = False
        self._scanning_active: bool = False
        self._connected_active: bool = False

        self._advertising_snapshot: AdvertisingState = AdvertisingState()
        self._scanning_snapshot: ScanningState = ScanningState()
        self._profiles: Dict[str, str] = {}

        self._advertising_timeout_s = advertising_timeout_s
        self._scanning_timeout_s = scanning_timeout_s

        self._last_advertising_seen: Optional[float] = None
        self._last_scanning_seen: Optional[float] = None
        self._last_timestamp: float = 0.0

        self._current_summary = StateSummary(
            serial='unknown',
            active_states={BluetoothState.UNKNOWN},
            metrics={},
            timestamp=0.0,
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def apply_snapshot(self, snapshot: ParsedSnapshot) -> StateUpdate:
        self._ensure_serial(snapshot.serial)

        self._adapter_enabled = snapshot.adapter_enabled
        self._advertising_snapshot = snapshot.advertising
        self._scanning_snapshot = snapshot.scanning
        self._profiles = snapshot.profiles
        self._last_timestamp = snapshot.timestamp

        if snapshot.advertising.is_advertising:
            self._advertising_active = True
            self._last_advertising_seen = snapshot.timestamp
        else:
            self._advertising_active = False

        if snapshot.scanning.is_scanning:
            self._scanning_active = True
            self._last_scanning_seen = snapshot.timestamp
        else:
            self._scanning_active = False

        self._apply_timeouts(snapshot.timestamp)
        return self._emit_summary(snapshot.timestamp)

    def apply_event(self, event: ParsedEvent) -> StateUpdate:
        if event is None:
            return self._emit_summary(self._last_timestamp)

        self._ensure_serial(event.serial)
        self._last_timestamp = event.timestamp

        if event.event_type == BluetoothEventType.ADVERTISING_START:
            self._advertising_active = True
            self._last_advertising_seen = event.timestamp
        elif event.event_type == BluetoothEventType.ADVERTISING_STOP:
            self._advertising_active = False
        elif event.event_type == BluetoothEventType.SCAN_START:
            self._scanning_active = True
            self._last_scanning_seen = event.timestamp
        elif event.event_type == BluetoothEventType.SCAN_STOP:
            self._scanning_active = False
        elif event.event_type == BluetoothEventType.CONNECT:
            self._connected_active = True
        elif event.event_type == BluetoothEventType.DISCONNECT:
            self._connected_active = False

        self._apply_timeouts(event.timestamp)
        return self._emit_summary(event.timestamp)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _ensure_serial(self, serial: str) -> None:
        if self._serial is None:
            self._serial = serial
            self._current_summary = StateSummary(
                serial=serial,
                active_states={BluetoothState.UNKNOWN},
                metrics={},
                timestamp=0.0,
            )

    def _apply_timeouts(self, timestamp: float) -> None:
        if self._advertising_active and self._advertising_timeout_s is not None:
            if self._last_advertising_seen is not None:
                elapsed = timestamp - self._last_advertising_seen
                if elapsed > self._advertising_timeout_s:
                    self._advertising_active = False

        if self._scanning_active and self._scanning_timeout_s is not None:
            if self._last_scanning_seen is not None:
                elapsed = timestamp - self._last_scanning_seen
                if elapsed > self._scanning_timeout_s:
                    self._scanning_active = False

    def _emit_summary(self, timestamp: float) -> StateUpdate:
        states = self._calculate_states()
        metrics = self._calculate_metrics()

        summary = StateSummary(
            serial=self._serial or self._current_summary.serial,
            active_states=states,
            metrics=metrics,
            timestamp=timestamp,
        )

        changed = self._state_changed(summary)
        if changed:
            self._current_summary = summary
        else:
            # Preserve latest timestamp even if nothing else changed
            self._current_summary = StateSummary(
                serial=summary.serial,
                active_states=self._current_summary.active_states,
                metrics=self._current_summary.metrics,
                timestamp=summary.timestamp,
            )
        return StateUpdate(summary=self._current_summary, changed=changed)

    def _calculate_states(self) -> Set[BluetoothState]:
        if not self._adapter_enabled:
            return {BluetoothState.OFF}

        states: Set[BluetoothState] = set()
        if self._advertising_active:
            states.add(BluetoothState.ADVERTISING)
        if self._scanning_active:
            states.add(BluetoothState.SCANNING)
        if self._connected_active or self._has_connected_profile():
            states.add(BluetoothState.CONNECTED)

        if not states:
            states.add(BluetoothState.IDLE)
        return states

    def _has_connected_profile(self) -> bool:
        for state in self._profiles.values():
            if 'CONNECTED' in state.upper() and 'DISCONNECTED' not in state.upper():
                return True
        return False

    def _calculate_metrics(self) -> Dict[str, object]:
        advertising_sets = len(self._advertising_snapshot.sets) if self._advertising_snapshot.sets else 0
        scanners = len(self._scanning_snapshot.clients) if self._scanning_snapshot.clients else 0

        metrics: Dict[str, object] = {
            'adapter_enabled': self._adapter_enabled,
            'advertising_sets': advertising_sets,
            'scanners': scanners,
        }
        if self._profiles:
            metrics['profiles'] = dict(self._profiles)
        if self._last_advertising_seen is not None:
            metrics['last_advertising_seen'] = self._last_advertising_seen
        if self._last_scanning_seen is not None:
            metrics['last_scanning_seen'] = self._last_scanning_seen
        return metrics

    def _state_changed(self, summary: StateSummary) -> bool:
        if self._current_summary.active_states != summary.active_states:
            return True
        if self._current_summary.metrics != summary.metrics:
            return True
        return False

