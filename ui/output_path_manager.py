"""Output path orchestration for WindowMain."""

from __future__ import annotations

from typing import Optional

from config.constants import PathConstants
from utils import common


class OutputPathManager:
    """Handle shared output path behaviour across the UI."""

    def __init__(self, parent_window, file_dialog_manager) -> None:
        self._window = parent_window
        self._file_dialog_manager = file_dialog_manager
        self._previous_primary_path: str = ''

    # ------------------------------------------------------------------
    # Path setters
    # ------------------------------------------------------------------
    def set_primary_output_path(
        self,
        path: str,
        *,
        sync_generation_if_following: bool = True,
        update_previous: bool = True,
    ) -> str:
        """Set the primary output path and optionally keep generation path in sync."""
        trimmed = path.strip()
        if not trimmed:
            return ''

        primary_edit = getattr(self._window, 'output_path_edit', None)
        if primary_edit is not None:
            primary_edit.setText(trimmed)

        if sync_generation_if_following:
            file_gen_edit = getattr(self._window, 'file_gen_output_path_edit', None)
            if file_gen_edit is not None:
                current = file_gen_edit.text().strip()
                if not current or current == self._previous_primary_path:
                    file_gen_edit.setText(trimmed)

        if update_previous:
            self._previous_primary_path = trimmed

        return trimmed

    def set_file_generation_output_path(self, path: str) -> str:
        """Set the dedicated file generation output path."""
        trimmed = path.strip()
        file_gen_edit = getattr(self._window, 'file_gen_output_path_edit', None)
        if file_gen_edit is not None:
            file_gen_edit.setText(trimmed)
        return trimmed

    # ------------------------------------------------------------------
    # Browsing helpers
    # ------------------------------------------------------------------
    def browse_primary_output_path(self) -> str:
        """Open directory picker for the primary output path."""
        directory = self._file_dialog_manager.select_directory(
            self._window,
            'Select Output Directory',
        )
        if not directory:
            return ''

        normalized = common.make_gen_dir_path(directory)
        return self.set_primary_output_path(normalized)

    def browse_file_generation_output_path(self) -> str:
        """Open directory picker for the file generation path."""
        directory = self._file_dialog_manager.select_directory(
            self._window,
            'Select File Generation Output Directory',
        )
        if not directory:
            return ''

        normalized = common.make_gen_dir_path(directory)
        self.set_file_generation_output_path(normalized)
        return normalized

    # ------------------------------------------------------------------
    # Accessors
    # ------------------------------------------------------------------
    def get_primary_output_path(self) -> str:
        """Return the active primary output path, initialising defaults if missing."""
        return self.ensure_primary_output_path()

    def ensure_primary_output_path(self) -> str:
        """Ensure a primary output path always exists."""
        primary_edit = getattr(self._window, 'output_path_edit', None)
        primary_value = primary_edit.text().strip() if primary_edit is not None else ''
        if primary_value:
            return primary_value

        fallback = self.get_file_generation_output_path(raw=True)
        if fallback:
            self.set_primary_output_path(
                fallback,
                sync_generation_if_following=False,
                update_previous=True,
            )
            return fallback

        default_dir = common.make_gen_dir_path(PathConstants.DEFAULT_OUTPUT_DIR)
        self.set_primary_output_path(
            default_dir,
            sync_generation_if_following=False,
            update_previous=True,
        )
        file_gen_edit = getattr(self._window, 'file_gen_output_path_edit', None)
        if file_gen_edit is not None and not file_gen_edit.text().strip():
            file_gen_edit.setText(default_dir)
        return default_dir

    def get_file_generation_output_path(self, *, raw: bool = False) -> str:
        """Return the file generation path or fall back to the primary path."""
        file_gen_edit = getattr(self._window, 'file_gen_output_path_edit', None)
        file_gen_value = file_gen_edit.text().strip() if file_gen_edit is not None else ''
        if file_gen_value:
            return file_gen_value

        if raw:
            return ''

        primary_edit = getattr(self._window, 'output_path_edit', None)
        return primary_edit.text().strip() if primary_edit is not None else ''

    def get_adb_tools_output_path(self) -> str:
        """Return the output path used by ADB tools features."""
        primary_edit = getattr(self._window, 'output_path_edit', None)
        return primary_edit.text().strip() if primary_edit is not None else ''

    # ------------------------------------------------------------------
    # Configuration helpers
    # ------------------------------------------------------------------
    def apply_legacy_paths(self, primary_path: Optional[str], file_gen_path: Optional[str]) -> None:
        """Restore paths from legacy configuration format."""
        primary = (primary_path or '').strip()
        file_gen = (file_gen_path or '').strip()

        if primary:
            self.set_primary_output_path(
                primary,
                sync_generation_if_following=not bool(file_gen),
                update_previous=True,
            )

        if file_gen:
            self.set_file_generation_output_path(file_gen)

        if not primary and file_gen:
            self.set_primary_output_path(
                file_gen,
                sync_generation_if_following=False,
                update_previous=True,
            )

    # ------------------------------------------------------------------
    # Diagnostics
    # ------------------------------------------------------------------
    def get_previous_primary_path(self) -> str:
        """Expose previous primary path for diagnostics/testing."""
        return self._previous_primary_path
