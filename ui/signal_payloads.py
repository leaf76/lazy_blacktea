"""Dataclasses describing signal payloads used across the UI layer."""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Optional

__all__ = [
    "RecordingEventType",
    "RecordingProgressEvent",
    "OperationStatus",
    "OperationType",
    "DeviceOperationEvent",
]


class OperationStatus(str, Enum):
    """Status of a device operation."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class OperationType(str, Enum):
    """Type of device operation."""

    SCREENSHOT = "screenshot"
    REBOOT = "reboot"
    INSTALL_APK = "install_apk"
    BLUETOOTH = "bluetooth"
    SCRCPY = "scrcpy"
    UI_INSPECTOR = "ui_inspector"
    RECORDING = "recording"
    RECORDING_START = "recording_start"  # Deprecated: use RECORDING
    RECORDING_STOP = "recording_stop"  # Deprecated: use RECORDING
    BUG_REPORT = "bug_report"
    SHELL_COMMAND = "shell_command"

    @property
    def display_name(self) -> str:
        """Human-readable name for the operation type."""
        names = {
            OperationType.SCREENSHOT: "Screenshot",
            OperationType.REBOOT: "Reboot",
            OperationType.INSTALL_APK: "Install APK",
            OperationType.BLUETOOTH: "Bluetooth",
            OperationType.SCRCPY: "scrcpy",
            OperationType.UI_INSPECTOR: "UI Inspector",
            OperationType.RECORDING: "Recording",
            OperationType.RECORDING_START: "Recording",  # Deprecated: backward compat
            OperationType.RECORDING_STOP: "Recording",  # Deprecated: backward compat
            OperationType.BUG_REPORT: "Bug Report",
            OperationType.SHELL_COMMAND: "Shell Command",
        }
        return names.get(self, self.value.replace("_", " ").title())

    @property
    def icon(self) -> str:
        """Emoji icon for the operation type."""
        icons = {
            OperationType.SCREENSHOT: "📸",
            OperationType.REBOOT: "🔄",
            OperationType.INSTALL_APK: "📦",
            OperationType.BLUETOOTH: "📶",
            OperationType.SCRCPY: "🖥️",
            OperationType.UI_INSPECTOR: "🔍",
            OperationType.RECORDING: "🎬",
            OperationType.RECORDING_START: "🎬",  # Deprecated: backward compat
            OperationType.RECORDING_STOP: "🎬",  # Deprecated: backward compat
            OperationType.BUG_REPORT: "🐛",
            OperationType.SHELL_COMMAND: "💻",
        }
        return icons.get(self, "⚙️")


OPERATION_ID_LENGTH = 8


def _generate_operation_id() -> str:
    """Generate a unique operation ID."""
    return str(uuid.uuid4())[:OPERATION_ID_LENGTH]


@dataclass(slots=True)
class DeviceOperationEvent:
    """Event representing a device operation status change.

    This dataclass is used to communicate operation state changes
    between DeviceOperationsManager and the status UI components.
    """

    device_serial: str
    operation_type: OperationType
    status: OperationStatus
    operation_id: str = field(default_factory=_generate_operation_id)
    started_at: float = field(default_factory=time.time)
    device_name: Optional[str] = None
    progress: Optional[float] = None  # 0.0 - 1.0
    message: Optional[str] = None
    can_cancel: bool = False
    completed_at: Optional[float] = None
    error_message: Optional[str] = None

    @property
    def is_active(self) -> bool:
        """Check if operation is still active (pending or running)."""
        return self.status in (OperationStatus.PENDING, OperationStatus.RUNNING)

    @property
    def is_terminal(self) -> bool:
        """Check if operation has reached a terminal state."""
        return self.status in (
            OperationStatus.COMPLETED,
            OperationStatus.FAILED,
            OperationStatus.CANCELLED,
        )

    @property
    def elapsed_seconds(self) -> float:
        """Get elapsed time since operation started."""
        end_time = self.completed_at or time.time()
        return end_time - self.started_at

    @property
    def status_icon(self) -> str:
        """Get status indicator icon."""
        icons = {
            OperationStatus.PENDING: "⏳",
            OperationStatus.RUNNING: "⟳",
            OperationStatus.COMPLETED: "✓",
            OperationStatus.FAILED: "✗",
            OperationStatus.CANCELLED: "⊘",
        }
        return icons.get(self.status, "?")

    @property
    def display_status(self) -> str:
        """Get human-readable status text."""
        if self.status == OperationStatus.RUNNING and self.progress is not None:
            return f"{int(self.progress * 100)}%"
        if self.status == OperationStatus.FAILED and self.error_message:
            return f"Failed: {self.error_message[:30]}"
        return self.status.value.capitalize()

    def with_status(
        self, new_status: OperationStatus, **kwargs: Any
    ) -> "DeviceOperationEvent":
        completed_at = self.completed_at
        if new_status in (
            OperationStatus.COMPLETED,
            OperationStatus.FAILED,
            OperationStatus.CANCELLED,
        ):
            completed_at = kwargs.pop("completed_at", time.time())

        return DeviceOperationEvent(
            device_serial=self.device_serial,
            operation_type=self.operation_type,
            status=new_status,
            operation_id=self.operation_id,
            started_at=self.started_at,
            device_name=kwargs.get("device_name", self.device_name),
            progress=kwargs.get("progress", self.progress),
            message=kwargs.get("message", self.message),
            can_cancel=kwargs.get("can_cancel", self.can_cancel),
            completed_at=completed_at,
            error_message=kwargs.get("error_message", self.error_message),
        )

    @classmethod
    def create(
        cls,
        device_serial: str,
        operation_type: OperationType,
        *,
        device_name: Optional[str] = None,
        message: Optional[str] = None,
        can_cancel: bool = False,
    ) -> "DeviceOperationEvent":
        """Factory method to create a new pending operation event."""
        return cls(
            device_serial=device_serial,
            operation_type=operation_type,
            status=OperationStatus.PENDING,
            device_name=device_name,
            message=message,
            can_cancel=can_cancel,
        )


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
