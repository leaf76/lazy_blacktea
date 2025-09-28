"""Device search and filtering functionality for the device list."""

from typing import List, Dict, Tuple
from utils import adb_models


class DeviceSearchManager:
    """Manages device search, filtering, and sorting operations."""

    def __init__(self, main_window=None):
        self.main_window = main_window
        self.current_search_text = ""
        self.current_sort_mode = "name"

    def fuzzy_match_score(self, query: str, text: str) -> float:
        """Calculate fuzzy match score between query and text.
        Returns a score between 0 (no match) and 1 (perfect match).
        """
        if not query:
            return 1.0

        if not text:
            return 0.0

        query = query.lower().strip()
        text = text.lower()

        # Exact substring match gets highest score
        if query in text:
            # Perfect match for equal strings
            if query == text:
                return 1.0
            # High score for substring matches, better for shorter text
            position_factor = 1.0 - (text.find(query) / len(text)) if len(text) > 0 else 1.0
            length_factor = len(query) / len(text) if len(text) > 0 else 0.0
            return 0.8 + (position_factor * 0.1) + (length_factor * 0.1)

        # For non-substring matches, use character-by-character matching
        query_chars = list(query)
        text_chars = list(text)
        matches = 0
        text_index = 0

        # Count sequential character matches
        for query_char in query_chars:
            found = False
            # Find the character in remaining text
            for i in range(text_index, len(text_chars)):
                if text_chars[i] == query_char:
                    matches += 1
                    text_index = i + 1
                    found = True
                    break

            # If we can't find a character, this is a poor match
            if not found:
                break

        # Score based on how many characters matched
        if matches == 0:
            return 0.0

        # Calculate score with emphasis on match completeness
        char_ratio = matches / len(query)  # How much of query was matched

        # Only give partial score if we matched most of the query
        if char_ratio < 0.9:  # Stricter threshold
            return char_ratio * 0.2  # Even lower score for poor matches
        else:
            # Better score for good character matches
            density_factor = matches / len(text) if len(text) > 0 else 0.0
            return char_ratio * 0.6 + density_factor * 0.2

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
        """Sort devices by the specified mode."""
        descending = False
        if sort_mode and ':' in sort_mode:
            base_mode, direction = sort_mode.split(':', 1)
            sort_mode = base_mode
            descending = direction.lower().startswith('desc')

        if sort_mode == "name":
            result = sorted(devices, key=lambda d: d.device_model or "")
        elif sort_mode == "serial":
            result = sorted(devices, key=lambda d: d.device_serial_num or "")
        elif sort_mode == "status":
            result = sorted(devices, key=lambda d: self._get_device_operation_status(d.device_serial_num) or "idle")
        elif sort_mode == "selected":
            result = sorted(devices, key=lambda d: not self._is_device_selected(d.device_serial_num))
        elif sort_mode == "wifi":
            result = sorted(
                devices,
                key=lambda d: (
                    not bool(d.wifi_is_on),
                    d.device_model or "",
                ),
            )
        elif sort_mode == "bt":
            result = sorted(
                devices,
                key=lambda d: (
                    not bool(d.bt_is_on),
                    d.device_model or "",
                ),
            )
        else:
            result = devices

        if descending:
            return list(reversed(result))
        return result

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
