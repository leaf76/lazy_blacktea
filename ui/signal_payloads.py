"""Dataclasses describing signal payloads used across the UI layer."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Optional

__all__ = [
    "RecordingEventType",
    "RecordingProgressEvent",
]


class RecordingEventType(str, Enum):
    """Enumerates the known recording progress event types."""

    SEGMENT_COMPLETED = "segment_completed"
    ERROR = "error"
    HEARTBEAT = "heartbeat"


@dataclass(slots=True)
class RecordingProgressEvent:
    """Structured representation of a recording progress event."""

    event_type: RecordingEventType
    device_serial: str
    device_name: Optional[str] = None
    output_path: Optional[str] = None
    segment_index: Optional[int] = None
    segment_filename: Optional[str] = None
    duration_seconds: Optional[float] = None
    total_duration_seconds: Optional[float] = None
    message: Optional[str] = None
    request_origin: Optional[str] = None

    @classmethod
    def from_payload(cls, payload: Dict[str, Any]) -> "RecordingProgressEvent":
        """Build an event from the raw payload emitted by background workers."""
        if payload is None:
            raise ValueError("payload must be a mapping")

        raw_type = payload.get("type", RecordingEventType.SEGMENT_COMPLETED.value)
        try:
            event_type = RecordingEventType(raw_type)
        except ValueError:
            event_type = RecordingEventType.SEGMENT_COMPLETED

        device_serial = payload.get("device_serial")
        if not device_serial:
            raise ValueError("device_serial is required")

        segment_index = payload.get("segment_index")
        try:
            normalized_index = int(segment_index) if segment_index is not None else None
        except (TypeError, ValueError):
            normalized_index = None

        def _float(value: Any) -> Optional[float]:
            if value in (None, ""):
                return None
            try:
                return float(value)
            except (TypeError, ValueError):
                return None

        return cls(
            event_type=event_type,
            device_serial=device_serial,
            device_name=payload.get("device_name"),
            output_path=payload.get("output_path"),
            segment_index=normalized_index,
            segment_filename=payload.get("segment_filename"),
            duration_seconds=_float(payload.get("duration_seconds")),
            total_duration_seconds=_float(payload.get("total_duration_seconds")),
            message=payload.get("message"),
            request_origin=payload.get("request_origin"),
        )

    def to_payload(self) -> Dict[str, Any]:
        """Convert the event back to a serializable payload."""
        return {
            "type": self.event_type.value,
            "device_serial": self.device_serial,
            "device_name": self.device_name,
            "output_path": self.output_path,
            "segment_index": self.segment_index,
            "segment_filename": self.segment_filename,
            "duration_seconds": self.duration_seconds,
            "total_duration_seconds": self.total_duration_seconds,
            "message": self.message,
            "request_origin": self.request_origin,
        }
