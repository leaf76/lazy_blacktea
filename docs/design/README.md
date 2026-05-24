# Lazy Blacktea Design System

The single source of truth for the redesigned Lazy Blacktea UX.

## Documents

| File | Scope |
| --- | --- |
| [`tokens.md`](tokens.md) | Color, typography, spacing, radius, elevation, motion, z-index |
| [`components.md`](components.md) | Reusable widgets (button, input, table, dialog, toast, …) |
| [`screens.md`](screens.md) | App shell + per-pane wireframes (Devices, Tools, Logcat, Files, Tasks, Preferences) |
| [`interaction.md`](interaction.md) | Keyboard model, command palette, async state machine, accessibility |

## Status & roadmap

| Phase | Deliverable | Status |
| --- | --- | --- |
| **0** | Design spec (this folder) | **Implemented as baseline spec** |
| 1 | `ui/design_tokens.py` + external `ui/qss/*.qss` + SVG icon set | implemented |
| 2 | Shell refactor (`ui/shell/app_shell.py`), sidebar nav, inspector, command palette | partially wired |
| 3 | Devices pane, Tools workspace, Logcat redesign, Tasks pane | not started |
| 4 | `AppDialog` shell, Preferences merge, a11y sweep | not started |

Phase 2 is currently running in compatibility mode: `WindowMain` installs
`AppShell` around the existing device/tools/console workspace, registers the
`Ctrl+K` command palette, and keeps the legacy `QMainWindow` status bar as the
active status surface. Full top-level pane splitting for Overview, ADB Tools,
Shell Commands, Device Files, Apps, and Tasks remains Phase 3 work.

## Design principles

1. **Density over decoration.** This is a developer tool used for hours; trade
   pretty for legible.
2. **Status before storytelling.** Always show what's happening (devices,
   tasks, traces) without forcing the user to dig.
3. **Keyboard-first.** Every action has a shortcut; the command palette is the
   primary discovery surface.
4. **Ask once, remember forever.** Selection, density, theme, and last-pane
   persist across launches.
5. **No magic strings.** All visual values come from tokens; all status comes
   from a defined state machine.
6. **Technology-neutral.** Specs use hex / px / ms so the Rust port can adopt
   the same language verbatim.

## Working with the spec

- Editing tokens: update `tokens.md`, then update `ui/design_tokens.py` and the
  matching regression tests in the same change.
- Adding a component: add a section to `components.md` covering anatomy,
  variants, sizes, states, do/don't, and implementation notes.
- New screens: prefer ASCII wireframes inline with `screens.md` so reviews stay
  in version control.

## Glossary

- **Pane** — A primary content area (Devices, Tools, Logcat, …).
- **Inspector** — The right-side collapsible panel.
- **Sidebar** — The left navigation rail.
- **App shell** — Title bar + sidebar + primary pane + inspector + status bar.
- **Density** — Spacing/font multiplier preference (`compact` / `cozy` /
  `comfortable`).
- **Trace ID** — Correlation ID from `utils.common.trace_id_scope`, surfaced in
  the status bar and Tasks pane.
