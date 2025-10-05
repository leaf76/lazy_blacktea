#!/usr/bin/env python3
"""Cancellation handling tests for TaskDispatcher internals."""

import os
import sys
import unittest

# Ensure project root on path
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(PROJECT_ROOT))

from PyQt6.QtCore import QCoreApplication

from utils.task_dispatcher import TaskContext, TaskHandle, TaskCancelledError, _TaskRunnable


class TaskCancellationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QCoreApplication.instance() or QCoreApplication([])

    def test_failed_signal_emits_task_cancelled_error(self) -> None:
        """Raising TaskCancelledError should emit failed with the same error."""

        context = TaskContext(name="cancel_test")
        handle = TaskHandle(context)

        def fn():
            raise TaskCancelledError("Operation cancelled")

        runnable = _TaskRunnable(fn, tuple(), {}, handle, False, False)

        captured = {"exc": None, "finished": False}

        def on_failed(exc: Exception) -> None:
            captured["exc"] = exc

        handle.failed.connect(on_failed)
        handle.finished.connect(lambda: captured.__setitem__("finished", True))

        # Run synchronously and process pending events to deliver signals
        runnable.run()
        QCoreApplication.processEvents()

        self.assertIsNotNone(captured["exc"])
        self.assertIsInstance(captured["exc"], TaskCancelledError)
        self.assertTrue(captured["finished"])  # finished should always be emitted


if __name__ == "__main__":
    unittest.main()

