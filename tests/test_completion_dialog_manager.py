import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class DummySystemActionsManager:
    """Minimal system actions stub for dialog tests."""

    def __init__(self):
        self.copied_values = []
        self.opened_paths = []

    def copy_to_clipboard(self, value):
        self.copied_values.append(value)

    def open_folder(self, path):
        self.opened_paths.append(path)


class DummyWindow:
    def __init__(self):
        self.take_screenshot_called = False
        self.start_screen_record_called = False
        self.system_actions_manager = DummySystemActionsManager()

    def take_screenshot(self):
        self.take_screenshot_called = True

    def start_screen_record(self):
        self.start_screen_record_called = True


class CompletionDialogManagerTest(unittest.TestCase):
    def setUp(self):
        from ui.completion_dialog_manager import CompletionDialogManager

        self.window = DummyWindow()
        self.screenshot_payloads = []
        self.file_payloads = []

        def screenshot_builder(window, payload):
            self.assertIs(window, self.window)
            self.screenshot_payloads.append(payload)

        def file_builder(window, payload):
            self.assertIs(window, self.window)
            self.file_payloads.append(payload)

        self.manager = CompletionDialogManager(
            self.window,
            screenshot_builder=screenshot_builder,
            file_builder=file_builder,
        )

    def test_show_screenshot_summary_collects_models(self):
        self.manager.show_screenshot_summary('/tmp/output', ['Pixel', 'Galaxy'])
        payload = self.screenshot_payloads.pop()
        self.assertEqual(payload['title'], '⚡ Screenshot Quick Actions')
        self.assertEqual(payload['output_path'], '/tmp/output')
        self.assertEqual(payload['device_models'], ['Pixel', 'Galaxy'])
        self.assertIn('file_count', payload['suggested_actions'])

    def test_show_file_generation_summary(self):
        self.manager.show_file_generation_summary(
            operation_name='Bug Report',
            summary_text='Completed successfully',
            output_path='/tmp/report',
            success_metric=3,
            icon='✅',
        )
        payload = self.file_payloads.pop()
        self.assertEqual(payload['title'], '✅ Bug Report Completed')
        self.assertEqual(payload['summary_text'], 'Completed successfully')
        self.assertEqual(payload['processed'], 3)
        self.assertEqual(payload['output_path'], '/tmp/report')

    def test_quick_actions_open_folder_button_calls_open(self):
        from ui.completion_dialog_manager import CompletionDialogManager

        window = DummyWindow()
        manager = CompletionDialogManager(window)

        payload = {
            'title': '⚡ Screenshot Quick Actions',
            'device_summary': 'Pixel 7',
            'output_path': '/tmp/screens',
            'suggested_actions': {'file_count': 0},
        }

        class FakeSignal:
            def __init__(self):
                self.slot = None

            def connect(self, slot):
                self.slot = slot

        class FakeButton:
            instances = []

            def __init__(self, text):
                self.text = text
                self.clicked = FakeSignal()
                self._style = None
                self._height = None
                FakeButton.instances.append(self)

            def setStyleSheet(self, style):
                self._style = style

            def setFixedHeight(self, height):
                self._height = height

        class FakeLabel:
            def __init__(self, text):
                self.text = text
                self._style = None
                self.word_wrap = False

            def setStyleSheet(self, style):
                self._style = style

            def setWordWrap(self, state):
                self.word_wrap = state

        class FakeLayout:
            def __init__(self, *_):
                self.widgets = []

            def addWidget(self, widget):
                self.widgets.append(widget)

            def addLayout(self, layout):
                self.widgets.append(layout)

        class FakeDialog:
            def __init__(self, *_):
                self.accepted = False

            def setWindowTitle(self, title):
                self.title = title

            def setModal(self, modal):
                self.modal = modal

            def resize(self, width, height):
                self.size = (width, height)

            def accept(self):
                self.accepted = True

            def exec(self):
                self.exec_called = True

        FakeButton.instances = []

        with patch('ui.completion_dialog_manager.QDialog', FakeDialog), \
             patch('ui.completion_dialog_manager.QVBoxLayout', FakeLayout), \
             patch('ui.completion_dialog_manager.QLabel', FakeLabel), \
             patch('ui.completion_dialog_manager.QPushButton', FakeButton):
            manager._build_screenshot_dialog(window, payload)

        open_buttons = [btn for btn in FakeButton.instances if 'Open Folder' in btn.text]
        self.assertTrue(open_buttons, 'Open Folder quick action should be present')

        open_button = open_buttons[0]
        self.assertIsNotNone(open_button.clicked.slot)

        open_button.clicked.slot()

        self.assertEqual(window.system_actions_manager.opened_paths, ['/tmp/screens'])
        self.assertEqual(window.system_actions_manager.copied_values, [])


if __name__ == '__main__':
    unittest.main()
