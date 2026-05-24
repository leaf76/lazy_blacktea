"""Application shell layout container — Phase 2 of the redesign.

Provides the redesigned layout described in ``docs/design/screens.md``:

::

    ┌──────────┬───────────────────────┬───────────┐
    │ Sidebar  │  Primary pane         │ Inspector │
    │ (220/56) │  (QStackedWidget)     │ (320/0)   │
    │          │                       │           │
    └──────────┴───────────────────────┴───────────┘
    │ AppStatusBar (chips)                         │
    └──────────────────────────────────────────────┘

The shell is a *pure* layout container: it owns no domain state. Callers
register named panes (``add_pane``), an optional inspector widget per pane,
sidebar metadata, and status-bar chips. Pane switching is keyboard- and
mouse-driven, and ``pane_changed`` is emitted whenever the active pane
changes.

Design constraints
------------------
* No imports from ``ui.main_window`` — the shell must remain independently
  testable, demoable, and reusable.
* Token-driven look: all colors come from :mod:`ui.design_tokens` so theme
  switches reflow without manual restyle calls.
* Sidebar collapses based on shell width to honour the responsiveness rules
  in ``docs/design/screens.md§1``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional

from PyQt6.QtCore import QObject, Qt, pyqtSignal
from PyQt6.QtGui import QCursor, QKeySequence, QShortcut
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSizePolicy,
    QStackedWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from ui.design_tokens import get_palette
from ui.shell.status_bar import AppStatusBar


SIDEBAR_EXPANDED_WIDTH = 220
SIDEBAR_COLLAPSED_WIDTH = 56
INSPECTOR_DEFAULT_WIDTH = 320
RESPONSIVE_COLLAPSE_THRESHOLD = 1100
RESPONSIVE_HIDE_INSPECTOR_THRESHOLD = 900


@dataclass
class _PaneRecord:
    name: str
    label: str
    widget: QWidget
    icon_name: Optional[str] = None
    badge_text_provider: Optional[Callable[[], str]] = None
    inspector_widget: Optional[QWidget] = None


class AppShellSignals(QObject):
    """Standalone signal carrier so callers can subscribe before instantiation.

    The shell itself also emits these signals, but a separate ``QObject`` is
    handy when the shell is constructed lazily.
    """

    pane_changed = pyqtSignal(str)
    sidebar_toggled = pyqtSignal(bool)  # True when expanded
    inspector_toggled = pyqtSignal(bool)  # True when visible


class AppShell(QWidget):
    """Sidebar + main + inspector + status bar layout container."""

    pane_changed = pyqtSignal(str)
    sidebar_toggled = pyqtSignal(bool)
    inspector_toggled = pyqtSignal(bool)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("appShell")

        self._panes: Dict[str, _PaneRecord] = {}
        self._pane_order: List[str] = []
        self._active_pane: Optional[str] = None
        self._sidebar_expanded: bool = True
        self._inspector_visible: bool = False
        self._theme: str = "light"

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # ---- Top region: sidebar + main + inspector --------------------
        self._top_frame = QFrame(self)
        self._top_frame.setObjectName("appShellTop")
        self._top_frame.setFrameShape(QFrame.Shape.NoFrame)

        top_layout = QHBoxLayout(self._top_frame)
        top_layout.setContentsMargins(0, 0, 0, 0)
        top_layout.setSpacing(0)

        self._sidebar = self._build_sidebar()
        self._stack = QStackedWidget(self._top_frame)
        self._stack.setObjectName("appShellStack")
        self._inspector_frame = self._build_inspector_frame()

        top_layout.addWidget(self._sidebar)
        top_layout.addWidget(self._stack, stretch=1)
        top_layout.addWidget(self._inspector_frame)

        outer.addWidget(self._top_frame, stretch=1)

        # ---- Bottom: status bar ----------------------------------------
        self._status_bar = AppStatusBar(self)
        outer.addWidget(self._status_bar)

        # Initial inspector hidden.
        self._inspector_frame.setVisible(False)

        # Sidebar toggle keyboard shortcut.
        self._sidebar_shortcut = QShortcut(QKeySequence("Ctrl+B"), self)
        self._sidebar_shortcut.setContext(Qt.ShortcutContext.WindowShortcut)
        self._sidebar_shortcut.activated.connect(self.toggle_sidebar)

        self._inspector_shortcut = QShortcut(QKeySequence("Ctrl+I"), self)
        self._inspector_shortcut.setContext(Qt.ShortcutContext.WindowShortcut)
        self._inspector_shortcut.activated.connect(self.toggle_inspector)

        self._pane_shortcuts: List[QShortcut] = []
        for index in range(9):
            shortcut = QShortcut(QKeySequence(f"Ctrl+{index + 1}"), self)
            shortcut.setContext(Qt.ShortcutContext.WindowShortcut)
            shortcut.activated.connect(
                lambda checked=False, pane_index=index: self.activate_pane_at(
                    pane_index
                )
            )
            self._pane_shortcuts.append(shortcut)

        self._apply_palette()

    # ------------------------------------------------------------------ API
    def add_pane(
        self,
        name: str,
        label: str,
        widget: QWidget,
        *,
        icon_name: Optional[str] = None,
        inspector_widget: Optional[QWidget] = None,
        badge_text_provider: Optional[Callable[[], str]] = None,
    ) -> None:
        """Register a pane. Replaces an existing pane with the same name."""

        if name in self._panes:
            self.remove_pane(name)

        record = _PaneRecord(
            name=name,
            label=label,
            widget=widget,
            icon_name=icon_name,
            inspector_widget=inspector_widget,
            badge_text_provider=badge_text_provider,
        )
        self._panes[name] = record
        self._pane_order.append(name)

        self._stack.addWidget(widget)
        item = QListWidgetItem(self._format_label(label))
        item.setData(Qt.ItemDataRole.UserRole, name)
        item.setToolTip(label)
        self._sidebar_list.addItem(item)
        self._refresh_badge_for(name)

        if self._active_pane is None:
            self.set_active_pane(name)

    def remove_pane(self, name: str) -> bool:
        record = self._panes.pop(name, None)
        if record is None:
            return False
        self._pane_order = [n for n in self._pane_order if n != name]

        # Remove sidebar list item.
        for row in range(self._sidebar_list.count()):
            item = self._sidebar_list.item(row)
            if item and item.data(Qt.ItemDataRole.UserRole) == name:
                self._sidebar_list.takeItem(row)
                break

        # Remove from stacked widget.
        idx = self._stack.indexOf(record.widget)
        if idx != -1:
            self._stack.removeWidget(record.widget)

        if self._active_pane == name:
            self._active_pane = None
            if self._pane_order:
                self.set_active_pane(self._pane_order[0])
        return True

    def pane_names(self) -> List[str]:
        return list(self._pane_order)

    def active_pane(self) -> Optional[str]:
        return self._active_pane

    def set_active_pane(self, name: str) -> bool:
        record = self._panes.get(name)
        if record is None:
            return False
        if self._active_pane == name:
            return True
        self._active_pane = name
        self._stack.setCurrentWidget(record.widget)
        # Sync sidebar selection without recursion.
        for row in range(self._sidebar_list.count()):
            item = self._sidebar_list.item(row)
            if item and item.data(Qt.ItemDataRole.UserRole) == name:
                self._sidebar_list.blockSignals(True)
                self._sidebar_list.setCurrentRow(row)
                self._sidebar_list.blockSignals(False)
                break
        # Update inspector content for this pane.
        self._set_inspector_widget(record.inspector_widget)
        self.pane_changed.emit(name)
        return True

    def activate_pane_at(self, index: int) -> bool:
        """Activate a pane by sidebar order.

        The method backs the ``Ctrl+1`` ... ``Ctrl+9`` shortcut contract and is
        intentionally public so integration tests and host windows do not need
        to poke at private sidebar widgets.
        """

        if index < 0 or index >= len(self._pane_order):
            return False
        return self.set_active_pane(self._pane_order[index])

    def set_inspector_widget(self, name: str, widget: Optional[QWidget]) -> bool:
        record = self._panes.get(name)
        if record is None:
            return False
        record.inspector_widget = widget
        if self._active_pane == name:
            self._set_inspector_widget(widget)
        return True

    def show_inspector(self) -> None:
        self._inspector_visible = True
        self._inspector_frame.setVisible(True)
        self.inspector_toggled.emit(True)

    def hide_inspector(self) -> None:
        self._inspector_visible = False
        self._inspector_frame.setVisible(False)
        self.inspector_toggled.emit(False)

    def toggle_inspector(self) -> None:
        if self._inspector_visible:
            self.hide_inspector()
        else:
            self.show_inspector()

    def inspector_visible(self) -> bool:
        return self._inspector_visible

    def set_sidebar_collapsed(self, collapsed: bool) -> None:
        self._set_sidebar_expanded(not collapsed)

    def toggle_sidebar(self) -> None:
        self._set_sidebar_expanded(not self._sidebar_expanded)

    def sidebar_expanded(self) -> bool:
        return self._sidebar_expanded

    def status_bar(self) -> AppStatusBar:
        return self._status_bar

    def refresh_badges(self) -> None:
        for name in list(self._pane_order):
            self._refresh_badge_for(name)

    def set_theme(self, theme: str) -> None:
        self._theme = theme if theme in ("light", "dark") else "light"
        self._apply_palette()
        self._status_bar.set_theme(self._theme)

    # --------------------------------------------------------------- events
    def resizeEvent(self, event):  # noqa: N802 (Qt API)
        super().resizeEvent(event)
        width = event.size().width()
        # Auto-collapse sidebar / hide inspector based on width.
        if width < RESPONSIVE_HIDE_INSPECTOR_THRESHOLD and self._inspector_visible:
            self.hide_inspector()
        if width < RESPONSIVE_COLLAPSE_THRESHOLD and self._sidebar_expanded:
            self._set_sidebar_expanded(False, emit=False)
        elif width >= RESPONSIVE_COLLAPSE_THRESHOLD and not self._sidebar_expanded:
            self._set_sidebar_expanded(True, emit=False)

    # --------------------------------------------------------------- helpers
    def _build_sidebar(self) -> QFrame:
        sidebar = QFrame(self)
        sidebar.setObjectName("appShellSidebar")
        sidebar.setFrameShape(QFrame.Shape.NoFrame)
        sidebar.setFixedWidth(SIDEBAR_EXPANDED_WIDTH)

        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(8, 12, 8, 12)
        layout.setSpacing(8)

        # Header: collapse toggle + brand label.
        header = QHBoxLayout()
        header.setSpacing(6)
        self._sidebar_brand = QLabel("Lazy Blacktea")
        self._sidebar_brand.setObjectName("appShellBrand")
        self._sidebar_collapse_btn = QToolButton()
        self._sidebar_collapse_btn.setObjectName("appShellSidebarToggle")
        self._sidebar_collapse_btn.setText("\u2630")  # ☰
        self._sidebar_collapse_btn.setToolTip("Collapse sidebar (Ctrl+B)")
        self._sidebar_collapse_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._sidebar_collapse_btn.setAutoRaise(True)
        self._sidebar_collapse_btn.clicked.connect(self.toggle_sidebar)
        header.addWidget(self._sidebar_collapse_btn)
        header.addWidget(self._sidebar_brand, stretch=1)
        layout.addLayout(header)

        self._sidebar_list = QListWidget(sidebar)
        self._sidebar_list.setObjectName("appShellSidebarList")
        self._sidebar_list.setFrameShape(QFrame.Shape.NoFrame)
        self._sidebar_list.setUniformItemSizes(True)
        self._sidebar_list.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        self._sidebar_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._sidebar_list.setSpacing(2)
        self._sidebar_list.itemSelectionChanged.connect(self._on_sidebar_selection_changed)
        layout.addWidget(self._sidebar_list, stretch=1)

        # Footer: hint or palette shortcut.
        self._sidebar_footer = QLabel("Ctrl+K to search")
        self._sidebar_footer.setObjectName("appShellSidebarFooter")
        self._sidebar_footer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._sidebar_footer)

        return sidebar

    def _build_inspector_frame(self) -> QFrame:
        frame = QFrame(self)
        frame.setObjectName("appShellInspector")
        frame.setFrameShape(QFrame.Shape.NoFrame)
        frame.setFixedWidth(INSPECTOR_DEFAULT_WIDTH)
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        # Placeholder shown when no inspector widget is set.
        self._inspector_placeholder = QLabel("No selection.\nUse the inspector to view details.")
        self._inspector_placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._inspector_placeholder.setObjectName("appShellInspectorPlaceholder")
        self._inspector_placeholder.setWordWrap(True)
        layout.addWidget(self._inspector_placeholder)
        # Future widgets are inserted at position 0 and the placeholder is
        # hidden in ``_set_inspector_widget``.
        self._inspector_layout = layout
        self._inspector_current_widget: Optional[QWidget] = None
        return frame

    def _on_sidebar_selection_changed(self) -> None:
        item = self._sidebar_list.currentItem()
        if item is None:
            return
        name = item.data(Qt.ItemDataRole.UserRole)
        if isinstance(name, str):
            self.set_active_pane(name)

    def _set_inspector_widget(self, widget: Optional[QWidget]) -> None:
        # Detach the current widget (if any).
        if self._inspector_current_widget is not None:
            self._inspector_layout.removeWidget(self._inspector_current_widget)
            self._inspector_current_widget.setParent(None)
            self._inspector_current_widget = None

        if widget is None:
            self._inspector_placeholder.setVisible(True)
            return

        self._inspector_placeholder.setVisible(False)
        self._inspector_layout.insertWidget(0, widget)
        self._inspector_current_widget = widget
        if self._inspector_visible:
            widget.show()

    def _set_sidebar_expanded(self, expanded: bool, *, emit: bool = True) -> None:
        if expanded == self._sidebar_expanded:
            return
        self._sidebar_expanded = expanded
        target_width = SIDEBAR_EXPANDED_WIDTH if expanded else SIDEBAR_COLLAPSED_WIDTH
        self._sidebar.setFixedWidth(target_width)
        self._sidebar_brand.setVisible(expanded)
        self._sidebar_footer.setVisible(expanded)
        for row in range(self._sidebar_list.count()):
            item = self._sidebar_list.item(row)
            if item is None:
                continue
            name = item.data(Qt.ItemDataRole.UserRole)
            record = self._panes.get(name) if isinstance(name, str) else None
            if record is None:
                continue
            item.setText(self._format_label(record.label))
            item.setToolTip(self._format_label(record.label, include_badge=True))
        if emit:
            self.sidebar_toggled.emit(expanded)

    def _refresh_badge_for(self, name: str) -> None:
        record = self._panes.get(name)
        if record is None:
            return
        for row in range(self._sidebar_list.count()):
            item = self._sidebar_list.item(row)
            if item and item.data(Qt.ItemDataRole.UserRole) == name:
                item.setText(self._format_label(record.label))
                item.setToolTip(self._format_label(record.label, include_badge=True))
                break

    def _format_label(self, label: str, *, include_badge: bool = False) -> str:
        badge = ""
        for record in self._panes.values():
            if record.label == label and record.badge_text_provider is not None:
                try:
                    badge = str(record.badge_text_provider() or "").strip()
                except Exception:
                    badge = ""
                break

        if include_badge:
            return f"{label} · {badge}" if badge else label

        if not self._sidebar_expanded:
            # Collapsed: show only the first letter as a glyph.
            return label[:1].upper() if label else ""
        if badge:
            return f"{label} · {badge}"
        return label

    def _apply_palette(self) -> None:
        palette = get_palette(self._theme)
        self.setStyleSheet(
            f"""
            #appShell {{
                background-color: {palette['bg_canvas']};
                color: {palette['fg_primary']};
            }}
            #appShellSidebar {{
                background-color: {palette['bg_surface']};
                border-right: 1px solid {palette['border_subtle']};
            }}
            #appShellInspector {{
                background-color: {palette['bg_surface']};
                border-left: 1px solid {palette['border_subtle']};
            }}
            #appShellStack {{
                background-color: {palette['bg_canvas']};
            }}
            #appShellBrand {{
                color: {palette['fg_primary']};
                font-weight: 600;
                font-size: 13px;
            }}
            #appShellSidebarFooter {{
                color: {palette['fg_muted']};
                font-size: 11px;
            }}
            #appShellInspectorPlaceholder {{
                color: {palette['fg_muted']};
                padding: 24px 16px;
            }}
            QListWidget#appShellSidebarList {{
                background-color: transparent;
                border: none;
                outline: none;
                color: {palette['fg_secondary']};
                font-size: 13px;
            }}
            QListWidget#appShellSidebarList::item {{
                padding: 6px 10px;
                border-radius: 6px;
                margin: 1px 2px;
            }}
            QListWidget#appShellSidebarList::item:hover {{
                background-color: {palette['bg_hover']};
                color: {palette['fg_primary']};
            }}
            QListWidget#appShellSidebarList::item:selected {{
                background-color: {palette['bg_active']};
                color: {palette['fg_primary']};
            }}
            QToolButton#appShellSidebarToggle {{
                color: {palette['fg_secondary']};
                background: transparent;
                border: none;
                padding: 4px 6px;
                font-size: 14px;
            }}
            QToolButton#appShellSidebarToggle:hover {{
                background-color: {palette['bg_hover']};
                border-radius: 4px;
            }}
            """
        )


__all__ = ["AppShell", "AppShellSignals"]
