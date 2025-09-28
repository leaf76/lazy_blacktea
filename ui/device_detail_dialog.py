"""Dialog for displaying detailed device information."""

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QGuiApplication
from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QLabel,
    QPlainTextEdit,
    QDialogButtonBox,
    QMessageBox,
)

class DeviceDetailDialog(QDialog):
    """Modal dialog that shows formatted device details."""

    def __init__(self, parent, device, detail_text: str, refresh_callback, copy_callback=None):
        super().__init__(parent)
        self.setWindowTitle(f'Device Details - {device.device_model}')
        self.setModal(True)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.resize(680, 520)
        self._refresh_callback = refresh_callback
        self._copy_callback = copy_callback

        layout = QVBoxLayout(self)

        header = QLabel(f"{device.device_model} ({device.device_serial_num})")
        header.setStyleSheet("font-weight: bold; font-size: 14px;")
        layout.addWidget(header)

        self.detail_view = QPlainTextEdit()
        self.detail_view.setReadOnly(True)
        self.detail_view.setPlainText(detail_text)
        layout.addWidget(self.detail_view)

        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        button_box.rejected.connect(self.reject)
        button_box.accepted.connect(self.accept)
        self.refresh_button = button_box.addButton('Refresh Details', QDialogButtonBox.ButtonRole.ActionRole)
        self.refresh_button.clicked.connect(self._refresh_details)
        self.copy_button = button_box.addButton('📋 Copy Device Info', QDialogButtonBox.ButtonRole.ActionRole)
        self.copy_button.clicked.connect(self._copy_device_info)
        layout.addWidget(button_box)

    def _refresh_details(self):
        if not callable(self._refresh_callback):
            return

        self.refresh_button.setEnabled(False)
        try:
            updated_text = self._refresh_callback()
            if isinstance(updated_text, str):
                self.detail_view.setPlainText(updated_text)
        except Exception as exc:  # pragma: no cover - defensive UI path
            QMessageBox.warning(self, 'Refresh Failed', str(exc))
        finally:
            self.refresh_button.setEnabled(True)

    def _copy_device_info(self):
        detail_text = self.detail_view.toPlainText()
        if not detail_text.strip():
            QMessageBox.warning(self, 'Copy Failed', 'No device details available to copy.')
            return

        try:
            if callable(self._copy_callback):
                self._copy_callback(detail_text)
            else:
                clipboard = QGuiApplication.clipboard()
                clipboard.setText(detail_text)
        except Exception as exc:  # pragma: no cover - defensive UI path
            QMessageBox.warning(self, 'Copy Failed', str(exc))
