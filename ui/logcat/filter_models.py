"""Data models for logcat filter management.

Provides dataclasses for filter patterns, presets, and runtime filter state.
"""

from dataclasses import dataclass, field
from typing import List, Optional
import re
import time


@dataclass
class FilterPattern:
    """Single filter pattern with metadata."""

    pattern: str
    created_at: float = field(default_factory=time.time)

    def is_valid_regex(self) -> bool:
        """Check if pattern compiles as valid regex."""
        try:
            re.compile(self.pattern, re.IGNORECASE)
            return True
        except re.error:
            return False

    def compile(self) -> Optional[re.Pattern[str]]:
        """Compile and return the regex pattern, or None if invalid."""
        try:
            return re.compile(self.pattern, re.IGNORECASE)
        except re.error:
            return None


@dataclass
class FilterPreset:
    """Named collection of filter patterns for persistence.

    Stored as JSON files in ~/.lazy_blacktea/presets/{name}.json
    """

    name: str
    filters: List[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        """Serialize preset to dictionary for JSON storage."""
        return {
            "name": self.name,
            "filters": self.filters,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "FilterPreset":
        """Deserialize preset from dictionary."""
        return cls(
            name=data.get("name", ""),
            filters=data.get("filters", []),
            created_at=data.get("created_at", time.time()),
            updated_at=data.get("updated_at", time.time()),
        )

    def is_empty(self) -> bool:
        """Check if preset has no filters."""
        return len(self.filters) == 0


@dataclass
class ActiveFilterState:
    """Runtime state for currently applied filters.

    Represents the three-level filter architecture:
    - Level 1: live_pattern (real-time input)
    - Level 2: active_patterns (applied filters)
    - Level 3: Presets are stored in PresetManager, loaded into active_patterns
    """

    live_pattern: Optional[str] = None
    active_patterns: List[str] = field(default_factory=list)

    def all_patterns(self) -> List[str]:
        """Get combined list of live + active patterns for filtering."""
        patterns = list(self.active_patterns)
        if self.live_pattern and self.live_pattern.strip():
            patterns.insert(0, self.live_pattern.strip())
        return patterns

    def is_empty(self) -> bool:
        """Check if no filters are active."""
        return not self.live_pattern and not self.active_patterns

    def add_pattern(self, pattern: str) -> bool:
        """Add a pattern to active filters. Returns True if added."""
        pattern = pattern.strip()
        if not pattern:
            return False
        if pattern in self.active_patterns:
            return False
        self.active_patterns.append(pattern)
        return True

    def remove_pattern(self, pattern: str) -> bool:
        """Remove a pattern from active filters. Returns True if removed."""
        pattern = pattern.strip()
        if pattern in self.active_patterns:
            self.active_patterns.remove(pattern)
            return True
        return False

    def clear(self) -> None:
        """Clear all active filters (keeps live pattern)."""
        self.active_patterns.clear()

    def clear_all(self) -> None:
        """Clear all filters including live pattern."""
        self.live_pattern = None
        self.active_patterns.clear()

    def load_from_preset(self, preset: FilterPreset) -> None:
        """Load filters from a preset, replacing current active filters."""
        self.active_patterns = list(preset.filters)

    def to_preset(self, name: str) -> FilterPreset:
        """Create a preset from current active filters."""
        return FilterPreset(
            name=name,
            filters=list(self.active_patterns),
        )
