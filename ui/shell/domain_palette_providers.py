"""Domain command-palette providers: connected devices and recent tasks (#14).

These reflect live runtime state, so they read from the window on every
``entries()`` call (the palette re-queries providers as the query changes).
"""

from __future__ import annotations

from typing import Callable, List, Sequence

from ui.shell.command_palette import PaletteEntry


class DevicesPaletteProvider:
    """Palette entries for each connected device (search by model/serial)."""

    SECTION = "Devices"

    def __init__(self, window) -> None:
        self._window = window

    def section_label(self) -> str:
        return self.SECTION

    def entries(self, query: str) -> Sequence[PaletteEntry]:
        device_dict = getattr(self._window, "device_dict", {}) or {}
        result: List[PaletteEntry] = []
        for serial, device in device_dict.items():
            model = getattr(device, "device_model", None) or "Unknown"
            result.append(
                PaletteEntry(
                    title=f"{model} · {serial}",
                    subtitle="Make active device",
                    section=self.SECTION,
                    invoke=self._make_invoker(serial),
                    keywords=("device", str(model), str(serial)),
                )
            )
        return result

    def _make_invoker(self, serial: str) -> Callable[[], None]:
        window = self._window

        def _invoke() -> None:
            selector = getattr(window, "select_only_device", None)
            if callable(selector):
                selector(serial)
            else:
                sel = getattr(window, "device_selection_manager", None)
                if sel is not None:
                    sel.set_active_serial(serial)
            shell = getattr(window, "app_shell", None)
            pane = getattr(window, "PANE_DEVICES", None)
            if shell is not None and pane is not None:
                shell.set_active_pane(pane)

        return _invoke


class RecentTasksPaletteProvider:
    """Palette entries for recent terminal operations (open the Tasks pane)."""

    SECTION = "Recent tasks"
    MAX_ENTRIES = 10

    def __init__(self, window) -> None:
        self._window = window

    def section_label(self) -> str:
        return self.SECTION

    def entries(self, query: str) -> Sequence[PaletteEntry]:
        manager = getattr(self._window, "device_operation_status_manager", None)
        if manager is None:
            return []
        try:
            operations = manager.get_all_operations()
        except Exception:
            return []

        terminal = [op for op in operations if getattr(op, "is_terminal", False)]
        terminal.sort(key=lambda op: getattr(op, "completed_at", 0) or 0, reverse=True)

        result: List[PaletteEntry] = []
        for op in terminal[: self.MAX_ENTRIES]:
            op_type = getattr(op, "operation_type", None)
            name = getattr(op_type, "display_name", None) or str(op_type)
            device = getattr(op, "device_name", None) or getattr(op, "device_serial", "")
            status = getattr(op, "status", None)
            status_text = getattr(status, "value", None) or str(status)
            result.append(
                PaletteEntry(
                    title=f"{name} — {device}",
                    subtitle=status_text.capitalize(),
                    section=self.SECTION,
                    invoke=self._make_invoker(),
                    keywords=("task", "recent", str(name), str(device)),
                )
            )
        return result

    def _make_invoker(self) -> Callable[[], None]:
        window = self._window

        def _invoke() -> None:
            shell = getattr(window, "app_shell", None)
            pane = getattr(window, "PANE_TASKS", None)
            if shell is not None and pane is not None:
                shell.set_active_pane(pane)

        return _invoke


__all__ = ["DevicesPaletteProvider", "RecentTasksPaletteProvider"]
