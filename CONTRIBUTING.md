# Contributing to Lazy Blacktea

Thank you for taking the time to improve Lazy Blacktea. This guide outlines how to propose changes, report issues, and collaborate effectively with the maintainers.

> Current release: v0.0.21

## Before You Start
- Review open issues and discussions to avoid duplicate work
- Ensure you can reproduce the behaviour you plan to report or change
- Read the repository guidelines in the project documentation and follow the coding conventions described there

## Reporting Bugs
1. Search existing issues to confirm the bug has not been reported
2. Use the bug-report template and include:
   - Operating system version
   - Python version
   - ADB version and how it was installed
   - Lazy Blacktea version and distribution (source, App bundle, AppImage)
3. Provide clear reproduction steps and expected vs. actual results
4. Attach logs (`tests/logs/`), screenshots, or screen recordings when possible

## Requesting Features
1. Describe the use case and why it helps device automation workflows
2. Explain how the feature should behave in the UI
3. Share any constraints or dependencies (permissions, device requirements)
4. Reference related discussions or issues when applicable

## Setting Up Your Environment
```bash
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
adb devices                      # verify connectivity
python3 lazy_blacktea_pyqt.py    # smoke test the UI
```
- Keep ADB available on your PATH; the tooling assumes `adb devices` succeeds
- Prefer `utils.common.get_logger` for logs instead of `print`
- Respect the existing module layout (`ui/`, `utils/`, `config/`, `tests/`)

## Development Workflow
1. Create a topic branch from the latest main branch (`git checkout -b feat/device-inspector`)
2. Follow a Test-Driven Development loop: start with tests under `tests/` or `tests/run_tests.py`, make them fail, add the implementation, then refactor
3. Update or add documentation (README, inline docstrings) when behaviour changes
4. Keep commits focused and use Conventional Commit messages (for example, `feat: add device sorting by API level`)
5. Where helpful, create short helper scripts for complex refactors but delete them before submitting

## Testing Expectations
- Run the full suite before submitting a pull request:
  ```bash
  python3 tests/run_tests.py
  ```
- Execute targeted smoke tests when relevant:
  ```bash
  python3 test_device_list_performance.py
  ```
- Clean any `/tmp/lazy_blacktea_*` artifacts your changes generate
- Document remaining risks or manual verification steps in the pull request description

## Code Quality Guidelines
- Adhere to PEP 8 and use type hints for new public functions or classes
- Keep modules cohesive; shared utilities belong in `utils/`
- Use descriptive variable and function names, avoiding redundant comments
- Remove dead code and outdated configuration values instead of leaving them disabled
- Keep UI strings and logs in English to stay consistent with the project convention

## Submitting a Pull Request
1. Push your branch and open a pull request targeting `main`
2. Fill out the pull-request template, including the commands you ran locally
3. Attach screenshots or console excerpts for user-visible changes
4. Ensure CI checks pass; address feedback promptly and keep discussions professional
5. Squash or rebase only when requested by a maintainer to preserve review history

## Release Checklist for Maintainers
- Confirm `python3 tests/run_tests.py` has passed on the release candidate
- Verify macOS and Linux bundles built by `python3 build-scripts/build.py`
- Update `~/.lazy_blacktea_config.json` schema version carefully; document migrations if touched
- Publish release notes summarising new features, bug fixes, and breaking changes

## Getting Help
- Issues: https://github.com/cy76/lazy_blacktea/issues
- Discussions: https://github.com/cy76/lazy_blacktea/discussions
- Security concerns: open a private advisory instead of a public issue

We appreciate every contribution. Thank you for helping the community build a better Android automation toolkit.
