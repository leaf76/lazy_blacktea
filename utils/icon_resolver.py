"""Helpers for locating application icons across environments."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Iterable, Iterator, Optional

from config.constants import PathConstants


def _candidate_roots(extra_roots: Iterable[Path] | None = None) -> Iterator[Path]:
    """Yield directories that might contain icon assets."""
    if extra_roots:
        for root in extra_roots:
            yield root

    env_root = os.environ.get('LAZY_BLACKTEA_ASSET_ROOT')
    if env_root:
        yield Path(env_root)

    bundle_root = getattr(sys, '_MEIPASS', None)
    if bundle_root:
        yield Path(bundle_root)

    # Repository root (two levels up from this file)
    repo_root = Path(__file__).resolve().parents[1]
    yield repo_root

    # Current working directory as a last resort
    yield Path.cwd()


def _iter_icon_candidates(extra_roots: Iterable[Path] | None = None) -> Iterator[Path]:
    """Return possible icon files in preference order."""
    seen: set[str] = set()

    env_override = os.environ.get('LAZY_BLACKTEA_ICON')
    if env_override:
        candidate = Path(env_override).expanduser()
        candidate_path = candidate.resolve(strict=False)
        key = candidate_path.as_posix()
        if key not in seen and candidate_path.exists():
            seen.add(key)
            yield candidate_path

    for root in _candidate_roots(extra_roots):
        for relative in PathConstants.ICON_PATHS:
            path = Path(relative)
            if not path.is_absolute():
                path = (root / relative)
            candidate = path.resolve(strict=False)
            key = candidate.as_posix()
            if key in seen:
                continue
            seen.add(key)
            if candidate.exists():
                yield candidate


def iter_icon_paths(extra_roots: Iterable[Path] | None = None) -> Iterator[Path]:
    """Yield icon candidates in priority order."""
    yield from _iter_icon_candidates(extra_roots)


def resolve_icon_path(extra_roots: Iterable[Path] | None = None) -> Optional[Path]:
    """Return the first available icon path, if any."""
    return next(iter_icon_paths(extra_roots), None)


__all__ = ['resolve_icon_path', 'iter_icon_paths']
