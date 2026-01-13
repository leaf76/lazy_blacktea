"""Facade to encapsulate Logcat viewer launch and actions.

This facade keeps `WindowMain` slim by handling the details of creating and
showing the Logcat window, selecting the target device, and clearing logcat
buffers on selected devices.
"""

from __future__ import annotations

from functools import partial
from typing import Dict, Optional, TYPE_CHECKING

from utils import adb_models, common
from ui.logcat_viewer import LogcatWindow

if TYPE_CHECKING:  # pragma: no cover
    from ui.main_window import WindowMain


logger = common.get_logger("logcat_facade")

MAX_LOGCAT_WINDOWS = 5


class LogcatFacade:
    """Facade for Logcat viewer interactions.

    Public methods are kept small and type-annotated to align with project
    style guidelines and improve readability.
    """

    def __init__(self, window: "WindowMain") -> None:
        self.window = window

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def show_logcat_for_selected(self) -> None:
        """Open the Logcat viewer for each selected device.

        Opens a separate Logcat window for each device in the current selection.
        If no devices are selected, shows a warning and returns.
        """
        devices = self.window.get_checked_devices()
        if not devices:
            self.window.show_warning(
                "Logcat Viewer", "Please select at least one device."
            )
            return

        for device in devices:
            self._open_logcat_for_device(device)

    def view_logcat_for_device(self, device_serial: str) -> None:
        """Open the Logcat viewer for a given device serial if available."""
        device = self.window.device_dict.get(device_serial)
        if not device:
            self.window.show_error(
                "Logcat Error", "Target device is no longer available."
            )
            return
        self._open_logcat_for_device(device)

    def clear_logcat_selected_devices(self) -> None:
        """Clear logcat buffers on the currently selected devices, if supported."""
        manager = getattr(self.window.logging_manager, "logcat_manager", None)
        if manager is None:
            logger.debug("No logcat manager available; skip clearing.")
            return
        manager.clear_logcat_selected_devices()

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    def _open_logcat_for_device(self, device: adb_models.DeviceInfo) -> None:
        """Instantiate and show the Logcat window for the provided device."""
        if not device:
            self.window.show_error("Error", "Selected device is not available.")
            return

        serial = device.device_serial_num
        logcat_windows = getattr(self.window, "logcat_windows", None)
        if logcat_windows is None:
            logcat_windows = {}
            self.window.logcat_windows = logcat_windows

        existing_window = logcat_windows.get(serial)
        if existing_window is not None:
            try:
                if existing_window.isVisible():
                    existing_window.raise_()
                    existing_window.activateWindow()
                    return
            except RuntimeError:
                pass
            logcat_windows.pop(serial, None)

        if len(logcat_windows) >= MAX_LOGCAT_WINDOWS:
            self.window.show_info(
                "Logcat Viewer",
                f"You can open up to {MAX_LOGCAT_WINDOWS} Logcat windows. "
                "Please close an existing Logcat window first.",
            )
            return

        try:
            settings_payload: Dict[str, int] = {}
            logcat_settings = getattr(self.window, "logcat_settings", None)
            if logcat_settings is not None:
                settings_payload = {
                    "max_lines": logcat_settings.max_lines,
                    "history_multiplier": logcat_settings.history_multiplier,
                    "update_interval_ms": logcat_settings.update_interval_ms,
                    "max_lines_per_update": logcat_settings.max_lines_per_update,
                    "max_buffer_size": logcat_settings.max_buffer_size,
                }

            device_manager = getattr(self.window, "device_manager", None)
            config_manager = getattr(self.window, "config_manager", None)

            logcat_window = LogcatWindow(
                device,
                None,
                settings=settings_payload,
                on_settings_changed=self.window.persist_logcat_settings,
                device_manager=device_manager,
                config_manager=config_manager,
            )

            logcat_windows[serial] = logcat_window
            logcat_window.destroyed.connect(
                partial(self._on_logcat_window_destroyed, serial)
            )
            logcat_window.show()
        except Exception as exc:  # pragma: no cover - defensive UI path
            logger.error("Failed to open logcat window: %s", exc)
            self.window.show_error(
                "Logcat Error", f"Unable to launch Logcat viewer.\n\nDetails: {exc}"
            )

    def _on_logcat_window_destroyed(self, serial: str) -> None:
        """Remove the logcat window reference when it is destroyed."""
        logcat_windows = getattr(self.window, "logcat_windows", None)
        if logcat_windows is not None:
            logcat_windows.pop(serial, None)


__all__ = ["LogcatFacade"]
