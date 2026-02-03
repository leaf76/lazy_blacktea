# Lazy Blacktea

![Lazy Blacktea logo](assets/icons/icon_128x128.png)

[![Build Status](https://github.com/cy76/lazy_blacktea/workflows/build/badge.svg)](https://github.com/cy76/lazy_blacktea/actions)
[![Test Status](https://github.com/cy76/lazy_blacktea/workflows/test/badge.svg)](https://github.com/cy76/lazy_blacktea/actions)
[![Python](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

> Current release: v0.0.50 (2026-02-03)
> Release notes: [CHANGELOG.md](CHANGELOG.md)

**Languages:** English | [繁體中文](README_zh-TW.md)

## Why Lazy Blacktea?
- Monitor multiple Android devices and schedule operations from a single window.
- Ship ready-to-run automation tasks (install, record, capture, shell commands, logcat streaming).
- Offer a clear device table, progress indicators, and dual light/dark themes.
- Accelerate heavy I/O and file workloads with a Rust native companion module.
- Rely on built-in tests and CI pipelines to lower regression risks.

## Quick Start
See the full setup guide in [docs/quickstart.md](docs/quickstart.md).

```bash
uv run python lazy_blacktea_pyqt.py
```
For headless environments (CI, remote), add `QT_QPA_PLATFORM=offscreen`.

## Core Features
| Area | Highlights | Key Modules |
| --- | --- | --- |
| Device management | Live discovery, grouping, and dynamic refresh | `ui.async_device_manager`, `ui.device_manager` |
| Automation tasks | Batch installs (with transfer progress + cancel), bug reports, shell, recording, screenshots | `ui.device_operations_manager`, `utils.adb_tools` |
| File workflows | Browse device files, preview, and coordinate export paths | `ui.device_file_browser_manager`, `utils.file_generation_utils` |
| Diagnostics | Logcat streaming, buffer controls, error classification, completion dialogs | `ui.logcat_viewer`, `ui.console_manager`, `ui.error_handler` |
| Performance | Debounced refresh, batched UI updates, native helpers | `utils.debounced_refresh`, `utils.task_dispatcher`, `native_lbb` |

## UI Preview
![Lazy Blacktea overview in dark mode](assets/screenshots/Screenshot_0036.png)

## Architecture
See [docs/architecture.md](docs/architecture.md) for the project tour, module responsibilities, and troubleshooting notes.

## Deployment & Release
See [docs/deployment.md](docs/deployment.md) for packaging steps, version management, and release checklist details.

## Community & Support
- Issue tracker: <https://github.com/cy76/lazy_blacktea/issues>
- Discussions: <https://github.com/cy76/lazy_blacktea/discussions>
- Contribution guide: [`CONTRIBUTING.md`](CONTRIBUTING.md)
- Security reports: submit privately via GitHub Security Advisories.

## How to Contribute
1. Fork the repository and create a feature branch.
2. Practice TDD: add tests, implement the change, refactor when green. Use Conventional Commits.
3. Run `python3 tests/run_tests.py` and update docs or performance notes as needed.
4. Open a pull request with test results, screenshots for UI changes, and relevant context.

## License
Lazy Blacktea ships under the [MIT License](LICENSE); PyQt6 and third-party dependencies keep their respective licenses.

## Roadmap
- Provide richer automation templates and script samples.
- Sync preferences, tagging, and usage metrics via optional cloud services.
- Expand Windows support (experimental).
- Add guided onboarding and interactive tutorials.

Like the project? Drop a ⭐, share it with your team, and tell us how it helped!
