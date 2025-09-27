import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class DummyWindow:
    def __init__(self):
        self.take_screenshot_called = False
        self.start_screen_record_called = False

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


if __name__ == '__main__':
    unittest.main()
