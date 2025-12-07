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
    QGridLayout,
    QSizePolicy,
    QScrollArea,
    QTextEdit,
    QFrame,
)

from utils import adb_models
from ui.style_manager import StyleManager, LabelStyle, PanelButtonVariant
from ui.collapsible_panel import CollapsiblePanel


class DeviceOverviewWidget(QWidget):
    """Provides an always-visible summary for the active device."""

    _PLACEHOLDER_TEXT = 'Select a device from the list to view details.'

    # Default collapse states: Device and Battery expanded, others collapsed
    _DEFAULT_COLLAPSE_STATES = {
        'device': False,      # Expanded
        'connectivity': True,  # Collapsed
        'hardware': True,      # Collapsed
        'battery': False,      # Expanded
        'status': True,        # Collapsed
    }

    def __init__(self, main_window) -> None:
        super().__init__(main_window)
        self._window = main_window
        self._active_serial: Optional[str] = None
        self._active_model: str = ''
        self._summary_labels: Dict[str, QLabel] = {}
        self._current_detail_text: str = self._PLACEHOLDER_TEXT
        self._last_summary_signature: Optional[Tuple] = None
        self._collapsible_panels: Dict[str, CollapsiblePanel] = {}
        self._collapse_states: Dict[str, bool] = dict(self._DEFAULT_COLLAPSE_STATES)

        self._build_ui()
        self.set_overview(None, None, None)

    def _build_ui(self) -> None:
        palette = self._palette()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(6)

        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)

        # Title row with Refresh button
        title_row = QHBoxLayout()
        title_row.setSpacing(8)
        title_label = QLabel('Active Device Overview')
        title_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        StyleManager.apply_label_style(title_label, LabelStyle.HEADER)
        self._apply_header_label_palette(title_label)
        title_row.addWidget(title_label)

        title_row.addStretch(1)

        self.refresh_button = QPushButton('Refresh')
        self.refresh_button.setToolTip('Refresh details')
        StyleManager.apply_panel_button_style(
            self.refresh_button,
            PanelButtonVariant.REFRESH,
            fixed_height=28,
            min_width=80,
        )
        self.refresh_button.clicked.connect(self._window.refresh_active_device_overview)
        title_row.addWidget(self.refresh_button)

        layout.addLayout(title_row)

        # Device header label
        self._device_header_label = QLabel('')
        self._device_header_label.setObjectName('device_overview_header')
        StyleManager.apply_label_style(self._device_header_label, LabelStyle.SUBHEADER)
        self._apply_device_header_style(self._device_header_label)
        layout.addWidget(self._device_header_label)

        # Unauthorized warning banner (hidden by default)
        self._unauthorized_banner = QFrame()
        self._unauthorized_banner.setObjectName('unauthorized_warning_banner')
        self._unauthorized_banner.setStyleSheet("""
            QFrame#unauthorized_warning_banner {
                background-color: #fef3c7;
                border: 1px solid #f59e0b;
                border-radius: 6px;
                padding: 8px;
            }
        """)
        banner_layout = QHBoxLayout(self._unauthorized_banner)
        banner_layout.setContentsMargins(8, 6, 8, 6)
        banner_layout.setSpacing(8)

        warning_icon = QLabel('⚠️')
        warning_icon.setStyleSheet('font-size: 14px;')
        banner_layout.addWidget(warning_icon)

        warning_text = QLabel('Device unauthorized. Please allow USB debugging on the device.')
        warning_text.setObjectName('unauthorized_warning_text')
        warning_text.setStyleSheet("""
            QLabel#unauthorized_warning_text {
                color: #92400e;
                font-size: 11px;
                font-weight: 500;
            }
        """)
        warning_text.setWordWrap(True)
        banner_layout.addWidget(warning_text, 1)

        self._unauthorized_banner.hide()
        layout.addWidget(self._unauthorized_banner)

        # Scroll area containing collapsible panels
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll_area.setObjectName('device_overview_scroll')
        scroll_area.setStyleSheet(f"""
            QScrollArea#device_overview_scroll {{
                background-color: transparent;
                border: none;
            }}
            QScrollArea#device_overview_scroll > QWidget > QWidget {{
                background-color: transparent;
            }}
        """)

        scroll_content = QWidget()
        scroll_content.setObjectName('device_overview_scroll_content')
        self._scroll_layout = QVBoxLayout(scroll_content)
        self._scroll_layout.setContentsMargins(0, 0, 0, 0)
        self._scroll_layout.setSpacing(4)

        scroll_area.setWidget(scroll_content)
        layout.addWidget(scroll_area, 1)

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
            self._device_header_label.setText('')
            self._unauthorized_banner.hide()
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
            # Still update unauthorized banner state even if content unchanged
            self._update_unauthorized_banner(serial)
            return

        self._active_model = device.device_model or 'Unknown Device'
        truncated_serial = f'{serial[:8]}...' if len(serial) > 8 else serial
        header_text = f'{self._active_model} ({truncated_serial})'
        self._device_header_label.setText(header_text)

        self._update_unauthorized_banner(serial)
        self._render_summary(summary_sections)

        self._current_detail_text = normalized_detail_text
        self._set_controls_enabled(True)
        self._last_summary_signature = summary_signature

    def _update_unauthorized_banner(self, serial: Optional[str]) -> None:
        """Show or hide the unauthorized warning banner based on device state."""
        if serial is None:
            self._unauthorized_banner.hide()
            return

        try:
            device_manager = getattr(self._window, 'device_manager', None)
            if device_manager is None:
                self._unauthorized_banner.hide()
                return

            async_manager = getattr(device_manager, 'async_device_manager', None)
            if async_manager is None:
                self._unauthorized_banner.hide()
                return

            if async_manager.is_device_unauthorized(serial):
                self._unauthorized_banner.show()
            else:
                self._unauthorized_banner.hide()
        except Exception:
            # Silently hide banner if check fails
            self._unauthorized_banner.hide()

    def _set_controls_enabled(self, enabled: bool) -> None:
        self.refresh_button.setEnabled(enabled)

    def _palette(self) -> Dict[str, str]:
        """Return palette values aligned with the active StyleManager theme."""
        colors = StyleManager.COLORS
        panel_bg = colors.get('panel_background', '#252A37')
        tile_bg = colors.get('tile_bg', '#2E3449')
        tile_primary_bg = colors.get('tile_primary_bg', '#333A56')
        tile_primary_border = colors.get('tile_primary_border', '#55608C')
        tile_border = colors.get('tile_border', '#454C63')
        return {
            'panel_background': panel_bg,
            'panel_border': colors.get('panel_border', '#3E4455'),
            'surface_alt': tile_bg,
            'surface_highlight': tile_primary_bg,
            'primary_border_active': tile_primary_border,
            'secondary_border': tile_border,
            'text_primary': colors.get('text_primary', '#EAEAEA'),
            'text_secondary': colors.get('text_secondary', '#C8C8C8'),
            'text_hint': colors.get('text_hint', '#9DA5B3'),
            'value_text': colors.get('tile_text', colors.get('text_primary', '#EAEAEA')),
            'value_strong': colors.get('tile_primary_text', colors.get('tile_text', '#EAEAEA')),
            'input_background': colors.get('input_background', tile_bg),
            'input_border': colors.get('input_border', tile_primary_border),
            'accent': colors.get('secondary', colors.get('text_primary', '#EAEAEA')),
        }

    def _apply_header_label_palette(self, label: QLabel) -> None:
        palette = self._palette()
        label.setStyleSheet(
            label.styleSheet()
            + f"""
            QLabel {{
                color: {palette['text_primary']};
                border-bottom: 1px solid {palette['panel_border']};
                padding-bottom: 4px;
                margin-bottom: 2px;
            }}
            """
        )

    def _apply_device_header_style(self, label: QLabel) -> None:
        palette = self._palette()
        label.setStyleSheet(f"""
            QLabel#device_overview_header {{
                color: {palette['value_strong']};
                font-weight: 600;
                font-size: 13px;
                padding: 4px 0;
            }}
        """)

    def get_active_model(self) -> str:
        """Return the model associated with the displayed device."""
        return self._active_model

    def _save_collapse_states(self) -> None:
        """Save current collapse states before re-rendering."""
        for key, panel in self._collapsible_panels.items():
            self._collapse_states[key] = panel.is_collapsed()

    def _render_summary(
        self,
        sections: Optional[OrderedDict[str, List[Tuple[str, str]]]] = None,
    ) -> None:
        palette = self._palette()
        if sections is None:
            sections = OrderedDict()

        # Save collapse states before clearing
        self._save_collapse_states()

        # Clear existing panels
        for i in reversed(range(self._scroll_layout.count())):
            item = self._scroll_layout.takeAt(i)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        self._collapsible_panels.clear()
        self._summary_labels.clear()

        if not sections:
            placeholder = QLabel('Select a device to view hardware, battery, and status details.')
            StyleManager.apply_label_style(placeholder, LabelStyle.STATUS)
            placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
            placeholder.setStyleSheet(
                placeholder.styleSheet()
                + f"\nQLabel {{ color: {palette['text_hint']}; padding: 20px; }}"
            )
            self._scroll_layout.addWidget(placeholder)
            return

        # Create collapsible panels for each section
        for section_key, entries in sections.items():
            title = self._format_section_header(section_key)
            collapsed = self._collapse_states.get(
                section_key,
                self._DEFAULT_COLLAPSE_STATES.get(section_key, True)
            )

            panel = CollapsiblePanel(title, collapsed=collapsed, compact=True)
            panel.collapsed_changed.connect(
                lambda state, key=section_key: self._on_section_collapsed(key, state)
            )

            # Create content widget
            content_widget = self._create_section_content(section_key, entries, palette)
            panel.set_content(content_widget)

            self._collapsible_panels[section_key] = panel
            self._scroll_layout.addWidget(panel)

        self._scroll_layout.addStretch(1)

    def _on_section_collapsed(self, section_key: str, collapsed: bool) -> None:
        """Track collapse state changes."""
        self._collapse_states[section_key] = collapsed

    def _create_section_content(
        self,
        section_key: str,
        entries: List[Tuple[str, str]],
        palette: Dict[str, str],
    ) -> QWidget:
        """Create the content widget for a collapsible section."""
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(2)

        grid = QGridLayout()
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(2)
        grid.setColumnMinimumWidth(0, 100)
        grid.setColumnStretch(1, 1)

        for row, (label_text, value_text) in enumerate(entries):
            label_widget = QLabel(label_text)
            label_widget.setStyleSheet(f"""
                QLabel {{
                    color: {palette['text_secondary']};
                    font-size: 11px;
                    font-weight: 500;
                }}
            """)
            grid.addWidget(label_widget, row, 0, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)

            sanitized = ''.join(
                ch if ch.isalnum() else '_' for ch in label_text.lower()
            ).rstrip('_')
            object_name = f'device_overview_value_{section_key}_{sanitized}'

            if section_key == 'device' and label_text.lower() == 'build fingerprint':
                value_widget = QTextEdit()
                value_widget.setObjectName(object_name)
                value_widget.setReadOnly(True)
                value_widget.setPlainText(value_text)
                value_widget.setMinimumHeight(40)
                value_widget.setMaximumHeight(72)
                value_widget.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
                value_widget.setStyleSheet(f"""
                    QTextEdit#{object_name} {{
                        background-color: {palette['input_background']};
                        border: 1px solid {palette['input_border']};
                        border-radius: 4px;
                        padding: 4px;
                        font-size: 10px;
                        font-weight: 500;
                        color: {palette['value_text']};
                    }}
                    QTextEdit#{object_name}:focus {{
                        border: 1px solid {palette['accent']};
                    }}
                """)
            else:
                value_widget = QLabel(value_text)
                value_widget.setObjectName(object_name)
                value_widget.setStyleSheet(f"""
                    QLabel#{object_name} {{
                        font-size: 11px;
                        font-weight: 600;
                        color: {palette['value_strong']};
                        background-color: transparent;
                    }}
                """)
                value_widget.setWordWrap(True)
                value_widget.setTextInteractionFlags(
                    Qt.TextInteractionFlag.TextSelectableByMouse
                    | Qt.TextInteractionFlag.TextSelectableByKeyboard
                )

            grid.addWidget(value_widget, row, 1, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
            self._summary_labels[f'{section_key}_{label_text.lower()}'] = value_widget

        content_layout.addLayout(grid)
        return content

    @staticmethod
    def _format_section_header(key: str) -> str:
        mapping = {
            'device': 'Device',
            'connectivity': 'Connectivity',
            'hardware': 'Hardware',
            'battery': 'Battery',
            'status': 'Status',
        }
        return mapping.get(key, key.title())


__all__ = ['DeviceOverviewWidget']
