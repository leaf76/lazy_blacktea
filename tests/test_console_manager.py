import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class DummyAction:
    def __init__(self, text):
        self.text = text
        self.triggered_callbacks = []

    @property
    def triggered(self):
        class _Signal:
            def __init__(self, outer):
                self._outer = outer

            def connect(self, callback):
                self._outer.triggered_callbacks.append(callback)

        return _Signal(self)


class DummyMenu:
    def __init__(self):
        self.actions = []
        self.exec_pos = None

    def addAction(self, text):
        action = DummyAction(text)
        self.actions.append(action)
        return action

    def exec(self, pos):
        self.exec_pos = pos


class DummyClipboard:
    def __init__(self):
        self.text = ""

    def setText(self, text):
        self.text = text


class DummyCursor:
    def __init__(self):
        self.selected = False
        self.text = ""

    def hasSelection(self):
        return self.selected

    def selectedText(self):
        return self.text


class DummyConsole:
    def __init__(self):
        self.cursor = DummyCursor()
        self.all_text = ""
        self.map_to_global_pos = None

    def textCursor(self):
        return self.cursor

    def toPlainText(self):
        return self.all_text

    def setPlainText(self, text):
        self.all_text = text

    def mapToGlobal(self, pos):
        self.map_to_global_pos = pos
        return pos

    def setContextMenuPolicy(self, policy):
        self.policy = policy

    def customContextMenuRequested(self, callback):
        self.callback = callback

    def clear(self):
        self.all_text = ""


class DummyStatusBar:
    def showMessage(self, message, timeout=0):
        self.message = message


class DummyWindow:
    def __init__(self):
        self.console_text = DummyConsole()
        self.status_bar = DummyStatusBar()
        self.log_messages = []
        self.cleared = False

    def write_to_console(self, message):
        self.log_messages.append(message)

    def clear_console_widget(self):
        self.console_text.all_text = ""
        self.cleared = True


class ConsoleManagerTest(unittest.TestCase):
    def setUp(self):
        from ui.console_manager import ConsoleManager

        self.window = DummyWindow()
        self.clipboard = DummyClipboard()
        self.manager = ConsoleManager(
            self.window,
            clipboard_provider=lambda: self.clipboard,
            menu_factory=lambda parent: DummyMenu(),
        )
        self.window.copy_console_text = self.manager.copy_console_text
        self.window.clear_console = self.manager.clear_console

    def test_copy_selection_prefers_selected_text(self):
        self.window.console_text.cursor.selected = True
        self.window.console_text.cursor.text = "hello"

        self.manager.copy_console_text()

        self.assertEqual(self.clipboard.text, "hello")

    def test_copy_selection_falls_back_to_all_text(self):
        self.window.console_text.all_text = "all logs"

        self.manager.copy_console_text()

        self.assertEqual(self.clipboard.text, "all logs")

    def test_clear_console_wipes_text(self):
        self.window.console_text.all_text = "something"

        self.manager.clear_console()

        self.assertEqual(self.window.console_text.all_text, "")

    def test_console_context_menu_builds_actions(self):
        menu = self.manager.create_console_context_menu()
        actions = [action.text for action in menu.actions]
        self.assertEqual(actions, ["Copy", "Clear Console"])


if __name__ == "__main__":
    unittest.main()
