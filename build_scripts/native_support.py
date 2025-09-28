"""Helper utilities for building and packaging native extensions."""

from __future__ import annotations

import platform
import shutil
import subprocess
from pathlib import Path
from typing import Optional

_LIBRARY_NAMES = {
    'Darwin': 'libnative_lbb.dylib',
    'Linux': 'libnative_lbb.so',
}


def library_filename(system: Optional[str] = None) -> str:
    """Return the native library filename for the given platform."""
    resolved = system or platform.system()
    try:
        return _LIBRARY_NAMES[resolved]
    except KeyError as exc:  # pragma: no cover - unsupported platforms
        raise RuntimeError(f'Unsupported platform for native build: {resolved}') from exc


def prepare_native_library(project_root: Path, output_dir: Path, *, cargo_bin: str = 'cargo') -> Path:
    """Build the Rust native library and copy it into ``output_dir``.

    Args:
        project_root: Repository root containing ``native_lbb``.
        output_dir: Destination directory for bundled artifacts.
        cargo_bin: Cargo executable name/path.

    Returns:
        Path to the copied native library.
    """
    native_root = project_root / 'native_lbb'
    if not native_root.exists():
        raise FileNotFoundError(f'Native project not found: {native_root}')

    build_cmd = [cargo_bin, 'build', '--release']
    subprocess.run(build_cmd, cwd=native_root, check=True, capture_output=True, text=True)

    artifact = native_root / 'target' / 'release' / library_filename()
    if not artifact.exists():
        raise FileNotFoundError(f'Native build artifact missing: {artifact}')

    output_dir.mkdir(parents=True, exist_ok=True)
    destination = output_dir / artifact.name
    shutil.copy2(artifact, destination)
    return destination


__all__ = ['library_filename', 'prepare_native_library']
