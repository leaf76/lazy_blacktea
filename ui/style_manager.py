#!/usr/bin/env python3
"""
樣式管理器 - 統一管理所有UI樣式，減少重複代碼

這個模組負責：
1. 定義常用的按鈕、標籤、面板樣式
2. 提供統一的顏色主題管理
3. 支援動態樣式應用和主題切換
4. 減少重複的CSS代碼
"""

from typing import Dict, List, Mapping, Sequence, Tuple
from enum import Enum
from textwrap import dedent
from copy import deepcopy
import platform

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QSizePolicy


_THEME_PRESETS: Dict[str, Dict[str, str]] = {
    'light': {
        'primary': '#4CAF50',
        'primary_hover': '#45A049',
        'secondary': '#1976D2',
        'secondary_hover': '#1565C0',
        'warning': '#FF9800',
        'warning_hover': '#F57C00',
        'danger': '#F44336',
        'danger_hover': '#D32F2F',
        'neutral': '#757575',
        'neutral_hover': '#616161',
        'success': '#2E7D32',
        'error': '#C62828',
        'info': '#1976D2',
        'text_primary': '#212121',
        'text_secondary': '#424242',
        'text_hint': '#666666',
        'border': '#D7DCE6',
        'background': '#F3F4F6',
        'background_hover': 'rgba(200, 220, 255, 0.45)',
        'panel_background': '#FFFFFF',
        'panel_border': '#D7DCE6',
        'tile_primary_bg': '#EEF2FF',
        'tile_primary_border': '#A5B4FC',
        'tile_primary_hover': '#E1E7FF',
        'tile_bg': '#F8FAFC',
        'tile_border': '#D0D7E2',
        'tile_hover': '#EEF2F7',
        'tile_text': '#1F2937',
        'tile_primary_text': '#111827',
        'status_text_on_dark': '#FFFFFF',
        'status_disabled_bg': '#EBEBEB',
        'status_disabled_text': '#9A9A9A',
        'status_disabled_border': '#D1D1D1',
        'tooltip_background': 'rgba(45, 45, 45, 0.95)',
        'tooltip_text': '#FFFFFF',
        'tooltip_border': 'rgba(255, 255, 255, 0.2)',
        'input_background': '#FFFFFF',
        'input_border': '#CCCCCC',
        'console_background': '#FFFFFF',
        'console_text': '#000000',
        'console_border': '#B0B8C2',
        'tile_processing_bg': '#444444',
        'tile_processing_border': '#2F2F2F',
        'tile_processing_hover': '#3A3A3A',
        'tile_ready_bg': '#111111',
        'tile_ready_border': '#000000',
        'tile_ready_hover': '#000000',
    },
    'dark': {
        'primary': '#66BB6A',
        'primary_hover': '#57A65B',
        'secondary': '#64B5F6',
        'secondary_hover': '#4A9DE0',
        'warning': '#FFB74D',
        'warning_hover': '#FFA726',
        'danger': '#EF5350',
        'danger_hover': '#E53935',
        'neutral': '#9E9E9E',
        'neutral_hover': '#BDBDBD',
        'success': '#81C784',
        'error': '#E57373',
        'info': '#64B5F6',
        'text_primary': '#EAEAEA',
        'text_secondary': '#C8C8C8',
        'text_hint': '#9DA5B3',
        'border': '#3F4657',
        'background': '#1B1E26',
        'background_hover': 'rgba(120, 160, 255, 0.25)',
        'panel_background': '#252A37',
        'panel_border': '#3E4455',
        'tile_primary_bg': '#333A56',
        'tile_primary_border': '#55608C',
        'tile_primary_hover': '#3F4566',
        'tile_bg': '#2E3449',
        'tile_border': '#454C63',
        'tile_hover': '#3A4159',
        'tile_text': '#E6EAF7',
        'tile_primary_text': '#F5F7FF',
        'status_text_on_dark': '#FFFFFF',
        'status_disabled_bg': '#2C3143',
        'status_disabled_text': '#8088A0',
        'status_disabled_border': '#3F465A',
        'tooltip_background': 'rgba(240, 240, 240, 0.95)',
        'tooltip_text': '#111111',
        'tooltip_border': 'rgba(0, 0, 0, 0.35)',
        'input_background': '#2D3142',
        'input_border': '#4A5168',
        'console_background': '#1C2030',
        'console_text': '#E0E6F3',
        'console_border': '#3A4052',
        'tile_processing_bg': '#5A6076',
        'tile_processing_border': '#707791',
        'tile_processing_hover': '#666D86',
        'tile_ready_bg': '#66BB6A',
        'tile_ready_border': '#4A9B4E',
        'tile_ready_hover': '#57A65B',
    },
}

_THEME_ALIASES = {
    'default': 'light',
}

# Unified spacing system constants (based on 8px grid)
SPACING_UNIT = 8
SPACING_SMALL = 8     # For inner element spacing
SPACING_MEDIUM = 16   # For spacing between elements in the same group
SPACING_LARGE = 24    # For spacing between different groups
SPACING_XLARGE = 32   # For spacing between major sections

# Material Design elevation (shadow) levels
MD_SHADOW_1 = '0 1px 3px rgba(0,0,0,0.12), 0 1px 2px rgba(0,0,0,0.08)'  # Resting elevation
MD_SHADOW_2 = '0 2px 8px rgba(0,0,0,0.12), 0 2px 4px rgba(0,0,0,0.06)'  # Card/button elevation
MD_SHADOW_3 = '0 4px 16px rgba(0,0,0,0.16), 0 4px 8px rgba(0,0,0,0.08)'  # Raised/hover elevation
MD_SHADOW_4 = '0 8px 24px rgba(0,0,0,0.18), 0 8px 12px rgba(0,0,0,0.10)'  # Dialog/modal elevation


CSSDeclaration = Tuple[str, str]
CSSBlock = Tuple[str, Sequence[CSSDeclaration]]
CSSBlocks = Sequence[CSSBlock]


def _combine_css(*blocks: str) -> str:
    """合併並格式化多個CSS區塊。"""

    formatted_blocks = [dedent(block).strip() for block in blocks if block]
    return "\n\n".join(formatted_blocks)


def _render_css(blocks: CSSBlocks, tokens: Mapping[str, str], extra: Mapping[str, str] | None = None) -> str:
    """以資料驅動方式渲染CSS區塊。"""

    context: Dict[str, str] = {key: str(value) for key, value in tokens.items()}
    if extra:
        context.update({key: str(value) for key, value in extra.items()})

    rendered: List[str] = []
    for selector, declarations in blocks:
        lines = [f"{selector} {{"]
        for name, raw_value in declarations:
            value_template = str(raw_value)
            try:
                resolved_value = value_template.format_map(context)
            except KeyError:
                resolved_value = value_template
            lines.append(f"    {name}: {resolved_value};")
        lines.append("}")
        rendered.append("\n".join(lines))

    return "\n\n".join(rendered)


class ButtonStyle(Enum):
    """按鈕樣式類型"""
    PRIMARY = "primary"      # 主要動作按鈕（綠色）
    SECONDARY = "secondary"  # 次要按鈕（藍色）
    WARNING = "warning"      # 警告按鈕（橙色）
    DANGER = "danger"        # 危險按鈕（紅色）
    NEUTRAL = "neutral"      # 中性按鈕（灰色）
    SYSTEM = "system"        # 系統按鈕（自適應）


class PanelButtonVariant(Enum):
    """面板按鈕樣式，用於工具頁籤保持一致風格"""

    PRIMARY = "panel_primary"
    SECONDARY = "panel_secondary"
    NEUTRAL = "panel_neutral"
    DANGER = "panel_danger"
    REFRESH = "panel_refresh"


class LabelStyle(Enum):
    """標籤樣式類型"""
    HEADER = "header"        # 標題樣式
    SUBHEADER = "subheader"  # 副標題樣式
    SUCCESS = "success"      # 成功狀態
    ERROR = "error"          # 錯誤狀態
    WARNING = "warning"      # 警告狀態
    INFO = "info"            # 信息狀態
    STATUS = "status"        # 一般狀態


class PanelStyle(Enum):
    """面板樣式類型"""
    DEFAULT = "default"      # 預設面板
    HIGHLIGHT = "highlight"  # 高亮面板
    TRANSPARENT = "transparent"  # 透明面板


class StyleManager:
    """樣式管理器類"""

    # 動態顏色表（會依主題更新）
    COLORS: Dict[str, str] = deepcopy(_THEME_PRESETS['light'])

    BUTTON_STYLE_PROFILES: Dict[ButtonStyle, Dict[str, str]] = {
        ButtonStyle.PRIMARY: {
            'bg': '#111111',
            'fg': '#ffffff',
            'hover': '#000000',
            'hover_fg': '#ffffff',
            'pressed': '#1a1a1a',
            'pressed_fg': '#ffffff',
            'border': '#000000',
            'border_width': '1px',
        },
        ButtonStyle.SECONDARY: {
            'bg': '#f9f9f9',
            'fg': '#111111',
            'hover': '#e8e8e8',
            'hover_fg': '#111111',
            'pressed': '#dcdcdc',
            'pressed_fg': '#111111',
            'border': '#111111',
            'border_width': '1px',
        },
        ButtonStyle.WARNING: {
            'bg': '#444444',
            'fg': '#ffffff',
            'hover': '#2f2f2f',
            'hover_fg': '#ffffff',
            'pressed': '#1f1f1f',
            'pressed_fg': '#ffffff',
            'border': '#444444',
            'border_width': '1px',
        },
        ButtonStyle.DANGER: {
            'bg': '#000000',
            'fg': '#ffffff',
            'hover': '#1a1a1a',
            'hover_fg': '#ffffff',
            'pressed': '#000000',
            'pressed_fg': '#ffffff',
            'border': '#000000',
            'border_width': '1px',
        },
        ButtonStyle.NEUTRAL: {
            'bg': '#f2f2f2',
            'fg': '#111111',
            'hover': '#dfdfdf',
            'hover_fg': '#111111',
            'pressed': '#d0d0d0',
            'pressed_fg': '#111111',
            'border': '#c4c4c4',
            'border_width': '1px',
        },
    }

    BUTTON_DISABLED_STATE: Dict[str, str] = {
        'disabled_bg': '#ebebeb',
        'disabled_fg': '#9a9a9a',
        'disabled_border': '#d1d1d1',
        'disabled_border_width': '1px',
    }

    _HIGH_CONTRAST_PLATFORMS = {'darwin', 'linux'}

    _HIGH_CONTRAST_BUTTON_PROFILES: Dict[ButtonStyle, Dict[str, str]] = {
        ButtonStyle.PRIMARY: {
            'border_width': '2px',
            'disabled_border_width': '2px',
        },
        ButtonStyle.SECONDARY: {
            'bg': '#c8c8c8',
            'fg': '#111111',
            'hover': '#b8b8b8',
            'hover_fg': '#111111',
            'pressed': '#a3a3a3',
            'pressed_fg': '#111111',
            'border': '#2b2b2b',
            'border_width': '2px',
            'disabled_border_width': '2px',
        },
        ButtonStyle.WARNING: {
            'border_width': '2px',
            'disabled_border_width': '2px',
        },
        ButtonStyle.DANGER: {
            'border_width': '2px',
            'disabled_border_width': '2px',
        },
        ButtonStyle.NEUTRAL: {
            'bg': '#d2d2d2',
            'fg': '#111111',
            'hover': '#bcbcbc',
            'hover_fg': '#111111',
            'pressed': '#a7a7a7',
            'pressed_fg': '#111111',
            'border': '#2b2b2b',
            'border_width': '2px',
            'disabled_border_width': '2px',
        },
        ButtonStyle.SYSTEM: {
            'bg': '#d0d0d0',
            'fg': '#111111',
            'hover': '#bcbcbc',
            'hover_fg': '#111111',
            'pressed': '#a6a6a6',
            'pressed_fg': '#111111',
            'border': '#292929',
            'border_width': '2px',
            'disabled_border_width': '2px',
        },
    }

    _LABEL_STYLE_BLOCKS: Dict[LabelStyle, CSSBlocks] = {
        LabelStyle.HEADER: (
            (
                "QLabel",
                (
                    ("font-size", "14px"),
                    ("font-weight", "bold"),
                    ("padding", "8px 0px"),
                    ("border-bottom", "1px solid palette(mid)"),
                    ("margin-bottom", "8px"),
                    ("color", "{text_primary}"),
                ),
            ),
        ),
        LabelStyle.SUBHEADER: (
            (
                "QLabel",
                (
                    ("font-size", "12px"),
                    ("font-weight", "bold"),
                    ("padding", "4px 0px"),
                    ("color", "#1b2533"),
                ),
            ),
        ),
        LabelStyle.SUCCESS: (
            (
                "QLabel",
                (
                    ("font-weight", "bold"),
                    ("color", "{success}"),
                    ("font-size", "14px"),
                ),
            ),
        ),
        LabelStyle.ERROR: (
            (
                "QLabel",
                (
                    ("font-weight", "bold"),
                    ("color", "{error}"),
                    ("font-size", "14px"),
                ),
            ),
        ),
        LabelStyle.WARNING: (
            (
                "QLabel",
                (
                    ("font-weight", "bold"),
                    ("color", "{warning}"),
                    ("font-size", "14px"),
                ),
            ),
        ),
        LabelStyle.INFO: (
            (
                "QLabel",
                (
                    ("color", "{text_secondary}"),
                    ("margin", "10px 0px"),
                ),
            ),
        ),
        LabelStyle.STATUS: (
            (
                "QLabel",
                (
                    ("color", "{text_hint}"),
                    ("font-style", "italic"),
                ),
            ),
        ),
    }

    _STATIC_STYLE_BLOCKS: Dict[str, CSSBlocks] = {
        "input": (
            (
                "QLineEdit",
                (
                    ("padding", "6px 8px"),
                    ("font-size", "12px"),
                    ("border", "1px solid {input_border}"),
                    ("border-radius", "4px"),
                    ("background-color", "{input_background}"),
                    ("color", "{text_primary}"),
                ),
            ),
            (
                "QLineEdit:focus",
                (
                    ("border-color", "{secondary}"),
                ),
            ),
        ),
        "search_input": (
            (
                "QLineEdit",
                (
                    ("padding", "6px 8px"),
                    ("font-size", "12px"),
                    ("border-radius", "4px"),
                    ("border", "1px solid {input_border}"),
                    ("background-color", "{input_background}"),
                    ("color", "{text_primary}"),
                ),
            ),
        ),
        "search_label": (
            (
                "QLabel",
                (
                    ("font-size", "14px"),
                    ("color", "{text_hint}"),
                    ("padding", "4px"),
                ),
            ),
        ),
        "tree": (
            (
                "QTreeWidget",
                (
                    ("font-size", "11px"),
                ),
            ),
            (
                "QTreeWidget::item",
                (
                    ("padding", "4px"),
                ),
            ),
        ),
        "console": (
            (
                "QTextEdit",
                (
                    ("background-color", "{console_background}"),
                    ("color", "{console_text}"),
                    ("border", "2px solid {console_border}"),
                    ("padding", "5px"),
                ),
            ),
        ),
        "checkbox": (
            (
                "QCheckBox",
                (
                    ("padding", "8px"),
                    ("border", "2px solid transparent"),
                    ("border-radius", "6px"),
                    ("background-color", "rgba(240, 240, 240, 0.3)"),
                    ("margin", "2px"),
                ),
            ),
            (
                "QCheckBox:hover",
                (
                    ("background-color", "{background_hover}"),
                    ("border", "2px solid rgba(100, 150, 255, 0.3)"),
                ),
            ),
            (
                "QCheckBox:checked",
                (
                    ("background-color", "rgba(100, 200, 100, 0.2)"),
                    ("border", "2px solid rgba(50, 150, 50, 0.6)"),
                    ("font-weight", "bold"),
                ),
            ),
            (
                "QCheckBox:checked:hover",
                (
                    ("background-color", "rgba(100, 200, 100, 0.3)"),
                    ("border", "2px solid rgba(50, 150, 50, 0.8)"),
                ),
            ),
            (
                "QCheckBox::indicator",
                (
                    ("width", "16px"),
                    ("height", "16px"),
                    ("border-radius", "3px"),
                    ("border", "2px solid #666"),
                    ("background-color", "white"),
                ),
            ),
            (
                "QCheckBox::indicator:checked",
                (
                    ("background-color", "{primary}"),
                    ("border", "2px solid {primary}"),
                    (
                        "image",
                        "url(data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMTAiIGhlaWdodD0iNyIgdmlld0JveD0iMCAwIDEwIDciIGZpbGw9Im5vbmUiIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyI+CjxwYXRoIGQ9Ik04LjUgMUwzLjUgNkwxLjUgNCIgc3Ryb2tlPSJ3aGl0ZSIgc3Ryb2tlLXdpZHRoPSIyIiBzdHJva2UtbGluZWNhcD0icm91bmQiIHN0cm9rZS1saW5lam9pbj0icm91bmQiLz4KPHN2Zz4K)",
                    ),
                ),
            ),
            (
                "QCheckBox::indicator:hover",
                (
                    ("border", "2px solid {secondary}"),
                ),
            ),
            (
                'QCheckBox[activeDevice="true"]',
                (
                    ('border', '2px solid rgba(60, 120, 220, 0.85)'),
                    ('background-color', 'rgba(90, 160, 255, 0.25)'),
                ),
            ),
            (
                'QCheckBox[activeDevice="true"]:checked',
                (
                    ('background-color', 'rgba(70, 140, 240, 0.4)'),
                    ('border', '2px solid rgba(50, 110, 210, 0.95)'),
                ),
            ),
        ),
        "menu": (
            (
                "QMenu::item:disabled",
                (
                    ("font-weight", "bold"),
                ),
            ),
            (
                "QMenu::separator",
                (
                    ("height", "1px"),
                    ("background-color", "{border}"),
                    ("margin", "4px 0px"),
                ),
            ),
        ),
        "device_info": (
            (
                "QLabel",
                (
                    ("font-size", "14px"),
                    ("font-weight", "bold"),
                    ("padding", "8px 12px"),
                    ("border", "1px solid palette(mid)"),
                    ("border-radius", "6px"),
                ),
            ),
        ),
        "tooltip": (
            (
                "QToolTip",
                (
                    ("background-color", "{tooltip_background}"),
                    ("color", "{tooltip_text}"),
                    ("border", "1px solid {tooltip_border}"),
                    ("border-radius", "6px"),
                    ("padding", "6px"),
                    ("font-size", "11px"),
                    ("font-family", "'Segoe UI', Arial, sans-serif"),
                    ("max-width", "350px"),
                ),
            ),
        ),
        "action_button": (
            (
                "QPushButton",
                (
                    ("background-color", "{background}"),
                    ("border", "1px solid {border}"),
                    ("color", "{text_primary}"),
                    ("padding", "10px"),
                    ("border-radius", "5px"),
                    ("text-align", "left"),
                ),
            ),
            (
                "QPushButton:hover",
                (
                    ("background-color", "{background_hover}"),
                ),
            ),
            (
                "QPushButton:pressed",
                (
                    ("background-color", "{border}"),
                    ("color", "{text_primary}"),
                ),
            ),
            (
                "QPushButton:focus",
                (
                    ("outline", "none"),
                    ("border", "1px solid {secondary}"),
                ),
            ),
        ),
    }

    @classmethod
    def _resolve_panel_palette(cls) -> Dict[str, str]:
        """取得面板按鈕使用的調色盤。"""

        colors = cls.COLORS
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
            'status_text_on_dark': colors.get('status_text_on_dark', '#FFFFFF'),
            'input_background': colors.get('input_background', tile_bg),
            'input_border': colors.get('input_border', tile_primary_border),
            'accent': colors.get('secondary', colors.get('text_primary', '#EAEAEA')),
            'accent_hover': colors.get('secondary_hover', colors.get('secondary', '#64B5F6')),
            'disabled_bg': colors.get('status_disabled_bg', '#2C3143'),
            'disabled_text': colors.get('status_disabled_text', '#8088A0'),
            'disabled_border': colors.get('status_disabled_border', '#3F465A'),
            'danger': colors.get('danger', '#EF5350'),
            'danger_hover': colors.get('danger_hover', colors.get('danger', '#E53935')),
            'neutral': colors.get('neutral', panel_bg),
            'neutral_hover': colors.get('neutral_hover', tile_hover),
        }

    @classmethod
    def _panel_button_tokens(cls, variant: PanelButtonVariant) -> Dict[str, str]:
        """取得面板按鈕樣式顏色配置。"""

        palette = cls._resolve_panel_palette()
        tokens: Dict[str, str] = {
            'hover_border': palette['accent'],
            'pressed_border': palette['accent_hover'],
            'disabled_bg': palette['disabled_bg'],
            'disabled_fg': palette['disabled_text'],
            'disabled_border': palette['disabled_border'],
            'letter_spacing': '0.3px',
        }

        if variant == PanelButtonVariant.PRIMARY:
            tokens.update(
                {
                    'bg': palette['surface_highlight'],
                    'fg': palette['value_strong'],
                    'border': palette['panel_border'],
                    'hover_bg': palette['primary_hover'],
                    'hover_fg': palette['value_strong'],
                    'pressed_bg': palette['primary_border_active'],
                    'pressed_fg': palette['value_strong'],
                    'letter_spacing': '0.4px',
                }
            )
        elif variant == PanelButtonVariant.SECONDARY:
            tokens.update(
                {
                    'bg': palette['panel_background'],
                    'fg': palette['text_secondary'],
                    'border': palette['secondary_border'],
                    'hover_bg': palette['secondary_hover'],
                    'hover_fg': palette['value_text'],
                    'pressed_bg': palette['surface_highlight'],
                    'pressed_fg': palette['value_strong'],
                }
            )
        elif variant == PanelButtonVariant.NEUTRAL:
            tokens.update(
                {
                    'bg': palette['neutral'],
                    'fg': palette['text_primary'],
                    'border': palette['panel_border'],
                    'hover_bg': palette['neutral_hover'],
                    'hover_fg': palette['text_primary'],
                    'pressed_bg': palette['surface_alt'],
                    'pressed_fg': palette['value_text'],
                }
            )
        elif variant == PanelButtonVariant.DANGER:
            danger_bg = palette['danger']
            danger_hover = palette['danger_hover']
            tokens.update(
                {
                    'bg': danger_bg,
                    'fg': palette['status_text_on_dark'],
                    'border': danger_hover,
                    'hover_bg': danger_hover,
                    'hover_fg': palette['status_text_on_dark'],
                    'pressed_bg': danger_hover,
                    'pressed_fg': palette['status_text_on_dark'],
                    'hover_border': danger_hover,
                    'pressed_border': danger_hover,
                }
            )
        else:  # PanelButtonVariant.REFRESH
            tokens.update(
                {
                    'bg': palette['surface_highlight'],
                    'fg': palette['value_strong'],
                    'border': palette['panel_border'],
                    'hover_bg': palette['primary_hover'],
                    'hover_fg': palette['value_strong'],
                    'pressed_bg': palette['primary_border_active'],
                    'pressed_fg': palette['value_strong'],
                    'letter_spacing': '0.3px',
                }
            )

        return tokens

    @classmethod
    def get_panel_button_style(cls, variant: PanelButtonVariant) -> str:
        """根據面板按鈕變體生成統一樣式。"""

        tokens = cls._panel_button_tokens(variant)
        border_radius = '10px' if variant == PanelButtonVariant.REFRESH else '12px'
        padding = '6px 14px' if variant == PanelButtonVariant.REFRESH else '10px 14px'
        base_css = dedent(
            f"""
            QPushButton {{
                background-color: {tokens['bg']};
                color: {tokens['fg']};
                border: 1px solid {tokens['border']};
                border-radius: {border_radius};
                padding: {padding};
                font-weight: 600;
                letter-spacing: {tokens['letter_spacing']};
            }}
            QPushButton:hover {{
                background-color: {tokens['hover_bg']};
                color: {tokens['hover_fg']};
                border: 1px solid {tokens['hover_border']};
            }}
            QPushButton:pressed {{
                background-color: {tokens['pressed_bg']};
                color: {tokens['pressed_fg']};
                border: 1px solid {tokens['pressed_border']};
            }}
            """
        ).strip()

        disabled_css = dedent(
            f"""
            QPushButton:disabled {{
                background-color: {tokens['disabled_bg']};
                color: {tokens['disabled_fg']};
                border: 1px solid {tokens['disabled_border']};
            }}
            """
        ).strip()

        return _combine_css(base_css, disabled_css)

    @classmethod
    def apply_panel_button_style(
        cls,
        button,
        variant: PanelButtonVariant,
        *,
        fixed_height: int | None = 38,
        min_width: int | None = None,
    ) -> None:
        """套用面板按鈕樣式並同步常用屬性。"""

        button.setStyleSheet(cls.get_panel_button_style(variant))
        button.setCursor(Qt.CursorShape.PointingHandCursor)

        if fixed_height:
            button.setFixedHeight(fixed_height)
            button.setProperty('_lazy_button_height', fixed_height)
        else:
            button.setProperty('_lazy_button_height', 0)

        if min_width is not None:
            button.setMinimumWidth(min_width)
        elif variant == PanelButtonVariant.REFRESH:
            button.setMinimumWidth(96)

        if variant == PanelButtonVariant.REFRESH:
            button.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        else:
            button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        button.setProperty('_lazy_panel_button_variant', variant.value)

    _BUTTON_BASE_BLOCKS: CSSBlocks = (
        (
            "QPushButton",
            (
                ("padding", "8px 16px"),
                ("border-radius", "4px"),
                ("font-weight", "600"),
                ("font-size", "12px"),
                ("min-width", "92px"),
                ("height", "{button_height}"),
                ("letter-spacing", "0.2px"),
                ("transition", "background-color 100ms ease, color 100ms ease"),
            ),
        ),
    )

    _SYSTEM_BUTTON_BLOCKS: CSSBlocks = (
        (
            "QPushButton",
            (
                ("padding", "0px 16px"),
                ("font-weight", "bold"),
                ("font-size", "12px"),
                ("min-width", "80px"),
                ("height", "{button_height}"),
                ("border-radius", "4px"),
            ),
        ),
    )

    @staticmethod
    def _monochrome_button_blocks() -> CSSBlocks:
        return (
            (
                "QPushButton",
                (
                    ("background-color", "{bg}"),
                    ("color", "{fg}"),
                    ("border", "{border_width} solid {border}"),
                ),
            ),
            (
                "QPushButton:hover",
                (
                    ("background-color", "{hover}"),
                    ("color", "{hover_fg}"),
                    ("border", "{border_width} solid {border}"),
                ),
            ),
            (
                "QPushButton:pressed",
                (
                    ("background-color", "{pressed}"),
                    ("color", "{pressed_fg}"),
                    ("border", "{border_width} solid {border}"),
                ),
            ),
            (
                "QPushButton:disabled",
                (
                    ("background-color", "{disabled_bg}"),
                    ("color", "{disabled_fg}"),
                    ("border", "{disabled_border_width} solid {disabled_border}"),
                ),
            ),
        )

    @staticmethod
    def _detect_platform() -> str:
        """回傳目前執行平台名稱 (小寫)。"""

        try:
            return platform.system().lower()
        except Exception:
            return ""

    @classmethod
    def _requires_high_contrast(cls) -> bool:
        """判斷是否需要啟用高對比按鈕樣式。"""

        return cls._detect_platform() in cls._HIGH_CONTRAST_PLATFORMS

    @classmethod
    def _resolve_button_profile(cls, style: ButtonStyle) -> Dict[str, str]:
        """取得按鈕樣式設定並套用高對比調整。"""

        profile = dict(cls.BUTTON_STYLE_PROFILES.get(style, cls.BUTTON_STYLE_PROFILES[ButtonStyle.NEUTRAL]))
        profile.setdefault('border_width', '1px')
        profile.setdefault('disabled_border_width', cls.BUTTON_DISABLED_STATE['disabled_border_width'])

        if cls._requires_high_contrast():
            overrides = cls._HIGH_CONTRAST_BUTTON_PROFILES.get(style)
            if overrides:
                profile.update(overrides)

        return profile

    @classmethod
    def get_button_style(cls, style: ButtonStyle, fixed_height: int = 36) -> str:
        """獲取按鈕樣式"""
        overrides = {"button_height": f"{fixed_height}px"}
        base_blocks = cls._SYSTEM_BUTTON_BLOCKS if style == ButtonStyle.SYSTEM else cls._BUTTON_BASE_BLOCKS
        base_style = _render_css(base_blocks, cls.COLORS, overrides)

        include_monochrome = style != ButtonStyle.SYSTEM or cls._requires_high_contrast()
        if not include_monochrome:
            return base_style

        profile = cls._resolve_button_profile(style)
        profile.setdefault('hover', profile.get('bg', '#e0e0e0'))
        profile.setdefault('hover_fg', profile.get('fg', '#111111'))
        profile.setdefault('pressed', profile.get('hover'))
        profile.setdefault('pressed_fg', profile.get('hover_fg'))

        css_tokens = {**cls.BUTTON_DISABLED_STATE, **profile}
        button_css = _render_css(cls._monochrome_button_blocks(), {}, css_tokens)
        return _combine_css(base_style, button_css)

    @classmethod
    def get_label_style(cls, style: LabelStyle) -> str:
        """獲取標籤樣式"""
        blocks = cls._LABEL_STYLE_BLOCKS.get(style)
        if not blocks:
            return ""
        return _render_css(blocks, cls.COLORS)

    @classmethod
    def _get_static_style(cls, key: str) -> str:
        """取得靜態樣式定義。"""

        blocks = cls._STATIC_STYLE_BLOCKS.get(key)
        if not blocks:
            return ""
        return _render_css(blocks, cls.COLORS)

    @classmethod
    def get_input_style(cls) -> str:
        """獲取輸入框樣式"""
        return cls._get_static_style("input")

    @classmethod
    def get_search_input_style(cls) -> str:
        """獲取搜索輸入框樣式"""
        return cls._get_static_style("search_input")

    @classmethod
    def get_search_label_style(cls) -> str:
        """獲取搜索標籤樣式"""
        return cls._get_static_style("search_label")

    @classmethod
    def get_tree_style(cls) -> str:
        """獲取樹狀控件樣式"""
        return cls._get_static_style("tree")

    @classmethod
    def get_console_style(cls) -> str:
        """獲取控制台樣式"""
        return cls._get_static_style("console")

    @classmethod
    def get_checkbox_style(cls) -> str:
        """獲取複選框樣式"""
        return cls._get_static_style("checkbox")

    @classmethod
    def get_menu_style(cls) -> str:
        """獲取菜單樣式"""
        return cls._get_static_style("menu")

    @classmethod
    def get_device_info_style(cls) -> str:
        """獲取設備信息標籤樣式"""
        return cls._get_static_style("device_info")

    @classmethod
    def get_tooltip_style(cls) -> str:
        """獲取工具提示樣式"""
        return cls._get_static_style("tooltip")

    @classmethod
    def get_action_button_style(cls) -> str:
        """獲取動作按鈕樣式（用於對話框中的按鈕）"""
        return cls._get_static_style("action_button")

    @classmethod
    def apply_button_style(cls, button, style: ButtonStyle, fixed_height: int = 36):
        """應用按鈕樣式到按鈕控件"""
        button.setStyleSheet(cls.get_button_style(style, fixed_height))
        if fixed_height:
            button.setFixedHeight(fixed_height)
            button.setProperty('_lazy_button_height', fixed_height)
        else:
            button.setProperty('_lazy_button_height', 0)
        button.setProperty('_lazy_button_style', style.value)

    @classmethod
    def apply_label_style(cls, label, style: LabelStyle):
        """應用標籤樣式到標籤控件"""
        label.setStyleSheet(cls.get_label_style(style))
        label.setProperty('_lazy_label_style', style.value)
        label.setProperty('_lazy_hint_label', False)

    @classmethod
    def apply_panel_frame(cls, frame, *, accent: bool = False) -> None:
        """套用卡片式面板樣式，維持一致邊距與背景。"""
        object_name = frame.objectName() or f'panel_{id(frame)}'
        frame.setObjectName(object_name)

        background = cls.COLORS.get('panel_background', '#FFFFFF')
        border = cls.COLORS.get('panel_border', '#D7DCE6')
        if accent:
            border = cls.COLORS.get('secondary', border)
        frame.setStyleSheet(
            f"""
            #{object_name} {{
                background-color: {background};
                border: 1px solid {border};
                border-radius: 12px;
            }}
            #{object_name} QLabel {{
                color: {cls.COLORS['text_primary']};
            }}
            """
        )
        frame.setProperty('_lazy_panel_accent', bool(accent))

    @classmethod
    def apply_hint_label(cls, label, *, margin: str | None = None) -> None:
        """套用提示樣式標籤。"""
        declarations: List[Tuple[str, str]] = [
            ("color", "{text_hint}"),
            ("font-style", "italic"),
        ]
        if margin:
            declarations.append(("margin", margin))
        css = _render_css((('QLabel', tuple(declarations)),), cls.COLORS)
        label.setStyleSheet(css)
        label.setProperty('_lazy_hint_label', True)
        label.setProperty('_lazy_hint_margin', margin or '')
        label.setProperty('_lazy_label_style', None)

    @classmethod
    def _resolve_tile_palette(cls, primary: bool, state: str) -> Dict[str, str]:
        palette: Dict[str, str] = {}
        if state == 'processing':
            palette['bg'] = cls.COLORS.get('tile_processing_bg', cls.COLORS.get('tile_primary_bg', '#444444'))
            palette['border'] = cls.COLORS.get('tile_processing_border', palette['bg'])
            palette['hover'] = cls.COLORS.get('tile_processing_hover', palette['border'])
            palette['pressed'] = palette['border']
            palette['fg'] = cls.COLORS.get('status_text_on_dark', '#FFFFFF')
        elif state == 'ready':
            palette['bg'] = cls.COLORS.get('tile_ready_bg', cls.COLORS.get('tile_primary_bg', '#111111'))
            palette['border'] = cls.COLORS.get('tile_ready_border', palette['bg'])
            palette['hover'] = cls.COLORS.get('tile_ready_hover', palette['border'])
            palette['pressed'] = palette['border']
            palette['fg'] = cls.COLORS.get('status_text_on_dark', '#FFFFFF')
        else:
            if primary:
                palette['bg'] = cls.COLORS.get('tile_primary_bg', '#EEF2FF')
                palette['border'] = cls.COLORS.get('tile_primary_border', '#A5B4FC')
                palette['hover'] = cls.COLORS.get('tile_primary_hover', '#E1E7FF')
                palette['pressed'] = palette['hover']
                palette['fg'] = cls.COLORS.get('tile_primary_text', cls.COLORS['text_primary'])
            else:
                palette['bg'] = cls.COLORS.get('tile_bg', '#F8FAFC')
                palette['border'] = cls.COLORS.get('tile_border', '#D0D7E2')
                palette['hover'] = cls.COLORS.get('tile_hover', '#EEF2F7')
                palette['pressed'] = palette['hover']
                palette['fg'] = cls.COLORS.get('tile_text', cls.COLORS['text_primary'])
        return palette

    @classmethod
    def apply_tile_button_style(cls, button, *, primary: bool = False, state: str = 'default') -> None:
        """套用格狀工具按鈕樣式，使用透明背景突出 SVG 圖示的語意化色彩。"""

        palette = cls._resolve_tile_palette(primary, state)
        selector = button.metaObject().className()
        object_name = button.objectName()
        if object_name:
            selector = f"{selector}#{object_name}"
        disabled_fg = cls.COLORS.get('status_disabled_text', '#9A9A9A')

        # Enhanced focus color for better keyboard navigation visibility
        focus_border = cls.COLORS.get('secondary', '#1976D2')

        css = f"""
{selector} {{
    background-color: transparent;
    border: none;
    border-radius: 14px;
    padding: 12px;
    color: {palette['fg']};
    font-weight: 600;
    transition: transform 0.2s ease-in-out, box-shadow 0.2s ease-in-out;
}}

{selector}:hover {{
    background-color: transparent;
    border: none;
    transform: translateY(-3px) scale(1.02);
    box-shadow: 0 6px 12px rgba(0, 0, 0, 0.18);
}}

{selector}:pressed {{
    background-color: transparent;
    border: none;
    transform: translateY(-1px) scale(1.0);
    box-shadow: 0 3px 6px rgba(0, 0, 0, 0.12);
}}

{selector}:focus {{
    outline: none;
    border: 2px solid {focus_border};
    box-shadow: 0 0 0 3px rgba(25, 118, 210, 0.2);
}}

{selector}:disabled {{
    background-color: transparent;
    color: {disabled_fg};
    border: none;
    opacity: 0.4;
    cursor: not-allowed;
}}

{selector}:disabled:hover {{
    transform: none;
    box-shadow: none;
}}
"""
        button.setStyleSheet(dedent(css).strip())
        button.setProperty('_lazy_tile_primary', bool(primary))
        button.setProperty('_lazy_tile_state', state)
        button.setProperty('_lazy_status_role', None)

    @classmethod
    def apply_material_card_frame_style(cls, frame, *, primary: bool = False) -> None:
        """Apply Material Design card style to a frame container.

        Args:
            frame: QFrame or QWidget to style as a card
            primary: Whether this is a primary/featured card
        """
        object_name = frame.objectName() or f'material_card_{id(frame)}'
        frame.setObjectName(object_name)

        # Material Design card colors
        card_bg = '#FFFFFF'
        card_border = '#E9ECEF'
        card_hover_border = '#DEE2E6'
        icon_container_bg = '#E7F5FF' if primary else '#F1F3F5'
        icon_color = '#1971C2' if primary else '#495057'
        title_color = '#212529'
        description_color = '#6C757D'

        css = f"""
#{object_name} {{
    background-color: {card_bg};
    border: 1px solid {card_border};
    border-radius: 16px;
    padding: 0px;  /* Padding handled by inner layout */
}}

#{object_name}:hover {{
    border: 1px solid {card_hover_border};
    box-shadow: {MD_SHADOW_3};
}}

#{object_name} QLabel[materialCardTitle="true"] {{
    color: {title_color};
    font-size: 14px;
    font-weight: 600;
    letter-spacing: 0.2px;
}}

#{object_name} QLabel[materialCardDescription="true"] {{
    color: {description_color};
    font-size: 12px;
    font-weight: 400;
    line-height: 1.4;
}}

#{object_name} QLabel[iconContainer="true"] {{
    background-color: {icon_container_bg};
    border-radius: 28px;
}}
"""
        frame.setStyleSheet(dedent(css).strip())
        frame.setProperty('_lazy_material_card', True)
        frame.setProperty('_lazy_material_primary', bool(primary))

    @classmethod
    def apply_status_style(cls, widget, status_key: str) -> None:
        """套用狀態樣式到元件（按鈕/標籤）。"""

        styles = cls.get_status_styles()
        status_css = styles.get(status_key)
        if not status_css:
            return

        class_name = widget.metaObject().className()
        object_name = widget.objectName()
        selector = f"{class_name}#{object_name}" if object_name else class_name
        transformed_css = status_css.replace('QPushButton', selector)
        widget.setStyleSheet(transformed_css)
        widget.setProperty('_lazy_status_role', status_key)
        widget.setProperty('_lazy_hint_label', False)

    @classmethod
    def get_global_stylesheet(cls) -> str:
        """取得應用程式全域樣式。"""
        return dedent(f"""
        QMainWindow {{
            background-color: {cls.COLORS['background']};
            color: {cls.COLORS['text_primary']};
        }}

        QWidget#mainCentralWidget {{
            background-color: {cls.COLORS['background']};
            color: {cls.COLORS['text_primary']};
        }}

        QLabel {{
            color: {cls.COLORS['text_primary']};
        }}
        """).strip()

    @classmethod
    def apply_global_stylesheet(cls, window) -> None:
        """套用全域樣式到主視窗。"""
        window.setStyleSheet(
            _combine_css(
                cls.get_global_stylesheet(),
                cls.get_tooltip_style(),
            )
        )

    @classmethod
    def reapply_theme(cls, root) -> None:
        """重新套用主題到既有控件。"""
        from PyQt6.QtWidgets import QLabel, QPushButton, QGroupBox, QToolButton

        for frame in root.findChildren(QGroupBox):
            accent = bool(frame.property('_lazy_panel_accent'))
            cls.apply_panel_frame(frame, accent=accent)

        for label in root.findChildren(QLabel):
            status_role = label.property('_lazy_status_role')
            if status_role:
                cls.apply_status_style(label, status_role)
                continue
            style_name = label.property('_lazy_label_style')
            if style_name:
                cls.apply_label_style(label, LabelStyle(style_name))
                continue
            if label.property('_lazy_hint_label'):
                margin = label.property('_lazy_hint_margin') or None
                cls.apply_hint_label(label, margin=margin)

        for button in root.findChildren(QPushButton):
            status_role = button.property('_lazy_status_role')
            if status_role:
                cls.apply_status_style(button, status_role)
                continue
            style_name = button.property('_lazy_button_style')
            if style_name:
                height = button.property('_lazy_button_height') or button.height()
                cls.apply_button_style(button, ButtonStyle(style_name), fixed_height=int(height))

        for tool_button in root.findChildren(QToolButton):
            status_role = tool_button.property('_lazy_status_role')
            if status_role:
                cls.apply_status_style(tool_button, status_role)
                continue
            primary_flag = tool_button.property('_lazy_tile_primary')
            if primary_flag is not None:
                state = tool_button.property('_lazy_tile_state') or 'default'
                cls.apply_tile_button_style(tool_button, primary=bool(primary_flag), state=state)

    @classmethod
    def get_status_styles(cls) -> Dict[str, str]:
        """獲取各種狀態的樣式字典"""
        return {
            'recording_active': f"color: {cls.COLORS['danger']}; font-weight: bold;",
            'recording_inactive': f"color: {cls.COLORS['text_hint']}; font-style: italic;",
            'screenshot_ready': cls._build_status_button_style(
                bg=cls.COLORS['tile_ready_bg'],
                border=cls.COLORS['tile_ready_border'],
                fg=cls.COLORS['status_text_on_dark'],
            ),
            'screenshot_processing': cls._build_status_button_style(
                bg=cls.COLORS['tile_processing_bg'],
                border=cls.COLORS['tile_processing_border'],
                fg=cls.COLORS['status_text_on_dark'],
            ),
        }

    @classmethod
    def _build_status_button_style(
        cls,
        *,
        bg: str,
        border: str,
        fg: str,
        base_selector: str = 'QPushButton',
    ) -> str:
        """建構狀態按鈕樣式，支援主題色彩。"""

        disabled_bg = cls.COLORS.get('status_disabled_bg', '#ebebeb')
        disabled_fg = cls.COLORS.get('status_disabled_text', '#9a9a9a')
        disabled_border = cls.COLORS.get('status_disabled_border', '#d1d1d1')

        template = f"""
{base_selector} {{
    padding: 8px 16px;
    border-radius: 6px;
    font-weight: 600;
    font-size: 12px;
    letter-spacing: 0.2px;
    min-width: 92px;
    height: 36px;
    transition: background-color 100ms ease, color 100ms ease, border-color 100ms ease;
    background-color: {bg};
    color: {fg};
    border: 2px solid {border};
}}

{base_selector}:hover {{
    background-color: {border};
    color: {fg};
    border: 2px solid {border};
}}

{base_selector}:pressed {{
    background-color: {border};
    color: {fg};
    border: 2px solid {border};
}}

{base_selector}:disabled {{
    background-color: {disabled_bg};
    color: {disabled_fg};
    border: 2px solid {disabled_border};
}}
"""
        return dedent(template).strip()


class ThemeManager:
    """主題管理器 - 支援主題切換"""

    def __init__(self):
        self.themes = {name: deepcopy(palette) for name, palette in _THEME_PRESETS.items()}
        self.current_theme = 'light'
        StyleManager.COLORS = deepcopy(self.themes[self.current_theme])

    def set_theme(self, theme_name: str) -> str:
        """設置主題並回傳最終套用的主題名稱。"""

        key = (theme_name or '').lower()
        key = _THEME_ALIASES.get(key, key)
        if key not in self.themes:
            return self.current_theme

        StyleManager.COLORS = deepcopy(self.themes[key])
        self.current_theme = key
        return self.current_theme

    def get_current_theme(self) -> str:
        """獲取當前主題名稱"""
        return self.current_theme
