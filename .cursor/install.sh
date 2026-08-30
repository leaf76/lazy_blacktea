#!/usr/bin/env bash
# Idempotent Cloud Agent bootstrap for Lazy Blacktea (PyQt6 + Rust native module).
# Installs uv, the Qt/X11 system libraries PyQt6 needs, Python dependencies,
# ADB, and compiles the native Rust helper crate.
set -euo pipefail

cd "$(dirname "$0")/.."

echo "==> Installing system packages (Qt/X11 runtime, adb, xvfb)"
export DEBIAN_FRONTEND=noninteractive
sudo apt-get update -qq
# Qt xcb platform plugin dependencies (see utils/qt_dependency_checker.py) plus
# adb for device automation and xvfb for headless GUI rendering/tests.
sudo apt-get install -y -qq \
  libxcb-cursor0 libxcb1 libxcb-xkb1 libxcb-xinput0 \
  libfontconfig1 libfreetype6 libx11-6 libxi6 \
  libgl1-mesa-dev libxkbcommon-x11-0 libegl1 libdbus-1-3 \
  xvfb adb

echo "==> Installing uv (if missing)"
if ! command -v uv >/dev/null 2>&1; then
  curl -LsSf https://astral.sh/uv/install.sh | sh
fi
# uv installs to ~/.local/bin; make it available for the rest of this script.
export PATH="$HOME/.local/bin:$PATH"

echo "==> Syncing Python dependencies (creates .venv)"
uv sync

echo "==> Building native Rust module (native_lbb)"
if command -v cargo >/dev/null 2>&1; then
  (cd native_lbb && cargo build --release)
else
  echo "WARNING: cargo not found; skipping native module build" >&2
fi

echo "==> Bootstrap complete"
