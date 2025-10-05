"""Reusable mixin for consistent operation logging in UI classes.

This provides small helpers that delegate to an attached `logging_manager`.
Expectations:
- `self.logging_manager` exposes: `log_operation_start`, `log_operation_complete`, `log_operation_failure`.
"""

from __future__ import annotations

from typing import Any, Callable, Optional


class OperationLoggingMixin:
    """Mixin that standardizes operation logging patterns for UI actions."""

    def _log_operation_start(self, operation: str, details: Optional[str] = None) -> None:
        manager = getattr(self, "logging_manager", None)
        if manager is None:
            return
        if details:
            manager.log_operation_start(operation, details)
        else:
            manager.log_operation_start(operation)

    def _log_operation_complete(self, operation: str, details: Optional[str] = None) -> None:
        manager = getattr(self, "logging_manager", None)
        if manager is None:
            return
        if details:
            manager.log_operation_complete(operation, details)
        else:
            manager.log_operation_complete(operation)

    def _log_operation_failure(self, operation: str, error: str) -> None:
        manager = getattr(self, "logging_manager", None)
        if manager is None:
            return
        manager.log_operation_failure(operation, error)

    def _execute_with_operation_logging(
        self,
        operation: str,
        action: Callable[[], Any],
        *,
        success_details: Optional[str] = None,
    ) -> Any:
        """Run `action()` with standardized start/complete/failure logging.

        - Logs start before execution.
        - Logs failure and re-raises on exception.
        - Logs completion on success and returns result.
        """
        self._log_operation_start(operation)
        try:
            result = action()
        except Exception as exc:  # pragma: no cover - raising is validated by callers/tests
            self._log_operation_failure(operation, str(exc))
            raise
        else:
            self._log_operation_complete(operation, success_details)
            return result


__all__ = ["OperationLoggingMixin"]

