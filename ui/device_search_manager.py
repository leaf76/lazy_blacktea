"""Device search and filtering functionality for the device list."""

from difflib import SequenceMatcher
import re
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
