# Screens & Wireframes

Wireframes for the redesigned Lazy Blacktea. Layouts are in monospace ASCII so
they round-trip through code review and stay technology-neutral. Every region
references components from `components.md` and tokens from `tokens.md`.

> **Status:** Phase 0 spec only. PNG mocks may be added in Phase 1 if needed.

---

## 1. App Shell (every screen shares this)

```
┌─ Title bar (drag region, 32px) ──────────────────────────────────────────────┐
│  Lazy Blacktea            ⌕ Search devices, actions, files…  ⌘K     ◐  ?    │
├──────────┬──────────────────────────────────────────────┬────────────────────┤
│          │                                              │                    │
│ Sidebar  │  Primary pane                                │  Inspector         │
│ 220 / 56 │  flex                                        │  320 / 0           │
│          │                                              │  (collapsible)     │
│  Devices │                                              │                    │
│  Tools   │                                              │                    │
│  Logcat  │                                              │                    │
│  Files   │                                              │                    │
│  Tasks ²│                                              │                    │
│          │                                              │                    │
│ ── Settings                                             │                    │
│  Preferences                                            │                    │
│          │                                              │                    │
├──────────┴──────────────────────────────────────────────┴────────────────────┤
│ ●●●● 4/4 devices  ·  ▶ 2 tasks  ·  trace ab12cd  ·  v0.0.51  ·  adb 35.0.0  │
└──────────────────────────────────────────────────────────────────────────────┘
```

### Regions

| Region | Width / height | Background | Notes |
| --- | --- | --- | --- |
| Title bar | full × 32px | `bg/canvas` | Search at center, palette `Ctrl+K` opens from icon or shortcut |
| Sidebar | 220px (cozy) / 56px (collapsed) | `bg/surface` + right `border/subtle` | Nav items per `components.md::Sidebar Nav Item` |
| Primary pane | flex | `bg/canvas` | Pane content below |
| Inspector | 320px / 0 | `bg/surface` + left `border/subtle` | Toggle with `Ctrl+I` |
| Status bar | full × 28px | `bg/surface-alt` + top `border/subtle` | Items separated by `·`; each clickable |

### Title bar elements

- **Search** (centered, max 480px): triggers command palette, identical to
  `Ctrl+K`.
- **`◐` Theme switcher**: cycles `system → light → dark`; tooltip names current.
- **`?` Help menu**: opens keymap overlay (see `interaction.md`).

### Status bar items

- `●●●● 4/4 devices` — colour reflects health summary; click → Devices pane.
- `▶ 2 tasks` — count of running tasks; click → Tasks pane.
- `trace ab12cd` — current `trace_id_scope` value; click copies; long-press
  opens log file.
- `v0.0.51` — app version; click opens CHANGELOG.
- `adb 35.0.0` — adb client version; click opens settings.

### Responsive behaviour

| Width | Sidebar | Inspector |
| --- | --- | --- |
| ≥ 1440 | expanded (220) | open (320) |
| 1100 – 1439 | expanded | collapsed |
| 900 – 1099 | collapsed (56) | collapsed |
| < 900 | collapsed | hidden |

Min supported window 960×640. Below that, show a "resize to continue" hint.

---

## 2. Devices pane (default home)

```
┌─ Devices ───────────────────────────────────────────────────────────────────┐
│ ⌕ Search by serial, model, group…             [+ New group] [↻ Refresh]    │
│ Filters:  [● Online ✕]  [USB]  [Wi-Fi]  [Group: QA]  + Add filter           │
├─────────────────────────────────────────────────────────────────────────────┤
│ ✓ 3 selected   [📷 Screenshot] [🎬 Record] [⚙ Run shell]   3 / 8   ✕ Clear │   ← sticky selection bar
├─────────────────────────────────────────────────────────────────────────────┤
│ ☐ │ ● │ Model              │ Serial          │ Android │ Battery │  ⋯       │
├───┼───┼────────────────────┼─────────────────┼─────────┼─────────┼──────────┤
│ ☑ │ ● │ Pixel 7 Pro        │ 1A123BC456…     │ 14      │ ▮▮▮▮ 84% │  ⋯       │
│ ☑ │ ● │ Pixel 6a           │ 9X9Y8Z7…        │ 13      │ ▮▮▮▯ 67% │  ⋯       │
│ ☑ │ ● │ Galaxy S22         │ R3CN…           │ 14      │ ▮▮▯▯ 41% │  ⋯       │
│ ☐ │ ◌ │ Mi 11              │ —               │ ?       │  —       │  ⋯       │  ← unauthorized
│ ☐ │ ▲ │ Test rig (offline) │ TR-04           │ —       │  —       │  ⋯       │  ← warning
├─────────────────────────────────────────────────────────────────────────────┤
│ Showing 5 of 8  ·  ▾ Compact rows                                           │
└─────────────────────────────────────────────────────────────────────────────┘
```

Notes:

- Header search uses the search bar component; `/` focuses it.
- Filter row is the only filter surface (no second filter pane).
- Selection bar appears only when ≥ 1 row is selected; sticky under the header.
- Row click selects (no extra navigation). `Enter` opens the inspector.
- Right-click on a row opens the context menu (existing
  `device_list_context_menu.py`).

### Inspector content (Devices)

```
┌─ Inspector ─────────────────────────┐
│ Pixel 7 Pro                       ✕ │
│ 1A123BC456                          │
│ ──────────────────────────────────  │
│ Status                              │
│  ● Connected · USB · Authorized     │
│ Hardware                            │
│  Android 14 (API 34) · 3120×1440    │
│  CPU: Tensor G2 · 12 GB RAM         │
│ Power                               │
│  Battery 84% (charging)             │
│ Network                             │
│  Wi-Fi: corp-5g · IP 10.0.0.42      │
│ Quick actions                       │
│  [Screenshot]  [Record]  [Open shell]│
│ Recent ops                          │
│  • bug_report (00:42)               │
│  • install apk (-3m)                │
│ Open detail …                       │
└─────────────────────────────────────┘
```

`Open detail …` links to a full-page detail in the primary pane (replaces
existing `device_detail_dialog`).

---

## 3. Tools pane

Workspace with a 200px left rail (categories) and a flex canvas (current
action).

```
┌─ Tools ─────────────────────────────────────────────────────────────────────┐
│ ┌─ Capture ──────────┬─ Configure screenshot ────────────────────────────┐ │
│ │  ▸ Screenshot       │ Target devices                                    │ │
│ │    Recording        │  All selected (3)   [Change…]                      │ │
│ │    Scrcpy           │                                                    │ │
│ │ ── Install         │ Output                                             │ │
│ │    Install APK      │  ~/Downloads/lb_screens   [Browse]                  │ │
│ │    Manage apps      │                                                    │ │
│ │    Uninstall        │ Filename pattern                                   │ │
│ │ ── Diagnostics     │  {model}-{serial4}-{ts}.png                         │ │
│ │    Bug report       │                                                    │ │
│ │    UI inspector     │ Options                                            │ │
│ │    Bluetooth        │  ☑ Stitch as grid    ☐ Open folder when done       │ │
│ │ ── Shell           │                                                    │ │
│ │    Run command      │                                                    │ │
│ │    History          │  [ Take screenshot ]    Estimated: ~3.2s on 3 dev. │ │
│ │                     │                                                    │ │
│ │                     │ Latest results                                     │ │
│ │                     │  ✓ pixel-7  · 2.1s · open ⇗                        │ │
│ │                     │  ✓ pixel-6a · 1.8s · open ⇗                        │ │
│ │                     │  … see all in Tasks                                │ │
│ └─────────────────────┴────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────────────────┘
```

Each action page follows the same template:

```
Header: title + small "applies to N devices" label
─────────────────────────────────────────────────
Form (Configuration)
─────────────────────────────────────────────────
Run button + estimated impact
─────────────────────────────────────────────────
Latest results (link to Tasks)
```

Categories (left rail):

- **Capture** — Screenshot, Recording, Scrcpy preview.
- **Install** — Install APK, Manage apps (list/force-stop), Uninstall.
- **Diagnostics** — Bug report, UI inspector, Bluetooth monitor.
- **Shell** — Run command (with history), Saved commands.

`⌘P` jumps focus into the rail; arrow keys navigate; `Enter` selects.

---

## 4. Logcat pane

Three columns. Filters and Inspector are collapsible; Stream is always present.

```
┌─ Logcat ─────────────────────────────────────────────────────────────────────┐
│ ⌕ tag:ActivityManager level:E   [⏵ Start] [⏺ Recording 01:14] [Clear buffer]│
├──────────┬───────────────────────────────────────────────────┬───────────────┤
│ Filters  │  Stream                                           │  Inspector   │
│  ── Active filters                                                          │
│   [tag:ActivityManager ✕]                                                   │
│   [level:E ✕]                                                               │
│   [pid:1234 ✕]                                                              │
│  ── Saved presets                                                          │
│   ▸ Crash hunt                                                              │
│   ▸ Network only                                                            │
│   + New preset                                                              │
│  ── Devices                                                                │
│   ☑ Pixel 7 Pro                                                             │
│   ☑ Pixel 6a                                                                │
│          │                                                   │              │
│          │ │ 12:01:42.123  E ActivityManager  Pixel 7  …    │  Selected    │
│          │ │ 12:01:42.221  W InputDispatcher  Pixel 7  …    │  log entry   │
│          │ │ 12:01:42.305  I System.out       Pixel 6a …    │  Tag, PID,   │
│          │ │ 12:01:43.014  E AndroidRuntime  Pixel 7  …    │  TID, full   │
│          │ │   FATAL EXCEPTION: main                        │  message,    │
│          │ │   java.lang.NullPointerException…              │  copy / open │
│          │ │ 12:01:43.992  D OkHttp           Pixel 6a …    │  in editor   │
│          │ │ 12:01:44.512  W SurfaceFlinger   Pixel 7  …    │              │
│          │                                                   │              │
└──────────┴───────────────────────────────────────────────────┴──────────────┘
```

### Severity gutter

- 3px-wide left bar per row, color from `tokens.md §1.6`.
- Density: errors visually clump together so user can scroll-skim.

### Filter model (simplified)

- Old three-level (Live / Active / Presets) collapses into **Active filters**
  (chips, drag to reorder) + **Saved presets**.
- Adding a filter:
  - Type into search bar → DSL chip recognised on `Space`.
  - Or right-click a row's tag/level/pid → "Filter by …".
  - Or `+ Add filter` button.

### Recording control

- Toolbar in the header (above the three columns), not a separate pane.
- States: `Idle`, `Recording 01:14` (warning pill, pulsing dot), `Stopping`,
  `Saved · open ⇗`.

### Scrcpy

- Lives as an optional secondary window, opened from `Tools › Capture › Scrcpy`
  or `Ctrl+Shift+S`. Not in the main Logcat layout.

---

## 5. Files pane (device file browser)

```
┌─ Files ─────────────────────────────────────────────────────────────────────┐
│ Device: [ Pixel 7 Pro ▾ ]    Path: /sdcard/Download   [↻ Refresh]            │
├─────────────────────────────────────────────────────────────────────────────┤
│ ↑ ..                                                                        │
│ 📁 DCIM                                            12 items   2026-02-01    │
│ 📁 Pictures                                        58 items   2026-01-30    │
│ 📄 trace_ab12cd.log                                  2.3 MB   2026-02-03    │
│ 📄 build.gradle.kts                                  4.1 KB   2026-01-29    │
├─────────────────────────────────────────────────────────────────────────────┤
│ Selected: 2 files (2.3 MB)   [⬇ Pull]  [⬆ Push]  [🗑 Delete]                │
└─────────────────────────────────────────────────────────────────────────────┘
```

- Single device focus (multi-device pull goes through Tools › Capture).
- Left arrow / `Backspace` → parent directory.
- Right-click → preview / pull / delete (existing `device_file_controller`).
- Inspector shows file metadata and preview (image, text, hex).

---

## 6. Tasks pane

Replaces the implicit "completion dialog + toast" combo.

```
┌─ Tasks ─────────────────────────────────────────────────────────────────────┐
│ Active (2)                                                                  │
│  ▶ Install apk · com.acme.app · 3 devices              42%   [Cancel]       │
│  ▶ Recording  · Pixel 7 Pro · 01:42 / 03:00            ░░░   [Stop]         │
│ ──────────────────────────────────────────────────────────────────────────── │
│ Recent                                                                      │
│  ✓ Screenshot · 3 devices                  3.2s   2 min ago   [Open folder] │
│  ✓ Bug report · Pixel 7 Pro              28.4s   5 min ago   [Open file]   │
│  ✗ Install apk · Galaxy S22              0.9s   8 min ago   [View error]  │
│  ✓ Pull /sdcard/Download/trace.log         1.4s  12 min ago   [Open folder] │
└─────────────────────────────────────────────────────────────────────────────┘
```

- Active tasks float at top with progress.
- Recent (last 50 by default) groups by day.
- `[View error]` opens inspector with stack/log, copy buttons.
- "Clear completed" lives in the pane menu (`⋯`).
- `Esc` while in pane closes inspector if open.

---

## 7. Preferences

Replaces the four standalone settings dialogs.

```
┌─ Preferences ───────────────────────────────────────────────────────────────┐
│ ┌─ Sections ──────────┬─ General ────────────────────────────────────────┐ │
│ │  ▸ General           │ Theme         (○) System  (●) Light  (○) Dark   │ │
│ │    Capture           │ Density       (○) Compact (●) Cozy   (○) Comfy  │ │
│ │    Recording         │ Language      [English ▾]                       │ │
│ │    Scrcpy            │                                                  │ │
│ │    Output paths      │ Startup                                          │ │
│ │    Shortcuts         │  ☑ Auto-refresh devices on launch                │ │
│ │    Advanced          │  ☐ Restore last selection                        │ │
│ │                      │                                                  │ │
│ │                      │ Telemetry                                        │ │
│ │                      │  ☐ Send anonymous usage stats                    │ │
│ │                      │                                                  │ │
│ │                      │  [Restore defaults]              [Cancel] [Save] │ │
│ └──────────────────────┴──────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────────────────┘
```

- Min size 720×520, max width 960; never modal-stack on top of itself.
- Sections persist last-visited tab between launches.
- Shortcuts section is a read/write keymap (see `interaction.md`).

---

## 8. Empty / loading / error wireframes

### 8.1 No devices

```
                ┌──────┐
                │ icon │
                └──────┘
        No devices connected
   Connect a device with USB debugging
   enabled, or run `adb devices` to verify.
        [ Refresh ]   Open ADB guide ↗
```

### 8.2 Loading first time

```
   ░░░░░░░░░░░░░░░░░░  Loading device list…
   ▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒  Querying basic info…
```

Use 3 skeleton rows in the table; do not block UI.

### 8.3 Error banner

```
[ ! ]  ADB executable not found.
       Set ANDROID_HOME or pick the binary in Preferences › Advanced.
                                              [Set path]   [Dismiss]
```

Banner sits above the affected pane content (sticky, full width). Uses
`tint/danger` background, `accent/danger` icon.

---

## 9. Cross-pane affordances

| Affordance | Implementation |
| --- | --- |
| Persistent selection | Selected devices are shared across panes. Tools and Logcat reflect them in their headers. |
| Trace correlation | `trace_id` shown in status bar; Tasks pane and Inspector show the trace per task; click copies. |
| Density toggle | In status bar `⋯` menu and Preferences. Affects table and form spacing. |
| Theme | System default; persisted per OS theme override. |

---

## 10. Implementation notes (Phase 2 / 3)

- Shell layout lives in `ui/shell/app_shell.py`; existing managers connect to
  named slots (`add_pane`, `set_inspector`, `set_status_chip`).
- Current production wiring is compatibility mode: `WindowMain` mounts the
  existing device/tools/console splitter as a single `workspace` pane and wires
  `Ctrl+K` to `ui/shell/command_palette.py` for navigation and high-value
  legacy actions.
- Sidebar uses `QStackedWidget` for pane swap.
- Inspector is a single `QWidget` slot; each pane provides its own builder.
- Status bar is its own widget with a slot model: `chip(name, value, click)`.
- Command palette indexes:
  1. Nav targets (Devices / Tools / Logcat / …)
  2. Action verbs (Take screenshot, Start recording, Run shell command…)
  3. Devices (focus a device → inspector)
  4. Recent tasks
