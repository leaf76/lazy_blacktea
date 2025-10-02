"""Utilities for adapting PyInstaller spec templates."""

from __future__ import annotations

import os
from typing import Dict


def _ensure_trailing_sep(path: str) -> str:
    """Return the path with a trailing separator, if missing."""
    return path if path.endswith(os.sep) else f"{path}{os.sep}"


def prepare_spec_content(spec_content: str, project_root: str) -> str:
    """Replace relative paths in the spec template with absolute ones."""
    abs_root = os.path.abspath(project_root)
    abs_pyqt = os.path.join(abs_root, 'lazy_blacktea_pyqt.py')
    abs_assets = os.path.join(abs_root, 'assets')
    abs_config = os.path.join(abs_root, 'config')
    abs_ui = os.path.join(abs_root, 'ui')
    abs_utils = os.path.join(abs_root, 'utils')
    abs_icons = _ensure_trailing_sep(os.path.join(abs_assets, 'icons'))
    abs_native = os.path.join(abs_root, 'build', 'native-libs')
    abs_version = os.path.join(abs_root, 'VERSION')

    replacements: Dict[str, str] = {
        "['../lazy_blacktea_pyqt.py']": f"['{abs_pyqt}']",
        "['lazy_blacktea_pyqt.py']": f"['{abs_pyqt}']",
        "('../assets'": f"('{abs_assets}'",
        "('assets'": f"('{abs_assets}'",
        "('../config'": f"('{abs_config}'",
        "('config'": f"('{abs_config}'",
        "('../ui'": f"('{abs_ui}'",
        "('ui'": f"('{abs_ui}'",
        "('../utils'": f"('{abs_utils}'",
        "('utils'": f"('{abs_utils}'",
        "'../assets/icons/": f"'{abs_icons}",
        "'assets/icons/": f"'{abs_icons}",
        "('build/native-libs'": f"('{abs_native}'",
        "('../build/native-libs'": f"('{abs_native}'",
        "('../VERSION'": f"('{abs_version}'",
        "('VERSION'": f"('{abs_version}'",
    }

    updated = spec_content
    for target, replacement in replacements.items():
        updated = updated.replace(target, replacement)

    return updated
