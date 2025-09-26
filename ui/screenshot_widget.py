"""Reusable screenshot label with interactive overlays."""

from __future__ import annotations

from typing import Iterable, List, Optional

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QBrush, QColor, QFont, QPainter, QPen
from PyQt6.QtWidgets import QLabel


class ClickableScreenshotLabel(QLabel):
    """Label widget that renders UI element overlays and emits click positions."""

    element_clicked = pyqtSignal(int, int)

    def __init__(self) -> None:
        super().__init__()
        self.ui_elements: List[dict] = []
        self.selected_element: Optional[dict] = None
        self.scale_factor: float = 1.0

    def set_ui_elements(self, elements: Iterable[dict], scale_factor: float = 1.0) -> None:
        """Attach UI elements for visualization."""
        self.ui_elements = list(elements)
        self.scale_factor = scale_factor
        self.update()

    def set_selected_element(self, element: Optional[dict]) -> None:
        """Highlight a specific UI element."""
        self.selected_element = element
        self.update()

    def _rectangles_overlap(self, rect1, rect2, overlap_threshold: float = 0.8) -> bool:
        """Return True when two rectangles overlap beyond the threshold."""
        x1, y1, w1, h1 = rect1
        x2, y2, w2, h2 = rect2

        left = max(x1, x2)
        top = max(y1, y2)
        right = min(x1 + w1, x2 + w2)
        bottom = min(y1 + h1, y2 + h2)

        if left >= right or top >= bottom:
            return False

        intersection_area = (right - left) * (bottom - top)
        smaller_area = min(w1 * h1, w2 * h2)
        return intersection_area / smaller_area >= overlap_threshold

    def mousePressEvent(self, event) -> None:  # type: ignore[override]
        if event.button() == 1:
            x = int(event.position().x() / self.scale_factor)
            y = int(event.position().y() / self.scale_factor)
            self.element_clicked.emit(x, y)
        super().mousePressEvent(event)

    def paintEvent(self, event) -> None:  # type: ignore[override]
        super().paintEvent(event)
        if not self.ui_elements:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setFont(QFont("Arial", 8, QFont.Weight.Bold))

        processed_elements = self._process_elements()
        if not processed_elements:
            return

        element_count = self._draw_ui_elements(painter, processed_elements)
        self._draw_selected_element(painter)
        self._draw_element_count(painter, element_count)

    def _process_elements(self):
        sorted_elements = sorted(self.ui_elements, key=lambda e: (
            not e.get('clickable', False),
            not bool(e.get('text', '').strip()),
            not bool(e.get('resource_id')),
            not bool(e.get('content_desc'))
        ))

        processed = []
        drawn_bounds: List[tuple] = []
        for element in sorted_elements:
            bounds = element['bounds']
            scaled_rect = self._calculate_scaled_rect(bounds)
            if not scaled_rect:
                continue

            if self._check_overlap(scaled_rect, drawn_bounds):
                continue

            styling = self._get_element_styling(element, scaled_rect[2], scaled_rect[3])
            if not styling:
                continue

            processed.append({'rect': scaled_rect, 'styling': styling, 'element': element})
            drawn_bounds.append(scaled_rect)
        return processed

    def _calculate_scaled_rect(self, bounds):
        x1 = int(bounds[0] * self.scale_factor)
        y1 = int(bounds[1] * self.scale_factor)
        x2 = int(bounds[2] * self.scale_factor)
        y2 = int(bounds[3] * self.scale_factor)

        width = x2 - x1
        height = y2 - y1
        if width < 5 or height < 5:
            return None
        return (x1, y1, width, height)

    def _check_overlap(self, current_rect, drawn_bounds):
        for drawn_rect in drawn_bounds:
            if self._rectangles_overlap(current_rect, drawn_rect, overlap_threshold=0.8):
                return True
        return False

    def _get_element_styling(self, element, width, height):
        if element.get('clickable', False):
            if element.get('text'):
                return {
                    'pen_color': QColor(0, 200, 255, 180),
                    'brush_color': QColor(0, 200, 255, 30),
                    'label_bg_color': QColor(0, 150, 255, 200),
                    'label': "🔵"
                }
            return {
                'pen_color': QColor(0, 255, 0, 180),
                'brush_color': QColor(0, 255, 0, 30),
                'label_bg_color': QColor(0, 200, 0, 200),
                'label': "🖱️"
            }
        if element.get('text') and element['text'].strip():
            return {
                'pen_color': QColor(0, 100, 255, 150),
                'brush_color': QColor(0, 100, 255, 20),
                'label_bg_color': QColor(0, 100, 255, 180),
                'label': "📝"
            }
        if element.get('resource_id'):
            return {
                'pen_color': QColor(150, 0, 255, 150),
                'brush_color': QColor(150, 0, 255, 20),
                'label_bg_color': QColor(150, 0, 255, 180),
                'label': "🆔"
            }
        if element.get('content_desc'):
            return {
                'pen_color': QColor(255, 165, 0, 150),
                'brush_color': QColor(255, 165, 0, 20),
                'label_bg_color': QColor(255, 165, 0, 180),
                'label': "💬"
            }
        if width >= 20 and height >= 20:
            return {
                'pen_color': QColor(128, 128, 128, 100),
                'brush_color': QColor(128, 128, 128, 15),
                'label_bg_color': QColor(128, 128, 128, 150),
                'label': "📦"
            }
        return None

    def _draw_ui_elements(self, painter, processed_elements):
        element_count = 0
        for item in processed_elements:
            x1, y1, width, height = item['rect']
            styling = item['styling']

            painter.setPen(QPen(styling['pen_color'], 1, Qt.PenStyle.SolidLine))
            painter.setBrush(QBrush(styling['brush_color']))
            painter.drawRect(x1, y1, width, height)

            if width > 25 and height > 15:
                self._draw_element_label(painter, x1, y1, styling)
            element_count += 1
        return element_count

    def _draw_element_label(self, painter, x1, y1, styling):
        label_x, label_y, label_size = x1 + 2, y1 + 2, 12
        painter.setPen(QPen(Qt.GlobalColor.transparent))
        painter.setBrush(QBrush(styling['label_bg_color']))
        painter.drawRect(label_x, label_y, label_size, label_size)
        painter.setPen(QPen(Qt.GlobalColor.white))
        painter.drawText(label_x + 1, label_y + 10, styling['label'])

    def _draw_selected_element(self, painter):
        if not self.selected_element:
            return
        scaled_rect = self._calculate_scaled_rect(self.selected_element['bounds'])
        if not scaled_rect:
            return
        x1, y1, width, height = scaled_rect
        painter.setPen(QPen(QColor(255, 0, 0, 255), 3, Qt.PenStyle.SolidLine))
        painter.setBrush(QBrush(QColor(255, 0, 0, 50)))
        painter.drawRect(x1, y1, width, height)
        painter.setPen(QPen(Qt.GlobalColor.white))
        painter.setBrush(QBrush(QColor(255, 0, 0, 220)))
        painter.drawRect(x1, y1 - 20, 80, 18)
        painter.drawText(x1 + 5, y1 - 6, "🎯 SELECTED")

    def _draw_element_count(self, painter, element_count):
        if element_count <= 0:
            return
        painter.setPen(QPen(Qt.GlobalColor.white))
        painter.setBrush(QBrush(QColor(0, 0, 0, 180)))
        text_width = 120
        painter.drawRect(self.width() - text_width - 10, 10, text_width, 20)
        painter.drawText(self.width() - text_width - 5, 25, f"📱 {element_count} elements")


__all__ = ["ClickableScreenshotLabel"]
