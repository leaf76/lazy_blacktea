"""Widget displaying details for the active device selection."""

from __future__ import annotations

from collections import OrderedDict
from typing import Dict, List, Optional, Tuple

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QLabel,
    QHBoxLayout,
    QPushButton,
    QFrame,
    QGridLayout,
    QSizePolicy,
    QScrollArea,
    QTextEdit,
)

from utils import adb_models
from ui.style_manager import StyleManager, ButtonStyle, LabelStyle


class DeviceOverviewWidget(QWidget):
    """Provides an always-visible summary for the active device."""

    _PLACEHOLDER_TEXT = 'Select a device from the list to view details.'

    def __init__(self, main_window) -> None:
        super().__init__(main_window)
        self._window = main_window
        self._active_serial: Optional[str] = None
        self._active_model: str = ''
        self._summary_labels: Dict[str, QLabel] = {}
        self._current_detail_text: str = self._PLACEHOLDER_TEXT
        self._last_summary_signature: Optional[Tuple] = None

        self._build_ui()
        self.set_overview(None, None, None)

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 16, 14, 16)
        layout.setSpacing(14)

        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)

        title_label = QLabel('Active Device Overview')
        title_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        StyleManager.apply_label_style(title_label, LabelStyle.HEADER)
        layout.addWidget(title_label)

        scroll_container = QFrame()
        scroll_container.setObjectName('device_overview_summary_container')
        StyleManager.apply_panel_frame(scroll_container, accent=True)
        container_layout = QVBoxLayout(scroll_container)
        container_layout.setContentsMargins(0, 0, 0, 0)

        summary_scroll = QScrollArea()
        summary_scroll.setWidgetResizable(True)
        summary_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        summary_scroll.setObjectName('device_overview_summary_scroll')

        summary_frame = QFrame()
        summary_frame.setObjectName('device_overview_summary')
        summary_frame.setStyleSheet('#device_overview_summary { background-color: #ffffff; }')
        self._summary_layout = QVBoxLayout(summary_frame)
        self._summary_layout.setContentsMargins(18, 16, 18, 16)
        self._summary_layout.setSpacing(16)

        summary_scroll.setWidget(summary_frame)
        container_layout.addWidget(summary_scroll)

        layout.addWidget(scroll_container, 1)

        button_row = QHBoxLayout()
        button_row.setSpacing(12)

        button_row.addStretch(1)

        self.refresh_button = QPushButton('🔄 Refresh Details')
        StyleManager.apply_button_style(self.refresh_button, ButtonStyle.PRIMARY, fixed_height=36)
        self.refresh_button.clicked.connect(self._window.refresh_active_device_overview)
        button_row.addWidget(self.refresh_button)

        self.copy_button = QPushButton('📋 Copy Overview')
        StyleManager.apply_button_style(self.copy_button, ButtonStyle.SECONDARY, fixed_height=36)
        self.copy_button.clicked.connect(self._window.copy_active_device_overview)
        button_row.addWidget(self.copy_button)

        layout.addLayout(button_row)

    def get_active_serial(self) -> Optional[str]:
        """Return the serial currently displayed in the overview."""
        return self._active_serial

    def get_current_detail_text(self) -> str:
        """Expose the current detail payload (used for copy operations)."""
        return self._current_detail_text

    def set_overview(
        self,
        device: Optional[adb_models.DeviceInfo],
        serial: Optional[str],
        detail_text: Optional[str],
    ) -> None:
        """Render overview state for the provided device or show a placeholder."""
        self._active_serial = serial
        if device is None or serial is None:
            self._active_model = ''
            self._current_detail_text = self._PLACEHOLDER_TEXT
            self._render_summary()
            self._set_controls_enabled(False)
            self._last_summary_signature = None
            return

        summary_sections = self._window.device_list_controller.get_device_overview_summary(device, serial)
        summary_signature = tuple(
            (section_key, tuple(entries))
            for section_key, entries in summary_sections.items()
        )

        normalized_detail_text = detail_text or 'No details available.'

        if (
            self._active_serial == serial
            and self._current_detail_text == normalized_detail_text
            and self._last_summary_signature == summary_signature
        ):
            return

        self._active_model = device.device_model or 'Unknown Device'
        truncated_serial = f'{serial[:8]}...' if len(serial) > 8 else serial
        header_text = f'{self._active_model} ({truncated_serial})'

        self._render_summary(summary_sections, header_text=header_text)

        self._current_detail_text = normalized_detail_text
        self._set_controls_enabled(True)
        self._last_summary_signature = summary_signature

    def _set_controls_enabled(self, enabled: bool) -> None:
        self.refresh_button.setEnabled(enabled)
        self.copy_button.setEnabled(enabled)

    def get_active_model(self) -> str:
        """Return the model associated with the displayed device."""
        return self._active_model

    def _render_summary(
        self,
        sections: Optional[OrderedDict[str, List[Tuple[str, str]]]] = None,
        *,
        header_text: Optional[str] = None,
    ) -> None:
        if sections is None:
            sections = OrderedDict()

        for i in reversed(range(self._summary_layout.count())):
            item = self._summary_layout.takeAt(i)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        if not sections:
            placeholder = QLabel('Select a device to view hardware, battery, and status details.')
            StyleManager.apply_label_style(placeholder, LabelStyle.STATUS)
            placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._summary_layout.addWidget(placeholder)
            self._summary_labels.clear()
            return

        self._summary_labels.clear()

        if header_text:
            header_label = QLabel(header_text)
            StyleManager.apply_label_style(header_label, LabelStyle.SUBHEADER)
            header_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            self._summary_layout.addWidget(header_label)

        for section_key, entries in sections.items():
            section_frame = QFrame()
            section_frame.setObjectName(f'overview_section_frame_{section_key}')
            section_layout = QVBoxLayout(section_frame)
            section_layout.setContentsMargins(0, 0, 0, 0)
            section_layout.setSpacing(6)

            header_label = QLabel(self._format_section_header(section_key))
            header_label.setObjectName(f'overview_section_{section_key}')
            StyleManager.apply_label_style(header_label, LabelStyle.SUBHEADER)
            section_layout.addWidget(header_label)

            grid = QGridLayout()
            grid.setHorizontalSpacing(18)
            grid.setVerticalSpacing(4)
            grid.setColumnMinimumWidth(0, 130)
            grid.setColumnStretch(1, 1)

            for row, (label_text, value_text) in enumerate(entries):
                label_widget = QLabel(label_text)
                StyleManager.apply_label_style(label_widget, LabelStyle.INFO)
                grid.addWidget(label_widget, row, 0, Qt.AlignmentFlag.AlignLeft)

                sanitized = ''.join(
                    ch if ch.isalnum() else '_' for ch in label_text.lower()
                ).rstrip('_')
                object_name = f'device_overview_value_{section_key}_{sanitized}'

                if section_key == 'device' and label_text.lower() == 'build fingerprint':
                    value_widget = QTextEdit()
                    value_widget.setObjectName(object_name)
                    value_widget.setReadOnly(True)
                    value_widget.setPlainText(value_text)
                    value_widget.setMinimumHeight(48)
                    value_widget.setMaximumHeight(96)
                    value_widget.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
                    value_widget.setStyleSheet(
                        'background-color: #f8fafc;'
                        'border: 1px solid #d0d7e2;'
                        'border-radius: 8px;'
                        'padding: 6px;'
                        'font-weight: 500;'
                        'color: #1c2a3f;'
                    )
                else:
                    value_widget = QLabel(value_text)
                    value_widget.setObjectName(object_name)
                    value_widget.setStyleSheet('font-weight: 600; color: #1c2a3f;')
                    value_widget.setWordWrap(True)
                    value_widget.setTextInteractionFlags(
                        Qt.TextInteractionFlag.TextSelectableByMouse
                        | Qt.TextInteractionFlag.TextSelectableByKeyboard
                    )

                grid.addWidget(value_widget, row, 1, Qt.AlignmentFlag.AlignLeft)
                self._summary_labels[f'{section_key}_{label_text.lower()}'] = value_widget

            section_layout.addLayout(grid)

            self._summary_layout.addWidget(section_frame)

    @staticmethod
    def _format_section_header(key: str) -> str:
        mapping = {
            'device': 'Device',
            'connectivity': 'Connectivity',
            'hardware': 'Hardware Information',
            'battery': 'Battery Information',
        }
        return mapping.get(key, key.title())


__all__ = ['DeviceOverviewWidget']
