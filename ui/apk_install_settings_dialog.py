"""Dialog for configuring APK install arguments."""

from __future__ import annotations

from typing import Optional

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QVBoxLayout,
)

from config.config_manager import ApkInstallSettings


class ApkInstallSettingsDialog(QDialog):
    """Provide UI for adjusting adb install flags used by the app."""

    def __init__(self, current_settings: ApkInstallSettings, parent=None):
        super().__init__(parent)
        self.setWindowTitle('APK Install Settings')
        self.setModal(True)
        self._result_settings: Optional[ApkInstallSettings] = None

        self._build_ui()
        self._populate_from_settings(current_settings)

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        intro = QLabel('Choose default flags applied to "adb install". These will be used for future installs.')
        intro.setWordWrap(True)
        layout.addWidget(intro)

        # Flags
        self.replace_checkbox = QCheckBox('Replace existing app (-r)')
        self.downgrade_checkbox = QCheckBox('Allow version downgrade (-d)')
        self.grant_checkbox = QCheckBox('Grant all runtime permissions (-g)')
        self.test_checkbox = QCheckBox('Allow test packages (-t)')

        layout.addWidget(self.replace_checkbox)
        layout.addWidget(self.downgrade_checkbox)
        layout.addWidget(self.grant_checkbox)
        layout.addWidget(self.test_checkbox)

        # Extra args
        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
        form.setFormAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        form.setHorizontalSpacing(16)
        form.setVerticalSpacing(10)

        self.extra_args_edit = QLineEdit()
        self.extra_args_edit.setPlaceholderText('Additional args, e.g. --abi arm64-v8a --install-location 1')
        form.addRow('Extra args', self.extra_args_edit)
        layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._handle_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _populate_from_settings(self, s: ApkInstallSettings) -> None:
        self.replace_checkbox.setChecked(s.replace_existing)
        self.downgrade_checkbox.setChecked(s.allow_downgrade)
        self.grant_checkbox.setChecked(s.grant_permissions)
        self.test_checkbox.setChecked(s.allow_test_packages)
        self.extra_args_edit.setText(s.extra_args)

    def _handle_accept(self) -> None:
        self._result_settings = ApkInstallSettings(
            replace_existing=self.replace_checkbox.isChecked(),
            allow_downgrade=self.downgrade_checkbox.isChecked(),
            grant_permissions=self.grant_checkbox.isChecked(),
            allow_test_packages=self.test_checkbox.isChecked(),
            extra_args=self.extra_args_edit.text().strip(),
        )
        self.accept()

    def get_settings(self) -> Optional[ApkInstallSettings]:
        return self._result_settings


__all__ = ["ApkInstallSettingsDialog"]

