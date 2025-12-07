"""
Floating search bar widget for logcat viewer.

Provides VS Code-style search functionality with:
- Real-time search input
- Match count display (X of Y)
- Previous/Next navigation (F3/Shift+F3)
- Case sensitivity toggle
- Regex mode toggle
- Close button (Escape)
"""

import re
from typing import Optional, List, Tuple

from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QLineEdit, QPushButton, QLabel,
    QCheckBox, QSizePolicy, QGraphicsDropShadowEffect
)
from PyQt6.QtCore import pyqtSignal, Qt, QTimer
from PyQt6.QtGui import QKeySequence, QShortcut, QColor


class SearchBarWidget(QWidget):
    """Floating search bar widget for log search with highlighting."""

    # Signals
    search_changed = pyqtSignal(str)  # Emitted when search pattern changes
    navigate_next = pyqtSignal()      # Emitted when user wants next match
    navigate_prev = pyqtSignal()      # Emitted when user wants previous match
    closed = pyqtSignal()             # Emitted when search bar is closed

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._match_count = 0
        self._current_match = 0
        self._debounce_timer = QTimer()
        self._debounce_timer.setSingleShot(True)
        self._debounce_timer.setInterval(150)
        self._debounce_timer.timeout.connect(self._emit_search_changed)

        self._init_ui()
        self._setup_shortcuts()
        self.hide()

    def _init_ui(self) -> None:
        """Initialize the search bar UI."""
        self.setObjectName('logcat_search_bar')
        self.setStyleSheet('''
            QWidget#logcat_search_bar {
                background-color: #252526;
                border: 1px solid #007acc;
                border-radius: 6px;
                padding: 6px;
            }
            QLineEdit {
                background-color: #3c3c3c;
                color: #ffffff;
                border: 1px solid #007acc;
                border-radius: 4px;
                padding: 5px 10px;
                min-width: 220px;
                font-size: 13px;
            }
            QLineEdit:focus {
                border-color: #0098ff;
                background-color: #404040;
            }
            QPushButton {
                background-color: #3c3c3c;
                color: #cccccc;
                border: 1px solid #555555;
                padding: 4px 8px;
                border-radius: 4px;
                min-width: 26px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #505050;
                border-color: #007acc;
            }
            QPushButton:pressed {
                background-color: #007acc;
            }
            QPushButton:disabled {
                color: #555555;
                background-color: #2d2d2d;
            }
            QLabel {
                color: #cccccc;
                padding: 0 6px;
                font-size: 12px;
            }
            QCheckBox {
                color: #cccccc;
                spacing: 4px;
                font-size: 12px;
            }
            QCheckBox::indicator {
                width: 16px;
                height: 16px;
                border: 1px solid #555555;
                border-radius: 3px;
                background-color: #3c3c3c;
            }
            QCheckBox::indicator:hover {
                border-color: #007acc;
            }
            QCheckBox::indicator:checked {
                background-color: #007acc;
                border-color: #007acc;
            }
        ''')

        # Add drop shadow effect for floating appearance
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(20)
        shadow.setXOffset(0)
        shadow.setYOffset(4)
        shadow.setColor(QColor(0, 0, 0, 150))
        self.setGraphicsEffect(shadow)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 4, 6, 4)
        layout.setSpacing(4)

        # Search input
        self._search_input = QLineEdit()
        self._search_input.setPlaceholderText('Search logs...')
        self._search_input.textChanged.connect(self._on_text_changed)
        self._search_input.returnPressed.connect(self._on_enter_pressed)
        layout.addWidget(self._search_input)

        # Match count label
        self._match_label = QLabel('No results')
        self._match_label.setMinimumWidth(70)
        layout.addWidget(self._match_label)

        # Navigation buttons
        self._prev_btn = QPushButton('▲')
        self._prev_btn.setToolTip('Previous match (Shift+F3)')
        self._prev_btn.clicked.connect(self.navigate_prev.emit)
        self._prev_btn.setEnabled(False)
        layout.addWidget(self._prev_btn)

        self._next_btn = QPushButton('▼')
        self._next_btn.setToolTip('Next match (F3)')
        self._next_btn.clicked.connect(self.navigate_next.emit)
        self._next_btn.setEnabled(False)
        layout.addWidget(self._next_btn)

        # Separator
        separator = QWidget()
        separator.setFixedWidth(1)
        separator.setStyleSheet('background-color: #464646;')
        layout.addWidget(separator)

        # Options
        self._case_checkbox = QCheckBox('Aa')
        self._case_checkbox.setToolTip('Match case')
        self._case_checkbox.toggled.connect(self._on_option_changed)
        layout.addWidget(self._case_checkbox)

        self._regex_checkbox = QCheckBox('.*')
        self._regex_checkbox.setToolTip('Use regular expression')
        self._regex_checkbox.toggled.connect(self._on_option_changed)
        layout.addWidget(self._regex_checkbox)

        # Close button
        close_btn = QPushButton('✕')
        close_btn.setToolTip('Close (Escape)')
        close_btn.clicked.connect(self.close_search)
        layout.addWidget(close_btn)

        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        self.setFixedHeight(36)

    def _setup_shortcuts(self) -> None:
        """Setup keyboard shortcuts."""
        # Escape to close
        escape_shortcut = QShortcut(QKeySequence(Qt.Key.Key_Escape), self)
        escape_shortcut.activated.connect(self.close_search)

        # F3 for next match (handled at window level)
        # Shift+F3 for previous match (handled at window level)

    def _on_text_changed(self, text: str) -> None:
        """Handle search input text changes with debouncing."""
        self._debounce_timer.start()

    def _emit_search_changed(self) -> None:
        """Emit the search changed signal after debounce."""
        pattern = self.get_search_pattern()
        self.search_changed.emit(pattern)

    def _on_enter_pressed(self) -> None:
        """Handle Enter key - navigate to next match."""
        if self._match_count > 0:
            self.navigate_next.emit()

    def _on_option_changed(self) -> None:
        """Handle option checkbox changes."""
        self._emit_search_changed()

    def get_search_pattern(self) -> str:
        """Get the current search pattern."""
        return self._search_input.text().strip()

    def is_case_sensitive(self) -> bool:
        """Return whether case-sensitive search is enabled."""
        return self._case_checkbox.isChecked()

    def is_regex_mode(self) -> bool:
        """Return whether regex mode is enabled."""
        return self._regex_checkbox.isChecked()

    def compile_pattern(self) -> Optional[re.Pattern]:
        """Compile the current search pattern into a regex."""
        pattern = self.get_search_pattern()
        if not pattern:
            return None

        flags = 0 if self.is_case_sensitive() else re.IGNORECASE

        try:
            if self.is_regex_mode():
                return re.compile(pattern, flags)
            else:
                # Escape special regex characters for literal search
                return re.compile(re.escape(pattern), flags)
        except re.error:
            return None

    def update_match_count(
        self, current: int, total: int, *, limited: bool = False
    ) -> None:
        """Update the match count display.

        Args:
            current: Current match index (1-based)
            total: Total number of matches
            limited: If True, indicates results were truncated (shows "X of Y+")
        """
        self._current_match = current
        self._match_count = total

        if total == 0:
            if self.get_search_pattern():
                self._match_label.setText('No results')
                self._match_label.setStyleSheet('color: #f48771;')  # Red for no results
            else:
                self._match_label.setText('')
                self._match_label.setStyleSheet('color: #969696;')
        else:
            suffix = '+' if limited else ''
            self._match_label.setText(f'{current} of {total}{suffix}')
            self._match_label.setStyleSheet('color: #969696;')

        self._prev_btn.setEnabled(total > 0)
        self._next_btn.setEnabled(total > 0)

    def show_search(self) -> None:
        """Show the search bar and focus the input."""
        self.show()
        self._search_input.setFocus()
        self._search_input.selectAll()

    def close_search(self) -> None:
        """Close the search bar."""
        self.hide()
        self._search_input.clear()
        self.closed.emit()

    def focus_input(self) -> None:
        """Focus the search input field."""
        self._search_input.setFocus()
        self._search_input.selectAll()

    def set_search_text(self, text: str) -> None:
        """Set the search input text."""
        self._search_input.setText(text)

    def get_match_positions(self, text: str) -> List[Tuple[int, int]]:
        """Find all match positions in the given text.

        Args:
            text: The text to search in

        Returns:
            List of (start, end) tuples for each match
        """
        pattern = self.compile_pattern()
        if not pattern:
            return []

        positions = []
        for match in pattern.finditer(text):
            positions.append((match.start(), match.end()))
        return positions
