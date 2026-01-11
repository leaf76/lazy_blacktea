"""Three-level filter panel widget for logcat viewer.

Provides a structured UI for managing filters with three distinct levels:
- Level 1: Live filter input (real-time filtering)
- Level 2: Active filters (currently applied)
- Level 3: Saved presets (persistent filter combinations)
"""

from typing import Optional, List
import logging

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QListWidget,
    QListWidgetItem,
    QComboBox,
    QLabel,
    QInputDialog,
    QMessageBox,
    QAbstractItemView,
    QSizePolicy,
)

from ui.logcat.filter_models import ActiveFilterState, FilterPreset
from ui.logcat.preset_manager import PresetManager

logger = logging.getLogger(__name__)


class FilterPanelWidget(QWidget):
    """Three-level filter panel for logcat viewer.

    Signals:
        filters_changed: Emitted when any filter state changes
        live_filter_changed: Emitted when live filter text changes

    Usage:
        panel = FilterPanelWidget(parent=self)
        panel.filters_changed.connect(self._apply_filters)
    """

    filters_changed = pyqtSignal()  # Emitted when active/preset filters change
    live_filter_changed = pyqtSignal(str)  # Emitted on live filter text change

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        preset_manager: Optional[PresetManager] = None,
    ) -> None:
        super().__init__(parent)
        self._preset_manager = preset_manager or PresetManager()
        self._filter_state = ActiveFilterState()
        self._init_ui()
        self._refresh_active_list()
        self._refresh_presets()

    def _init_ui(self) -> None:
        """Build the three-level filter panel layout."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        # Level 1: Live Filter
        layout.addWidget(self._create_level1_widget())

        # Level 2: Active Filters
        layout.addWidget(self._create_level2_widget())

        # Level 3: Saved Presets
        layout.addWidget(self._create_level3_widget())

        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)

    def _create_level1_widget(self) -> QWidget:
        """Create Level 1: Live Filter input row."""
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        label = QLabel("Filter:")
        label.setFixedWidth(50)
        layout.addWidget(label)

        self._live_filter_input = QLineEdit()
        self._live_filter_input.setPlaceholderText(
            "Type to filter logs in real-time..."
        )
        self._live_filter_input.textChanged.connect(self._on_live_filter_changed)
        layout.addWidget(self._live_filter_input)

        self._add_btn = QPushButton("+ Add")
        self._add_btn.setFixedWidth(64)
        self._add_btn.setToolTip("Add current filter to active filters")
        self._add_btn.clicked.connect(self._add_live_to_active)
        layout.addWidget(self._add_btn)

        return container

    def _create_level2_widget(self) -> QWidget:
        """Create Level 2: Active Filters section."""
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        # Header row
        header = QHBoxLayout()
        header.setSpacing(6)

        label = QLabel("Active:")
        label.setStyleSheet("font-weight: bold;")
        header.addWidget(label)
        header.addStretch()

        self._save_preset_btn = QPushButton("Save as Preset")
        self._save_preset_btn.setFixedWidth(110)
        self._save_preset_btn.clicked.connect(self._save_as_preset)
        header.addWidget(self._save_preset_btn)

        layout.addLayout(header)

        # Active filters list
        self._active_list = QListWidget()
        self._active_list.setSelectionMode(
            QAbstractItemView.SelectionMode.ExtendedSelection
        )
        self._active_list.setMaximumHeight(80)
        self._active_list.setMinimumHeight(24)  # Single row when empty
        self._active_list.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self._active_list.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        layout.addWidget(self._active_list)

        # Actions row
        actions = QHBoxLayout()
        actions.setSpacing(6)

        self._remove_btn = QPushButton("Remove")
        self._remove_btn.setFixedWidth(70)
        self._remove_btn.clicked.connect(self._remove_selected)
        actions.addWidget(self._remove_btn)

        self._clear_btn = QPushButton("Clear All")
        self._clear_btn.setFixedWidth(70)
        self._clear_btn.clicked.connect(self._clear_active)
        actions.addWidget(self._clear_btn)

        actions.addStretch()
        layout.addLayout(actions)

        return container

    def _create_level3_widget(self) -> QWidget:
        """Create Level 3: Saved Presets section."""
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        label = QLabel("Presets:")
        label.setFixedWidth(50)
        layout.addWidget(label)

        self._preset_combo = QComboBox()
        self._preset_combo.setMinimumWidth(150)
        layout.addWidget(self._preset_combo, stretch=1)

        self._load_preset_btn = QPushButton("Load")
        self._load_preset_btn.setFixedWidth(60)
        self._load_preset_btn.clicked.connect(self._load_preset)
        layout.addWidget(self._load_preset_btn)

        self._delete_preset_btn = QPushButton("Delete")
        self._delete_preset_btn.setFixedWidth(60)
        self._delete_preset_btn.clicked.connect(self._delete_preset)
        layout.addWidget(self._delete_preset_btn)

        return container

    # -------------------------------------------------------------------------
    # Public API
    # -------------------------------------------------------------------------

    def get_filter_state(self) -> ActiveFilterState:
        """Get current filter state (live + active patterns)."""
        return self._filter_state

    def get_all_patterns(self) -> List[str]:
        """Get combined list of all active filter patterns."""
        return self._filter_state.all_patterns()

    def set_live_filter(self, pattern: str) -> None:
        """Set the live filter text programmatically."""
        self._live_filter_input.setText(pattern)

    def get_live_filter(self) -> str:
        """Get current live filter text."""
        return self._live_filter_input.text().strip()

    def clear_all(self) -> None:
        """Clear all filters including live input."""
        self._live_filter_input.clear()
        self._filter_state.clear_all()
        self._refresh_active_list()
        self.filters_changed.emit()

    def focus_live_filter(self) -> None:
        """Focus the live filter input and select all text."""
        self._live_filter_input.setFocus(Qt.FocusReason.ShortcutFocusReason)
        self._live_filter_input.selectAll()

    def has_active_filters(self) -> bool:
        """Check if any filters are active."""
        return not self._filter_state.is_empty()

    def add_active_pattern(self, pattern: str) -> bool:
        """Add a pattern to active filters programmatically.

        Returns True if added, False if pattern already exists or is empty.
        """
        if not pattern or not pattern.strip():
            return False
        if self._filter_state.add_pattern(pattern.strip()):
            self._refresh_active_list()
            self.filters_changed.emit()
            return True
        return False

    def remove_active_pattern(self, pattern: str) -> bool:
        """Remove a pattern from active filters programmatically.

        Returns True if removed, False if pattern was not found.
        """
        if self._filter_state.remove_pattern(pattern):
            self._refresh_active_list()
            self.filters_changed.emit()
            return True
        return False

    # -------------------------------------------------------------------------
    # Level 1: Live Filter
    # -------------------------------------------------------------------------

    def _on_live_filter_changed(self, text: str) -> None:
        """Handle live filter text changes."""
        pattern = text.strip() if text else None
        self._filter_state.live_pattern = pattern
        self.live_filter_changed.emit(text)

    def _add_live_to_active(self) -> None:
        """Add current live filter to active filters (Level 1 -> Level 2)."""
        pattern = self._live_filter_input.text().strip()
        if not pattern:
            return

        if self._filter_state.add_pattern(pattern):
            self._live_filter_input.clear()
            self._refresh_active_list()
            self.filters_changed.emit()
        else:
            # Pattern already exists
            QMessageBox.information(
                self,
                "Duplicate Filter",
                "This filter pattern is already active.",
            )

    # -------------------------------------------------------------------------
    # Level 2: Active Filters
    # -------------------------------------------------------------------------

    def _refresh_active_list(self) -> None:
        self._active_list.clear()

        if not self._filter_state.active_patterns:
            placeholder = QListWidgetItem("No active filters")
            placeholder.setFlags(Qt.ItemFlag.NoItemFlags)
            self._active_list.addItem(placeholder)
            self._active_list.setFixedHeight(24)
            return

        for pattern in self._filter_state.active_patterns:
            item = QListWidgetItem(pattern)
            self._active_list.addItem(item)

        row_height = 20
        padding = 8
        content_height = len(self._filter_state.active_patterns) * row_height + padding
        self._active_list.setFixedHeight(min(content_height, 80))

    def _remove_selected(self) -> None:
        """Remove selected patterns from active filters."""
        selected = self._active_list.selectedItems()
        if not selected:
            return

        for item in selected:
            pattern = item.text()
            self._filter_state.remove_pattern(pattern)

        self._refresh_active_list()
        self.filters_changed.emit()

    def _clear_active(self) -> None:
        """Clear all active filters (keeps live filter)."""
        if not self._filter_state.active_patterns:
            return

        self._filter_state.clear()
        self._refresh_active_list()
        self.filters_changed.emit()

    def _save_as_preset(self) -> None:
        """Save current active filters as a named preset (Level 2 -> Level 3)."""
        if not self._filter_state.active_patterns:
            QMessageBox.information(
                self,
                "No Filters",
                "Add some filters before saving a preset.",
            )
            return

        name, ok = QInputDialog.getText(
            self,
            "Save Preset",
            "Enter preset name:",
            text="My Filters",
        )

        if not ok or not name.strip():
            return

        name = name.strip()

        # Check for existing preset
        if self._preset_manager.preset_exists(name):
            reply = QMessageBox.question(
                self,
                "Overwrite Preset",
                f'Preset "{name}" already exists. Overwrite?',
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return

        preset = self._filter_state.to_preset(name)
        if self._preset_manager.save_preset(preset):
            self._refresh_presets()
            # Select the newly saved preset
            index = self._preset_combo.findText(name)
            if index >= 0:
                self._preset_combo.setCurrentIndex(index)
            QMessageBox.information(
                self, "Saved", f'Preset "{name}" saved successfully!'
            )
        else:
            QMessageBox.warning(self, "Error", "Failed to save preset.")

    # -------------------------------------------------------------------------
    # Level 3: Saved Presets
    # -------------------------------------------------------------------------

    def _refresh_presets(self) -> None:
        current = self._preset_combo.currentText()
        self._preset_combo.clear()

        presets = self._preset_manager.list_presets()
        has_presets = len(presets) > 0

        self._load_preset_btn.setVisible(has_presets)
        self._delete_preset_btn.setVisible(has_presets)

        if not has_presets:
            self._preset_combo.addItem("No saved presets")
            self._preset_combo.setEnabled(False)
            return

        self._preset_combo.setEnabled(True)
        for preset in presets:
            self._preset_combo.addItem(preset.name)
            idx = self._preset_combo.count() - 1
            self._preset_combo.setItemData(
                idx,
                f"{len(preset.filters)} filter(s)",
                Qt.ItemDataRole.ToolTipRole,
            )

        if current:
            idx = self._preset_combo.findText(current)
            if idx >= 0:
                self._preset_combo.setCurrentIndex(idx)

    def _load_preset(self) -> None:
        """Load selected preset into active filters (Level 3 -> Level 2)."""
        name = self._preset_combo.currentText()
        if not name:
            return

        preset = self._preset_manager.get_preset(name)
        if preset is None:
            QMessageBox.warning(self, "Error", f'Preset "{name}" not found.')
            return

        self._filter_state.load_from_preset(preset)
        self._refresh_active_list()
        self.filters_changed.emit()

    def _delete_preset(self) -> None:
        """Delete selected preset."""
        name = self._preset_combo.currentText()
        if not name:
            return

        reply = QMessageBox.question(
            self,
            "Delete Preset",
            f'Are you sure you want to delete preset "{name}"?',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )

        if reply != QMessageBox.StandardButton.Yes:
            return

        if self._preset_manager.delete_preset(name):
            self._refresh_presets()
        else:
            QMessageBox.warning(self, "Error", f'Failed to delete preset "{name}".')
