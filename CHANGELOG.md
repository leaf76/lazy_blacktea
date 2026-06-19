# Changelog

All notable changes to Lazy Blacktea are documented here.

This project follows [Conventional Commits](https://www.conventionalcommits.org/) for release notes.

## Unreleased
### Added
- Command palette now searches connected devices and recent tasks.
- Sticky batch-action bar (Screenshot / Record / Run Shell / Clear) appears in the Devices pane when devices are selected.
- Keyboard-first navigation: `/` focuses the device search, `?` opens a shortcuts overlay, and the device list supports ↑/↓ move, Space toggle, and Ctrl+A / Ctrl+Shift+A.
- Inspector pane shows a summary of the active device.
- Rich empty / first-run device states with USB-debugging guidance, an "Open ADB guide" link, and a "Clear filters" action.
- Device Groups promoted to a top-level sidebar pane.

### Changed
- Routine batch-operation success now shows a non-blocking toast instead of a blocking dialog (failures still use a dialog).
- Quick-filter chips (WiFi / BT / API / …) now actually filter the device list.
- Toast, unauthorized banner, and checkbox colours follow the active light/dark theme, and the theme is re-applied live on switch (no stale colours until restart).
- `accent_primary` design token is now the documented blue (`#2D6CDF` light / `#5B9DFF` dark).
- Error dialogs show a concise summary instead of a raw Python traceback.

### Fixed
- Screenshot, shell command, and file-download operations now report real per-device success/failure instead of always reporting success.
- Screen recording no longer fails to finalize on completion (devices could get stuck showing "recording").
- Reboot now requires confirmation from every entry point, including the device-list right-click.
- ADB commands now time out instead of hanging the app indefinitely on an offline/stuck device; large APK installs use a longer timeout.
- Device groups persist immediately when created or deleted (no longer lost on crash/force-quit).
- Devices reporting a dotted Android release (e.g. `13.0`) no longer show as "Android 0".
- Per-device checkboxes expose accessible names; the search field shows a visible focus ring.

### Internal
- Extracted pure logcat parsing helpers to `ui/logcat/log_parsing.py`; removed dead `optimized_device_list.py`.
- Decomposed `adb_tools.py` (~2940 → ~1050 lines, −64%) into a `utils/adb/` package (`_base`, `screenshot`, `recording`, `package`, `install`, `files`, `device_info`) behind re-export shims, preserving all existing imports. Bug-report functions stay in `adb_tools.py` to keep the existing test mock surface intact.

## 0.0.55 - 2026-05-25
### Fixed
- Pass `--arch` to the release build script so macOS Intel jobs build `LazyBlacktea-macos-x86_64.dmg`.

## 0.0.54 - 2026-05-25
### Fixed
- Set `TARGET_ARCH` in the release workflow so Intel builds publish `LazyBlacktea-macos-x86_64.dmg`.

## 0.0.53 - 2026-05-25
### Fixed
- Support macOS ZIP updater assets and Intel asset aliases when selecting GitHub Release downloads.
- Publish macOS DMG assets using updater-compatible architecture names in the release workflow.

## 0.0.52 - 2026-05-25
### Added
- Wire the redesigned AppShell into the main window with Devices, Tools, Logcat, Files, Apps, and Tasks panes.
- Add a verified GitHub Releases updater with SHA256 manifest enforcement.
- Add the tabbed Preferences dialog with Appearance, device, capture, APK install, scrcpy, output, updates, and advanced sections.

### Changed
- Move Settings menu entries to Preferences deep links and add command palette settings actions.
- Add UI density persistence and apply density styling to AppShell surfaces.

### Fixed
- Harden Phase 3 AppShell GUI startup, ADB integration, and shutdown behavior.

## 0.0.51 - 2026-03-06
### Fixed
- Refresh the active device overview when detailed device data and battery snapshots update.
- Avoid terminal startup aborts on macOS/Qt environments that treat missing font warnings as fatal.

## 0.0.50 - 2026-02-03
### Added
- Logcat viewer button to clear the device logcat buffer with confirmation.

### Changed
- Logcat streaming no longer clears the device logcat buffer on start.

## 0.0.49 - 2026-02-03
### Added
- APK install transfer progress with cancel support (`1d36edc`).

### Changed
- Logcat streaming/filtering moved off the UI thread for smoother performance (`accf3d6`).

### Fixed
- Normalize WiFi/Bluetooth status values (`9246cc7`).
- Stream ADB push progress during APK installs (`d3abe45`).
- Improve terminal cancellation and history navigation (`22d892e`).
- Enable logcat text selection and preset overwrite fixes (`3c3f179`).
- Refresh device list details from cached info (`50aaa9a`).

## 0.0.48 - 2026-01-13
### Added
- Operation status tracking for all ADB tools (`d0f6c2c`).
- Track scrcpy operations in device operations status (`7bc4226`).

### Changed
- Move recording status labels inside collapsible panel (`432472e`).
- Move recording status into recording section (`d0f898b`).
- Unify recording operations in status panel (`cab37ac`).
- Update CI runners to macos-15 and ubuntu (`6599466`).

### Fixed
- Allow multiple Logcat windows for different devices (`12a78f7`).
- Scrcpy operation status stuck at pending (`333412c`).
- Complete recording operation status when manually stopped (`03fec0e`).
- Update recording operation status from pending to running (`abf1e21`).
- Improve UI behaviors and device info functionality (`261eab0`).

## 0.0.47 - 2026-01-12
### Notes
- Release notes for this version were not captured yet. Refer to git history if needed.
