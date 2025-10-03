"""Data models for the Bluetooth monitoring subsystem."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Set


class BluetoothState(Enum):
    """High-level Bluetooth activity states surfaced to the UI."""

    IDLE = 'IDLE'
    SCANNING = 'SCANNING'
    ADVERTISING = 'ADVERTISING'
    CONNECTED = 'CONNECTED'
    OFF = 'OFF'
    UNKNOWN = 'UNKNOWN'


class BluetoothEventType(Enum):
    """Canonicalised Bluetooth event types parsed from logcat."""

    ADVERTISING_START = 'BLE_ADVERTISING_START'
    ADVERTISING_STOP = 'BLE_ADVERTISING_STOP'
    SCAN_START = 'BLE_SCAN_START'
    SCAN_RESULT = 'BLE_SCAN_RESULT'
    SCAN_STOP = 'BLE_SCAN_STOP'
    CONNECT = 'BLE_CONNECT'
    DISCONNECT = 'BLE_DISCONNECT'
    ERROR = 'BLE_ERROR'


@dataclass
class AdvertisingSet:
    """Represents a single BLE advertising set."""

    set_id: Optional[int] = None
    interval_ms: Optional[int] = None
    tx_power: Optional[str] = None
    data_length: int = 0
    service_uuids: List[str] = field(default_factory=list)


@dataclass
class AdvertisingState:
    """Aggregated advertising status derived from snapshots or events."""

    is_advertising: bool = False
    sets: List[AdvertisingSet] = field(default_factory=list)


@dataclass
class ScanningState:
    """Aggregated scanning status derived from snapshots or events."""

    is_scanning: bool = False
    clients: List[str] = field(default_factory=list)


@dataclass
class ParsedSnapshot:
    """Normalised view of a `dumpsys` snapshot."""

    serial: str
    timestamp: float
    adapter_enabled: bool
    address: Optional[str] = None
    scanning: ScanningState = field(default_factory=ScanningState)
    advertising: AdvertisingState = field(default_factory=AdvertisingState)
    profiles: Dict[str, str] = field(default_factory=dict)
    raw_text: str = ''


@dataclass
class ParsedEvent:
    """Normalised Bluetooth event parsed from logcat output."""

    serial: str
    timestamp: float
    event_type: BluetoothEventType
    message: str
    tag: Optional[str] = None
    metadata: Dict[str, object] = field(default_factory=dict)
    raw_line: str = ''


@dataclass
class StateSummary:
    """State machine output representing the consolidated Bluetooth state."""

    serial: str
    active_states: Set[BluetoothState]
    metrics: Dict[str, object]
    timestamp: float

    def is_active(self, state: BluetoothState) -> bool:
        """Return whether the provided state is currently active."""
        return state in self.active_states
