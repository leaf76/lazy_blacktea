import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class DummyWindow:
    pass


class DialogManagerTest(unittest.TestCase):
    def setUp(self):
        from ui.dialog_manager import DialogManager

        self.window = DummyWindow()
        self.calls = []

        def record(kind):
            def _inner(window, title, message):
                self.calls.append((kind, window, title, message))
            return _inner

        self.manager = DialogManager(
            self.window,
            info_fn=record("info"),
            warning_fn=record("warning"),
            error_fn=record("error"),
        )

    def test_show_info_uses_injected_callable(self):
        self.manager.show_info("Title", "Message")
        self.assertEqual(self.calls, [("info", self.window, "Title", "Message")])

    def test_show_warning(self):
        self.manager.show_warning("Warn", "Check")
        self.assertEqual(self.calls, [("warning", self.window, "Warn", "Check")])

    def test_show_error(self):
        self.manager.show_error("Err", "Boom")
        self.assertEqual(self.calls, [("error", self.window, "Err", "Boom")])


if __name__ == "__main__":
    unittest.main()
