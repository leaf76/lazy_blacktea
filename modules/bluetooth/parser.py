"""Parsing helpers for the Bluetooth monitoring pipeline."""

from __future__ import annotations

import re
import time
from typing import Dict, Iterable, List, Optional, Tuple

from .models import (
    AdvertisingSet,
    AdvertisingState,
    BluetoothEventType,
    ParsedEvent,
    ParsedSnapshot,
    ScanningState,
)


class BluetoothParser:
    """Transforms raw `dumpsys` output and logcat lines into structured models."""

    _RE_ADDRESS = re.compile(r'address\s*[:=]\s*([0-9A-Fa-f:]{11,})', re.IGNORECASE)
    _RE_INTERVAL = re.compile(r'interval(?:=|:)\s*(\d+)', re.IGNORECASE)
    _RE_TX_POWER = re.compile(r'tx\s*power(?:=|:)\s*([A-Za-z0-9+\-]+)', re.IGNORECASE)
    _RE_DATA_LEN = re.compile(r'data(?:Len|Length)?(?:=|:)\s*(\d+)', re.IGNORECASE)
    _RE_UUIDS = re.compile(r'uuid[s]?\s*[:=]\s*([^\r\n]+)')
    _RE_PROFILE_STATE = re.compile(
        r'^(?P<profile>[A-Za-z0-9_\- ]+?)\s*(?:state\s*[:=]|[:=])\s*(?P<state>[A-Za-z0-9_ \-]+)$',
        re.IGNORECASE,
    )
    _RE_CLIENT_UID = re.compile(r'uid\s*/([\w\./:-]+)', re.IGNORECASE)
    _RE_CLIENT = re.compile(r'client\s*=\s*([\w\./:-]+)', re.IGNORECASE)
    _RE_MESSAGE = re.compile(r'\s([A-Za-z0-9_.-]+):\s(.+)$')
    _RE_SET_ID = re.compile(r'set(?:=|\s)(\d+)')

    _SCANNING_KEYWORDS = (
        'startscan',
        'isdiscovering: true',
        'isscanning: true',
        'onbatchscanresults',
        'onscanresult',
    )
    _SCANNING_STOP_KEYWORDS = ('stopscan', 'isdiscovering: false', 'isscanning: false')

    _ADVERTISING_KEYWORDS = (
        'startadvertising',
        'onadvertisingsetstarted',
        'isadvertising: true',
    )
    _ADVERTISING_STOP_KEYWORDS = (
        'stopadvertising',
        'onadvertisingsetstopped',
        'isadvertising: false',
    )

    def parse_snapshot(
        self,
        serial: str,
        raw_text: str,
        timestamp: Optional[float] = None,
    ) -> ParsedSnapshot:
        """Parse bluetooth-related information from a dumpsys snapshot."""
        effective_ts = float(timestamp) if timestamp is not None else time.time()
        lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
        lowered = [line.lower() for line in lines]

        adapter_enabled = any('state=on' in line or 'enabled: true' in line for line in lowered)
        address = self._extract_address(lines)

        scanning_state = self._extract_scanning_state(lines, lowered)
        advertising_state = self._extract_advertising_state(lines, lowered)
        profiles = self._extract_profile_states(lines)

        return ParsedSnapshot(
            serial=serial,
            timestamp=effective_ts,
            adapter_enabled=adapter_enabled,
            address=address,
            scanning=scanning_state,
            advertising=advertising_state,
            profiles=profiles,
            raw_text=raw_text,
        )

    def parse_log_line(
        self,
        serial: str,
        line: str,
        timestamp: Optional[float] = None,
    ) -> Optional[ParsedEvent]:
        """Parse a single logcat line into a structured Bluetooth event."""
        if not line or not line.strip():
            return None

        lowered = line.lower()
        event_type = self._classify_event(lowered)
        if event_type is None:
            return None

        effective_ts = float(timestamp) if timestamp is not None else time.time()
        tag, message = self._split_tag_and_message(line)
        metadata = self._extract_metadata(lowered, message)

        return ParsedEvent(
            serial=serial,
            timestamp=effective_ts,
            event_type=event_type,
            message=message.strip(),
            tag=tag,
            metadata=metadata,
            raw_line=line,
        )

    # ------------------------------------------------------------------
    # Snapshot helpers
    # ------------------------------------------------------------------
    def _extract_address(self, lines: Iterable[str]) -> Optional[str]:
        for line in lines:
            match = self._RE_ADDRESS.search(line)
            if match:
                return match.group(1).upper()
        return None

    def _extract_scanning_state(
        self,
        lines: Iterable[str],
        lowered: Iterable[str],
    ) -> ScanningState:
        lowered_list = list(lowered)
        is_scanning = any(keyword in text for keyword in self._SCANNING_KEYWORDS for text in lowered_list)
        clients = []
        for line in lines:
            for match in self._RE_CLIENT_UID.finditer(line):
                value = f"uid/{match.group(1)}"
                if value and value not in clients:
                    clients.append(value)
            for match in self._RE_CLIENT.finditer(line):
                value = match.group(1)
                if value and value not in clients:
                    clients.append(value)
        return ScanningState(is_scanning=is_scanning, clients=clients)

    def _extract_advertising_state(
        self,
        lines: Iterable[str],
        lowered: Iterable[str],
    ) -> AdvertisingState:
        lowered_list = list(lowered)
        is_advertising = any(keyword in text for keyword in self._ADVERTISING_KEYWORDS for text in lowered_list)
        sets = [self._build_advertising_set(lines)] if is_advertising else []
        return AdvertisingState(is_advertising=is_advertising, sets=sets)

    def _build_advertising_set(self, lines: Iterable[str]) -> AdvertisingSet:
        raw_dump = '\n'.join(lines)
        interval = self._extract_int(self._RE_INTERVAL, raw_dump)
        tx_power_match = self._RE_TX_POWER.search(raw_dump)
        tx_power = tx_power_match.group(1) if tx_power_match else None
        data_len = self._extract_int(self._RE_DATA_LEN, raw_dump) or 0
        uuids = self._extract_uuids(raw_dump)

        set_id_match = self._RE_SET_ID.search(raw_dump)
        set_id = int(set_id_match.group(1)) if set_id_match else None

        return AdvertisingSet(
            set_id=set_id,
            interval_ms=interval,
            tx_power=tx_power,
            data_length=data_len,
            service_uuids=uuids,
        )

    def _extract_profile_states(self, lines: Iterable[str]) -> Dict[str, str]:
        profiles: Dict[str, str] = {}
        for line in lines:
            match = self._RE_PROFILE_STATE.search(line)
            if not match:
                continue
            profile = match.group('profile').strip().upper()
            state = match.group('state').strip().upper()
            if profile and state:
                profiles[profile] = state
        return profiles

    # ------------------------------------------------------------------
    # Event helpers
    # ------------------------------------------------------------------
    def _classify_event(self, lowered_line: str) -> Optional[BluetoothEventType]:
        if any(keyword in lowered_line for keyword in self._ADVERTISING_KEYWORDS):
            return BluetoothEventType.ADVERTISING_START
        if any(keyword in lowered_line for keyword in self._ADVERTISING_STOP_KEYWORDS):
            return BluetoothEventType.ADVERTISING_STOP
        if 'onscanresult' in lowered_line:
            return BluetoothEventType.SCAN_RESULT
        if any(keyword in lowered_line for keyword in self._SCANNING_KEYWORDS):
            return BluetoothEventType.SCAN_START
        if any(keyword in lowered_line for keyword in self._SCANNING_STOP_KEYWORDS):
            return BluetoothEventType.SCAN_STOP
        if 'connect' in lowered_line and 'gatt' in lowered_line:
            return BluetoothEventType.CONNECT
        if 'disconnect' in lowered_line and 'gatt' in lowered_line:
            return BluetoothEventType.DISCONNECT
        if 'error' in lowered_line or 'failed' in lowered_line:
            return BluetoothEventType.ERROR
        return None

    def _split_tag_and_message(self, line: str) -> Tuple[Optional[str], str]:
        match = self._RE_MESSAGE.search(line)
        if not match:
            return None, line.strip()
        tag = match.group(1)
        message = match.group(2)
        return tag, message

    def _extract_metadata(self, lowered_line: str, message: str) -> Dict[str, object]:
        metadata: Dict[str, object] = {}

        set_match = self._RE_SET_ID.search(lowered_line)
        if set_match:
            metadata['set_id'] = int(set_match.group(1))

        tx_power_match = self._RE_TX_POWER.search(lowered_line)
        if tx_power_match:
            metadata['tx_power'] = tx_power_match.group(1).upper()

        data_len_match = self._RE_DATA_LEN.search(lowered_line)
        if data_len_match:
            metadata['data_length'] = int(data_len_match.group(1))

        client_match = self._RE_CLIENT_UID.search(message)
        if client_match:
            metadata['client'] = f"uid/{client_match.group(1)}"
        else:
            client_match = self._RE_CLIENT.search(message)
            if client_match:
                metadata['client'] = client_match.group(1)

        return metadata

    # ------------------------------------------------------------------
    # Primitive helpers
    # ------------------------------------------------------------------
    def _extract_int(self, pattern: re.Pattern, text: str) -> Optional[int]:
        match = pattern.search(text)
        if match:
            try:
                return int(match.group(1))
            except ValueError:
                return None
        return None

    def _extract_uuids(self, text: str) -> List[str]:
        match = self._RE_UUIDS.search(text)
        if not match:
            return []
        raw_list = match.group(1)
        uuids = [uuid.strip().upper() for uuid in re.split(r'[,:]', raw_list) if uuid.strip()]
        return uuids
