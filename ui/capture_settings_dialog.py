"""Dialog to configure Screenshot and Screen Record options."""

from __future__ import annotations

from typing import Optional

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGridLayout,
    QLabel,
    QLineEdit,
    QSpinBox,
    QVBoxLayout,
    QGroupBox,
)

from config.config_manager import ScreenshotSettings, ScreenRecordSettings


class CaptureSettingsDialog(QDialog):
    """Settings dialog for screenshot and screen recording parameters."""

    def __init__(self, screenshot: ScreenshotSettings, record: ScreenRecordSettings, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Capture Settings')
        self.setModal(True)
        self._result_screenshot: Optional[ScreenshotSettings] = None
        self._result_record: Optional[ScreenRecordSettings] = None

        self._build_ui()
        self._populate_from_settings(screenshot, record)

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        intro = QLabel('Configure default parameters for screenshots and screen recordings.')
        intro.setWordWrap(True)
        layout.addWidget(intro)

        # Screenshot section
        ss_group = QGroupBox('Screenshot (screencap)')
        ss_form = QFormLayout()
        ss_form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
        ss_form.setFormAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        ss_form.setHorizontalSpacing(16)
        ss_form.setVerticalSpacing(10)
        self.screenshot_extra_args = QLineEdit()
        self.screenshot_extra_args.setPlaceholderText('Additional args to screencap, e.g. -d 0')
        ss_form.addRow('Extra args', self.screenshot_extra_args)
        ss_group.setLayout(ss_form)
        layout.addWidget(ss_group)

        # Screen record section
        rec_group = QGroupBox('Screen Record (screenrecord)')
        rec_form = QFormLayout()
        rec_form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
        rec_form.setFormAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        rec_form.setHorizontalSpacing(16)
        rec_form.setVerticalSpacing(10)

        self.record_bitrate = QLineEdit()
        self.record_bitrate.setPlaceholderText('Bit rate in bps (e.g., 8000000)')
        rec_form.addRow('Bit rate', self.record_bitrate)

        self.record_time_limit = QSpinBox()
        self.record_time_limit.setRange(0, 36000)
        self.record_time_limit.setSuffix(' s')
        self.record_time_limit.setToolTip('0 means unlimited')
        rec_form.addRow('Time limit', self.record_time_limit)

        self.record_size = QLineEdit()
        self.record_size.setPlaceholderText('Width x Height (e.g., 1280x720)')
        rec_form.addRow('Size', self.record_size)

        self.record_extra_args = QLineEdit()
        self.record_extra_args.setPlaceholderText('Additional args, e.g. --verbose --rot 90')
        rec_form.addRow('Extra args', self.record_extra_args)

        rec_group.setLayout(rec_form)
        layout.addWidget(rec_group)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._handle_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _populate_from_settings(self, screenshot: ScreenshotSettings, record: ScreenRecordSettings) -> None:
        self.screenshot_extra_args.setText(screenshot.extra_args)
        self.record_bitrate.setText(record.bit_rate)
        self.record_time_limit.setValue(max(0, int(record.time_limit_sec or 0)))
        self.record_size.setText(record.size)
        self.record_extra_args.setText(record.extra_args)

    def _handle_accept(self) -> None:
        ss = ScreenshotSettings(
            extra_args=self.screenshot_extra_args.text().strip()
        )
        rec = ScreenRecordSettings(
            bit_rate=self.record_bitrate.text().strip(),
            time_limit_sec=int(self.record_time_limit.value()),
            size=self.record_size.text().strip(),
            extra_args=self.record_extra_args.text().strip(),
        )
        self._result_screenshot = ss
        self._result_record = rec
        self.accept()

    def get_settings(self) -> tuple[Optional[ScreenshotSettings], Optional[ScreenRecordSettings]]:
        return self._result_screenshot, self._result_record


__all__ = ["CaptureSettingsDialog"]

