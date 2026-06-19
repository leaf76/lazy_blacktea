# UI/UX & Usage-Logic Audit — Progress Tracker

A multi-agent audit (8 dimensions, adversarially verified) produced 63 ranked
findings. This file tracks what has been implemented and what remains. All
implemented changes are covered by tests and keep `tests/run_tests.py` green.

## ✅ Implemented (with tests)

### Batch A — Operation correctness & "false success"
- **#1/#21** Recording completion: removed `{duration:.1f}` crash on a string
  duration; routed completion through a GUI-thread `operation_finished_signal`.
- **#2** Reboot confirmation centralised in `WindowMain.reboot_device` so the
  device-list right-click paths can no longer bypass it.
- **#4** Screenshots report real success (per-device PNG existence →
  `start_to_screen_shot` returns `serial→bool`; only successes marked COMPLETED).
- **#6** Shell commands capture per-device exit codes; failures show
  `Failed (exit N)` instead of always "Completed".
- **#17** File downloads verify success (structured `pull_device_paths` result);
  partial/failed downloads now warn with the failed paths.
- **#18** `force_stop_app`/`open_app_info` return the real adb outcome
  (new `common.run_command_with_status`).
- **#12** Device groups persist immediately on save/delete (not only on close).
- **#36** APK install parsing: whole-line success match (no substring false
  positives), exact `INSTALL_FAILED_*` token mapping, no list-repr leak.

### Batch B — UI/UX & accessibility quick wins
- **#7** Quick-filter chips now actually filter (`search_filter_and_sort_devices`).
- **#8/#19/#22/#23/#25** Per-device checkbox accessible names; search focus ring;
  collapse-button + pane/inspector/workspace accessible names; collapsed sidebar
  keeps full label for screen readers.
- **#16** Failed operations expose the full error via tooltip (visible label
  widened 30→60 + ellipsis).
- **#26/#27/#24** Toast, unauthorized banner, and checkbox indicator are now
  theme-aware (no hardcoded light colours in dark mode).
- **#10** Error dialogs show only the `Type: message` summary; full traceback
  stays in the log.
- **#52** Removed duplicate command-palette navigation entries.
- **#11** Routine batch-operation success uses a non-blocking toast
  (`WindowMain.show_toast`) instead of a blocking modal; failures stay dialogs.

### Batch C — ADB robustness / perf / dead code
- **#3/#5** `run_command`/`mp_run_command` gained a `timeout` (default 30s, install
  120s) and reclaim the process on timeout; fixed 6 callers that passed a number
  as `ignore_index` when they meant `timeout`.
- **#34** `get_android_version` returns the release string / `Unknown` (no more
  "Android 0" for `13.0`, `4.4.2`, codenames).
- **#51** APK paths use `shlex.quote`.
- **#39** Deleted dead `ui/optimized_device_list.py` (421 lines, zero references).
- **#47** Basic-info discovery phase filters to the requested serials.
- **#48** Recording status timer skips the per-tick rebuild while idle.
- **#60** Enumeration-failure retry uses exponential backoff (1s→30s, reset on
  success) instead of retrying every second forever.

### Batch D — started
- **#28** `accent_primary` is now the documented blue (`#2D6CDF` light /
  `#5B9DFF` dark) in the spec tokens; legacy `primary` stays green so existing
  legacy-styled buttons are unaffected. **(Product decision: blue, per user.)**
- **#9 (D1)** Live theme switch now re-styles custom-painted widgets:
  `CollapsiblePanel`, `SelectedDevicesBar`, `DeviceOverviewWidget` expose
  `refresh_theme()`, invoked by `WindowMain._refresh_custom_painted_themes()` via
  a duck-typed `findChildren` sweep. (DeviceOverviewWidget section sub-headers
  still use an append-style helper — minor remaining polish.)

## ⏳ Deferred (rationale)

- **#20** Auto-dismiss terminal operations — do with **D3**: naive manager-level
  removal regresses the recent-tasks chip and the planned RecentTasksPaletteProvider
  (both read `get_all_operations`). Correct fix is panel-level fade keeping the
  manager record.
- **#46** Alternating device-table rows — the table is a hidden legacy widget
  (see #54); no user-visible effect. Do alongside #54.
- **#35** Offline sentinels for wifi/bt/api/gms — needs a `DeviceInfo` type
  decision (these are bool/int; `'Unknown'` would break filter predicates and
  `_format_on_off`). Consider an explicit "availability" flag.
- **#50 (remaining)** `shlex.quote` for legacy builders' `output_path` (UI dump
  line 154, DCIM line 469 — 469 also has a suspicious stray `dcims` token to
  investigate). Serial-only builders are not injectable under `shell=False`.
- **#33/#56** Refresh perf (getprop consolidation 6→fewer subprocess; O(N²)
  per-device rebuild debounce) — hot-path changes; do as a measured follow-up.
- **#43/#38** Worker `self.worker` race; untracked `run_in_thread` daemon threads —
  need careful threading analysis.
- **#40/#32/#54** Dead duplicate screenshot/recording impl; logcat QListView
  proxy/delegate pipeline; hidden legacy table rebuild — each needs per-call-site
  live-caller verification before removal.

### Batch D — implemented
- **#28** accent_primary → documented blue (light `#2D6CDF` / dark `#5B9DFF`).
- **#9 (D1)** Live theme re-apply for custom-painted widgets via `refresh_theme()`.
- **#13 (D2)** Inspector pane filled with the active-device summary
  (`DeviceInspectorWidget`), shown on the Devices pane.
- **#14 (D3)** `DevicesPaletteProvider` + `RecentTasksPaletteProvider` registered;
  type a model/serial or jump to a recent task. **#20** completed rows now
  auto-dismiss from the panel only (manager keeps the record for these providers;
  failed rows stay until cleared).
- **#15 (D4)** Sticky `SelectionActionBar` (Screenshot/Record/Run Shell/Clear) in
  the Devices pane, visible when ≥1 device is selected.
- **#30/#31 (D5)** Keyboard-first model: `/` focuses search, `?` opens a
  read-only `ShortcutsOverlay`; the device list supports ↑/↓ navigation, Space
  toggle, Ctrl+A / Ctrl+Shift+A. **#53** also fixed — `update_devices` now keeps
  rows in the incoming sorted order.
- **#37 (D6)** Rich empty / first-run states (`EmptyStateWidget`): no-devices
  guidance with Refresh + Open ADB guide; no-match state with Clear filters.
- **#61 (D8)** Pure logcat helpers extracted to `ui/logcat/log_parsing.py`
  (re-exported from `logcat_viewer.py`).
- **#57 (D7)** Device Groups promoted to a first-class sidebar pane
  (`PANE_GROUPS`), removed from the Tools workspace; the duplicate palette entry
  was dropped (NavigationPaletteProvider now covers it).
- **#63 (D8)** `adb_tools.py` decomposed from **2941 → ~1050 lines (−64%)** into the
  `utils/adb/` package, each module re-exported from `adb_tools.py` so all 321
  references keep resolving (full suite green at every step):
  - `_base.py` — shared decorators + parallel-exec primitives + worker count
  - `screenshot.py` — screenshot capture
  - `recording.py` — screen recording (+ `_active_recordings` state)
  - `package.py` — package/app listing, permissions, uninstall, force-stop, open-info
  - `install.py` — APK info/validate/split/install
  - `files.py` — pull / list-directory / DCIM / HSV
  - `device_info.py` — device discovery/enumeration + DeviceInfo build, property
    reads, version/api/gms/fingerprint, wifi/bt/audio state (19 functions +
    `gms_package_name` / `ACCEPTED_DEVICE_STATUSES`).
  - Residual in `adb_tools.py` = ADB-server/path management, shell command exec,
    reboot/root/bluetooth, discovery-service parsing, scrcpy, tool-availability,
    and the **bug-report** functions. Bug-report is intentionally kept in
    `adb_tools.py` (not split into `utils/adb/`): it calls the device-info helpers
    (`_is_device_available`, `_get_device_manufacturer_info`, `get_gms_version`) by
    bare name, so co-locating keeps those calls resolving through `adb_tools`'
    globals — which preserves the established test mock surface
    (`patch('utils.adb_tools._is_device_available')` still intercepts the
    bug-report path; ~5 bug-report smoke/workflow suites depend on this).
- **#53** `ExpandableDeviceList.update_devices` keeps rows in the incoming sorted
  order (fixed while implementing keyboard navigation).

## 🎨 Remaining (optional)

- **D8 (#63)** Complete. Six domains are extracted (`_base`, `screenshot`,
  `recording`, `package`, `install`, `files`, `device_info`); `adb_tools.py` is
  down to ~1050 lines (core utilities + bug-report). Bug-report deliberately stays
  in `adb_tools.py` to preserve the established `patch('utils.adb_tools.<helper>')`
  test mock surface (see #63 note above) — extracting it would silently break ~5
  CI-only bug-report smoke/workflow suites for no structural gain.

## Deferred non-D items (rationale above)

`#35` (offline sentinels — DeviceInfo type decision), `#33`/`#56` (refresh-path
perf, needs measurement), `#40`/`#32`/`#54` (dead-duplicate removal — per-site
verification), `#43`/`#38` (threading races), `#50` remainder, `#46`
(hidden-legacy table).
