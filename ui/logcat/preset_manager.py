"""Preset manager for logcat filter presets.

Handles CRUD operations for filter presets stored in ~/.lazy_blacktea/presets/
and migration from legacy filter format.
"""

from pathlib import Path
from typing import List, Optional, Set
import json
import logging
import os
import re
import shutil
import tempfile
import time

from ui.logcat.filter_models import FilterPreset

logger = logging.getLogger(__name__)


class PresetManager:
    """Manage filter presets in ~/.lazy_blacktea/presets/

    Presets are stored as individual JSON files for easy management and editing.
    """

    PRESETS_DIR = "~/.lazy_blacktea/presets"
    LEGACY_FILTERS_FILE = "~/.lazy_blacktea_filters.json"

    def __init__(self) -> None:
        self._presets_dir = Path(self.PRESETS_DIR).expanduser()
        self._legacy_path = Path(self.LEGACY_FILTERS_FILE).expanduser()
        self._ensure_presets_dir()

    def _ensure_presets_dir(self) -> None:
        """Create presets directory if it doesn't exist."""
        try:
            self._presets_dir.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            logger.warning("Failed to create presets directory: %s", exc)

    def _preset_path(self, name: str) -> Path:
        """Get file path for a preset by name."""
        safe_name = self._sanitize_filename(name)
        return self._presets_dir / f"{safe_name}.json"

    @staticmethod
    def _sanitize_filename(name: str) -> str:
        """Sanitize preset name for use as filename."""
        safe = re.sub(r"[^\w\-_]", "_", name.strip())
        # Ensure non-empty and reasonable length
        return safe[:64] if safe else "unnamed"

    def list_presets(self) -> List[FilterPreset]:
        """List all available presets, sorted by name."""
        presets: List[FilterPreset] = []
        if not self._presets_dir.exists():
            return presets

        for path in self._presets_dir.glob("*.json"):
            try:
                preset = self._load_preset_file(path)
                if preset:
                    presets.append(preset)
            except Exception as exc:
                logger.warning("Failed to load preset %s: %s", path, exc)

        return sorted(presets, key=lambda p: p.name.lower())

    def _load_preset_file(self, path: Path) -> Optional[FilterPreset]:
        """Load a single preset from file."""
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return FilterPreset.from_dict(data)
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Failed to parse preset file %s: %s", path, exc)
            return None

    def save_preset(self, preset: FilterPreset) -> bool:
        """Save a preset to disk atomically. Returns True on success.

        Uses atomic write pattern: writes to temp file first, then renames.
        This prevents data loss if the process crashes during write.
        """
        try:
            preset.updated_at = time.time()
            path = self._preset_path(preset.name)
            content = json.dumps(preset.to_dict(), indent=2, ensure_ascii=False)

            # Write to temp file first, then atomically rename
            fd, tmp_path = tempfile.mkstemp(
                dir=str(self._presets_dir),
                suffix=".tmp",
                prefix="preset_",
            )
            tmp_path_obj = Path(tmp_path)
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    f.write(content)
                # Atomic replace across platforms (overwrites existing file)
                os.replace(str(tmp_path_obj), str(path))
            except (OSError, IOError):
                # Clean up temp file on failure
                try:
                    tmp_path_obj.unlink(missing_ok=True)
                except OSError:
                    pass
                raise

            logger.info("Saved preset: %s", preset.name)
            return True
        except (OSError, TypeError) as exc:
            logger.error("Failed to save preset %s: %s", preset.name, exc)
            return False

    def delete_preset(self, name: str) -> bool:
        """Delete a preset by name. Returns True if deleted."""
        try:
            path = self._preset_path(name)
            if path.exists():
                path.unlink()
                logger.info("Deleted preset: %s", name)
                return True
            return False
        except OSError as exc:
            logger.error("Failed to delete preset %s: %s", name, exc)
            return False

    def get_preset(self, name: str) -> Optional[FilterPreset]:
        """Get a preset by name, or None if not found."""
        path = self._preset_path(name)
        if path.exists():
            return self._load_preset_file(path)
        return None

    def preset_exists(self, name: str) -> bool:
        """Check if a preset with the given name exists."""
        return self._preset_path(name).exists()

    def migrate_legacy_filters(self) -> int:
        """Migrate old ~/.lazy_blacktea_filters.json to new preset format.

        Creates a "Migrated Filters" preset containing all patterns from
        the legacy file, then renames the legacy file to prevent re-migration.

        Returns:
            Number of patterns migrated.
        """
        if not self._legacy_path.exists():
            return 0

        try:
            with open(self._legacy_path, "r", encoding="utf-8") as f:
                legacy_data = json.load(f)

            if not isinstance(legacy_data, dict):
                logger.warning("Legacy filters file has unexpected format")
                return 0

            # Extract unique patterns from legacy format {key: pattern}
            patterns: List[str] = []
            seen: Set[str] = set()
            for value in legacy_data.values():
                if isinstance(value, str) and value.strip():
                    pattern = value.strip()
                    if pattern not in seen:
                        patterns.append(pattern)
                        seen.add(pattern)

            if not patterns:
                logger.info("No patterns found in legacy filters file")
                return 0

            # Create a "Migrated Filters" preset
            preset = FilterPreset(
                name="Migrated Filters",
                filters=patterns,
            )

            if self.save_preset(preset):
                # Rename legacy file to indicate migration complete
                backup_path = self._legacy_path.with_suffix(".json.migrated")
                try:
                    self._legacy_path.rename(backup_path)
                except OSError as exc:
                    logger.warning("Failed to rename legacy file: %s", exc)

                logger.info("Migrated %d patterns from legacy format", len(patterns))
                return len(patterns)

            return 0

        except (json.JSONDecodeError, OSError) as exc:
            logger.error("Failed to migrate legacy filters: %s", exc)
            return 0
