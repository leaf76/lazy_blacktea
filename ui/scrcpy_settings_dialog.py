"""Dialog for configuring scrcpy mirroring options."""

from __future__ import annotations

import re
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
    QMessageBox,
    QVBoxLayout,
)

from config.config_manager import ScrcpySettings


class ScrcpySettingsDialog(QDialog):
    """Provide a lightweight UI for adjusting scrcpy launch parameters."""

    def __init__(self, current_settings: ScrcpySettings, parent=None):
        super().__init__(parent)
        self.setWindowTitle('scrcpy Settings')
        self.setModal(True)
        self._current_settings = current_settings
        self._result_settings: Optional[ScrcpySettings] = None

        self._build_ui()
        self._populate_from_settings(current_settings)

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        intro_label = QLabel(
            'Customize how scrcpy mirrors your devices. These options apply to future sessions.'
        )
        intro_label.setWordWrap(True)
        layout.addWidget(intro_label)

        checkbox_layout = QGridLayout()
        checkbox_layout.setVerticalSpacing(6)
        checkbox_layout.setHorizontalSpacing(24)

        self.stay_awake_checkbox = QCheckBox('Keep device awake (--stay-awake)')
        checkbox_layout.addWidget(self.stay_awake_checkbox, 0, 0)

        self.turn_screen_off_checkbox = QCheckBox('Turn device screen off (--turn-screen-off)')
        checkbox_layout.addWidget(self.turn_screen_off_checkbox, 0, 1)

        self.disable_screensaver_checkbox = QCheckBox('Disable host screensaver (--disable-screensaver)')
        checkbox_layout.addWidget(self.disable_screensaver_checkbox, 1, 0)

        self.enable_audio_checkbox = QCheckBox('Forward audio playback (scrcpy 3.x+)')
        checkbox_layout.addWidget(self.enable_audio_checkbox, 1, 1)

        layout.addLayout(checkbox_layout)

        form_layout = QFormLayout()
        form_layout.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
        form_layout.setFormAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        form_layout.setHorizontalSpacing(16)
        form_layout.setVerticalSpacing(10)

        self.bitrate_edit = QLineEdit()
        self.bitrate_edit.setPlaceholderText('Example: 12M or 8000000 (leave blank for default)')
        form_layout.addRow('Bit rate', self.bitrate_edit)

        self.max_size_edit = QLineEdit()
        self.max_size_edit.setPlaceholderText('Maximum width in pixels (leave blank for default)')
        form_layout.addRow('Max size', self.max_size_edit)

        self.extra_args_edit = QLineEdit()
        self.extra_args_edit.setPlaceholderText('Additional arguments, e.g. --window-title "My Device"')
        form_layout.addRow('Extra args', self.extra_args_edit)

        layout.addLayout(form_layout)

        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        button_box.accepted.connect(self._handle_accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def _populate_from_settings(self, settings: ScrcpySettings) -> None:
        self.stay_awake_checkbox.setChecked(settings.stay_awake)
        self.turn_screen_off_checkbox.setChecked(settings.turn_screen_off)
        self.disable_screensaver_checkbox.setChecked(settings.disable_screensaver)
        self.enable_audio_checkbox.setChecked(settings.enable_audio_playback)

        self.bitrate_edit.setText(settings.bitrate)
        self.max_size_edit.setText(str(settings.max_size) if settings.max_size > 0 else '')
        self.extra_args_edit.setText(settings.extra_args)

    def _handle_accept(self) -> None:
        bitrate = self.bitrate_edit.text().strip()
        if bitrate and not re.fullmatch(r'\d+[kKmMgG]?', bitrate):
            self._show_validation_error('Bit rate must be numeric optionally followed by K or M (e.g. 12M).')
            return

        max_size_text = self.max_size_edit.text().strip()
        max_size = 0
        if max_size_text:
            try:
                max_size = int(max_size_text)
            except ValueError:
                self._show_validation_error('Max size must be a positive integer.')
                return
            if max_size <= 0:
                self._show_validation_error('Max size must be greater than zero when provided.')
                return

        extra_args = self.extra_args_edit.text().strip()

        self._result_settings = ScrcpySettings(
            stay_awake=self.stay_awake_checkbox.isChecked(),
            turn_screen_off=self.turn_screen_off_checkbox.isChecked(),
            disable_screensaver=self.disable_screensaver_checkbox.isChecked(),
            enable_audio_playback=self.enable_audio_checkbox.isChecked(),
            bitrate=bitrate,
            max_size=max_size,
            extra_args=extra_args,
        )
        self.accept()

    def _show_validation_error(self, message: str) -> None:
        QMessageBox.warning(self, 'Validation Error', message)

    def get_settings(self) -> Optional[ScrcpySettings]:
        """Return the settings collected from the dialog, if any."""
        return self._result_settings


__all__ = ["ScrcpySettingsDialog"]
