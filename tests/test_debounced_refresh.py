#!/usr/bin/env python3
"""Unit tests for utils.debounced_refresh.DebouncedRefresh."""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt6.QtCore import QCoreApplication
from PyQt6.QtTest import QTest

from utils.debounced_refresh import DebouncedRefresh


class TestDebouncedRefresh(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        # Ensure a Qt core application exists for timers/signals
        cls._app = QCoreApplication.instance() or QCoreApplication([])

    def test_request_refresh_debounces_multiple_calls(self) -> None:
        calls = {"count": 0}

        def cb():
            calls["count"] += 1

        d = DebouncedRefresh(callback=cb, delay_ms=50)

        # Burst of requests within debounce window should lead to a single execution
        d.request_refresh()
        QTest.qWait(15)
        d.request_refresh()
        QTest.qWait(15)
        d.request_refresh()

        # Wait beyond debounce delay to allow execution (use 4x buffer for CI stability)
        QTest.qWait(200)

        self.assertEqual(calls["count"], 1, "Debounced callback should run once")
        self.assertEqual(d.pending_count, 0, "Pending count resets after execution")

    def test_refresh_executed_signal_emitted(self) -> None:
        calls = {"count": 0, "signal": 0}

        def cb():
            calls["count"] += 1

        d = DebouncedRefresh(callback=cb, delay_ms=50)
        d.refresh_executed.connect(lambda: calls.__setitem__("signal", calls["signal"] + 1))

        d.request_refresh()
        QTest.qWait(150)

        self.assertEqual(calls["count"], 1, "Callback executed once")
        self.assertEqual(calls["signal"], 1, "Signal emitted once")

    def test_force_refresh_executes_immediately(self) -> None:
        calls = {"count": 0}

        def cb():
            calls["count"] += 1

        d = DebouncedRefresh(callback=cb, delay_ms=1000)

        d.force_refresh()
        # No wait required; should execute immediately
        self.assertEqual(calls["count"], 1, "Force refresh calls callback immediately")


if __name__ == "__main__":
    unittest.main()

