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
Latest release: v0.0.51 (2026-03-06). Highlights from recent commits:
- APK installs now show transfer progress with cancel support.
- ADB push progress is streamed during APK installs.
- Logcat streaming/filtering moved off the UI thread for smoother performance.
- Logcat text selection is enabled, and preset overwrite behavior is fixed.
- Device list details refresh from cached info for faster updates.
- WiFi/Bluetooth status values are normalized for consistent display.
- Terminal cancellation/history navigation is more reliable.

## Application Updater Requirements
- The desktop updater checks the latest GitHub Release at `leaf76/lazy_blacktea`.
- Every release that should be installable from the app must upload a `SHA256SUMS.txt` asset.
- `SHA256SUMS.txt` must include the exact package filename and SHA256 digest for each published desktop artifact.
- The updater blocks download/open actions when the checksum manifest is missing, the platform asset is missing, or the downloaded file digest does not match.
- Supported updater artifacts:
  - macOS: `LazyBlacktea-macos-arm64.dmg` or `LazyBlacktea-macos-x86_64.dmg`
  - Linux: `LazyBlacktea-x86_64.AppImage`, fallback `lazyblacktea-linux.tar.gz`

## Release/Deployment Checklist
1. Run `uv run python tests/run_tests.py`.
2. Bump version via `scripts/bump_version.py` (updates `VERSION` and constants).
3. Rebuild native module if needed: `cd native_lbb && cargo build --release`.
4. Build installers via `build-scripts/build_macos.sh` and `build-scripts/build_linux.sh`.
5. Generate `SHA256SUMS.txt` for all desktop artifacts and verify the digest file locally.
6. Verify artifacts on target OSes and publish a GitHub Release with `CHANGELOG.md` notes and `SHA256SUMS.txt`.
