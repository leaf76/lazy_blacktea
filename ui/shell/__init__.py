"""Application shell package — Phase 2 of the UI/UX redesign.

Exposes the new layout container, status bar, and command palette as
standalone components. Each one is independently testable and may be wired
into ``WindowMain`` incrementally.

Public surface (kept intentionally small):

* :class:`AppShell` — sidebar + primary pane + collapsible inspector +
  custom status bar layout container.
* :class:`AppStatusBar` — chip-based status bar with click / tooltip support.
* :class:`CommandPalette` — modal command palette dialog (``Ctrl+K``) with
  pluggable :class:`PaletteProvider` registry.
* :class:`PaletteEntry` / :class:`PaletteProvider` — palette result contracts.
* :func:`build_default_palette_providers` — wires built-in nav / actions /
  recent providers used by the redesign.
"""

from ui.shell.app_shell import AppShell, AppShellSignals
from ui.shell.command_palette import (
    CommandPalette,
    PaletteEntry,
    PaletteProvider,
)
from ui.shell.palette_providers import (
    NavigationPaletteProvider,
    StaticActionsPaletteProvider,
    build_default_palette_providers,
)
from ui.shell.status_bar import AppStatusBar, StatusChipIntent

__all__ = [
    "AppShell",
    "AppShellSignals",
    "AppStatusBar",
    "CommandPalette",
    "NavigationPaletteProvider",
    "PaletteEntry",
    "PaletteProvider",
    "StaticActionsPaletteProvider",
    "StatusChipIntent",
    "build_default_palette_providers",
]
