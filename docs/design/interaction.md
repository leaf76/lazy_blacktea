# Interaction & Accessibility

Defines how the redesigned app *feels*: keyboard model, command palette,
state-machine for slow operations, and accessibility minimums. Anything visual
lives in `tokens.md` / `components.md`; anything spatial lives in `screens.md`.

> **Status:** Phase 0 spec only. Phase 2 / 3 implements palette, keymap, and
> consistent loading / empty / error states.

---

## 1. Keyboard model

Lazy Blacktea is keyboard-first. All non-trivial actions have a shortcut.

### 1.1 Conventions

- **macOS** uses `⌘` (`Cmd`); other OSes use `Ctrl`. Spec writes `Mod` to mean
  "the right modifier for the OS".
- `Shift` extends, `Alt`/`Option` modifies (often "all" or "alternate"),
  `Mod` is primary.
- Avoid 3-key combos unless industry-standard (`Mod+Shift+P` for palette).
- Single-letter shortcuts (`/`, `?`) only fire when no input is focused.

### 1.2 Global shortcuts

| Shortcut | Action |
| --- | --- |
| `Mod+K` / `Mod+Shift+P` | Open command palette |
| `Mod+,` | Open Preferences |
| `Mod+I` | Toggle inspector pane |
| `Mod+B` | Toggle sidebar (collapsed ↔ expanded) |
| `Mod+Shift+T` | Cycle theme (system → light → dark) |
| `Mod+Shift+D` | Cycle density (cozy → compact → comfortable) |
| `?` | Show keymap overlay |
| `Esc` | Close overlay / palette / inspector context |
| `Mod+1` … `Mod+5` | Switch to Devices / Tools / Logcat / Files / Tasks |
| `Mod+R` | Refresh current pane |
| `Mod+Q` | Quit |

### 1.3 Devices pane

| Shortcut | Action |
| --- | --- |
| `/` | Focus search |
| `↑` / `↓` | Move focused row |
| `Space` | Toggle selection on focused row |
| `Shift+↑` / `Shift+↓` | Range select |
| `Mod+A` | Select all visible |
| `Mod+Shift+A` | Clear selection |
| `Enter` | Open inspector for focused row |
| `Alt+Enter` | Open device detail page |
| `Mod+G` | Add selected to group… |
| `F2` | Rename group / device alias |
| `Delete` | Remove device from group (no destructive op) |

### 1.4 Tools pane

| Shortcut | Action |
| --- | --- |
| `Mod+P` | Focus left rail |
| `↑` / `↓` | Navigate rail |
| `Enter` | Run primary action of current page |
| `Mod+Enter` | Run with confirmation skipped |
| `Mod+Shift+S` | Open scrcpy |

### 1.5 Logcat pane

| Shortcut | Action |
| --- | --- |
| `/` | Focus search |
| `Mod+F` | Focus search and select content |
| `Mod+Shift+F` | Open filter panel if collapsed |
| `Mod+L` | Clear visible buffer (does not clear device buffer) |
| `Mod+Shift+L` | Clear device buffer (with confirm) |
| `Mod+R` | Restart stream |
| `Mod+S` | Save current stream to file |
| `Mod+E` | Toggle "Errors only" filter chip |
| `J` / `K` | Next / previous match |
| `Space` | Pause / resume autoscroll |

### 1.6 Files pane

| Shortcut | Action |
| --- | --- |
| `↑` / `↓` | Move focus |
| `Enter` | Open folder / preview file |
| `Backspace` | Parent directory |
| `Space` | Toggle selection |
| `Mod+D` | Pull selected |
| `Mod+U` | Push from local… |
| `Delete` | Delete with confirm |

### 1.7 Tasks pane

| Shortcut | Action |
| --- | --- |
| `↑` / `↓` | Navigate |
| `Enter` | Open output / error |
| `Mod+.` | Cancel running task |
| `Mod+Shift+K` | Clear completed |

### 1.8 Edit conventions

Inside any text input, the Mod/`Esc` defaults still apply (palette etc.) only
when their non-input semantics differ; otherwise the input handles them
normally (e.g. `Mod+A` selects text inside an input).

---

## 2. Command palette (`Ctrl+K`)

Single source of truth for fast navigation.

### 2.1 Layout

```
┌─ Command palette ───────────────────────────────────┐
│ ⌕ Type a command, action, or device…           Esc │
├─────────────────────────────────────────────────────┤
│ NAVIGATE                                            │
│  ▸ Devices                              Mod+1       │
│  ▸ Tools                                Mod+2       │
│  ▸ Logcat                               Mod+3       │
│ ACTIONS                                             │
│  ▸ Take screenshot (3 selected)                     │
│  ▸ Start recording (3 selected)         Mod+Shift+R │
│  ▸ Run shell command…                                │
│ DEVICES                                             │
│  ▸ Pixel 7 Pro · 1A123BC                            │
│  ▸ Pixel 6a · 9X9Y8Z                                │
│ RECENT TASKS                                        │
│  ▸ ✓ Bug report · Pixel 7 Pro · 5m ago              │
└─────────────────────────────────────────────────────┘
```

### 2.2 Sections (in order)

1. **Navigate** — pane switches.
2. **Actions** — verbs that operate on current selection. Show "(N selected)"
   when relevant; gray out when impossible (e.g. "Take screenshot" with 0
   devices).
3. **Devices** — focus a device (open inspector).
4. **Files** — recent / pinned paths.
5. **Recent tasks** — last 10 finished/failed tasks; selecting opens output.
6. **Settings** — direct jump to a preferences section ("Theme", "Output paths"…).

### 2.3 Behavior

- Fuzzy match: `pix6` matches `Pixel 6a`. Score by recency × match quality.
- `Enter` runs; `Tab` accepts current as filter (drills into a section); `↑/↓`
  navigates; `Esc` closes.
- Maximum 8 visible rows, virtual scroll beyond.
- Loads asynchronously; show skeleton rows for slow sections (devices via ADB).

### 2.4 Implementation notes

- `ui/shell/command_palette.py::CommandPalette` (Phase 2).
- Sections register as `PaletteProvider` instances; each pane's manager
  registers/unregisters when activated to keep results scoped & fast.

---

## 3. Mouse & touch

- Single-click: select / focus.
- Double-click: open primary action (open detail / preview file).
- Right-click: context menu.
- Drag in Logcat: select text.
- Drag a row in Devices: not supported (avoid accidental reordering).
- Trackpad scroll: respects momentum; pinch-zoom not supported in tables.

---

## 4. Loading / empty / error / done state machine

Every async operation transitions through these named states.

```
idle → pending → running → success
                       ↘  cancelled
                       ↘  error
```

| State | Visual treatment |
| --- | --- |
| idle | Default control (no spinner / banner) |
| pending | Show subtle loading indicator within 200ms; never sooner |
| running | Determinate progress (preferred) or indeterminate spinner |
| success | Toast (transient) + Tasks entry (persistent) |
| cancelled | Toast neutral + Tasks entry "Cancelled" |
| error | Toast danger + Tasks entry "Failed" + inspector with stack |

### 4.1 Timing rules

- **<200ms**: do not show loading UI; just update.
- **200ms – 1s**: spinner inline.
- **1s – 5s**: spinner + label.
- **>5s**: progress bar with cancel; consider running in Tasks pane.

### 4.2 Toast vs Tasks vs Dialog

| Use | When |
| --- | --- |
| **Toast** | Acknowledge a transient action (copied, saved, dismissed). |
| **Tasks pane** | Any operation > 1s, batch operations, anything user can cancel. |
| **Dialog** | The user must decide (confirm overwrite, destructive). Never use for "we did the thing". |

This kills the existing pattern of opening a completion dialog after a 30s
batch — that's now a Tasks entry; the dialog only fires if input is required.

### 4.3 Error contract

Errors must always include:

- **Headline** (≤8 words): "ADB executable not found"
- **Detail** (≤2 lines): suggested next step
- **Trace ID** (mono, copyable)
- **Primary recovery action** (button)
- **Secondary**: copy details, open log

`ui/error_handler.py::ErrorHandler` already classifies errors; Phase 3 adds
the Tasks/Inspector integration.

---

## 5. Empty states

Phase 0 enumerates them so we can author copy and illustrations once.

| Surface | Empty trigger | Headline | Body | Primary action |
| --- | --- | --- | --- | --- |
| Devices | No devices connected | No devices connected | "Plug in a device with USB debugging on, or check `adb devices`." | Refresh |
| Devices | Search has no match | No matches | "Try a different keyword or clear filters." | Clear filters |
| Tools › Capture | No selected devices | Select devices first | "Pick at least one device in Devices to take a screenshot." | Open Devices |
| Logcat | No logs yet | Waiting for logs… | "Start the stream or pick a different device." | Start stream |
| Logcat | No matches for filter | No matches | "Remove a filter to widen results." | Clear filters |
| Files | Empty directory | This folder is empty | "Push a file from your computer or navigate up." | Push file |
| Tasks | No tasks | Nothing here yet | "Run an action to see progress here." | Open Tools |

---

## 6. Accessibility minimums

### 6.1 Vision

- All text meets WCAG AA (`fg/secondary` on `bg/surface` ≥ 4.5:1).
- Status uses dot + label, never color alone (re-check: `Connected` pill).
- Focus ring: 2px `border/focus` with 2px offset; never suppressed.
- Respect OS reduced-motion: disable spinner rotation easing; cap to
  `motion/fast`.
- All icons have a tooltip / accessible name.

### 6.2 Keyboard

- Tab order follows reading order (sidebar → primary pane → inspector → status).
- Trap focus in dialogs; `Esc` closes.
- Skip-link from title bar to primary pane (`Mod+/` focuses pane).

### 6.3 Screen reader

- Every pane provides an accessible label (`Devices`, `Tools workspace`).
- Live regions:
  - `Tasks pane` updates announce status changes (start, complete, error).
  - `Toast` announces with polite assertiveness.
- Tables expose row/column headers via Qt accessibility.

### 6.4 Internationalization

- Keep strings short; provide context comments to translators.
- All translatable strings via existing i18n path; no string concatenation.
- Numbers / dates use locale formatting (battery %, timestamps in logcat).

---

## 7. Performance budgets (UX-relevant)

| Surface | Target |
| --- | --- |
| Pane switch | < 80ms perceived (use cached widgets) |
| Sidebar toggle animation | 240ms |
| Logcat row append | maintain 60 FPS up to 5k rows visible |
| Search-as-you-type | feedback < 80ms, results < 250ms |
| Device discovery (basic) | first row < 1.0s |

If a budget is at risk, prefer skeletons + async over blocking UI.

---

## 8. Telemetry & observability (UX side)

- Tasks pane displays `trace_id` for every entry; click copies.
- Status bar shows current scope; long-press opens log file at the right line.
- Errors always log + include `trace_id` for support requests.
- Opt-in anonymous usage stats (Preferences › General → Telemetry); off by
  default.

---

## 9. Open behaviors deferred to Phase 3+

- Multi-window (detach Logcat / Files into separate window).
- Drag-and-drop file from desktop → push to selected device.
- Bulk preset import / export for Logcat filters.
- Plugin / scripting hooks (post-redesign).
