# Changelog

All notable changes to Lazy Blacktea are documented here.

This project follows [Conventional Commits](https://www.conventionalcommits.org/) for release notes.

## Unreleased
- None.

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
