"""Centralized manager for tracking device operation states."""

from __future__ import annotations

from collections import defaultdict
from typing import Callable, Dict, List, Optional

from PyQt6.QtCore import QObject, QTimer, pyqtSignal

from ui.signal_payloads import DeviceOperationEvent, OperationStatus, OperationType
from utils.common import get_logger


class DeviceOperationStatusManager(QObject):
    """Manages operation states for all devices.

    Provides a central registry for tracking active operations per device,
    emits signals when operations change, and handles auto-dismiss of
    completed operations after a configurable delay.
    """

    operation_added = pyqtSignal(object)
    operation_updated = pyqtSignal(object)
    operation_removed = pyqtSignal(str)
    device_status_changed = pyqtSignal(str)

    AUTO_DISMISS_DELAY_MS = 3000
    MAX_COMPLETED_OPERATIONS = 50

    def __init__(self, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._logger = get_logger("device_operation_status_manager")

        self._operations: Dict[str, DeviceOperationEvent] = {}
        self._device_operations: Dict[str, List[str]] = defaultdict(list)
        self._dismiss_timers: Dict[str, QTimer] = {}
        self._cancel_callbacks: Dict[str, Callable[[], bool]] = {}

    def add_operation(
        self,
        event: DeviceOperationEvent,
        cancel_callback: Optional[Callable[[], bool]] = None,
    ) -> str:
        """Register a new operation. Returns the operation_id.

        For RECORDING operations, reuses existing operation_id if found.
        """
        is_recording = event.operation_type in (
            OperationType.RECORDING,
            OperationType.RECORDING_START,
            OperationType.RECORDING_STOP,
        )

        if is_recording:
            existing_op_id = self._find_recording_operation(event.device_serial)
            if existing_op_id:
                self.update_operation(
                    existing_op_id,
                    status=event.status,
                    message=event.message,
                    progress=event.progress,
                    error_message=event.error_message,
                )
                return existing_op_id

        op_id = event.operation_id
        self._operations[op_id] = event
        self._device_operations[event.device_serial].append(op_id)

        if cancel_callback and event.can_cancel:
            self._cancel_callbacks[op_id] = cancel_callback

        self._logger.debug(
            f"Operation added: {event.operation_type.value} on {event.device_serial} "
            f"(id={op_id})"
        )
        self.operation_added.emit(event)
        self.device_status_changed.emit(event.device_serial)
        return op_id

    def update_operation(
        self,
        operation_id: str,
        status: Optional[OperationStatus] = None,
        progress: Optional[float] = None,
        message: Optional[str] = None,
        error_message: Optional[str] = None,
    ) -> Optional[DeviceOperationEvent]:
        """Update an existing operation. Returns updated event or None if not found."""
        event = self._operations.get(operation_id)
        if event is None:
            self._logger.warning(f"Cannot update unknown operation: {operation_id}")
            return None

        kwargs = {}
        if progress is not None:
            kwargs["progress"] = progress
        if message is not None:
            kwargs["message"] = message
        if error_message is not None:
            kwargs["error_message"] = error_message

        if status is not None:
            updated = event.with_status(status, **kwargs)
        else:
            updated = DeviceOperationEvent(
                device_serial=event.device_serial,
                operation_type=event.operation_type,
                status=event.status,
                operation_id=event.operation_id,
                started_at=event.started_at,
                device_name=event.device_name,
                progress=kwargs.get("progress", event.progress),
                message=kwargs.get("message", event.message),
                can_cancel=event.can_cancel,
                completed_at=event.completed_at,
                error_message=kwargs.get("error_message", event.error_message),
            )

        self._operations[operation_id] = updated
        self.operation_updated.emit(updated)
        self.device_status_changed.emit(updated.device_serial)

        if updated.is_terminal:
            self._schedule_auto_dismiss(operation_id)
            self._cancel_callbacks.pop(operation_id, None)

        return updated

    def complete_operation(
        self,
        operation_id: str,
        message: Optional[str] = None,
    ) -> Optional[DeviceOperationEvent]:
        """Mark operation as completed."""
        return self.update_operation(
            operation_id,
            status=OperationStatus.COMPLETED,
            message=message,
        )

    def fail_operation(
        self,
        operation_id: str,
        error_message: str,
    ) -> Optional[DeviceOperationEvent]:
        """Mark operation as failed."""
        return self.update_operation(
            operation_id,
            status=OperationStatus.FAILED,
            error_message=error_message,
        )

    def cancel_operation(self, operation_id: str) -> bool:
        """Attempt to cancel an operation. Returns True if cancellation was initiated."""
        event = self._operations.get(operation_id)
        if event is None:
            return False

        if not event.can_cancel or event.is_terminal:
            return False

        callback = self._cancel_callbacks.get(operation_id)
        if callback:
            try:
                cancelled = callback()
                if cancelled:
                    self.update_operation(
                        operation_id, status=OperationStatus.CANCELLED
                    )
                    return True
            except Exception as e:
                self._logger.error(f"Cancel callback failed for {operation_id}: {e}")
                return False

        self.update_operation(operation_id, status=OperationStatus.CANCELLED)
        return True

    def remove_operation(self, operation_id: str) -> None:
        """Remove an operation from tracking."""
        event = self._operations.pop(operation_id, None)
        if event is None:
            return

        serial = event.device_serial
        if operation_id in self._device_operations.get(serial, []):
            self._device_operations[serial].remove(operation_id)

        timer = self._dismiss_timers.pop(operation_id, None)
        if timer:
            timer.stop()
            timer.deleteLater()

        self._cancel_callbacks.pop(operation_id, None)
        self.operation_removed.emit(operation_id)
        self.device_status_changed.emit(serial)

    def get_operation(self, operation_id: str) -> Optional[DeviceOperationEvent]:
        """Get an operation by ID."""
        return self._operations.get(operation_id)

    def get_device_operations(self, device_serial: str) -> List[DeviceOperationEvent]:
        """Get all operations for a device."""
        op_ids = self._device_operations.get(device_serial, [])
        return [
            self._operations[op_id] for op_id in op_ids if op_id in self._operations
        ]

    def get_active_operations(self) -> List[DeviceOperationEvent]:
        """Get all active (pending or running) operations."""
        return [op for op in self._operations.values() if op.is_active]

    def get_all_operations(self) -> List[DeviceOperationEvent]:
        """Get all tracked operations."""
        return list(self._operations.values())

    def _find_recording_operation(self, device_serial: str) -> Optional[str]:
        """Find existing recording operation ID for a device."""
        ops = self.get_device_operations(device_serial)
        for op in ops:
            if op.operation_type in (
                OperationType.RECORDING,
                OperationType.RECORDING_START,
                OperationType.RECORDING_STOP,
            ):
                return op.operation_id
        return None

    def get_device_active_operation(
        self, device_serial: str
    ) -> Optional[DeviceOperationEvent]:
        """Get the most recent active operation for a device, if any."""
        ops = self.get_device_operations(device_serial)
        active = [op for op in ops if op.is_active]
        return active[-1] if active else None

    def has_active_operations(self, device_serial: Optional[str] = None) -> bool:
        """Check if there are any active operations, optionally for a specific device."""
        if device_serial:
            return any(op.is_active for op in self.get_device_operations(device_serial))
        return any(op.is_active for op in self._operations.values())

    def clear_completed(self, device_serial: Optional[str] = None) -> int:
        """Remove all completed operations. Returns count of removed operations."""
        removed = 0
        ops_to_remove = []

        for op_id, event in self._operations.items():
            if event.is_terminal:
                if device_serial is None or event.device_serial == device_serial:
                    ops_to_remove.append(op_id)

        for op_id in ops_to_remove:
            self.remove_operation(op_id)
            removed += 1

        return removed

    def _schedule_auto_dismiss(self, operation_id: str) -> None:
        """Schedule automatic removal of a terminal operation."""
        if operation_id in self._dismiss_timers:
            return

        timer = QTimer(self)
        timer.setSingleShot(True)
        timer.timeout.connect(lambda: self._auto_dismiss(operation_id))
        timer.start(self.AUTO_DISMISS_DELAY_MS)
        self._dismiss_timers[operation_id] = timer

    def _auto_dismiss(self, operation_id: str) -> None:
        """Auto-dismiss handler called by timer."""
        self._dismiss_timers.pop(operation_id, None)
        event = self._operations.get(operation_id)
        if event and event.is_terminal:
            self.remove_operation(operation_id)
            self._cleanup_old_operations()

    def _cleanup_old_operations(self) -> None:
        """Ensure we don't accumulate too many completed operations."""
        terminal_ops = [
            (op_id, ev) for op_id, ev in self._operations.items() if ev.is_terminal
        ]
        if len(terminal_ops) > self.MAX_COMPLETED_OPERATIONS:
            excess = len(terminal_ops) - self.MAX_COMPLETED_OPERATIONS
            terminal_ops.sort(key=lambda x: x[1].completed_at or 0)
            for op_id, _ in terminal_ops[:excess]:
                self.remove_operation(op_id)
