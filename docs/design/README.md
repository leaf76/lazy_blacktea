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
| 2 | Shell refactor (`ui/shell/app_shell.py`), sidebar nav, inspector, command palette | implemented |
| 3 | Devices pane, Tools workspace, Logcat redesign, Tasks pane | implemented |
| 4 | `AppDialog` shell, Preferences merge, a11y sweep | partially implemented |

Phase 3 wires `WindowMain` into the real AppShell information architecture:
Devices, Tools, Logcat, Files, Apps, and Tasks are top-level panes, while the
console remains in a resizable host splitter below the shell. Tools now uses a
left-rail workspace for Overview, ADB Tools, Shell Commands, and Device Groups;
Files and Apps are promoted to first-class shell panes. Logcat is available as
an embedded pane through `LogcatViewerWidget`, while `LogcatWindow` remains as a
detached compatibility wrapper. The shell status bar is the active visual
surface for device/task/version/trace chips; the legacy `QStatusBar` API remains
available for existing progress and message calls.

Phase 4 now has the Preferences merge in place through a tabbed
`PreferencesDialog`. Appearance owns theme, UI scale, and density; existing
settings entries deep-link into Preferences sections; Updates exposes updater
preferences. The broader `AppDialog` replacement and full accessibility sweep
remain follow-up work.

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
