# Design Tokens

Source of truth for all visual primitives in Lazy Blacktea. Values are technology-neutral
(hex / px / ms) so the same tokens apply to the PyQt6 app and any future Rust / QML port.

> **Status:** Phase 0 deliverable. Not yet wired into code. See
> `docs/design/README.md` for the redesign overview.

## Conventions

- **Naming:** `<category>/<role>` (e.g. `bg/canvas`, `accent/danger`). The slash maps
  to `_` when used as a Python identifier (`BG_CANVAS`).
- **Theme:** Every token has a `light` and `dark` value. Dark is the **primary**
  theme; light is fully supported.
- **Units:** Colors in lowercase 6-digit hex (alpha as `rgba()` only when required).
  Spacing, radius, and font size in `px`. Motion in `ms`.
- **Density:** Tokens are calibrated for the default `cozy` density. `compact`
  multiplies spacing by `0.75` and font scale by `0.92`; `comfortable` multiplies
  spacing by `1.25`.

---

## 1. Color

### 1.1 Surfaces

| Token | Light | Dark | Usage |
| --- | --- | --- | --- |
| `bg/canvas` | `#F7F8FA` | `#0E1116` | App window background |
| `bg/surface` | `#FFFFFF` | `#161A22` | Panel, sidebar, table |
| `bg/surface-alt` | `#F1F3F7` | `#1B2030` | Zebra rows, nested groups |
| `bg/elevated` | `#FFFFFF` | `#1F2535` | Dialog, popover, command palette |
| `bg/hover` | `rgba(15, 23, 42, 0.04)` | `rgba(255, 255, 255, 0.06)` | Hover state |
| `bg/active` | `rgba(15, 23, 42, 0.08)` | `rgba(255, 255, 255, 0.10)` | Pressed / selected row |
| `bg/scrim` | `rgba(15, 23, 42, 0.45)` | `rgba(0, 0, 0, 0.55)` | Modal backdrop |

### 1.2 Borders

| Token | Light | Dark | Usage |
| --- | --- | --- | --- |
| `border/subtle` | `#E4E7ED` | `#262C3A` | Default separators |
| `border/default` | `#D2D7E0` | `#303749` | Inputs, cards |
| `border/strong` | `#9AA3B5` | `#4A5468` | Focus ring base |
| `border/focus` | `#2D6CDF` | `#5B9DFF` | Active focus (2px outline) |

### 1.3 Foreground (text & icons)

| Token | Light | Dark | Usage |
| --- | --- | --- | --- |
| `fg/primary` | `#111827` | `#E6E9F2` | Body text, table data |
| `fg/secondary` | `#475569` | `#A8B0C2` | Sub-headings, helper |
| `fg/muted` | `#6B7280` | `#7B8497` | Hints, disabled labels |
| `fg/inverse` | `#FFFFFF` | `#0E1116` | Text on accent fills |
| `fg/link` | `#2D6CDF` | `#5B9DFF` | Hyperlinks |

### 1.4 Accents (intent)

| Token | Light | Dark | Usage |
| --- | --- | --- | --- |
| `accent/primary` | `#2D6CDF` | `#5B9DFF` | Primary CTA, focus |
| `accent/primary-hover` | `#245AC0` | `#7AB1FF` | Primary hover |
| `accent/primary-press` | `#1D4DA3` | `#3F86E8` | Primary pressed |
| `accent/success` | `#1F8A4C` | `#3DD27D` | Connected, completed |
| `accent/warning` | `#B7791F` | `#F0B454` | Recording, throttled |
| `accent/danger` | `#C8341A` | `#F26E5C` | Destructive, error |
| `accent/info` | `#1F6FA8` | `#5BB8E8` | Logcat info, hint |

### 1.5 Surface tints (subtle backgrounds for state)

Each accent has a 12% alpha tint over `bg/surface` for state pills and banners.

| Token | Light | Dark |
| --- | --- | --- |
| `tint/primary` | `rgba(45, 108, 223, 0.10)` | `rgba(91, 157, 255, 0.16)` |
| `tint/success` | `rgba(31, 138, 76, 0.10)` | `rgba(61, 210, 125, 0.16)` |
| `tint/warning` | `rgba(183, 121, 31, 0.12)` | `rgba(240, 180, 84, 0.18)` |
| `tint/danger` | `rgba(200, 52, 26, 0.10)` | `rgba(242, 110, 92, 0.16)` |
| `tint/info` | `rgba(31, 111, 168, 0.10)` | `rgba(91, 184, 232, 0.16)` |

### 1.6 Logcat severity (gutter / row)

Used for the 3px left gutter and severity dot. Same values as `accent/*`.

| Severity | Token reused |
| --- | --- |
| `V` (verbose) | `fg/muted` |
| `D` (debug) | `accent/info` |
| `I` (info) | `accent/info` |
| `W` (warn) | `accent/warning` |
| `E` (error) | `accent/danger` |
| `F` (fatal) | `accent/danger` (bold weight) |

### 1.7 Contrast targets (WCAG)

| Pair | Light | Dark | Min |
| --- | --- | --- | --- |
| `fg/primary` on `bg/canvas` | 16.0:1 | 13.6:1 | AAA (≥7) |
| `fg/secondary` on `bg/surface` | 8.5:1 | 7.1:1 | AAA (≥7) |
| `fg/muted` on `bg/surface` | 5.4:1 | 4.7:1 | AA (≥4.5) |
| `fg/inverse` on `accent/primary` | 6.0:1 | 6.4:1 | AA (≥4.5) |

Verify on every token change with an automated script (Phase 1 task).

---

## 2. Typography

### 2.1 Font families

| Role | Stack |
| --- | --- |
| `font/ui` | `Inter, "SF Pro Text", "Segoe UI", "Noto Sans TC", sans-serif` |
| `font/mono` | `"JetBrains Mono", "SF Mono", "Cascadia Mono", Consolas, monospace` |
| `font/display` | `Inter, "SF Pro Display", system-ui, sans-serif` |

Inter / JetBrains Mono ship in `assets/fonts/` (Phase 1). System stack is the
fallback when the bundled file fails to load.

### 2.2 Type scale

| Token | Size | Line | Weight | Letter | Use |
| --- | --- | --- | --- | --- | --- |
| `text/xs` | 11px | 14px | 500 | 0.02em | Mono badges, table footers |
| `text/sm` | 12px | 16px | 400 | 0 | Table cells (compact), helper text |
| `text/md` | 13px | 18px | 400 | 0 | **Default UI** |
| `text/lg` | 14px | 20px | 500 | 0 | Sidebar nav, dialog body |
| `text/xl` | 16px | 22px | 600 | -0.005em | Section title |
| `text/2xl` | 20px | 26px | 600 | -0.01em | Pane title |
| `text/3xl` | 24px | 30px | 700 | -0.01em | Empty state hero |

Mono variants (`text/mono-xs` … `text/mono-md`) reuse the same sizes with
`font/mono`. Used for serial, command output, log lines.

### 2.3 Weights

| Token | Value | Use |
| --- | --- | --- |
| `weight/regular` | 400 | Body text |
| `weight/medium` | 500 | Sidebar, nav, label |
| `weight/semibold` | 600 | Headings, KPI numbers |
| `weight/bold` | 700 | Empty state hero only |

---

## 3. Spacing

Modular 4px base scale. **Never** use raw `px` outside tokens.

| Token | Value | Common use |
| --- | --- | --- |
| `space/0` | 0 | Reset |
| `space/1` | 2px | Inside icon group |
| `space/2` | 4px | Chip internal gap |
| `space/3` | 8px | Default vertical rhythm |
| `space/4` | 12px | Form field gap |
| `space/5` | 16px | Card padding |
| `space/6` | 24px | Section gap |
| `space/7` | 32px | Pane padding (top) |
| `space/8` | 48px | Empty state |

Density modifiers:

- `compact` → multiply by 0.75 (used in dense tables).
- `cozy` (default) → 1×.
- `comfortable` → 1.25×.

---

## 4. Radius

| Token | Value | Use |
| --- | --- | --- |
| `radius/none` | 0 | Tables, full-bleed |
| `radius/xs` | 4px | Chips, badges |
| `radius/sm` | 6px | Inputs, small buttons |
| `radius/md` | 8px | Cards, panels (default) |
| `radius/lg` | 12px | Dialogs, popovers |
| `radius/full` | 999px | Pills, avatar |

---

## 5. Elevation / shadow

Dark theme avoids drop shadows; uses border + background lift instead.

| Token | Light value | Dark value |
| --- | --- | --- |
| `elevation/0` | none | none |
| `elevation/1` | `0 1px 2px rgba(15,23,42,0.06), 0 1px 3px rgba(15,23,42,0.04)` | none + `bg/surface-alt` |
| `elevation/2` | `0 4px 8px rgba(15,23,42,0.08), 0 2px 4px rgba(15,23,42,0.04)` | none + `bg/elevated` + `border/default` |
| `elevation/3` | `0 12px 24px rgba(15,23,42,0.12), 0 4px 8px rgba(15,23,42,0.06)` | `0 8px 24px rgba(0,0,0,0.40)` + `border/default` |

Map by use: `surface=0`, `popover=2`, `dialog=3`, `toast=2`.

---

## 6. Motion

Keep motion subtle; this is a developer tool.

| Token | Value | Use |
| --- | --- | --- |
| `motion/instant` | 0ms | State without animation (focus ring) |
| `motion/fast` | 80ms | Hover, press |
| `motion/normal` | 160ms | Open dialog, expand row |
| `motion/slow` | 240ms | Pane slide, sidebar collapse |
| `easing/standard` | `cubic-bezier(0.2, 0, 0, 1)` | Default |
| `easing/decelerate` | `cubic-bezier(0, 0, 0, 1)` | Enter |
| `easing/accelerate` | `cubic-bezier(0.3, 0, 1, 1)` | Exit |

Respect OS "Reduce motion" → cap at `motion/fast` and disable easing.

---

## 7. Z-index

| Token | Value | Use |
| --- | --- | --- |
| `z/base` | 0 | Default |
| `z/sticky` | 100 | Selection bar, search bar |
| `z/dropdown` | 1000 | Menus |
| `z/popover` | 1100 | Hover cards |
| `z/dialog` | 1200 | Modal |
| `z/toast` | 1300 | Notifications |
| `z/palette` | 1400 | Command palette |
| `z/tooltip` | 1500 | Last on top |

---

## 8. Status mapping (for managers / signals)

Bridges UX status to color semantically.

| State | Token | Icon |
| --- | --- | --- |
| Online / connected | `accent/success` + `tint/success` | `circle-check` |
| Offline / disconnected | `fg/muted` + `tint/info` | `circle-dashed` |
| Recording | `accent/warning` (pulses 1.5s) | `record` |
| Running task | `accent/primary` | `loader` |
| Error / unauthorized | `accent/danger` + `tint/danger` | `triangle-alert` |
| Throttled / battery low | `accent/warning` + `tint/warning` | `battery-warning` |

---

## 9. Implementation notes (Phase 1)

- `ui/design_tokens.py` exports `LIGHT_TOKENS`, `DARK_TOKENS`,
  `LIGHT_LEGACY`, `DARK_LEGACY`, and helpers such as `get_tokens(theme)`,
  `get_legacy_palette(theme)`, and `get_palette(theme)`.
- `ui/style_manager.py::_THEME_PRESETS` is a derived view of
  `get_palette(theme)`, while `_LEGACY_THEME_PRESETS` is kept as a forensic
  snapshot to guard zero-regression legacy colors.
- Density is a single int enum (`compact`, `cozy`, `comfortable`) stored in
  `UISettings`.
- Tests: `tests/test_design_tokens.py`, `tests/test_qss_loader.py`,
  `tests/test_icon_loader.py`, and `tests/test_font_loader.py` cover Phase 1
  token, QSS, icon, and font-loader behavior.
