import os
import sys
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt6.QtWidgets import QApplication, QLabel  # noqa: E402


_APP = QApplication.instance() or QApplication([])


class _Device:
    def __init__(self, serial, model):
        self.device_serial_num = serial
        self.device_model = model


class _Viewer(QLabel):
    def __init__(self, device, parent=None):
        super().__init__(f"viewer:{device.device_serial_num}", parent)
        self.device = device
        self.cleaned = False

    def cleanup(self):
        self.cleaned = True


class LogcatPaneTests(unittest.TestCase):
    def setUp(self):
        from ui.shell import LogcatPane

        self.created = []

        def viewer_factory(device, parent=None):
            widget = _Viewer(device, parent)
            self.created.append(widget)
            return widget

        self.pane = LogcatPane(viewer_factory=viewer_factory)
        self.addCleanup(self.pane.deleteLater)

    def test_empty_state_is_default(self):
        self.assertTrue(self.pane.is_empty())
        self.assertEqual(self.pane.active_serial(), None)

    def test_set_devices_selects_first_device(self):
        self.pane.set_devices([_Device("SER1", "Pixel 7"), _Device("SER2", "Pixel 6")])

        self.assertFalse(self.pane.is_empty())
        self.assertEqual(self.pane.active_serial(), "SER1")

    def test_open_active_device_embeds_viewer(self):
        self.pane.set_devices([_Device("SER1", "Pixel 7")])

        self.assertTrue(self.pane.open_active_device())

        self.assertEqual(len(self.created), 1)
        self.assertEqual(self.pane.current_viewer().device.device_serial_num, "SER1")

    def test_cleanup_releases_embedded_viewer(self):
        self.pane.set_devices([_Device("SER1", "Pixel 7")])
        self.assertTrue(self.pane.open_active_device())
        viewer = self.pane.current_viewer()

        self.pane.cleanup()

        self.assertTrue(viewer.cleaned)
        self.assertIsNone(self.pane.current_viewer())


if __name__ == "__main__":
    unittest.main(verbosity=2)
