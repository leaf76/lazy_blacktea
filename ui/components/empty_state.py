"""Rich empty / first-run state for the device list (audit finding #37).

Replaces the bare "No devices found" label with an actionable empty state that
guides first-run users (enable USB debugging, open the ADB guide, refresh) and
offers a "Clear filters" action when a search/filter has hidden every device.
"""

from typing import Callable, Optional

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ui.style_manager import StyleManager


class EmptyStateWidget(QWidget):
    """Two-mode empty state: ``no_devices`` (first run) and ``no_match`` (filtered)."""

    def __init__(
        self,
        *,
        on_refresh: Optional[Callable[[], None]] = None,
        on_clear: Optional[Callable[[], None]] = None,
        on_open_guide: Optional[Callable[[], None]] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._on_refresh = on_refresh
        self._on_clear = on_clear
        self._on_open_guide = on_open_guide
        self.setObjectName("device_list_empty_state")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._build()
        self.show_no_devices()

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(10)
        layout.setContentsMargins(24, 24, 24, 24)

        self._icon = QLabel()
        self._icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._icon.setObjectName("empty_state_icon")

        self._headline = QLabel()
        self._headline.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._headline.setObjectName("empty_state_headline")

        self._body = QLabel()
        self._body.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._body.setWordWrap(True)
        self._body.setObjectName("empty_state_body")

        actions = QHBoxLayout()
        actions.setAlignment(Qt.AlignmentFlag.AlignCenter)
        actions.setSpacing(8)

        self._refresh_btn = QPushButton("Refresh")
        self._refresh_btn.clicked.connect(self._handle_refresh)
        self._clear_btn = QPushButton("Clear filters")
        self._clear_btn.clicked.connect(self._handle_clear)
        self._guide_btn = QPushButton("Open ADB guide")
        self._guide_btn.clicked.connect(self._handle_open_guide)
        for btn in (self._refresh_btn, self._clear_btn, self._guide_btn):
            actions.addWidget(btn)

        layout.addWidget(self._icon)
        layout.addWidget(self._headline)
        layout.addWidget(self._body)
        layout.addLayout(actions)

        self.refresh_theme()

    # -- modes --------------------------------------------------------------
    def show_no_devices(self) -> None:
        """First-run / nothing-connected guidance."""
        self._icon.setText("📱")
        self._headline.setText("No devices connected")
        self._body.setText(
            "Connect an Android device over USB and enable USB debugging,\n"
            "then refresh. You can verify the connection with `adb devices`."
        )
        self._refresh_btn.setVisible(True)
        self._guide_btn.setVisible(True)
        self._clear_btn.setVisible(False)

    def show_no_match(self) -> None:
        """Devices exist but the current search/filter hides them all."""
        self._icon.setText("🔍")
        self._headline.setText("No devices match")
        self._body.setText("No connected device matches the current search or filters.")
        self._refresh_btn.setVisible(False)
        self._guide_btn.setVisible(False)
        self._clear_btn.setVisible(True)

    # Backward-compat for callers that used the old QLabel.setText().
    def setText(self, text: str) -> None:  # noqa: N802 (Qt-style API)
        self._headline.setText(text)

    def refresh_theme(self) -> None:
        """Apply theme-derived colours (re-invoked on light/dark switch, #9)."""
        colors = StyleManager.COLORS
        fg = colors.get("text_primary", "#EAEAEA")
        muted = colors.get("text_hint", "#9DA5B3")
        self._icon.setStyleSheet("font-size: 32px;")
        self._headline.setStyleSheet(
            f"color: {fg}; font-size: 15px; font-weight: 600;"
        )
        self._body.setStyleSheet(f"color: {muted}; font-size: 12px;")

    # -- handlers -----------------------------------------------------------
    def _handle_refresh(self) -> None:
        if self._on_refresh:
            self._on_refresh()

    def _handle_clear(self) -> None:
        if self._on_clear:
            self._on_clear()

    def _handle_open_guide(self) -> None:
        if self._on_open_guide:
            self._on_open_guide()


__all__ = ["EmptyStateWidget"]
