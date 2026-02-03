# Quick Start

## Requirements
- Python 3.10 or newer.
- Android SDK Platform Tools with `adb` available on your `PATH`.
- A macOS or Linux desktop environment.
- (Optional) Rust and Cargo if you plan to rebuild the native module.

## First-Time Setup
```bash
# Clone the repository
git clone https://github.com/cy76/lazy_blacktea.git
cd lazy_blacktea

# Install uv (if not already installed)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Sync dependencies (creates .venv automatically)
uv sync
```

## Launch the App
```bash
uv run python lazy_blacktea_pyqt.py
```
For headless environments (CI, remote), add `QT_QPA_PLATFORM=offscreen`.

## Run the Automated Tests
```bash
uv run python tests/run_tests.py
```
Run the full suite before every commit to keep the project stable.
