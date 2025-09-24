"""Unified error handling module for the application."""

import logging
import traceback
import sys
from enum import Enum
from typing import Optional, Callable, Dict, Any
from dataclasses import dataclass
from PyQt6.QtWidgets import QMessageBox, QWidget
from PyQt6.QtCore import QObject, pyqtSignal

from utils import common

logger = common.get_logger('error_handler')


class ErrorLevel(Enum):
    """Error severity levels."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class ErrorCode(Enum):
    """Standardized error codes."""
    # Device errors
    DEVICE_NOT_FOUND = "DEVICE_NOT_FOUND"
    DEVICE_OFFLINE = "DEVICE_OFFLINE"
    DEVICE_UNAUTHORIZED = "DEVICE_UNAUTHORIZED"

    # Command errors
    COMMAND_FAILED = "COMMAND_FAILED"
    COMMAND_TIMEOUT = "COMMAND_TIMEOUT"
    INVALID_COMMAND = "INVALID_COMMAND"

    # File errors
    FILE_NOT_FOUND = "FILE_NOT_FOUND"
    FILE_PERMISSION_DENIED = "FILE_PERMISSION_DENIED"
    FILE_CORRUPTED = "FILE_CORRUPTED"

    # Network errors
    NETWORK_TIMEOUT = "NETWORK_TIMEOUT"
    CONNECTION_REFUSED = "CONNECTION_REFUSED"

    # Configuration errors
    CONFIG_INVALID = "CONFIG_INVALID"
    CONFIG_LOAD_FAILED = "CONFIG_LOAD_FAILED"

    # UI errors
    UI_INIT_FAILED = "UI_INIT_FAILED"
    WIDGET_ERROR = "WIDGET_ERROR"

    # Generic errors
    UNKNOWN_ERROR = "UNKNOWN_ERROR"
    INTERNAL_ERROR = "INTERNAL_ERROR"


@dataclass
class ErrorInfo:
    """Structured error information."""
    code: ErrorCode
    message: str
    level: ErrorLevel
    details: Optional[str] = None
    suggestion: Optional[str] = None
    technical_info: Optional[str] = None


class ErrorHandler(QObject):
    """Centralized error handling system."""

    # Signals for error communication
    error_occurred = pyqtSignal(object)  # ErrorInfo
    critical_error = pyqtSignal(str)  # message

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.parent = parent
        self.error_handlers: Dict[ErrorCode, Callable] = {}
        self.error_count = 0
        self.max_errors_before_exit = 50

        # Setup default error messages
        self._setup_error_messages()

    def _setup_error_messages(self):
        """Setup default error messages and suggestions."""
        self.error_templates = {
            ErrorCode.DEVICE_NOT_FOUND: ErrorInfo(
                code=ErrorCode.DEVICE_NOT_FOUND,
                message="No Android devices found",
                level=ErrorLevel.WARNING,
                suggestion="Connect device via USB and enable USB debugging"
            ),
            ErrorCode.DEVICE_OFFLINE: ErrorInfo(
                code=ErrorCode.DEVICE_OFFLINE,
                message="Device is offline",
                level=ErrorLevel.WARNING,
                suggestion="Check USB connection and device authorization"
            ),
            ErrorCode.DEVICE_UNAUTHORIZED: ErrorInfo(
                code=ErrorCode.DEVICE_UNAUTHORIZED,
                message="Device access unauthorized",
                level=ErrorLevel.ERROR,
                suggestion="Allow USB debugging authorization on device"
            ),
            ErrorCode.COMMAND_FAILED: ErrorInfo(
                code=ErrorCode.COMMAND_FAILED,
                message="ADB command execution failed",
                level=ErrorLevel.ERROR,
                suggestion="Check command syntax and device connectivity"
            ),
            ErrorCode.COMMAND_TIMEOUT: ErrorInfo(
                code=ErrorCode.COMMAND_TIMEOUT,
                message="Command execution timed out",
                level=ErrorLevel.WARNING,
                suggestion="Try again or increase timeout settings"
            ),
            ErrorCode.FILE_NOT_FOUND: ErrorInfo(
                code=ErrorCode.FILE_NOT_FOUND,
                message="Required file not found",
                level=ErrorLevel.ERROR,
                suggestion="Check file path and permissions"
            ),
            ErrorCode.FILE_PERMISSION_DENIED: ErrorInfo(
                code=ErrorCode.FILE_PERMISSION_DENIED,
                message="Permission denied accessing file",
                level=ErrorLevel.ERROR,
                suggestion="Run with appropriate permissions or change file location"
            ),
            ErrorCode.CONFIG_LOAD_FAILED: ErrorInfo(
                code=ErrorCode.CONFIG_LOAD_FAILED,
                message="Failed to load configuration",
                level=ErrorLevel.WARNING,
                suggestion="Configuration will be reset to defaults"
            ),
            ErrorCode.NETWORK_TIMEOUT: ErrorInfo(
                code=ErrorCode.NETWORK_TIMEOUT,
                message="Network operation timed out",
                level=ErrorLevel.WARNING,
                suggestion="Check network connection and try again"
            )
        }

    def handle_error(self, error_code: ErrorCode, details: str = None,
                    exception: Exception = None, context: Dict[str, Any] = None):
        """Handle an error with the specified code."""
        self.error_count += 1

        # Get error template or create generic one
        error_info = self.error_templates.get(error_code, ErrorInfo(
            code=error_code,
            message=f"Error occurred: {error_code.value}",
            level=ErrorLevel.ERROR
        ))

        # Add details if provided
        if details:
            error_info.details = details

        # Add technical information from exception
        if exception:
            error_info.technical_info = f"{type(exception).__name__}: {str(exception)}"
            if error_info.level == ErrorLevel.ERROR:
                error_info.technical_info += f"\n{traceback.format_exc()}"

        # Log the error
        self._log_error(error_info, context)

        # Emit signal
        self.error_occurred.emit(error_info)

        # Check for critical error count
        if (self.error_count > self.max_errors_before_exit and
            error_info.level == ErrorLevel.CRITICAL):
            self.critical_error.emit("Too many critical errors occurred")

        # Call custom handler if registered
        if error_code in self.error_handlers:
            try:
                self.error_handlers[error_code](error_info, context)
            except Exception as handler_error:
                logger.error(f"Error handler failed: {handler_error}")

        # Show UI dialog for errors and critical warnings
        if (error_info.level in [ErrorLevel.ERROR, ErrorLevel.CRITICAL] or
            (error_info.level == ErrorLevel.WARNING and self.parent)):
            self._show_error_dialog(error_info)

    def _log_error(self, error_info: ErrorInfo, context: Dict[str, Any] = None):
        """Log error information."""
        log_message = f"[{error_info.code.value}] {error_info.message}"

        if error_info.details:
            log_message += f" - Details: {error_info.details}"

        if context:
            log_message += f" - Context: {context}"

        if error_info.technical_info:
            log_message += f"\nTechnical: {error_info.technical_info}"

        # Log at appropriate level
        if error_info.level == ErrorLevel.INFO:
            logger.info(log_message)
        elif error_info.level == ErrorLevel.WARNING:
            logger.warning(log_message)
        elif error_info.level == ErrorLevel.ERROR:
            logger.error(log_message)
        else:  # CRITICAL
            logger.critical(log_message)

    def _show_error_dialog(self, error_info: ErrorInfo):
        """Show error dialog to user."""
        if not self.parent:
            return

        # Determine dialog type and icon
        if error_info.level == ErrorLevel.CRITICAL:
            dialog_type = QMessageBox.Icon.Critical
            title = "Critical Error"
        elif error_info.level == ErrorLevel.ERROR:
            dialog_type = QMessageBox.Icon.Critical
            title = "Error"
        else:  # WARNING
            dialog_type = QMessageBox.Icon.Warning
            title = "Warning"

        # Build message
        message = error_info.message
        if error_info.details:
            message += f"\n\nDetails: {error_info.details}"
        if error_info.suggestion:
            message += f"\n\nSuggestion: {error_info.suggestion}"

        # Show dialog
        msg_box = QMessageBox(self.parent)
        msg_box.setIcon(dialog_type)
        msg_box.setWindowTitle(title)
        msg_box.setText(message)

        if error_info.technical_info:
            msg_box.setDetailedText(error_info.technical_info)

        msg_box.exec()

    def register_error_handler(self, error_code: ErrorCode, handler: Callable):
        """Register custom error handler for specific error code."""
        self.error_handlers[error_code] = handler
        logger.debug(f"Registered custom handler for {error_code.value}")

    def handle_exception(self, exception: Exception, context: str = None):
        """Handle generic exceptions."""
        error_code = self._map_exception_to_error_code(exception)
        self.handle_error(
            error_code=error_code,
            details=context,
            exception=exception
        )

    def _map_exception_to_error_code(self, exception: Exception) -> ErrorCode:
        """Map Python exceptions to error codes."""
        exception_mapping = {
            FileNotFoundError: ErrorCode.FILE_NOT_FOUND,
            PermissionError: ErrorCode.FILE_PERMISSION_DENIED,
            ConnectionRefusedError: ErrorCode.CONNECTION_REFUSED,
            TimeoutError: ErrorCode.COMMAND_TIMEOUT,
            ValueError: ErrorCode.INVALID_COMMAND,
            KeyError: ErrorCode.CONFIG_INVALID,
        }

        return exception_mapping.get(type(exception), ErrorCode.UNKNOWN_ERROR)

    def show_info(self, message: str, title: str = "Information"):
        """Show information message."""
        if self.parent:
            QMessageBox.information(self.parent, title, message)
        logger.info(f"Info shown: {title} - {message}")

    def show_warning(self, message: str, title: str = "Warning"):
        """Show warning message."""
        if self.parent:
            QMessageBox.warning(self.parent, title, message)
        logger.warning(f"Warning shown: {title} - {message}")

    def show_error(self, title: str, message: str):
        """Show error message."""
        if self.parent:
            QMessageBox.critical(self.parent, title, message)
        logger.error(f"Error shown: {title} - {message}")

    def show_question(self, message: str, title: str = "Confirm") -> bool:
        """Show question dialog and return user response."""
        if self.parent:
            result = QMessageBox.question(
                self.parent, title, message,
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            return result == QMessageBox.StandardButton.Yes
        return False

    def reset_error_count(self):
        """Reset error counter."""
        self.error_count = 0
        logger.debug("Error count reset")


# Global error handler instance
global_error_handler = ErrorHandler()


def handle_error(error_code: ErrorCode, details: str = None,
                exception: Exception = None, context: Dict[str, Any] = None):
    """Global error handling function."""
    global_error_handler.handle_error(error_code, details, exception, context)


def handle_exception(exception: Exception, context: str = None):
    """Global exception handling function."""
    global_error_handler.handle_exception(exception, context)


def setup_exception_hook():
    """Setup global exception hook for unhandled exceptions."""
    def exception_hook(exc_type, exc_value, exc_traceback):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return

        logger.critical("Unhandled exception", exc_info=(exc_type, exc_value, exc_traceback))
        handle_exception(exc_value, "Unhandled exception")

    sys.excepthook = exception_hook