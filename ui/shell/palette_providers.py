"""Built-in palette providers used by the command palette.

Phase 2 ships two general-purpose providers and a registry helper. Domain
providers (devices, recent tasks, …) live in their own modules and register
themselves with the palette at runtime.

Providers
---------
* :class:`NavigationPaletteProvider` — turns ``AppShell`` panes into
  palette entries with ``Mod+N`` shortcut hints.
* :class:`StaticActionsPaletteProvider` — wraps a list of pre-declared
  actions (label + callable + optional shortcut/section).

Note: ``ui.shell.command_palette`` performs the scoring and filtering, so
providers only need to return their full entry list. Returning a fresh list
on every call lets providers reflect runtime state changes (selection,
permissions, …).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, List, Optional, Sequence

from ui.shell.command_palette import PaletteEntry, PaletteProvider


# ---------------------------------------------------------------------------
# Navigation provider
# ---------------------------------------------------------------------------


class NavigationPaletteProvider:
    """Palette entries that switch the active :class:`AppShell` pane."""

    SECTION = "Navigate"

    def __init__(self, app_shell, *, mod_label: str = "Ctrl") -> None:
        # Type-hint as ``Any`` to keep the cyclic import out; the protocol
        # we rely on is ``app_shell.pane_names()`` and ``set_active_pane``.
        self._shell = app_shell
        self._mod_label = mod_label

    def section_label(self) -> str:
        return self.SECTION

    def entries(self, query: str) -> Sequence[PaletteEntry]:
        result: List[PaletteEntry] = []
        for index, name in enumerate(self._shell.pane_names()):
            shortcut = f"{self._mod_label}+{index + 1}" if index < 9 else ""
            label = name.replace("_", " ").title()
            result.append(
                PaletteEntry(
                    title=label,
                    subtitle=f"Open {label} pane",
                    shortcut=shortcut,
                    section=self.SECTION,
                    invoke=self._make_invoker(name),
                    score_hint=1.0 if name == self._shell.active_pane() else 0.0,
                    keywords=("nav", "pane", name),
                )
            )
        return result

    def _make_invoker(self, name: str) -> Callable[[], None]:
        shell = self._shell

        def _invoke() -> None:
            shell.set_active_pane(name)

        return _invoke


# ---------------------------------------------------------------------------
# Static actions provider
# ---------------------------------------------------------------------------


@dataclass
class StaticPaletteAction:
    """Compact wrapper for declaring static palette actions."""

    title: str
    invoke: Callable[[], None]
    subtitle: str = ""
    shortcut: str = ""
    section: str = "Actions"
    keywords: Sequence[str] = ()


class StaticActionsPaletteProvider:
    """Hand-rolled provider that returns a stable list of actions."""

    def __init__(
        self,
        actions: Sequence[StaticPaletteAction],
        *,
        section_label: str = "Actions",
    ) -> None:
        self._actions = list(actions)
        self._section_label = section_label

    def section_label(self) -> str:
        return self._section_label

    def add_action(self, action: StaticPaletteAction) -> None:
        self._actions.append(action)

    def remove_action(self, title: str) -> bool:
        for index, action in enumerate(self._actions):
            if action.title == title:
                del self._actions[index]
                return True
        return False

    def entries(self, query: str) -> Sequence[PaletteEntry]:
        return [
            PaletteEntry(
                title=action.title,
                subtitle=action.subtitle,
                shortcut=action.shortcut,
                section=action.section or self._section_label,
                invoke=action.invoke,
                keywords=action.keywords,
            )
            for action in self._actions
        ]


# ---------------------------------------------------------------------------
# Convenience builder
# ---------------------------------------------------------------------------


def build_default_palette_providers(
    *,
    app_shell=None,
    extra_actions: Optional[Sequence[StaticPaletteAction]] = None,
    mod_label: str = "Ctrl",
) -> List[PaletteProvider]:
    """Construct the default provider set used by the redesigned shell."""

    providers: List[PaletteProvider] = []
    if app_shell is not None:
        providers.append(NavigationPaletteProvider(app_shell, mod_label=mod_label))
    if extra_actions:
        providers.append(StaticActionsPaletteProvider(extra_actions))
    return providers


__all__ = [
    "NavigationPaletteProvider",
    "StaticActionsPaletteProvider",
    "StaticPaletteAction",
    "build_default_palette_providers",
]
