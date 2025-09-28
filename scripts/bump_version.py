#!/usr/bin/env python3
"""Utility to bump Lazy Blacktea version across repository artifacts."""

from __future__ import annotations

import argparse
import re
from pathlib import Path

RELEASE_LINE_PATTERN = re.compile(r"^(>\s+Current\s+release:\s+v)(\S+)$", re.MULTILINE)


def write_version_file(root: Path, version: str) -> None:
    """Persist the canonical version string into the VERSION file."""
    version_path = root / "VERSION"
    version_path.write_text(f"{version}\n", encoding="utf-8")


def update_readme(root: Path, version: str) -> None:
    """Update the release banner in README.md."""
    readme_path = root / "README.md"
    content = readme_path.read_text(encoding="utf-8")

    def _replace(match: re.Match[str]) -> str:
        return f"{match.group(1)}{version}"

    updated, count = RELEASE_LINE_PATTERN.subn(_replace, content)
    if count == 0:
        raise RuntimeError("Failed to locate release line in README.md")
    readme_path.write_text(updated, encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Bump Lazy Blacktea version")
    parser.add_argument("version", help="New semantic version, e.g. 0.0.26")
    return parser.parse_args()


def validate_version(version: str) -> str:
    if not re.fullmatch(r"\d+\.\d+\.\d+", version):
        raise ValueError("Version must follow semantic pattern MAJOR.MINOR.PATCH")
    return version


def main() -> None:
    args = parse_args()
    version = validate_version(args.version)

    root = Path(__file__).resolve().parents[1]

    write_version_file(root, version)
    update_readme(root, version)

    print(f"Version bumped to {version}")
    print("Remember to commit the changes and update git tags if necessary.")


if __name__ == "__main__":
    main()
