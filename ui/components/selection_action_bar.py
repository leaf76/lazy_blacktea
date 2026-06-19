"""Sticky batch-action bar for the Devices pane (audit finding #15).

Surfaces the most common batch actions (Screenshot / Record / Run Shell) plus a
Clear action directly in the Devices pane, so the select→act workflow no longer
forces a trip to a separate Tools pane. Hidden until at least one device is
selected.
"""

from typing import Callable, Optional

from PyQt6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QWidget

from ui.style_manager import StyleManager


class SelectionActionBar(QWidget):
    """Visible only when ≥1 device is selected; runs batch actions on the selection."""

    def __init__(
        self,
        *,
        on_screenshot: Optional[Callable[[], None]] = None,
        on_record: Optional[Callable[[], None]] = None,
        on_shell: Optional[Callable[[], None]] = None,
        on_clear: Optional[Callable[[], None]] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("selection_action_bar")
        self._build(on_screenshot, on_record, on_shell, on_clear)
        self.setVisible(False)

    def _build(self, on_screenshot, on_record, on_shell, on_clear) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(6)

        self._count_label = QLabel("0 selected")
        self._count_label.setObjectName("selection_action_count")
        layout.addWidget(self._count_label)
        layout.addStretch()

        self._screenshot_btn = QPushButton("Screenshot")
        self._record_btn = QPushButton("Record")
        self._shell_btn = QPushButton("Run Shell")
        self._clear_btn = QPushButton("Clear")
        for btn, handler, tip in (
            (self._screenshot_btn, on_screenshot, "Capture a screenshot on the selected device(s)"),
            (self._record_btn, on_record, "Start screen recording on the selected device(s)"),
            (self._shell_btn, on_shell, "Open the Shell Commands workspace"),
            (self._clear_btn, on_clear, "Clear the current selection"),
        ):
            btn.setToolTip(tip)
            if handler is not None:
                btn.clicked.connect(lambda _checked=False, h=handler: h())
            layout.addWidget(btn)

        self.refresh_theme()

    def set_selection_count(self, count: int) -> None:
        """Update the label and show the bar only when something is selected."""
        self._count_label.setText(f"{count} selected")
        self.setVisible(count > 0)

    def refresh_theme(self) -> None:
        """Theme-aware styling for the count label (re-applied on theme switch, #9)."""
        colors = StyleManager.COLORS
        self._count_label.setStyleSheet(
            f"color: {colors.get('text_primary', '#EAEAEA')};"
            " font-weight: 600; font-size: 12px;"
        )


__all__ = ["SelectionActionBar"]
