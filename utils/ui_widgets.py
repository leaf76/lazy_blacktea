"""Reusable UI widgets and components for UI Inspector."""

from PyQt6.QtWidgets import QLabel, QWidget, QVBoxLayout
from PyQt6.QtCore import Qt
from typing import List, Optional

# Predefined styles for consistency and performance
LABEL_STYLES = {
    'header': '''
        QLabel {
            font-size: 16px;
            font-weight: bold;
            padding: 8px;
        }
    ''',
    'section_header': '''
        QLabel {{
            font-size: 14px;
            font-weight: bold;
            color: {color};
            padding: 10px 12px;
            border-radius: 6px;
            border-left: 4px solid {color};
            margin-bottom: 12px;
        }}
    ''',
    'content_item': '''
        QLabel {
            font-size: 12px;
            padding: 8px 12px;
            border-radius: 4px;
            margin-bottom: 6px;
            border: 1px solid palette(mid);
        }
    ''',
    'welcome': '''
        QLabel {
            font-size: 16px;
            font-weight: bold;
            color: #2196F3;
            padding: 8px;
        }
    ''',
    'instruction': '''
        QLabel {
            font-size: 12px;
            color: #666666;
            padding: 4px 8px;
            background-color: #E3F2FD;
            border-radius: 4px;
            margin: 4px 0px;
        }
    ''',
    'loading': '''
        QLabel {
            font-size: 16px;
            font-weight: bold;
            color: #FF9800;
            padding: 8px;
        }
    ''',
    'success': '''
        QLabel {
            font-size: 16px;
            font-weight: bold;
            color: #4CAF50;
            padding: 8px;
        }
    ''',
    'error': '''
        QLabel {
            font-size: 16px;
            font-weight: bold;
            color: #F44336;
            padding: 8px;
        }
    '''
}

# Color schemes for different UI sections
COLOR_SCHEMES = {
    'content': '#4CAF50',      # Green
    'position': '#FF9800',     # Orange
    'interaction': '#9C27B0',  # Purple
    'technical': '#607D8B',    # Blue Gray
    'automation': '#795548',   # Brown
    'device': '#2196F3',       # Blue
    'error': '#F44336',        # Red
    'warning': '#FF9800',      # Orange
    'info': '#2196F3'          # Blue
}


def create_styled_label(text: str, style_name: str, color: Optional[str] = None) -> QLabel:
    """
    Create a styled QLabel with predefined styles.

    Args:
        text: Label text
        style_name: Style name from LABEL_STYLES
        color: Optional color for styles that support it

    Returns:
        Styled QLabel
    """
    label = QLabel(text)

    if style_name in LABEL_STYLES:
        style = LABEL_STYLES[style_name]
        if color and '{color}' in style:
            style = style.format(color=color)
        label.setStyleSheet(style)

    # Common properties
    if style_name in ['instruction', 'content_item']:
        label.setWordWrap(True)

    if style_name == 'content_item':
        label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

    return label


class DetailSection(QWidget):
    """Reusable detail section widget for UI Inspector."""

    def __init__(self, title: str, icon: str, items: List[str], color: str = '#333333'):
        super().__init__()
        self.setup_ui(title, icon, items, color)

    def setup_ui(self, title: str, icon: str, items: List[str], color: str):
        """Setup the detail section UI with proper spacing."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(6)

        # Set minimum height to prevent overlap while allowing expansion
        required_height = self.calculateRequiredHeight(len(items))
        self.setMinimumHeight(required_height)
        from PyQt6.QtWidgets import QSizePolicy
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        # Apply styling directly to QWidget (not DetailSection)
        self.setStyleSheet('''
            QWidget {
                border: 1px solid palette(mid);
                border-radius: 8px;
                background-color: palette(base);
                margin-bottom: 12px;
            }
        ''')

        # Section header
        header_label = create_styled_label(f'{icon} {title}', 'section_header', color)
        layout.addWidget(header_label)

        # Section items
        for item in items:
            item_label = create_styled_label(item, 'content_item')
            layout.addWidget(item_label)

    def calculateRequiredHeight(self, item_count: int) -> int:
        """Calculate the required height for this section."""
        header_height = 60   # Section header (increased)
        item_height = 45     # Each content item (increased)
        padding = 24         # Top + bottom padding
        spacing = 8 * item_count  # Spacing between items

        return header_height + (item_height * item_count) + padding + spacing


class MessageWidget(QWidget):
    """Reusable message widget for different states."""

    def __init__(self, message: str, message_type: str = 'info', details: Optional[List[str]] = None):
        super().__init__()
        self.setup_ui(message, message_type, details)

    def setup_ui(self, message: str, message_type: str, details: Optional[List[str]]):
        """Setup the message widget UI with proper spacing."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Calculate and set minimum height to prevent overlap
        item_count = 1 + (len(details) if details else 0)
        required_height = self.calculateRequiredHeight(item_count)
        self.setMinimumHeight(required_height)

        # Clear background and border styling
        self.setStyleSheet('''
            MessageWidget {
                background-color: palette(base);
                border: 1px solid palette(mid);
                border-radius: 6px;
            }
        ''')

        # Main message
        main_label = create_styled_label(message, message_type)
        layout.addWidget(main_label)

        # Details if provided
        if details:
            for detail in details:
                detail_label = create_styled_label(detail, 'instruction')
                layout.addWidget(detail_label)

        layout.addStretch()

    def calculateRequiredHeight(self, item_count: int) -> int:
        """Calculate required height for message widget."""
        header_height = 60   # Main message (increased)
        item_height = 40     # Each detail item (increased)
        padding = 32         # Top + bottom padding
        spacing = 12 * item_count  # Spacing between items

        return header_height + (item_height * (item_count - 1)) + padding + spacing


def create_welcome_widget() -> QWidget:
    """Create the welcome message widget."""
    return MessageWidget(
        '👋 Welcome to UI Inspector!',
        'welcome',
        ['💡 Click on elements in the screenshot or hierarchy tree to inspect them']
    )


def create_loading_widget(device_model: str, device_serial: str) -> QWidget:
    """Create the loading message widget."""
    details = [
        f'📱 Device: {device_model}',
        f'🔧 Serial: {device_serial}',
        '📸 Capturing screenshot...',
        '🌳 Dumping UI hierarchy...'
    ]
    return MessageWidget('⏳ Loading UI Data...', 'loading', details)


def create_success_widget(device_model: str, element_count: int) -> QWidget:
    """Create the success message widget."""
    details = [
        f'📱 Device: {device_model}',
        f'🔍 Found {element_count} UI elements',
        '💡 Click elements to inspect them'
    ]
    return MessageWidget('✅ UI Data Loaded Successfully!', 'success', details)


def create_error_widget(device_model: str, device_serial: str, error_msg: str) -> QWidget:
    """Create the error message widget."""
    widget = QWidget()
    layout = QVBoxLayout(widget)
    layout.setContentsMargins(12, 12, 12, 12)
    layout.setSpacing(8)

    # Error header
    error_label = create_styled_label('❌ Error Loading UI Data', 'error')
    layout.addWidget(error_label)

    # Device information section
    device_info = [
        f'📱 Device: {device_model}',
        f'🔧 Serial: {device_serial}'
    ]
    device_section = DetailSection('Device Information', '📱', device_info, COLOR_SCHEMES['error'])
    layout.addWidget(device_section)

    # Error details section
    error_info = [f'Error: {error_msg}']
    error_section = DetailSection('Error Details', '❌', error_info, COLOR_SCHEMES['error'])
    layout.addWidget(error_section)

    # Solutions section
    solutions = [
        '• Check device connection',
        '• Enable USB debugging',
        '• Ensure device is unlocked',
        '• Try refreshing the data'
    ]
    solutions_section = DetailSection('Possible Solutions', '💡', solutions, COLOR_SCHEMES['warning'])
    layout.addWidget(solutions_section)

    layout.addStretch()
    return widget


def create_element_header(class_name: str) -> QLabel:
    """Create element header label."""
    header_label = QLabel(f'🔍 {class_name}')
    header_label.setStyleSheet('''
        QLabel {
            font-size: 18px;
            font-weight: bold;
            color: #2196F3;
            padding: 8px;
            background-color: #E3F2FD;
            border-radius: 6px;
            border-left: 4px solid #2196F3;
        }
    ''')
    return header_label


def create_content_section(element: dict) -> Optional[DetailSection]:
    """Create content information section for element."""
    content_items = []

    if element.get('text'):
        content_items.append(f"📝 Text: '{element['text']}'")

    if element.get('content_desc'):
        content_items.append(f"💬 Description: '{element['content_desc']}'")

    if element.get('resource_id'):
        resource_id = element['resource_id']
        if ':id/' in resource_id:
            short_id = resource_id.split(':id/')[-1]
            content_items.append(f"🆔 Resource ID: {short_id}")
            content_items.append(f"📦 Full ID: {resource_id}")
        else:
            content_items.append(f"🆔 Resource ID: {resource_id}")

    if content_items:
        return DetailSection('Content', '📝', content_items, COLOR_SCHEMES['content'])

    return None


def create_position_section(element: dict) -> DetailSection:
    """Create position and size section for element."""
    bounds = element['bounds']
    width = bounds[2] - bounds[0]
    height = bounds[3] - bounds[1]
    center_x = bounds[0] + width // 2
    center_y = bounds[1] + height // 2

    position_items = [
        f"📐 Bounds: [{bounds[0]}, {bounds[1]}] → [{bounds[2]}, {bounds[3]}]",
        f"📏 Size: {width} × {height} px",
        f"🎯 Center: ({center_x}, {center_y})",
        f"🗃️ Area: {width * height:,} px²"
    ]

    return DetailSection('Position & Size', '📍', position_items, COLOR_SCHEMES['position'])


def create_interaction_section(element: dict) -> DetailSection:
    """Create interaction properties section for element."""
    interaction_items = [
        f"🖱️ Clickable: {'Yes ✅' if element.get('clickable') else 'No ❌'}",
        f"⚡ Enabled: {'Yes ✅' if element.get('enabled') else 'No ❌'}",
        f"🎯 Focusable: {'Yes ✅' if element.get('focusable') else 'No ❌'}"
    ]

    # Additional properties
    extra_props = {
        'selected': '☑️ Selected',
        'checked': '✅ Checked',
        'checkable': '📋 Checkable',
        'password': '🔒 Password Field',
        'scrollable': '📜 Scrollable',
        'long_clickable': '🖱️ Long Clickable'
    }

    for prop, label in extra_props.items():
        if prop in element:
            interaction_items.append(f"{label}: {'Yes ✅' if element[prop] else 'No ❌'}")

    return DetailSection('Interaction', '🖱️', interaction_items, COLOR_SCHEMES['interaction'])


def create_technical_section(element: dict) -> DetailSection:
    """Create technical details section for element."""
    bounds = element['bounds']
    width = bounds[2] - bounds[0]
    height = bounds[3] - bounds[1]

    technical_items = [
        f"📂 Class: {element.get('class', 'N/A')}",
        f"🌳 XPath: {element.get('path', 'N/A')}"
    ]

    if element.get('path'):
        depth = element['path'].count('/') - 1
        technical_items.append(f"📊 Depth: Level {depth}")

    # Visibility status
    if width > 0 and height > 0:
        visibility_status = "🟢 Fully Visible"
        if bounds[0] < 0 or bounds[1] < 0:
            visibility_status = "🟡 Partially Visible"
        technical_items.append(f"👁️ Visibility: {visibility_status}")

    return DetailSection('Technical', '🔧', technical_items, COLOR_SCHEMES['technical'])


def create_automation_section(element: dict) -> DetailSection:
    """Create automation tips section for element."""
    from utils.ui_inspector_utils import get_element_automation_tips

    automation_items = get_element_automation_tips(element)
    return DetailSection('Automation Tips', '🤖', automation_items, COLOR_SCHEMES['automation'])