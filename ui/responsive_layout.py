"""Responsive grid layout system for adaptive UI sizing."""

from __future__ import annotations

from typing import List, Optional
from PyQt6.QtWidgets import QWidget, QGridLayout, QVBoxLayout
from PyQt6.QtCore import Qt, QSize


class ResponsiveGridLayout(QGridLayout):
    """A grid layout that adapts column count based on available space."""

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        *,
        min_columns: int = 1,
        max_columns: int = 4,
        min_item_width: int = 120,
        horizontal_spacing: int = 16,
        vertical_spacing: int = 12
    ):
        """
        Initialize a responsive grid layout.

        Args:
            parent: Parent widget
            min_columns: Minimum number of columns
            max_columns: Maximum number of columns
            min_item_width: Minimum width for each item in pixels
            horizontal_spacing: Horizontal spacing between items
            vertical_spacing: Vertical spacing between items
        """
        super().__init__(parent)

        self.min_columns = min_columns
        self.max_columns = max_columns
        self.min_item_width = min_item_width

        self.setHorizontalSpacing(horizontal_spacing)
        self.setVerticalSpacing(vertical_spacing)
        self.setContentsMargins(16, 24, 16, 16)

        self._items: List[QWidget] = []
        self._last_width = 0

    def addWidget(self, widget: QWidget, *args, **kwargs) -> None:
        """
        Add a widget to the layout.

        Args:
            widget: Widget to add
        """
        if not args and not kwargs:
            # Store widget for responsive repositioning
            self._items.append(widget)
            self._relayout()
        else:
            # Use default grid layout positioning
            super().addWidget(widget, *args, **kwargs)

    def _relayout(self) -> None:
        """Recalculate and apply layout based on current width."""
        if not self._items:
            return

        # Calculate optimal column count
        parent = self.parentWidget()
        if parent:
            available_width = parent.width()
            if available_width == self._last_width:
                return  # No change needed

            self._last_width = available_width

            # Calculate columns based on available width
            columns = max(
                self.min_columns,
                min(
                    self.max_columns,
                    available_width // (self.min_item_width + self.horizontalSpacing())
                )
            )

            # Clear existing layout
            while self.count():
                item = self.takeAt(0)
                if item.widget():
                    item.widget().setParent(None)

            # Re-add items in grid
            for index, widget in enumerate(self._items):
                row = index // columns
                col = index % columns
                super().addWidget(widget, row, col)

            # Set column stretch
            for col in range(columns):
                self.setColumnStretch(col, 1)

    def resizeEvent(self, event) -> None:
        """Handle resize events to trigger relayout."""
        super().resizeEvent(event)
        self._relayout()


class AdaptiveContainer(QWidget):
    """A container that wraps a responsive grid layout."""

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        min_columns: int = 1,
        max_columns: int = 4,
        min_item_width: int = 120
    ):
        """
        Initialize an adaptive container.

        Args:
            parent: Parent widget
            min_columns: Minimum number of columns
            max_columns: Maximum number of columns
            min_item_width: Minimum item width in pixels
        """
        super().__init__(parent)

        self.layout = ResponsiveGridLayout(
            self,
            min_columns=min_columns,
            max_columns=max_columns,
            min_item_width=min_item_width
        )
        self.setLayout(self.layout)

    def add_widget(self, widget: QWidget) -> None:
        """Add a widget to the container."""
        self.layout.addWidget(widget)

    def clear(self) -> None:
        """Remove all widgets from the container."""
        while self.layout.count():
            item = self.layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def resizeEvent(self, event) -> None:
        """Handle resize events."""
        super().resizeEvent(event)
        self.layout._relayout()


class BreakpointManager:
    """Manages responsive breakpoints for different screen sizes."""

    # Standard breakpoints (in pixels)
    BREAKPOINTS = {
        'xs': 0,      # Extra small (mobile)
        'sm': 640,    # Small (tablet portrait)
        'md': 768,    # Medium (tablet landscape)
        'lg': 1024,   # Large (desktop)
        'xl': 1280,   # Extra large (wide desktop)
        '2xl': 1536,  # 2X large (ultra-wide)
    }

    # Column configurations for different breakpoints
    COLUMN_CONFIG = {
        'xs': {'min': 1, 'max': 1},
        'sm': {'min': 1, 'max': 2},
        'md': {'min': 2, 'max': 3},
        'lg': {'min': 2, 'max': 3},
        'xl': {'min': 3, 'max': 4},
        '2xl': {'min': 3, 'max': 4},
    }

    @classmethod
    def get_breakpoint(cls, width: int) -> str:
        """
        Get the current breakpoint name for a given width.

        Args:
            width: Width in pixels

        Returns:
            Breakpoint name ('xs', 'sm', 'md', 'lg', 'xl', '2xl')
        """
        breakpoint = 'xs'
        for name, min_width in sorted(cls.BREAKPOINTS.items(), key=lambda x: x[1]):
            if width >= min_width:
                breakpoint = name
        return breakpoint

    @classmethod
    def get_column_config(cls, width: int) -> dict:
        """
        Get column configuration for a given width.

        Args:
            width: Width in pixels

        Returns:
            Dictionary with 'min' and 'max' column counts
        """
        breakpoint = cls.get_breakpoint(width)
        return cls.COLUMN_CONFIG[breakpoint]

    @classmethod
    def get_optimal_columns(cls, width: int, item_width: int, spacing: int = 16) -> int:
        """
        Calculate optimal number of columns for given constraints.

        Args:
            width: Available width in pixels
            item_width: Minimum item width in pixels
            spacing: Spacing between items in pixels

        Returns:
            Optimal number of columns
        """
        config = cls.get_column_config(width)
        calculated = max(1, width // (item_width + spacing))
        return max(config['min'], min(config['max'], calculated))


__all__ = [
    'ResponsiveGridLayout',
    'AdaptiveContainer',
    'BreakpointManager'
]
