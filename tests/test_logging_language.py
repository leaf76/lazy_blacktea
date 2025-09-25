"""Ensure logging messages use English text and meet formatting expectations."""

import ast
import pathlib
import unittest
from typing import Iterable, Tuple


PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
LOG_METHODS = {"debug", "info", "warning", "error", "critical"}
TARGET_ROOTS = ["lazy_blacktea_pyqt.py", "ui", "utils"]


def _iter_python_files() -> Iterable[pathlib.Path]:
    for target in TARGET_ROOTS:
        path = PROJECT_ROOT / target
        if path.is_file():
            yield path
        elif path.is_dir():
            yield from path.rglob("*.py")


def _extract_literals(node: ast.AST) -> Iterable[str]:
    """Yield literal string segments from a logging call argument."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        yield node.value
    elif isinstance(node, ast.JoinedStr):  # f-string
        for value in node.values:
            yield from _extract_literals(value)
    elif isinstance(node, ast.FormattedValue):
        yield from _extract_literals(node.value)
    elif isinstance(node, ast.Call):  # e.g. str.format("…")
        for arg in node.args:
            yield from _extract_literals(arg)
        for kw in node.keywords:
            if kw.value is not None:
                yield from _extract_literals(kw.value)


def _has_non_english(text: str) -> bool:
    return any("\u4e00" <= ch <= "\u9fff" for ch in text)


def _find_non_english_logs(file_path: pathlib.Path) -> Iterable[Tuple[int, str]]:
    tree = ast.parse(file_path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if not isinstance(func, ast.Attribute):
            continue
        if func.attr not in LOG_METHODS:
            continue
        value = func.value
        value_name = ""
        if isinstance(value, ast.Name):
            value_name = value.id
        elif isinstance(value, ast.Attribute):
            value_name = value.attr
        if not value_name.lower().startswith("logger"):
            continue
        for arg in node.args:
            for literal in _extract_literals(arg):
                if _has_non_english(literal):
                    yield (node.lineno, literal)
        for kw in node.keywords:
            if kw.value is None:
                continue
            for literal in _extract_literals(kw.value):
                if _has_non_english(literal):
                    yield (node.lineno, literal)


class LoggingLanguageTests(unittest.TestCase):
    """Verify that logging statements remain English-only."""

    def test_logging_messages_are_english(self):
        failures = []
        for file_path in _iter_python_files():
            relative = file_path.relative_to(PROJECT_ROOT)
            for line_no, text in _find_non_english_logs(file_path):
                failures.append(f"{relative}:{line_no} -> {text}")
        if failures:
            self.fail("Found non-English logging messages:\n" + "\n".join(failures))


if __name__ == "__main__":
    unittest.main()
