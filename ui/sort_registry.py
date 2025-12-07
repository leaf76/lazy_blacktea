"""Auto-extensible sort field registry for device sorting."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from utils import adb_models


@dataclass
class SortField:
    """Defines a sortable field configuration.

    Attributes:
        name: Unique identifier (e.g., "name", "serial", "api")
        label: Display label for UI (e.g., "Model Name", "API Level")
        attr: DeviceInfo attribute name for simple attribute-based sorts
        key_func: Custom key function for complex sorts (takes device, returns sortable value)
        default_value: Default value when attribute is None
        reverse_default: Whether to reverse sort by default (e.g., True for "highest first")
        secondary_attr: Secondary attribute for tie-breaking
    """

    name: str
    label: str
    attr: Optional[str] = None
    key_func: Optional[Callable[['adb_models.DeviceInfo'], Any]] = None
    default_value: Any = ""
    reverse_default: bool = False
    secondary_attr: Optional[str] = None

    def get_sort_key(
        self,
        device: 'adb_models.DeviceInfo',
        context: Optional[Dict[str, Callable]] = None,
    ) -> Any:
        """Extract the sort key from a device.

        Args:
            device: The device to extract key from
            context: Optional dict of context functions (e.g., get_status, is_selected)

        Returns:
            Sortable key value (possibly a tuple for multi-level sorting)
        """
        if self.key_func is not None:
            # Custom key function - may need context
            if context and self.name in context:
                primary = context[self.name](device)
            else:
                primary = self.key_func(device)
        elif self.attr:
            # Simple attribute access
            primary = getattr(device, self.attr, None)
            if primary is None:
                primary = self.default_value
        else:
            primary = self.default_value

        # Add secondary sort key if specified
        if self.secondary_attr:
            secondary = getattr(device, self.secondary_attr, None) or ""
            return (primary, secondary)

        return primary


class SortRegistry:
    """Registry for managing sort field configurations.

    This registry allows automatic extension of sort capabilities
    by registering new SortField configurations.
    """

    _instance: Optional['SortRegistry'] = None

    def __new__(cls) -> 'SortRegistry':
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._fields = {}
            cls._instance._register_builtin_fields()
        return cls._instance

    def _register_builtin_fields(self) -> None:
        """Register built-in sort fields based on DeviceInfo attributes."""
        builtin_fields = [
            # Basic device info
            SortField(
                name="name",
                label="Model Name",
                attr="device_model",
                default_value="",
            ),
            SortField(
                name="serial",
                label="Serial Number",
                attr="device_serial_num",
                default_value="",
            ),
            SortField(
                name="android",
                label="Android Version",
                attr="android_ver",
                default_value="",
            ),
            SortField(
                name="api",
                label="API Level",
                key_func=lambda d: int(d.android_api_level) if d.android_api_level and d.android_api_level.isdigit() else 0,
                default_value=0,
                reverse_default=True,  # Higher API first by default
            ),
            SortField(
                name="gms",
                label="GMS Version",
                attr="gms_version",
                default_value="",
            ),
            # Boolean state fields
            SortField(
                name="wifi",
                label="WiFi Status",
                key_func=lambda d: (not bool(d.wifi_is_on), d.device_model or ""),
                default_value=(True, ""),  # Off devices last
            ),
            SortField(
                name="bt",
                label="Bluetooth Status",
                key_func=lambda d: (not bool(d.bt_is_on), d.device_model or ""),
                default_value=(True, ""),  # Off devices last
            ),
            # Context-dependent fields (require external functions)
            SortField(
                name="status",
                label="Operation Status",
                key_func=None,  # Will use context
                default_value="idle",
            ),
            SortField(
                name="selected",
                label="Selection Status",
                key_func=None,  # Will use context
                default_value=False,
                reverse_default=True,  # Selected first
            ),
        ]

        for sort_field in builtin_fields:
            self.register(sort_field)

    def register(self, sort_field: SortField) -> None:
        """Register a new sort field.

        Args:
            field: The SortField configuration to register
        """
        self._fields[sort_field.name] = sort_field

    def unregister(self, name: str) -> bool:
        """Unregister a sort field by name.

        Args:
            name: The sort field name to remove

        Returns:
            True if removed, False if not found
        """
        if name in self._fields:
            del self._fields[name]
            return True
        return False

    def get(self, name: str) -> Optional[SortField]:
        """Get a sort field by name.

        Args:
            name: The sort field name

        Returns:
            SortField if found, None otherwise
        """
        return self._fields.get(name)

    def get_all(self) -> List[SortField]:
        """Get all registered sort fields.

        Returns:
            List of all SortField configurations
        """
        return list(self._fields.values())

    def get_names(self) -> List[str]:
        """Get all registered sort field names.

        Returns:
            List of sort field names
        """
        return list(self._fields.keys())

    def has(self, name: str) -> bool:
        """Check if a sort field is registered.

        Args:
            name: The sort field name

        Returns:
            True if registered, False otherwise
        """
        return name in self._fields


# Global singleton accessor
def get_sort_registry() -> SortRegistry:
    """Get the global sort registry instance."""
    return SortRegistry()


__all__ = ['SortField', 'SortRegistry', 'get_sort_registry']
