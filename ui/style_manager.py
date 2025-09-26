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

    # 顏色主題定義
    COLORS = {
        'primary': '#4CAF50',
        'primary_hover': '#45a049',
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
        'border': '#E0E0E0',
        'background': '#F5F5F5',
        'background_hover': 'rgba(200, 220, 255, 0.5)',
    }

    _BUTTON_COLOR_MAP = {
        ButtonStyle.PRIMARY: 'primary',
        ButtonStyle.SECONDARY: 'secondary',
        ButtonStyle.WARNING: 'warning',
        ButtonStyle.DANGER: 'danger',
        ButtonStyle.NEUTRAL: 'neutral',
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
                    ("color", "{text_secondary}"),
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
                    ("color", "gray"),
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
                    ("border", "1px solid #CCCCCC"),
                    ("border-radius", "4px"),
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
                    ("background-color", "white"),
                    ("color", "black"),
                    ("border", "2px solid {border}"),
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
                    ("background-color", "rgba(45, 45, 45, 0.95)"),
                    ("color", "white"),
                    ("border", "1px solid rgba(255, 255, 255, 0.2)"),
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
        ),
    }

    _BUTTON_BASE_BLOCKS: CSSBlocks = (
        (
            "QPushButton",
            (
                ("padding", "8px 16px"),
                ("border", "none"),
                ("border-radius", "4px"),
                ("font-weight", "bold"),
                ("font-size", "12px"),
                ("min-width", "80px"),
                ("height", "{button_height}"),
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

    @classmethod
    def _colored_button_blocks(cls, color_key: str) -> CSSBlocks:
        return (
            (
                "QPushButton",
                (
                    ("background-color", f"{{{color_key}}}"),
                    ("color", "white"),
                ),
            ),
            (
                "QPushButton:hover",
                (
                    ("background-color", f"{{{color_key}_hover}}"),
                ),
            ),
            (
                "QPushButton:disabled",
                (
                    ("background-color", "#CCCCCC"),
                    ("color", "#888888"),
                ),
            ),
        )

    @classmethod
    def get_button_style(cls, style: ButtonStyle, fixed_height: int = 36) -> str:
        """獲取按鈕樣式"""
        overrides = {"button_height": f"{fixed_height}px"}
        if style == ButtonStyle.SYSTEM:
            return _render_css(cls._SYSTEM_BUTTON_BLOCKS, cls.COLORS, overrides)

        base_style = _render_css(cls._BUTTON_BASE_BLOCKS, cls.COLORS, overrides)
        color_key = cls._BUTTON_COLOR_MAP.get(style)
        if color_key:
            color_css = _render_css(cls._colored_button_blocks(color_key), cls.COLORS)
            return _combine_css(base_style, color_css)
        return base_style

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

    @classmethod
    def apply_label_style(cls, label, style: LabelStyle):
        """應用標籤樣式到標籤控件"""
        label.setStyleSheet(cls.get_label_style(style))

    @classmethod
    def get_status_styles(cls) -> Dict[str, str]:
        """獲取各種狀態的樣式字典"""
        return {
            'recording_active': 'color: red; font-weight: bold;',
            'recording_inactive': 'color: gray; font-style: italic;',
            'screenshot_ready': cls.get_button_style(ButtonStyle.PRIMARY),
            'screenshot_processing': cls.get_button_style(ButtonStyle.WARNING),
        }


class ThemeManager:
    """主題管理器 - 支援主題切換"""

    def __init__(self):
        self.current_theme = "default"
        self.themes = {
            "default": StyleManager.COLORS,
            "dark": {
                **StyleManager.COLORS,
                'background': '#2E2E2E',
                'text_primary': '#FFFFFF',
                'text_secondary': '#CCCCCC',
                'border': '#555555',
            }
        }

    def set_theme(self, theme_name: str):
        """設置主題"""
        if theme_name in self.themes:
            self.current_theme = theme_name
            StyleManager.COLORS.update(self.themes[theme_name])

    def get_current_theme(self) -> str:
        """獲取當前主題名稱"""
        return self.current_theme
