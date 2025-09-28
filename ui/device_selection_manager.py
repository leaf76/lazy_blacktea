"""Device selection state management utilities."""

from __future__ import annotations

from collections import OrderedDict
from typing import Iterable, List, Optional, Tuple


class DeviceSelectionManager:
    """Keeps device selection state consistent and tracks the active device."""

    def __init__(self) -> None:
        self._selection: "OrderedDict[str, None]" = OrderedDict()
        self._active_serial: Optional[str] = None

    # ------------------------------------------------------------------
    # Selection bookkeeping
    # ------------------------------------------------------------------
    def apply_toggle(
        self,
        serial: str,
        is_checked: bool,
        available_serials: Optional[Iterable[str]] = None,
    ) -> List[str]:
        """Apply a checkbox/radio toggle to the tracked selection state."""
        if is_checked:
            self._selection.pop(serial, None)
            self._selection[serial] = None
            self._active_serial = serial
        else:
            self._selection.pop(serial, None)
            if self._active_serial == serial:
                self._active_serial = next(reversed(self._selection), None)

        if available_serials is not None:
            self.prune_selection(available_serials)

        return self.get_selected_serials()

    def get_selected_serials(self) -> List[str]:
        """Return the currently selected device serials in insertion order."""
        return list(self._selection.keys())

    def set_selected_serials(self, serials: Iterable[str]) -> List[str]:
        """Replace the tracked selection with the provided serials."""
        self._selection.clear()
        for serial in serials:
            self._selection[serial] = None
        self._active_serial = next(reversed(self._selection), None)
        return self.get_selected_serials()

    def prune_selection(self, valid_serials: Iterable[str]) -> List[str]:
        """Drop selections that no longer exist in the device list."""
        valid_set = set(valid_serials)
        self._selection = OrderedDict(
            (serial, None)
            for serial in self._selection
            if serial in valid_set
        )
        if self._active_serial not in self._selection:
            self._active_serial = next(reversed(self._selection), None)
        return self.get_selected_serials()

    def clear(self) -> None:
        """Reset tracked selection."""
        self._selection.clear()
        self._active_serial = None

    def set_active_serial(self, serial: Optional[str]) -> Optional[str]:
        """Mark the specified serial as the active device if it is selected."""
        if serial is not None and serial in self._selection:
            self._active_serial = serial
        elif serial is None:
            self._active_serial = None
        return self._active_serial

    def get_active_serial(self) -> Optional[str]:
        """Return the currently active device serial (if any)."""
        if self._active_serial in self._selection:
            return self._active_serial
        self._active_serial = next(reversed(self._selection), None)
        return self._active_serial

    # ------------------------------------------------------------------
    # Validation helpers
    # ------------------------------------------------------------------
    def require_single_device(self, action_label: str) -> Tuple[bool, List[str], Optional[str]]:
        """Ensure exactly one device is selected before running an action."""
        selected = self.get_selected_serials()
        active = self.get_active_serial()
        if active:
            return True, [active], None
        if len(selected) == 1:
            active_serial = selected[0]
            self._active_serial = active_serial
            return True, [active_serial], None

        message = (
            f"{action_label} requires a primary device. "
            "Select multiple as needed, then click or toggle the target device last to make it active."
        )
        return False, [], message

    def require_any_device(self, action_label: str) -> Tuple[bool, List[str], Optional[str]]:
        """Ensure at least one device is selected for batch actions."""
        selected = self.get_selected_serials()
        if selected:
            return True, selected, None

        message = (
            f"Please select at least one device before running {action_label}."
        )
        return False, [], message


__all__ = ["DeviceSelectionManager"]
