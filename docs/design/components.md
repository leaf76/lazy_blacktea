# Component Specs

Reusable UI building blocks. Every component references tokens defined in
`tokens.md`. Behavior is described as the contract that the PyQt6 implementation
(and any future port) must satisfy.

> **Status:** Phase 0 spec only. Phase 1 introduces matching QSS / Python APIs.

---

## Component checklist

- [Button](#button)
- [Icon Button](#icon-button)
- [Input (text)](#input)
- [Search Bar](#search-bar)
- [Chip / Filter Chip](#chip)
- [Selection Bar](#selection-bar)
- [Table / Device row](#table)
- [Sidebar Nav Item](#sidebar-nav-item)
- [Tab Bar (sub-tab)](#tab-bar)
- [Dialog (`AppDialog` shell)](#dialog)
- [Toast](#toast)
- [Status Pill / Badge](#status-pill)
- [Progress Bar / Spinner](#progress)
- [Empty State](#empty-state)
- [Command Palette item](#command-palette-item)
- [Inspector Section](#inspector-section)

---

## Button

Primary interactive control. Three variants by emphasis, three sizes.

| Variant | Background | Text | Border | Hover | Press |
| --- | --- | --- | --- | --- | --- |
| `primary` | `accent/primary` | `fg/inverse` | none | `accent/primary-hover` | `accent/primary-press` |
| `secondary` | `bg/surface` | `fg/primary` | `border/default` | `bg/hover` | `bg/active` |
| `ghost` | transparent | `fg/primary` | none | `bg/hover` | `bg/active` |
| `danger` | `accent/danger` | `fg/inverse` | none | darken 8% | darken 14% |
| `link` | transparent | `fg/link` | none | underline | — |

### Sizes

| Size | Height | Padding X | Font | Icon | Min width |
| --- | --- | --- | --- | --- | --- |
| `sm` | 28px | `space/3` (8) | `text/sm` | 14px | 64px |
| `md` (default) | 32px | `space/4` (12) | `text/md` | 16px | 80px |
| `lg` | 40px | `space/5` (16) | `text/lg` | 18px | 120px |

### States

- `:hover`, `:focus-visible` (2px `border/focus` ring with 2px offset),
  `:active`, `:disabled` (50% opacity, no hover).
- Loading: replace leading icon with spinner; label stays; disable click but keep
  focus ring.

### Anatomy

```
[ icon? ] [ label ] [ shortcut hint? ]
```

- Icon-only buttons → see [Icon Button](#icon-button).
- Shortcut hint uses `text/xs` + `font/mono`, color `fg/muted`, `space/2` gap.

### Don'ts

- No emoji inside button labels in the new design.
- No more than one `primary` button per visible region.
- Never combine `danger` with `link`.

---

## Icon Button

Square button for toolbar / row actions. Sizes `28×28`, `32×32`, `40×40`.

- Background `transparent` by default, `bg/hover` on hover.
- Tooltip is mandatory; describes the action verb.
- Pair with optional `aria-label` (Qt: `setAccessibleName`).
- Selected state: `bg/active` + `border/subtle`.

---

## Input

Text input, single line.

| Property | Value |
| --- | --- |
| Height | 32px |
| Padding | `0 space/4` |
| Border | `1px solid border/default` |
| Radius | `radius/sm` |
| Background | `bg/surface` |
| Font | `text/md` |
| Placeholder | `fg/muted` |
| Focus | `border/focus` 1px + 2px ring `border/focus @ 35%` |
| Invalid | `border/danger` (`accent/danger`) + helper text in `accent/danger` |
| Disabled | `bg/surface-alt`, `fg/muted` |

Slots: leading icon (16px, `space/3` from start), trailing icon, helper text
below. Helper text uses `text/sm`, `fg/muted` (or `accent/danger` when invalid).

Multi-line variant: same border + radius, min height 80px, monospace optional.

---

## Search Bar

Specialised input pinned at top of pane.

- Always shows leading `search` icon.
- Trailing `⌘K`-style hint (or `/` shortcut hint) when empty; clear (`✕`) when
  filled.
- Background `bg/surface`; sticky header uses `bg/canvas` with bottom
  `border/subtle`.
- Mini-DSL hint (logcat only): show inline tag chips when the user types
  `tag:`, `pid:`, `level:`. See `interaction.md`.

---

## Chip

Compact label with optional icon and dismiss button.

| Variant | Use |
| --- | --- |
| `neutral` | Default tag |
| `intent` | Reflects status (success / warning / danger / info) |
| `removable` | Has trailing `✕` |
| `selectable` (filter chip) | Toggle on/off |

Sizes:

- `sm`: height 22px, font `text/xs`, padding `0 space/3`.
- `md`: height 26px, font `text/sm`, padding `0 space/4`.

Selected filter chip: `tint/primary` background + `accent/primary` text +
`border/focus` border.

---

## Selection Bar

Sticky bar shown above tables when one or more rows are selected.

```
┌────────────────────────────────────────────────────────────┐
│ ✓ 3 selected     [Take screenshot] [Record] [Run shell]  ✕ │
└────────────────────────────────────────────────────────────┘
```

- Height 44px, `bg/elevated`, bottom `border/subtle`, `z/sticky`.
- Slide-down enter (`motion/normal`, `easing/decelerate`).
- Buttons: at most 4 primary actions + a `⋯` menu for the rest.
- Right side: total count `n / total` + `Clear` (`ghost` button).
- Disappears when count returns to 0.

---

## Table

Used for device list, app list, file browser.

### Layout

| Region | Height | Background |
| --- | --- | --- |
| Header | 36px | `bg/surface-alt` + bottom `border/subtle` |
| Row (cozy) | 40px | `bg/surface`, alt `bg/surface-alt` |
| Row (compact) | 32px | same |

- Column padding `0 space/4`.
- Column header: `text/sm`, `weight/medium`, `fg/secondary`, sortable shows
  caret on hover and active sort.
- Row hover: `bg/hover`. Row selected: `bg/active` + 2px left bar
  `accent/primary`.
- Multi-select via leading checkbox column (40px wide) + `Shift+Click` range.

### Device row anatomy (cozy)

```
[ ☐ ] [ ●status ] [ Pixel 7 (mono serial) ] [ Android 14 ] [ ▮▮▮ 78% ] [ ⋯ ]
```

- `●status` = 8px dot from §1.6 of tokens.md.
- Model name `weight/medium`, serial below in `text/mono-xs` `fg/muted` (only
  shown when row is expanded or in detail view to keep cozy density).
- Battery: 32px mini-bar + `%` text (mono).
- `⋯` opens row context menu (right-aligned, `z/dropdown`).

### Expanded detail row

Inline expansion (no modal) replicating `DeviceDetailPanel` content. Animates
height with `motion/normal`. Only one row may be expanded at a time unless the
user holds `Alt`.

---

## Sidebar Nav Item

Vertical list item in the left rail.

- Width 220px (expanded) / 56px (collapsed).
- Height 36px, padding `0 space/4`, `space/3` icon-label gap.
- Active: `bg/active` + 2px left bar `accent/primary`. Hover: `bg/hover`.
- Trailing badge for counts (e.g. `Tasks · 2`) using neutral chip.
- Collapsing animates width with `motion/slow`.

---

## Tab Bar

Sub-navigation **inside** a pane (not the main IA). Use sparingly; the main IA
is the sidebar.

- Underline style: 2px bottom `accent/primary` on active; inactive
  `fg/secondary`. No backgrounds.
- Height 36px.
- Avoid > 5 tabs; prefer Tools workspace's left rail when more.

---

## Dialog

`AppDialog` is the shared shell.

```
┌────────────────────────────────────────────┐
│ Title                                    ✕ │
│ Description (optional, fg/secondary)       │
├────────────────────────────────────────────┤
│                                            │
│ Body (scrollable, padding space/6)         │
│                                            │
├────────────────────────────────────────────┤
│ [ Destructive ]          [Cancel] [Primary]│
└────────────────────────────────────────────┘
```

- Min width 480px; max width 720px (use Preferences shell for wider).
- Background `bg/elevated`, radius `radius/lg`, `elevation/3`.
- Header: 56px, title `text/xl`, optional description in body.
- Footer: 60px; cancel/primary right-aligned, destructive left-aligned. Always
  close on `Esc`. `Enter` triggers primary unless focus is in a multi-line input.
- Backdrop `bg/scrim`. Click outside ≠ close (must use Cancel / `Esc`); prevents
  accidental dismissal of long forms.

---

## Toast

Short-lived feedback (3–6s).

- Anchored bottom-right, stack vertically with `space/3` gap.
- Width 320–420px, padding `space/4`.
- Variants: `info`, `success`, `warning`, `danger`. Each uses tint background +
  matching accent left bar (3px).
- Anatomy: `[icon] [title] [description?] [action?] [✕]`.
- Action button: `link` variant (e.g. "Open folder").
- Auto-dismiss: 4s default, 6s for `warning`, 8s for `danger`. Pauses on hover.

---

## Status Pill

Inline label for state.

- Height 22px, padding `0 space/3`, radius `radius/full`.
- Anatomy: `[●dot] [label]`.
- Background `tint/<intent>`, text `accent/<intent>` (use `weight/medium`).
- Examples: `Connected`, `Recording 02:14`, `Unauthorized`, `Throttled`.

---

## Progress

### Determinate bar

- Height 4px (inline) / 8px (page-level), radius `radius/full`.
- Track `bg/surface-alt`, fill `accent/primary` (or matching intent).
- Optional caption above: `Installing apk… 42 / 100 MB`.

### Indeterminate spinner

- 16px / 20px / 24px sizes. Stroke 2px, color `accent/primary`. 1.2s rotation,
  linear easing. Replace with static icon if "Reduce motion" is on.

### Stepper

- For multi-step task: 3–5 dots horizontally, `space/3` gap. Active dot
  `accent/primary`, others `border/default`.

---

## Empty State

Used for empty tables, no-search-results, no-devices.

```
        ╭──────╮
        │ icon │
        ╰──────╯
        Title (text/2xl, weight/semibold)
        Description (text/md, fg/secondary)
        [ Primary action ]
        Secondary link
```

- Vertical center, max width 360px text, padding `space/8`.
- Icon: 48px line illustration in `fg/muted`.
- Tone: explain the state in 1 sentence + give 1 next step.
- Examples:
  - **No devices** → "Connect a device or run `adb devices` to verify USB
    debugging." → primary `Refresh`, secondary link `Open ADB guide`.
  - **No logs match filters** → "Try removing a filter or clearing search." →
    primary `Clear filters`.

---

## Command Palette item

Row inside the `Ctrl+K` palette.

- Height 36px, padding `0 space/4`.
- Anatomy: `[icon] [primary label] [secondary label fg/muted] ............ [shortcut]`.
- Active row (keyboard): `bg/active`, left 2px `accent/primary`.
- Section headers: `text/xs`, `fg/muted`, `weight/medium`, all caps, padding
  `space/3 space/4`.

---

## Inspector Section

Collapsible section inside the right inspector pane.

- Header: 36px, padding `0 space/4`, caret on left, title `text/md`
  `weight/medium`, optional badge on right.
- Body padding `space/4`. Background follows pane (no extra fill).
- Multiple sections allowed; only one is collapsed/expanded by user click; state
  persists across sessions.

---

## State matrix (every interactive component)

Every component must define visuals for: `default`, `hover`, `focus-visible`,
`active`, `selected` (where relevant), `loading`, `disabled`, `error`. Phase 1
implementation uses a small QSS mixin per component to ensure coverage.

---

## Implementation notes (Phase 1)

- Base widget classes:
  - `ui/components/buttons.py::AppButton` (variant + size enum)
  - `ui/components/inputs.py::AppLineEdit`
  - `ui/components/chips.py::FilterChip` (already exists; align spec)
  - `ui/shell/dialog.py::AppDialog`
  - `ui/components/empty_state.py::EmptyState`
- All read tokens from `ui/design_tokens.py`; QSS lives in
  `ui/qss/<component>.qss` with `{{token}}` placeholders rendered at load.
- Existing widgets continue to work (legacy QSS path) until each is migrated;
  migration is tracked per Phase 3 ticket.
