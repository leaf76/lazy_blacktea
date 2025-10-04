#!/usr/bin/env python3
"""Task dispatcher safety tests."""

import sys
import os
import unittest

# Ensure project root on path
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(PROJECT_ROOT))

from PyQt6.QtCore import QCoreApplication, QObject, QEvent
from PyQt6 import sip

from utils.task_dispatcher import TaskContext, TaskHandle, _TaskRunnable


class TaskDispatcherSafetyTest(unittest.TestCase):
    """Validate TaskDispatcher behaviour under edge cases."""

    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QCoreApplication.instance() or QCoreApplication([])

    def test_runnable_survives_deleted_task_handle(self) -> None:
        """Running a task after TaskHandle destruction must not crash."""

        context = TaskContext(name="test")
        parent = QObject()
        handle = TaskHandle(context, parent=parent)
        runnable = _TaskRunnable(lambda: "result", tuple(), {}, handle, False, False)

        parent.deleteLater()
        QCoreApplication.sendPostedEvents(None, int(QEvent.Type.DeferredDelete))
        QCoreApplication.processEvents()

        self.assertTrue(sip.isdeleted(handle))

        try:
            runnable.run()
        except RuntimeError as exc:  # pragma: no cover - expectation fail path
            self.fail(f"_TaskRunnable should ignore deleted handles, but raised: {exc}")


if __name__ == "__main__":
    unittest.main()
