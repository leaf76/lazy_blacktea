# Deployment & Release

## Packaging & Release
- Use PyInstaller specs under `build-scripts/` to build macOS and Linux bundles.
- Platform scripts:
  - `build-scripts/build_macos.sh`
  - `build-scripts/build_linux.sh`

## Version Management
- `VERSION` file (source of truth).
- `config/constants.py::ApplicationConstants.APP_VERSION` (reads from VERSION).
- README `Current release` badge (manually or via `scripts/bump_version.py`).
- `CHANGELOG.md` for release notes.

## Latest Release
Latest release: v0.0.49 (2026-02-03). Highlights from recent commits:
- APK installs now show transfer progress with cancel support.
- ADB push progress is streamed during APK installs.
- Logcat streaming/filtering moved off the UI thread for smoother performance.
- Logcat text selection is enabled, and preset overwrite behavior is fixed.
- Device list details refresh from cached info for faster updates.
- WiFi/Bluetooth status values are normalized for consistent display.
- Terminal cancellation/history navigation is more reliable.

## Release/Deployment Checklist
1. Run `uv run python tests/run_tests.py`.
2. Bump version via `scripts/bump_version.py` (updates `VERSION` and constants).
3. Rebuild native module if needed: `cd native_lbb && cargo build --release`.
4. Build installers via `build-scripts/build_macos.sh` and `build-scripts/build_linux.sh`.
5. Verify artifacts on target OSes and publish a GitHub Release with `CHANGELOG.md` notes.
