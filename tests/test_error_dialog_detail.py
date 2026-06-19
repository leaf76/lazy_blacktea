"""Regression test: error dialogs must not leak raw tracebacks (finding #10)."""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ui.error_handler import ErrorHandler


class DialogDetailTests(unittest.TestCase):
    def test_only_summary_line_shown_not_traceback(self):
        technical = (
            "ValueError: bad thing\n"
            "Traceback (most recent call last):\n"
            '  File "x.py", line 1, in <module>\n'
            "    raise ValueError('bad thing')\n"
        )
        detail = ErrorHandler._dialog_detail(technical)
        self.assertEqual(detail, "ValueError: bad thing")
        self.assertNotIn("Traceback", detail)
        self.assertNotIn("File", detail)

    def test_empty_technical_info_returns_empty(self):
        self.assertEqual(ErrorHandler._dialog_detail(None), "")
        self.assertEqual(ErrorHandler._dialog_detail(""), "")


if __name__ == '__main__':
    unittest.main()
