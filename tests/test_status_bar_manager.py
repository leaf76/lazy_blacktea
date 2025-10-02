import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class DummyStatusBar:
    def __init__(self):
        self.message_calls = []
        self.widgets = []

    def addPermanentWidget(self, widget):
        self.widgets.append(widget)

    def showMessage(self, message, timeout=0):
        self.message_calls.append((message, timeout))


class DummyProgressBar:
    def __init__(self):
        self.visible = False
        self.minimum = 0
        self.maximum = 0
        self.value = 0

    def setVisible(self, value):
        self.visible = bool(value)

    def setMinimum(self, value):
        self.minimum = value

    def setMaximum(self, value):
        self.maximum = value

    def setValue(self, value):
        self.value = value

    def setRange(self, minimum, maximum):
        self.minimum = minimum
        self.maximum = maximum


class DummyLabel:
    def __init__(self):
        self.text = ''
        self.style = ''
        self.object_name = ''

    def setText(self, text):
        self.text = text

    def setStyleSheet(self, style):
        self.style = style

    def setObjectName(self, name):
        self.object_name = name


class DummyWindow:
    def __init__(self):
        self.status_bar = None
        self.progress_bar = None
        self.status_bar_set = False
        self.version_label = None

    def setStatusBar(self, status_bar):
        self.status_bar = status_bar
        self.status_bar_set = True


class StatusBarManagerTest(unittest.TestCase):
    def setUp(self):
        from ui.status_bar_manager import StatusBarManager
        from config.constants import ApplicationConstants

        self.window = DummyWindow()
        self.status_bar = DummyStatusBar()
        self.progress_bar = DummyProgressBar()
        self.expected_version_text = f"{ApplicationConstants.APP_NAME} v{ApplicationConstants.APP_VERSION}"

        self.manager = StatusBarManager(
            self.window,
            status_bar_factory=lambda: self.status_bar,
            progress_bar_factory=lambda: self.progress_bar,
            version_label_factory=lambda: DummyLabel(),
        )

    def test_create_status_bar_initialises_components(self):
        self.manager.create_status_bar()
        self.assertTrue(self.window.status_bar_set)
        self.assertIs(self.window.status_bar, self.status_bar)
        self.assertIs(self.window.progress_bar, self.progress_bar)
        self.assertTrue(self.progress_bar.visible is False)
        self.assertIn(('Ready', 0), self.status_bar.message_calls)
        self.assertIsInstance(self.window.version_label, DummyLabel)
        self.assertEqual(self.status_bar.widgets[0], self.window.version_label)
        self.assertEqual(self.window.version_label.text, self.expected_version_text)

    def test_show_message_delegates(self):
        self.manager.create_status_bar()
        self.manager.show_message('Hello', timeout=1000)
        self.assertEqual(self.status_bar.message_calls[-1], ('Hello', 1000))

    def test_update_and_reset_progress(self):
        self.manager.create_status_bar()
        self.manager.update_progress(current=5, total=10, message='Halfway')
        self.assertTrue(self.progress_bar.visible)
        self.assertEqual(self.progress_bar.minimum, 0)
        self.assertEqual(self.progress_bar.maximum, 10)
        self.assertEqual(self.progress_bar.value, 5)
        self.assertEqual(self.status_bar.message_calls[-1], ('Halfway', 0))

        self.manager.reset_progress()
        self.assertFalse(self.progress_bar.visible)
        self.assertEqual(self.progress_bar.value, 0)
        self.assertEqual(self.status_bar.message_calls[-1], ('Ready', 0))

    def test_update_progress_without_total_enables_busy_indicator(self):
        self.manager.create_status_bar()

        self.manager.update_progress(current=0, total=0, message='Loading devices')

        self.assertTrue(self.progress_bar.visible)
        self.assertEqual(self.progress_bar.minimum, 0)
        self.assertEqual(self.progress_bar.maximum, 0)
        self.assertEqual(self.progress_bar.value, 0)
        self.assertEqual(self.status_bar.message_calls[-1], ('Loading devices', 0))


if __name__ == '__main__':
    unittest.main()
