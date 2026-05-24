"""Command palette dialog (``Ctrl+K``).

Phase 2 deliverable. Provides a fast, keyboard-first launcher that surfaces
navigation targets, actions, devices, and recent tasks. Results come from
pluggable :class:`PaletteProvider` instances; built-in providers live in
:mod:`ui.shell.palette_providers`.

Key design points
-----------------
* **Async-friendly:** providers are queried each time the palette opens *or*
  when the query changes. They may return cheap synchronous results today
  and still cooperate with future async fillers.
* **Stable interface:** entries declare a ``title``, ``subtitle``, optional
  ``shortcut`` text, ``section`` label, ``score_hint`` (for tie-breaks), and
  a no-arg ``invoke`` callable.
* **Fuzzy matching:** the palette ranks entries with a tiny scoring function
  (substring + initials + recency-aware ``score_hint``). It does *not* depend
  on third-party libraries.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Callable, List, Optional, Protocol, Sequence

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QKeyEvent
from PyQt6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ui.design_tokens import get_palette


# ---------------------------------------------------------------------------
# Public contracts
# ---------------------------------------------------------------------------


@dataclass
class PaletteEntry:
    """A single palette result.

    Attributes:
        title: Bold primary line.
        subtitle: Optional dim line shown to the right.
        shortcut: Optional shortcut hint (``"⌘1"`` etc.).
        section: Section label used to group results.
        invoke: Callable executed on activation. Should not raise; the
            palette swallows exceptions and emits ``activation_failed``.
        score_hint: Optional bias added to the fuzzy score; useful for
            recency or pinning.
        keywords: Additional matching tokens not shown in the UI.
    """

    title: str
    invoke: Callable[[], None]
    subtitle: str = ""
    shortcut: str = ""
    section: str = "Other"
    score_hint: float = 0.0
    keywords: Sequence[str] = field(default_factory=tuple)


class PaletteProvider(Protocol):
    """Pluggable source of palette entries."""

    def section_label(self) -> str:  # noqa: D401 - protocol stub
        """Return a stable section label for grouping entries."""
        ...

    def entries(self, query: str) -> Sequence[PaletteEntry]:  # noqa: D401
        """Return entries that match ``query``."""
        ...


# ---------------------------------------------------------------------------
# Fuzzy scoring
# ---------------------------------------------------------------------------


_WORD_BOUNDARY = re.compile(r"\b\w")


def _score(query: str, entry: PaletteEntry) -> float:
    """Return a non-negative score; 0 means "no match"."""

    if not query:
        return 1.0 + entry.score_hint
    q = query.lower()
    haystack_parts = [entry.title, entry.subtitle, entry.section, *entry.keywords]
    haystack = " ".join(part.lower() for part in haystack_parts if part)
    if not haystack:
        return 0.0

    score = 0.0
    if q in haystack:
        # Direct substring hit; reward earlier matches.
        idx = haystack.find(q)
        score += max(1.0, 5.0 - idx * 0.05)
    # Word-boundary initials bonus: each query char must hit a fresh word.
    initials = "".join(m.group(0).lower() for m in _WORD_BOUNDARY.finditer(haystack))
    if initials:
        cursor = 0
        for ch in q:
            pos = initials.find(ch, cursor)
            if pos < 0:
                break
            cursor = pos + 1
        else:
            score += 2.0

    # Letter-by-letter ordered match (still allows non-contiguous typing).
    cursor = 0
    matched_chars = 0
    for ch in q:
        pos = haystack.find(ch, cursor)
        if pos < 0:
            break
        matched_chars += 1
        cursor = pos + 1
    if matched_chars == len(q):
        score += 0.5

    if score == 0.0:
        return 0.0
    return score + entry.score_hint


# ---------------------------------------------------------------------------
# Dialog
# ---------------------------------------------------------------------------


class CommandPalette(QDialog):
    """Keyboard-driven palette modal.

    Signals:
        entry_activated(PaletteEntry): emitted after ``invoke`` runs.
        activation_failed(str, Exception): emitted when ``invoke`` raises.
    """

    entry_activated = pyqtSignal(object)
    activation_failed = pyqtSignal(str, object)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("commandPalette")
        self.setWindowTitle("Command Palette")
        self.setModal(True)
        self.setWindowFlags(
            Qt.WindowType.Dialog
            | Qt.WindowType.FramelessWindowHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)

        self._providers: List[PaletteProvider] = []
        self._theme: str = "light"

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        frame = QFrame(self)
        frame.setObjectName("commandPaletteFrame")
        layout.addWidget(frame)

        inner = QVBoxLayout(frame)
        inner.setContentsMargins(0, 0, 0, 0)
        inner.setSpacing(0)

        # Header: search input.
        header = QFrame(frame)
        header.setObjectName("commandPaletteHeader")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(16, 12, 16, 12)
        header_layout.setSpacing(8)

        self._query_edit = QLineEdit(header)
        self._query_edit.setObjectName("commandPaletteQuery")
        self._query_edit.setPlaceholderText(
            "Type a command, action, or device…"
        )
        self._query_edit.setClearButtonEnabled(True)
        self._query_edit.textChanged.connect(self._refresh_entries)
        self._query_edit.installEventFilter(self)
        header_layout.addWidget(self._query_edit, stretch=1)
        self._dismiss_hint = QLabel("Esc", header)
        self._dismiss_hint.setObjectName("commandPaletteHint")
        header_layout.addWidget(self._dismiss_hint)
        inner.addWidget(header)

        # Results list.
        self._results = QListWidget(frame)
        self._results.setObjectName("commandPaletteList")
        self._results.setUniformItemSizes(True)
        self._results.itemActivated.connect(self._activate_item)
        self._results.itemClicked.connect(self._activate_item)
        inner.addWidget(self._results, stretch=1)

        # Footer (could host shortcuts hint later).
        self._footer = QLabel("\u2191 \u2193 navigate · Enter to run", frame)
        self._footer.setObjectName("commandPaletteFooter")
        self._footer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        inner.addWidget(self._footer)

        self.setMinimumSize(560, 360)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        self._apply_palette()

    # ------------------------------------------------------------------ API
    def register_provider(self, provider: PaletteProvider) -> None:
        if provider not in self._providers:
            self._providers.append(provider)

    def unregister_provider(self, provider: PaletteProvider) -> bool:
        try:
            self._providers.remove(provider)
            return True
        except ValueError:
            return False

    def providers(self) -> List[PaletteProvider]:
        return list(self._providers)

    def open_palette(self, *, focus: bool = True) -> None:
        """Show the palette centered on the parent window."""

        self._query_edit.clear()
        self._refresh_entries("")
        self.show()
        self.raise_()
        if focus:
            self._query_edit.setFocus(Qt.FocusReason.ShortcutFocusReason)
        self._reposition()

    def set_theme(self, theme: str) -> None:
        self._theme = theme if theme in ("light", "dark") else "light"
        self._apply_palette()

    def query(self) -> str:
        return self._query_edit.text()

    def visible_entries(self) -> List[PaletteEntry]:
        entries: List[PaletteEntry] = []
        for row in range(self._results.count()):
            item = self._results.item(row)
            if item is None:
                continue
            data = item.data(Qt.ItemDataRole.UserRole)
            if isinstance(data, PaletteEntry):
                entries.append(data)
        return entries

    def activate_top_entry(self) -> bool:
        """Activate the highest-ranked entry. Returns False when empty."""

        for row in range(self._results.count()):
            item = self._results.item(row)
            if item is None:
                continue
            data = item.data(Qt.ItemDataRole.UserRole)
            if isinstance(data, PaletteEntry):
                self._activate_item(item)
                return True
        return False

    # --------------------------------------------------------------- events
    def eventFilter(self, obj, event):  # noqa: N802 (Qt API)
        if obj is self._query_edit and isinstance(event, QKeyEvent):
            if event.type() == QKeyEvent.Type.KeyPress:
                key = event.key()
                if key in (Qt.Key.Key_Down, Qt.Key.Key_Up):
                    self._results.setFocus(Qt.FocusReason.ShortcutFocusReason)
                    if key == Qt.Key.Key_Down:
                        self._move_selection(+1)
                    else:
                        self._move_selection(-1)
                    return True
                if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                    if self.activate_top_entry_with_selection():
                        return True
                if key == Qt.Key.Key_Escape:
                    self.reject()
                    return True
        return super().eventFilter(obj, event)

    def keyPressEvent(self, event):  # noqa: N802 (Qt API)
        if event.key() == Qt.Key.Key_Escape:
            self.reject()
            return
        super().keyPressEvent(event)

    def activate_top_entry_with_selection(self) -> bool:
        item = self._results.currentItem() or (
            self._results.item(0) if self._results.count() else None
        )
        if item is None:
            return False
        self._activate_item(item)
        return True

    # --------------------------------------------------------------- helpers
    def _refresh_entries(self, query: str) -> None:
        scored: List[tuple[float, PaletteEntry]] = []
        for provider in self._providers:
            try:
                provider_entries = provider.entries(query)
            except Exception:
                provider_entries = ()
            for entry in provider_entries:
                score = _score(query, entry)
                if score > 0.0:
                    scored.append((score, entry))

        scored.sort(key=lambda pair: (-pair[0], pair[1].section, pair[1].title.lower()))

        self._results.clear()
        last_section: Optional[str] = None
        for _score_value, entry in scored:
            if entry.section != last_section:
                last_section = entry.section
                section_item = QListWidgetItem(entry.section.upper())
                section_item.setFlags(Qt.ItemFlag.NoItemFlags)
                section_item.setData(Qt.ItemDataRole.UserRole, None)
                section_item.setData(Qt.ItemDataRole.AccessibleDescriptionRole, "section")
                section_item.setData(Qt.ItemDataRole.AccessibleTextRole, entry.section)
                self._results.addItem(section_item)
            display = entry.title
            if entry.subtitle:
                display = f"{entry.title}    \u2014  {entry.subtitle}"
            if entry.shortcut:
                display = f"{display}    {entry.shortcut}"
            item = QListWidgetItem(display)
            item.setData(Qt.ItemDataRole.UserRole, entry)
            item.setToolTip(entry.subtitle or entry.title)
            self._results.addItem(item)

        # Auto-select first activatable row.
        for row in range(self._results.count()):
            candidate = self._results.item(row)
            if (
                candidate is not None
                and candidate.flags() & Qt.ItemFlag.ItemIsSelectable
            ):
                self._results.setCurrentRow(row)
                break

    def _move_selection(self, delta: int) -> None:
        if self._results.count() == 0:
            return
        current = self._results.currentRow()
        next_row = current + delta
        rows = self._results.count()
        # Skip non-selectable section headers.
        for _ in range(rows):
            if 0 <= next_row < rows:
                item = self._results.item(next_row)
                if item is not None and (item.flags() & Qt.ItemFlag.ItemIsSelectable):
                    self._results.setCurrentRow(next_row)
                    return
            next_row += delta
        # No selectable item found in the requested direction.

    def _activate_item(self, item: QListWidgetItem) -> None:
        if item is None:
            return
        entry = item.data(Qt.ItemDataRole.UserRole)
        if not isinstance(entry, PaletteEntry):
            return
        try:
            entry.invoke()
        except Exception as exc:  # pragma: no cover - defensive
            self.activation_failed.emit(entry.title, exc)
            return
        self.entry_activated.emit(entry)
        self.accept()

    def _reposition(self) -> None:
        parent = self.parentWidget()
        if parent is None:
            return
        parent_rect = parent.frameGeometry()
        size = self.size()
        x = parent_rect.x() + max(0, (parent_rect.width() - size.width()) // 2)
        # Snap near the top third of the parent for visibility.
        y = parent_rect.y() + max(0, parent_rect.height() // 6)
        self.move(x, y)

    def _apply_palette(self) -> None:
        palette = get_palette(self._theme)
        self.setStyleSheet(
            f"""
            QDialog#commandPalette {{
                background-color: {palette['bg_scrim']};
            }}
            QFrame#commandPaletteFrame {{
                background-color: {palette['bg_elevated']};
                border: 1px solid {palette['border_default']};
                border-radius: 12px;
            }}
            QFrame#commandPaletteHeader {{
                background-color: transparent;
                border-bottom: 1px solid {palette['border_subtle']};
            }}
            QLineEdit#commandPaletteQuery {{
                background: transparent;
                border: none;
                color: {palette['fg_primary']};
                font-size: 15px;
                padding: 4px 0;
            }}
            QLabel#commandPaletteHint {{
                color: {palette['fg_muted']};
                font-size: 11px;
                border: 1px solid {palette['border_subtle']};
                border-radius: 4px;
                padding: 1px 6px;
            }}
            QListWidget#commandPaletteList {{
                background: transparent;
                border: none;
                outline: none;
                color: {palette['fg_primary']};
                font-size: 13px;
                padding: 6px 0;
            }}
            QListWidget#commandPaletteList::item {{
                padding: 6px 16px;
            }}
            QListWidget#commandPaletteList::item:hover {{
                background-color: {palette['bg_hover']};
            }}
            QListWidget#commandPaletteList::item:selected {{
                background-color: {palette['bg_active']};
                color: {palette['fg_primary']};
            }}
            QLabel#commandPaletteFooter {{
                color: {palette['fg_muted']};
                font-size: 11px;
                padding: 8px 16px;
                border-top: 1px solid {palette['border_subtle']};
            }}
            """
        )


__all__ = ["CommandPalette", "PaletteEntry", "PaletteProvider"]
