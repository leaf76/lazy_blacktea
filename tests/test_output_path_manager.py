#!/usr/bin/env python3
"""Tests for the OutputPathManager helper."""

import sys
import types
import unittest
from types import SimpleNamespace
from unittest.mock import patch


if 'PyQt6' not in sys.modules:
    class _DummySignal:
        def connect(self, *_args, **_kwargs):
            return None

        def emit(self, *_args, **_kwargs):
            return None

    def _dummy_pyqt_signal(*_args, **_kwargs):
        return _DummySignal()

    class _DummyQTimer:
        def __init__(self, *_args, **_kwargs):
            self.timeout = _DummySignal()

        def start(self, *_args, **_kwargs):
            return None

        def stop(self):
            return None

        @staticmethod
        def singleShot(_milliseconds, callback):
            callback()

    def _make_dummy_class(name):
        def _init(self, *_args, **_kwargs):
            return None

        return type(name, (), {"__init__": _init})

    class _LazyWidgetModule(types.ModuleType):
        def __getattr__(self, name):
            value = _make_dummy_class(name)
            setattr(self, name, value)
            return value

    dummy_qtwidgets = _LazyWidgetModule('PyQt6.QtWidgets')

    class _LazyCoreModule(types.ModuleType):
        def __init__(self, name):
            super().__init__(name)
            self.QTimer = _DummyQTimer
            self.pyqtSignal = _dummy_pyqt_signal

        def __getattr__(self, name):
            value = _make_dummy_class(name)
            setattr(self, name, value)
            return value

    dummy_qtcore = _LazyCoreModule('PyQt6.QtCore')

    dummy_pyqt6 = types.ModuleType('PyQt6')
    dummy_pyqt6.QtWidgets = dummy_qtwidgets
    dummy_pyqt6.QtCore = dummy_qtcore

    sys.modules.setdefault('PyQt6', dummy_pyqt6)
    sys.modules.setdefault('PyQt6.QtWidgets', dummy_qtwidgets)
    sys.modules.setdefault('PyQt6.QtCore', dummy_qtcore)


from ui.output_path_manager import OutputPathManager


class _LineEditStub:
    def __init__(self, text: str = ''):
        self._text = text

    def text(self) -> str:
        return self._text

    def setText(self, value: str) -> None:
        self._text = value


class OutputPathManagerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.window = SimpleNamespace()
        self.window.output_path_edit = _LineEditStub()
        self.window.file_gen_output_path_edit = _LineEditStub()
        self.file_dialog_manager = SimpleNamespace(select_directory=lambda *_args, **_kwargs: '')
        self.manager = OutputPathManager(self.window, self.file_dialog_manager)

    def test_primary_path_syncs_generation_when_following(self) -> None:
        """Setting primary path aligns generation path when it follows the default."""
        self.manager.set_primary_output_path('/tmp/new')

        self.assertEqual(self.window.output_path_edit.text(), '/tmp/new')
        self.assertEqual(self.window.file_gen_output_path_edit.text(), '/tmp/new')

    def test_primary_path_respects_custom_generation(self) -> None:
        """Setting primary path keeps file generation path if user customised it."""
        self.manager.set_primary_output_path('/tmp/first')
        self.window.file_gen_output_path_edit.setText('/custom/path')

        self.manager.set_primary_output_path('/tmp/second')

        self.assertEqual(self.window.output_path_edit.text(), '/tmp/second')
        self.assertEqual(self.window.file_gen_output_path_edit.text(), '/custom/path')

    def test_ensure_primary_path_uses_default_when_empty(self) -> None:
        """Ensuring primary path uses default output when none configured."""
        with patch('ui.output_path_manager.common.make_gen_dir_path', return_value='/tmp/default'):
            ensured = self.manager.ensure_primary_output_path()

        self.assertEqual(ensured, '/tmp/default')
        self.assertEqual(self.window.output_path_edit.text(), '/tmp/default')
        self.assertEqual(self.window.file_gen_output_path_edit.text(), '/tmp/default')

    def test_apply_legacy_paths(self) -> None:
        """Applying paths from legacy config populates both fields."""
        self.manager.apply_legacy_paths('/tmp/main', '')

        self.assertEqual(self.window.output_path_edit.text(), '/tmp/main')
        self.assertEqual(self.window.file_gen_output_path_edit.text(), '/tmp/main')

    def test_get_file_generation_path_falls_back_to_primary(self) -> None:
        """File generation path falls back to primary path when empty."""
        self.window.output_path_edit.setText('/tmp/primary')

        path = self.manager.get_file_generation_output_path()

        self.assertEqual(path, '/tmp/primary')

    def test_get_adb_tools_path_returns_trimmed_value(self) -> None:
        """ADB tools output path reflects primary line edit contents."""
        self.window.output_path_edit.setText('  /tmp/adb  ')

        path = self.manager.get_adb_tools_output_path()

        self.assertEqual(path, '/tmp/adb')


if __name__ == '__main__':  # pragma: no cover
    unittest.main()
