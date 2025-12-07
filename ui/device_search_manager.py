"""Device search and filtering functionality for the device list."""

from difflib import SequenceMatcher
import re
from typing import Any, Callable, List, Dict, Optional, Tuple
from utils import adb_models
from ui.sort_registry import get_sort_registry, SortField


class DeviceSearchManager:
    """Manages device search, filtering, and sorting operations."""

    def __init__(self, main_window=None):
        self.main_window = main_window
        self.current_search_text = ""
        self.current_sort_mode = "name"

    def fuzzy_match_score(self, query: str, text: str) -> float:
        """Calculate fuzzy match score between query and text.
        Returns a score between 0 (no match) and 1 (perfect match).
        The algorithm combines substring, token, acronym and sequence
        similarity to better tolerate permutations and minor typos.
        """
        if not query:
            return 1.0

        if not text:
            return 0.0

        normalized_query = query.lower().strip()
        normalized_text = text.lower()

        if not normalized_query:
            return 1.0

        if normalized_query == normalized_text:
            return 1.0

        token_pattern = re.compile(r"[^a-z0-9]+")

        def tokenize(value: str) -> List[str]:
            return [token for token in token_pattern.split(value) if token]

        def build_acronym(tokens: List[str]) -> str:
            pieces: List[str] = []
            for token in tokens:
                if not token:
                    continue
                head = token[0]
                digits = "".join(ch for ch in token if ch.isdigit())
                if head.isdigit():
                    pieces.append(token)
                else:
                    pieces.append(f"{head}{digits}")
            return "".join(pieces)

        query_tokens = tokenize(normalized_query)
        text_tokens = tokenize(normalized_text)

        collapsed_query = "".join(query_tokens)
        collapsed_text = "".join(text_tokens)

        scores = []

        # Exact substring match gets the highest priority with positional bonus
        if normalized_query in normalized_text:
            position = normalized_text.find(normalized_query)
            coverage = len(normalized_query) / len(normalized_text)
            start_bonus = 0.1 if position == 0 else 0.0
            scores.append(min(0.85 + (coverage * 0.1) + start_bonus, 1.0))

        # Collapsed (alphanumeric only) substring helps with abbreviations
        if collapsed_query and collapsed_query in collapsed_text:
            position = collapsed_text.find(collapsed_query)
            coverage = len(collapsed_query) / len(collapsed_text)
            start_bonus = 0.05 if position == 0 else 0.0
            scores.append(min(0.8 + (coverage * 0.15) + start_bonus, 0.98))

        # Token coverage: ensure all query tokens appear regardless of order
        if query_tokens:
            token_hits = sum(1 for token in query_tokens if token in text_tokens)
            if token_hits:
                token_ratio = token_hits / len(query_tokens)
                coverage = min(len(query_tokens) / max(len(text_tokens), 1), 1.0)
                scores.append(0.5 + ((token_ratio ** 2) * 0.35) + (coverage * 0.05))

        # All query tokens present (permutation match)
        if query_tokens and text_tokens:
            if set(query_tokens).issubset(set(text_tokens)):
                scores.append(0.85)

        # Acronym match (e.g., sgs23 -> Samsung Galaxy S23)
        if collapsed_query and text_tokens:
            acronym = build_acronym(text_tokens)
            if collapsed_query in acronym:
                coverage = len(collapsed_query) / len(acronym)
                scores.append(0.75 + coverage * 0.1)

        # Sequence similarity for general fuzzy matching / typos
        seq_similarity = SequenceMatcher(None, normalized_query, normalized_text).ratio()
        if seq_similarity >= 0.2:
            scores.append(seq_similarity * 0.75)

        # Partial ratio to capture best window alignment
        partial_similarity = self._partial_ratio(normalized_query, normalized_text)
        shortest_length = min(len(normalized_query), len(normalized_text))
        if shortest_length >= 2 and partial_similarity >= 0.7:
            scores.append(partial_similarity * 0.85)

        if not scores:
            return 0.0

        best_score = max(scores)

        # Short queries can easily match noise; dampen weak evidence
        if len(normalized_query) <= 2 and best_score < 0.6:
            best_score *= 0.5

        if best_score < 0.3:
            best_score *= 0.5

        return max(0.0, min(best_score, 1.0))

    @staticmethod
    def _partial_ratio(text_a: str, text_b: str) -> float:
        """Compute a simplified partial ratio between two strings."""
        if not text_a or not text_b:
            return 0.0

        shorter, longer = (text_a, text_b) if len(text_a) <= len(text_b) else (text_b, text_a)

        if not shorter:
            return 0.0

        if shorter in longer:
            return 1.0

        matcher = SequenceMatcher(None)
        best_ratio = 0.0

        for idx in range(len(longer) - len(shorter) + 1):
            window = longer[idx : idx + len(shorter)]
            matcher.set_seqs(shorter, window)
            ratio = matcher.ratio()
            if ratio > best_ratio:
                best_ratio = ratio
                if best_ratio >= 0.99:
                    break

        return best_ratio

    def match_device(self, device: adb_models.DeviceInfo, query: str) -> float:
        """Calculate match score for a device against search query."""
        if not query:
            return 1.0

        # Prepare searchable fields with priorities
        # Higher priority fields get better scoring
        high_priority_fields = [
            # Primary device info - most important
            device.device_model,
            device.device_serial_num,
        ]

        medium_priority_fields = [
            # Brand and version info - only if not loading
            getattr(device, 'device_brand', ''),
        ]

        # Only add android version if it's available and not unknown
        if device.android_ver and device.android_ver not in [None, 'Unknown', '加載中...', 'Loading...']:
            medium_priority_fields.extend([
                device.android_ver,
                f"android {device.android_ver}",
            ])

        status_fields = []
        # Only add WiFi/Bluetooth status if loaded (not None)
        if device.wifi_is_on is not None:
            status_fields.extend([
                "wifi on" if device.wifi_is_on else "wifi off",
            ])
        if device.bt_is_on is not None:
            status_fields.extend([
                "bluetooth on" if device.bt_is_on else "bluetooth off",
                "bt on" if device.bt_is_on else "bt off",
            ])

        # Always include operation and selection status
        status_fields.extend([
            self._get_device_operation_status(device.device_serial_num) or "idle",
            "selected" if self._is_device_selected(device.device_serial_num) else "unselected",
            "recording" if self._get_device_recording_status(device.device_serial_num) else "",
        ])

        version_fields = []
        # Only add version fields if available and not unknown
        if device.android_api_level and device.android_api_level not in [None, 'Unknown', '加載中...', 'Loading...']:
            version_fields.extend([
                f"api {device.android_api_level}",
                f"android api {device.android_api_level}",
            ])
        if (device.gms_version and device.gms_version not in [None, 'N/A', 'Unknown', '加載中...', 'Loading...']):
            version_fields.extend([
                device.gms_version,
                f"gms {device.gms_version}",
            ])

        max_score = 0.0

        # Check high priority fields first
        for field in high_priority_fields:
            if field and str(field).strip():
                score = self.fuzzy_match_score(query, str(field))
                if score > 0.8:  # Strong match in high priority field
                    max_score = max(max_score, score)

        # Check medium priority fields
        for field in medium_priority_fields:
            if field and str(field).strip():
                score = self.fuzzy_match_score(query, str(field))
                if score > 0.7:  # Good match in medium priority field
                    max_score = max(max_score, score * 0.9)  # Slightly lower weight

        # Check status fields (need high accuracy)
        for field in status_fields:
            if field and str(field).strip():
                score = self.fuzzy_match_score(query, str(field))
                if score > 0.85:  # Only accept very good matches for status
                    max_score = max(max_score, score)

        # Check version fields (need exact matches)
        for field in version_fields:
            if field and str(field).strip():
                score = self.fuzzy_match_score(query, str(field))
                if score > 0.8:  # Only accept strong matches for versions
                    max_score = max(max_score, score)

        return max_score

    def filter_devices(self, devices: List[adb_models.DeviceInfo], query: str) -> List[Tuple[adb_models.DeviceInfo, float]]:
        """Filter devices by search query and return with match scores."""
        if not query:
            return [(device, 1.0) for device in devices]

        device_scores = []
        for device in devices:
            score = self.match_device(device, query)
            if score > 0:
                device_scores.append((device, score))

        # Sort by score (highest first)
        device_scores.sort(key=lambda x: x[1], reverse=True)
        return device_scores

    def sort_devices(self, devices: List[adb_models.DeviceInfo], sort_mode: str) -> List[adb_models.DeviceInfo]:
        """Sort devices by the specified mode using the sort registry.

        The sort registry allows automatic extension of sort capabilities.
        New sort fields can be registered without modifying this method.

        Args:
            devices: List of devices to sort
            sort_mode: Sort mode name, optionally with ':desc' or ':asc' suffix

        Returns:
            Sorted list of devices
        """
        if not devices:
            return devices

        # Parse sort mode and direction
        explicit_direction = False
        descending = False
        if sort_mode and ':' in sort_mode:
            base_mode, direction = sort_mode.split(':', 1)
            sort_mode = base_mode
            explicit_direction = True
            descending = direction.lower().startswith('desc')

        # Get sort field from registry
        registry = get_sort_registry()
        sort_field = registry.get(sort_mode)

        if sort_field is None:
            # Unknown sort mode, return unsorted
            return devices

        # Build context for context-dependent sort fields
        context = self._build_sort_context()

        # Create sort key function
        def get_key(device: adb_models.DeviceInfo) -> Any:
            return sort_field.get_sort_key(device, context)

        # Determine final sort direction
        # If explicit direction specified, use it; otherwise use field's default
        reverse = descending if explicit_direction else sort_field.reverse_default

        return sorted(devices, key=get_key, reverse=reverse)

    def _build_sort_context(self) -> Dict[str, Callable]:
        """Build context dictionary for context-dependent sort fields.

        Returns:
            Dictionary mapping sort field names to context functions
        """
        return {
            'status': lambda d: self._get_device_operation_status(d.device_serial_num) or "idle",
            'selected': lambda d: self._is_device_selected(d.device_serial_num),
        }

    def get_available_sort_modes(self) -> List[Dict[str, str]]:
        """Get list of available sort modes from the registry.

        Returns:
            List of dicts with 'name' and 'label' keys
        """
        registry = get_sort_registry()
        return [
            {'name': field.name, 'label': field.label}
            for field in registry.get_all()
        ]

    def register_sort_field(self, sort_field: SortField) -> None:
        """Register a custom sort field.

        Args:
            field: SortField configuration to register
        """
        registry = get_sort_registry()
        registry.register(sort_field)

    def search_and_sort_devices(self, devices: List[adb_models.DeviceInfo],
                              query: str = None, sort_mode: str = None) -> List[adb_models.DeviceInfo]:
        """Apply search filtering and sorting to device list."""
        if query is None:
            query = self.current_search_text
        if sort_mode is None:
            sort_mode = self.current_sort_mode

        # Update current state
        self.current_search_text = query
        self.current_sort_mode = sort_mode

        # Filter by search query
        if query:
            device_scores = self.filter_devices(devices, query)
            filtered_devices = [device for device, score in device_scores]
        else:
            filtered_devices = devices

        # Sort the filtered results
        return self.sort_devices(filtered_devices, sort_mode)

    def _get_device_operation_status(self, device_serial: str) -> str:
        """Get device operation status from main window."""
        if self.main_window and hasattr(self.main_window, '_get_device_operation_status'):
            return self.main_window._get_device_operation_status(device_serial)
        return None

    def _get_device_recording_status(self, device_serial: str) -> str:
        """Get device recording status from main window."""
        if self.main_window and hasattr(self.main_window, '_get_device_recording_status'):
            return self.main_window._get_device_recording_status(device_serial)
        return ""

    def _is_device_selected(self, device_serial: str) -> bool:
        """Check if device is selected from main window."""
        if self.main_window and hasattr(self.main_window, 'device_selection_manager'):
            selected = self.main_window.device_selection_manager.get_selected_serials()
            return device_serial in selected
        return False

    def set_search_text(self, text: str):
        """Set the current search text."""
        self.current_search_text = text

    def set_sort_mode(self, mode: str):
        """Set the current sort mode."""
        self.current_sort_mode = mode

    def get_search_text(self) -> str:
        """Get the current search text."""
        return self.current_search_text

    def get_sort_mode(self) -> str:
        """Get the current sort mode."""
        return self.current_sort_mode

    # ------------------------------------------------------------------
    # Quick filter chip support
    # ------------------------------------------------------------------
    def set_filter(self, name: str, value: Any) -> None:
        """Set a quick filter value.

        Args:
            name: Filter name ('wifi', 'bt', 'selected', 'recording', 'api')
            value: Filter value (True/False for toggle, int for API level, None to clear)
        """
        if not hasattr(self, 'active_filters'):
            self.active_filters: Dict[str, Any] = {}

        if value is None:
            self.active_filters.pop(name, None)
        else:
            self.active_filters[name] = value

    def set_filters(self, filters: Dict[str, Any]) -> None:
        """Set multiple filters at once."""
        if not hasattr(self, 'active_filters'):
            self.active_filters = {}
        self.active_filters = {k: v for k, v in filters.items() if v is not None}

    def clear_filters(self) -> None:
        """Clear all quick filters."""
        if hasattr(self, 'active_filters'):
            self.active_filters.clear()

    def get_active_filters(self) -> Dict[str, Any]:
        """Get currently active filters."""
        if not hasattr(self, 'active_filters'):
            self.active_filters = {}
        return dict(self.active_filters)

    def apply_filters(self, devices: List[adb_models.DeviceInfo]) -> List[adb_models.DeviceInfo]:
        """Apply quick filters to device list.

        Args:
            devices: List of devices to filter

        Returns:
            Filtered list of devices
        """
        if not hasattr(self, 'active_filters') or not self.active_filters:
            return devices

        result = []
        for device in devices:
            if self._device_matches_filters(device):
                result.append(device)
        return result

    def _device_matches_filters(self, device: adb_models.DeviceInfo) -> bool:
        """Check if a device matches all active filters."""
        if not hasattr(self, 'active_filters'):
            return True

        for name, value in self.active_filters.items():
            if value is None:
                continue

            if name == 'wifi':
                if device.wifi_is_on != value:
                    return False
            elif name == 'bt':
                if device.bt_is_on != value:
                    return False
            elif name == 'selected':
                if value and not self._is_device_selected(device.device_serial_num):
                    return False
            elif name == 'recording':
                if value:
                    status = self._get_device_recording_status(device.device_serial_num)
                    if not status:
                        return False
            elif name == 'api':
                try:
                    api_level = int(device.android_api_level or 0)
                    if api_level < value:
                        return False
                except (ValueError, TypeError):
                    return False

        return True

    def search_filter_and_sort_devices(
        self,
        devices: List[adb_models.DeviceInfo],
        query: str = None,
        sort_mode: str = None,
    ) -> List[adb_models.DeviceInfo]:
        """Apply search, quick filters, and sorting to device list.

        This is an enhanced version of search_and_sort_devices that also
        applies quick filters from filter chips.
        """
        if query is None:
            query = self.current_search_text
        if sort_mode is None:
            sort_mode = self.current_sort_mode

        self.current_search_text = query
        self.current_sort_mode = sort_mode

        # Step 1: Apply quick filters
        filtered_devices = self.apply_filters(devices)

        # Step 2: Apply text search
        if query:
            device_scores = self.filter_devices(filtered_devices, query)
            filtered_devices = [device for device, score in device_scores]

        # Step 3: Sort the results
        return self.sort_devices(filtered_devices, sort_mode)
