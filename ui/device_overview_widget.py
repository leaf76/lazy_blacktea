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
from ui.style_manager import StyleManager, LabelStyle


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
        palette = self._palette()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 16, 14, 16)
        layout.setSpacing(14)

        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)

        title_row = QHBoxLayout()
        title_label = QLabel('Active Device Overview')
        title_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        StyleManager.apply_label_style(title_label, LabelStyle.HEADER)
        self._apply_header_label_palette(title_label)
        title_row.addWidget(title_label)

        title_row.addStretch(1)

        self.refresh_button = QPushButton('Refresh')
        self.refresh_button.setToolTip('Refresh details')
        self._apply_refresh_button_style(self.refresh_button)
        self.refresh_button.clicked.connect(self._window.refresh_active_device_overview)
        title_row.addWidget(self.refresh_button)

        layout.addLayout(title_row)

        scroll_container = QFrame()
        scroll_container.setObjectName('device_overview_summary_container')
        StyleManager.apply_panel_frame(scroll_container)
        self._apply_dark_panel(scroll_container)
        container_layout = QVBoxLayout(scroll_container)
        container_layout.setContentsMargins(0, 0, 0, 0)

        summary_scroll = QScrollArea()
        summary_scroll.setWidgetResizable(True)
        summary_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        summary_scroll.setObjectName('device_overview_summary_scroll')

        summary_frame = QFrame()
        summary_frame.setObjectName('device_overview_summary')
        summary_frame.setStyleSheet(
            f"""
            #device_overview_summary {{
                background-color: {palette['surface_alt']};
                border: 1px solid {palette['panel_border']};
                border-radius: 12px;
            }}
            #device_overview_summary QLabel {{
                color: {palette['text_primary']};
            }}
            #device_overview_summary QTextEdit {{
                color: {palette['value_text']};
                background-color: {palette['input_background']};
                border: 1px solid {palette['input_border']};
                border-radius: 8px;
            }}
            """
        )
        self._summary_layout = QVBoxLayout(summary_frame)
        self._summary_layout.setContentsMargins(18, 16, 18, 16)
        self._summary_layout.setSpacing(16)

        summary_scroll.setWidget(summary_frame)
        container_layout.addWidget(summary_scroll)

        layout.addWidget(scroll_container, 1)

        tools_box = QFrame()
        StyleManager.apply_panel_frame(tools_box)
        self._apply_dark_panel(tools_box, highlight=True)
        tools_layout = QVBoxLayout(tools_box)
        tools_layout.setContentsMargins(16, 14, 16, 14)
        tools_layout.setSpacing(10)

        tools_header = QLabel('Quick Actions')
        StyleManager.apply_label_style(tools_header, LabelStyle.SUBHEADER)
        self._apply_subheader_label_palette(tools_header)
        tools_layout.addWidget(tools_header)

        button_grid = QGridLayout()
        button_grid.setContentsMargins(0, 0, 0, 0)
        button_grid.setHorizontalSpacing(12)
        button_grid.setVerticalSpacing(10)
        button_grid.setAlignment(Qt.AlignmentFlag.AlignTop)

        self.logcat_button = QPushButton('Logcat')
        self.logcat_button.setToolTip('View device logs')
        self._apply_primary_action_style(self.logcat_button)
        self.logcat_button.clicked.connect(self._window.show_logcat)
        button_grid.addWidget(self.logcat_button, 0, 0)

        self.ui_inspector_button = QPushButton('Inspect Layout')
        self.ui_inspector_button.setToolTip('Launch UI inspector')
        self._apply_primary_action_style(self.ui_inspector_button)
        self.ui_inspector_button.clicked.connect(self._window.launch_ui_inspector)
        button_grid.addWidget(self.ui_inspector_button, 0, 1)

        self.bluetooth_button = QPushButton('Bluetooth Monitor')
        self.bluetooth_button.setToolTip('Open Bluetooth monitor')
        self._apply_secondary_action_style(self.bluetooth_button)
        self.bluetooth_button.clicked.connect(self._window.monitor_bluetooth)
        button_grid.addWidget(self.bluetooth_button, 1, 0)

        self.copy_button = QPushButton('Copy Info')
        self.copy_button.setToolTip('Copy overview details to clipboard')
        self._apply_secondary_action_style(self.copy_button)
        self.copy_button.clicked.connect(self._window.copy_active_device_overview)
        button_grid.addWidget(self.copy_button, 1, 1)

        button_grid.setColumnStretch(0, 1)
        button_grid.setColumnStretch(1, 1)
        button_grid.setRowStretch(0, 1)
        button_grid.setRowStretch(1, 1)

        tools_layout.addLayout(button_grid)
        tools_layout.addStretch(1)
        layout.addWidget(tools_box)

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
        self.logcat_button.setEnabled(enabled)
        self.ui_inspector_button.setEnabled(enabled)
        self.bluetooth_button.setEnabled(enabled)

    def _palette(self) -> Dict[str, str]:
        """Return palette values aligned with the active StyleManager theme."""
        colors = StyleManager.COLORS
        panel_bg = colors.get('panel_background', '#252A37')
        tile_bg = colors.get('tile_bg', '#2E3449')
        tile_primary_bg = colors.get('tile_primary_bg', '#333A56')
        tile_primary_border = colors.get('tile_primary_border', '#55608C')
        tile_primary_hover = colors.get('tile_primary_hover', '#3F4566')
        tile_border = colors.get('tile_border', '#454C63')
        tile_hover = colors.get('tile_hover', '#3A4159')
        return {
            'panel_background': panel_bg,
            'panel_border': colors.get('panel_border', '#3E4455'),
            'surface_alt': tile_bg,
            'surface_highlight': tile_primary_bg,
            'primary_hover': tile_primary_hover,
            'primary_border_active': tile_primary_border,
            'secondary_hover': tile_hover,
            'secondary_border': tile_border,
            'text_primary': colors.get('text_primary', '#EAEAEA'),
            'text_secondary': colors.get('text_secondary', '#C8C8C8'),
            'text_hint': colors.get('text_hint', '#9DA5B3'),
            'value_text': colors.get('tile_text', colors.get('text_primary', '#EAEAEA')),
            'value_strong': colors.get('tile_primary_text', colors.get('tile_text', '#EAEAEA')),
            'input_background': colors.get('input_background', tile_bg),
            'input_border': colors.get('input_border', tile_primary_border),
            'accent': colors.get('secondary', colors.get('text_primary', '#EAEAEA')),
            'accent_hover': colors.get('secondary_hover', colors.get('secondary', '#64B5F6')),
            'disabled_bg': colors.get('status_disabled_bg', '#2C3143'),
            'disabled_text': colors.get('status_disabled_text', '#8088A0'),
            'disabled_border': colors.get('status_disabled_border', '#3F465A'),
        }

    def _apply_dark_panel(self, frame: QFrame, *, highlight: bool = False) -> None:
        """Apply a dark, theme-aligned panel style to the given frame."""
        object_name = frame.objectName() or f'panel_{id(frame)}'
        frame.setObjectName(object_name)
        palette = self._palette()
        background = palette['surface_highlight'] if highlight else palette['panel_background']
        frame.setStyleSheet(
            f"""
            #{object_name} {{
                background-color: {background};
                border: 1px solid {palette['panel_border']};
                border-radius: 12px;
            }}
            #{object_name} QLabel {{
                color: {palette['text_primary']};
            }}
            """
        )

    def _apply_header_label_palette(self, label: QLabel) -> None:
        palette = self._palette()
        label.setStyleSheet(
            label.styleSheet()
            + f"""
            QLabel {{
                color: {palette['text_primary']};
                border-bottom: 1px solid {palette['panel_border']};
            }}
            """
        )

    def _apply_subheader_label_palette(self, label: QLabel) -> None:
        palette = self._palette()
        label.setStyleSheet(
            label.styleSheet()
            + f"\nQLabel {{ color: {palette['text_secondary']}; letter-spacing: 0.3px; }}"
        )

    def _apply_section_header_palette(
        self,
        label: QLabel,
        *,
        emphasize: bool = False,
        uppercase: bool = True,
    ) -> None:
        palette = self._palette()
        color = palette['value_strong'] if emphasize else palette['value_text']
        transform_rule = 'text-transform: uppercase;' if uppercase else ''
        label.setStyleSheet(
            label.styleSheet()
            + f"\nQLabel {{ color: {color}; {transform_rule} letter-spacing: 0.5px; }}"
        )

    def _apply_refresh_button_style(self, button: QPushButton) -> None:
        palette = self._palette()
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setMinimumWidth(96)
        button.setFixedHeight(32)
        button.setStyleSheet(
            f"""
            QPushButton {{
                background-color: {palette['surface_highlight']};
                color: {palette['value_strong']};
                border: 1px solid {palette['panel_border']};
                border-radius: 10px;
                padding: 6px 14px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: {palette['primary_hover']};
                border: 1px solid {palette['accent']};
                color: {palette['value_strong']};
            }}
            QPushButton:pressed {{
                background-color: {palette['primary_border_active']};
                border: 1px solid {palette['accent_hover']};
            }}
            QPushButton:disabled {{
                background-color: {palette['disabled_bg']};
                color: {palette['disabled_text']};
                border: 1px solid {palette['disabled_border']};
            }}
            """
        )

    def _apply_primary_action_style(self, button: QPushButton) -> None:
        palette = self._palette()
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        button.setFixedHeight(38)
        button.setStyleSheet(
            f"""
            QPushButton {{
                background-color: {palette['surface_highlight']};
                color: {palette['value_strong']};
                border: 1px solid {palette['panel_border']};
                border-radius: 12px;
                padding: 10px 14px;
                font-weight: 600;
                letter-spacing: 0.4px;
            }}
            QPushButton:hover {{
                background-color: {palette['primary_hover']};
                border: 1px solid {palette['accent']};
            }}
            QPushButton:pressed {{
                background-color: {palette['primary_border_active']};
                border: 1px solid {palette['accent_hover']};
            }}
            QPushButton:disabled {{
                background-color: {palette['disabled_bg']};
                color: {palette['disabled_text']};
                border: 1px solid {palette['disabled_border']};
            }}
            """
        )

    def _apply_secondary_action_style(self, button: QPushButton) -> None:
        palette = self._palette()
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        button.setFixedHeight(38)
        button.setStyleSheet(
            f"""
            QPushButton {{
                background-color: {palette['panel_background']};
                color: {palette['text_secondary']};
                border: 1px solid {palette['secondary_border']};
                border-radius: 12px;
                padding: 10px 14px;
                font-weight: 600;
                letter-spacing: 0.3px;
            }}
            QPushButton:hover {{
                background-color: {palette['secondary_hover']};
                color: {palette['value_text']};
                border: 1px solid {palette['accent']};
            }}
            QPushButton:pressed {{
                background-color: {palette['surface_highlight']};
                border: 1px solid {palette['accent_hover']};
                color: {palette['value_strong']};
            }}
            QPushButton:disabled {{
                background-color: {palette['disabled_bg']};
                color: {palette['disabled_text']};
                border: 1px solid {palette['disabled_border']};
            }}
            """
        )


    def get_active_model(self) -> str:
        """Return the model associated with the displayed device."""
        return self._active_model

    def _render_summary(
        self,
        sections: Optional[OrderedDict[str, List[Tuple[str, str]]]] = None,
        *,
        header_text: Optional[str] = None,
    ) -> None:
        palette = self._palette()
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
            placeholder.setStyleSheet(
                placeholder.styleSheet()
                + f"\nQLabel {{ color: {palette['text_hint']}; }}"
            )
            self._summary_layout.addWidget(placeholder)
            self._summary_labels.clear()
            return

        self._summary_labels.clear()

        if header_text:
            header_label = QLabel(header_text)
            StyleManager.apply_label_style(header_label, LabelStyle.SUBHEADER)
            self._apply_section_header_palette(header_label, emphasize=True, uppercase=False)
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
            self._apply_section_header_palette(header_label)
            section_layout.addWidget(header_label)

            grid = QGridLayout()
            grid.setHorizontalSpacing(18)
            grid.setVerticalSpacing(4)
            grid.setColumnMinimumWidth(0, 130)
            grid.setColumnStretch(1, 1)
            grid.setAlignment(Qt.AlignmentFlag.AlignTop)

            for row, (label_text, value_text) in enumerate(entries):
                label_widget = QLabel(label_text)
                StyleManager.apply_label_style(label_widget, LabelStyle.INFO)
                label_widget.setStyleSheet(
                    label_widget.styleSheet()
                    + f"\nQLabel {{ color: {palette['text_secondary']}; font-weight: 500; }}"
                )
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
                        f"""
                        QTextEdit#{object_name} {{
                            background-color: {palette['input_background']};
                            border: 1px solid {palette['input_border']};
                            border-radius: 8px;
                            padding: 6px;
                            font-weight: 500;
                            color: {palette['value_text']};
                        }}
                        QTextEdit#{object_name}:focus {{
                            border: 1px solid {palette['accent']};
                        }}
                        """
                    )
                else:
                    value_widget = QLabel(value_text)
                    value_widget.setObjectName(object_name)
                    value_widget.setStyleSheet(
                        f"""
                        QLabel#{object_name} {{
                            font-weight: 600;
                            color: {palette['value_strong']};
                            background-color: transparent;
                        }}
                        """
                    )
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
