import os
import sys
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt6.QtWidgets import QApplication  # noqa: E402


_APP = QApplication.instance() or QApplication([])


class UpdateDialogTests(unittest.TestCase):
    def setUp(self):
        from utils.update_service import UpdateAsset, UpdateInfo

        self.asset = UpdateAsset(
            name="LazyBlacktea-macos-arm64.dmg",
            download_url="https://github.com/leaf76/lazy_blacktea/releases/download/v0.0.52/LazyBlacktea-macos-arm64.dmg",
            size=2048,
            sha256="a" * 64,
        )
        self.info = UpdateInfo(
            current_version="0.0.51",
            latest_version="0.0.52",
            release_url="https://github.com/leaf76/lazy_blacktea/releases/tag/v0.0.52",
            published_at="2026-05-24T00:00:00Z",
            release_notes="Release notes",
            asset=self.asset,
            is_update_available=True,
        )

    def test_check_result_enables_download_for_available_update(self):
        from ui.update_dialog import UpdateDialog

        dialog = UpdateDialog(current_version="0.0.51")
        self.addCleanup(dialog.deleteLater)

        dialog.set_check_result(self.info)

        self.assertIn("0.0.52", dialog.latest_version_label.text())
        self.assertIn("LazyBlacktea-macos-arm64.dmg", dialog.asset_label.text())
        self.assertTrue(dialog.download_button.isEnabled())
        self.assertTrue(dialog.open_release_button.isEnabled())

    def test_no_update_result_disables_download(self):
        from ui.update_dialog import UpdateDialog

        self.info.is_update_available = False
        self.info.asset = None
        dialog = UpdateDialog(current_version="0.0.51")
        self.addCleanup(dialog.deleteLater)

        dialog.set_check_result(self.info)

        self.assertIn("up to date", dialog.status_label.text().lower())
        self.assertFalse(dialog.download_button.isEnabled())

    def test_error_disables_download_action(self):
        from ui.update_dialog import UpdateDialog
        from utils.update_service import UpdateVerificationError

        dialog = UpdateDialog(current_version="0.0.51")
        self.addCleanup(dialog.deleteLater)

        dialog.set_error(UpdateVerificationError("Checksum mismatch"))

        self.assertIn("Checksum mismatch", dialog.status_label.text())
        self.assertFalse(dialog.download_button.isEnabled())
        self.assertFalse(dialog.open_download_button.isEnabled())

    def test_download_result_enables_open_download_action(self):
        from ui.update_dialog import UpdateDialog

        dialog = UpdateDialog(current_version="0.0.51")
        self.addCleanup(dialog.deleteLater)

        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "LazyBlacktea-macos-arm64.dmg"
            path.write_bytes(b"payload")
            dialog.set_download_result(path)

            self.assertIn("verified", dialog.status_label.text().lower())
            self.assertTrue(dialog.open_download_button.isEnabled())

    def test_skip_version_emits_signal_and_persists(self):
        from ui.update_dialog import UpdateDialog

        class _Config:
            def __init__(self):
                self.calls = []

            def update_update_settings(self, **kwargs):
                self.calls.append(kwargs)

        config = _Config()
        skipped = []
        dialog = UpdateDialog(current_version="0.0.51", config_manager=config)
        self.addCleanup(dialog.deleteLater)
        dialog.set_check_result(self.info)
        dialog.version_skipped.connect(skipped.append)

        dialog.skip_current_version()

        self.assertEqual(config.calls, [{"skipped_version": "0.0.52"}])
        self.assertEqual(skipped, ["0.0.52"])
        self.assertFalse(dialog.download_button.isEnabled())


if __name__ == "__main__":
    unittest.main(verbosity=2)
