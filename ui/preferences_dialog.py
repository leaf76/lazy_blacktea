"""Tabbed preferences dialog for application settings."""

from __future__ import annotations

import copy
import os
import re
from dataclasses import dataclass
from typing import Dict, Optional

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSpinBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from config.config_manager import (
    ApkInstallSettings,
    AppConfig,
    DeviceSettings,
    ScreenRecordSettings,
    ScreenshotSettings,
    ScrcpySettings,
    UISettings,
    UpdateSettings,
)
from ui.design_tokens import get_palette


THEME_OPTIONS = (("Light", "light"), ("Dark", "dark"))
UI_SCALE_OPTIONS = (
    ("Default", 1.0),
    ("Large", 1.25),
    ("Extra Large", 1.5),
)
DENSITY_OPTIONS = (
    ("Compact", "compact"),
    ("Cozy", "cozy"),
    ("Comfortable", "comfortable"),
)
VALID_DENSITIES = {value for _label, value in DENSITY_OPTIONS}
VALID_THEMES = {value for _label, value in THEME_OPTIONS}


@dataclass
class PreferencesResult:
    """Collected preferences ready to persist."""

    ui: UISettings
    device: DeviceSettings
    screenshot: ScreenshotSettings
    screen_record: ScreenRecordSettings
    apk_install: ApkInstallSettings
    scrcpy: ScrcpySettings
    update: UpdateSettings


class PreferencesDialog(QDialog):
    """Preferences shell with section navigation and save/cancel semantics."""

    SECTIONS = (
        ("appearance", "Appearance"),
        ("devices", "Devices"),
        ("capture", "Capture"),
        ("apk_install", "APK Install"),
        ("scrcpy", "scrcpy"),
        ("output", "Output"),
        ("updates", "Updates"),
        ("advanced", "Advanced"),
    )

    def __init__(
        self,
        config: AppConfig,
        *,
        initial_section: str = "appearance",
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Preferences")
        self.setModal(True)
        self.setMinimumSize(720, 520)
        self.resize(860, 560)

        self._source_config = copy.deepcopy(config)
        self._result: Optional[PreferencesResult] = None
        self._section_rows: Dict[str, int] = {}

        self._build_ui()
        self._populate_all(self._source_config)
        self._apply_theme_style(getattr(self._source_config.ui, "theme", "dark"))
        self.set_section(initial_section)

    def current_section(self) -> str:
        item = self._sections_list.currentItem()
        if item is None:
            return "appearance"
        section = item.data(Qt.ItemDataRole.UserRole)
        return section if isinstance(section, str) else "appearance"

    def set_section(self, section: str) -> bool:
        row = self._section_rows.get(section)
        if row is None:
            return False
        self._sections_list.setCurrentRow(row)
        self._stack.setCurrentIndex(row)
        return True

    def set_appearance_values(
        self,
        *,
        theme: str,
        ui_scale: float,
        density: str,
    ) -> None:
        self._set_checked(self._theme_buttons, theme if theme in VALID_THEMES else "dark")
        self._set_checked(self._scale_buttons, float(ui_scale))
        self._set_checked(
            self._density_buttons,
            density if density in VALID_DENSITIES else "cozy",
        )

    def restore_current_section_defaults(self) -> None:
        section = self.current_section()
        if section == "appearance":
            self._populate_appearance(UISettings())
        elif section == "devices":
            self._populate_devices(DeviceSettings())
        elif section == "capture":
            self._populate_capture(ScreenshotSettings(), ScreenRecordSettings())
        elif section == "apk_install":
            self._populate_apk_install(ApkInstallSettings())
        elif section == "scrcpy":
            self._populate_scrcpy(ScrcpySettings())
        elif section == "output":
            self._populate_output(UISettings())
        elif section == "updates":
            self._populate_updates(UpdateSettings())
        elif section == "advanced":
            self._populate_advanced(UISettings())

    def get_result(self) -> Optional[PreferencesResult]:
        return self._result

    def accept(self) -> None:  # noqa: D102 (Qt override)
        result = self._collect_result()
        if result is None:
            return
        self._result = result
        super().accept()

    def reject(self) -> None:  # noqa: D102 (Qt override)
        self._result = None
        super().reject()

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(16, 16, 16, 16)
        outer.setSpacing(12)

        title = QLabel("Preferences")
        title.setObjectName("preferencesTitle")
        title.setStyleSheet("font-size: 18px; font-weight: 600;")
        outer.addWidget(title)

        body = QHBoxLayout()
        body.setSpacing(12)
        outer.addLayout(body, stretch=1)

        self._sections_list = QListWidget(self)
        self._sections_list.setObjectName("preferencesSections")
        self._sections_list.setFixedWidth(170)
        self._sections_list.setFrameShape(QFrame.Shape.NoFrame)
        self._sections_list.currentRowChanged.connect(self._stack_row_changed)
        body.addWidget(self._sections_list)

        self._stack = QStackedWidget(self)
        body.addWidget(self._stack, stretch=1)

        for row, (section, label) in enumerate(self.SECTIONS):
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, section)
            self._sections_list.addItem(item)
            self._section_rows[section] = row

        self._stack.addWidget(self._wrap_page(self._build_appearance_page()))
        self._stack.addWidget(self._wrap_page(self._build_devices_page()))
        self._stack.addWidget(self._wrap_page(self._build_capture_page()))
        self._stack.addWidget(self._wrap_page(self._build_apk_install_page()))
        self._stack.addWidget(self._wrap_page(self._build_scrcpy_page()))
        self._stack.addWidget(self._wrap_page(self._build_output_page()))
        self._stack.addWidget(self._wrap_page(self._build_updates_page()))
        self._stack.addWidget(self._wrap_page(self._build_advanced_page()))

        button_row = QHBoxLayout()
        self.restore_button = QPushButton("Restore Defaults")
        self.restore_button.clicked.connect(self.restore_current_section_defaults)
        button_row.addWidget(self.restore_button)
        button_row.addStretch(1)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        button_row.addWidget(buttons)
        outer.addLayout(button_row)

    def _wrap_page(self, page: QWidget) -> QScrollArea:
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidget(page)
        return scroll

    def _page_layout(self, title: str, description: str) -> tuple[QWidget, QVBoxLayout]:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(8, 4, 8, 8)
        layout.setSpacing(14)

        title_label = QLabel(title)
        title_label.setStyleSheet("font-size: 16px; font-weight: 600;")
        layout.addWidget(title_label)

        desc_label = QLabel(description)
        desc_label.setWordWrap(True)
        desc_label.setStyleSheet("color: #6b7280;")
        layout.addWidget(desc_label)
        return page, layout

    def _build_appearance_page(self) -> QWidget:
        page, layout = self._page_layout(
            "Appearance",
            "Adjust the visual density and core presentation of the workspace.",
        )
        self._theme_buttons = self._add_radio_group(layout, "Theme", THEME_OPTIONS)
        self._scale_buttons = self._add_radio_group(layout, "UI Scale", UI_SCALE_OPTIONS)
        self._density_buttons = self._add_radio_group(
            layout,
            "Density",
            DENSITY_OPTIONS,
        )
        layout.addStretch(1)
        return page

    def _build_devices_page(self) -> QWidget:
        page, layout = self._page_layout(
            "Devices",
            "Configure device discovery behavior used by the main workspace.",
        )
        form = self._form_layout()
        self.refresh_interval_spin = QSpinBox()
        self.refresh_interval_spin.setRange(5, 3600)
        self.refresh_interval_spin.setSuffix(" s")
        form.addRow("Refresh interval", self.refresh_interval_spin)

        self.auto_connect_checkbox = QCheckBox("Auto-connect on launch")
        form.addRow("Startup", self.auto_connect_checkbox)

        self.show_offline_checkbox = QCheckBox("Show offline devices")
        form.addRow("Device list", self.show_offline_checkbox)
        layout.addLayout(form)
        layout.addStretch(1)
        return page

    def _build_capture_page(self) -> QWidget:
        page, layout = self._page_layout(
            "Capture",
            "Configure default screenshot and screen recording parameters.",
        )

        screenshot_group = QGroupBox("Screenshot")
        screenshot_form = self._form_layout()
        self.screenshot_extra_args = QLineEdit()
        self.screenshot_extra_args.setPlaceholderText("Additional args to screencap")
        screenshot_form.addRow("Extra args", self.screenshot_extra_args)
        self.screenshot_display_id = QSpinBox()
        self.screenshot_display_id.setRange(-1, 64)
        self.screenshot_display_id.setToolTip("Use -1 for default display")
        screenshot_form.addRow("Display ID", self.screenshot_display_id)
        screenshot_group.setLayout(screenshot_form)
        layout.addWidget(screenshot_group)

        record_group = QGroupBox("Screen Record")
        record_form = self._form_layout()
        self.record_bitrate = QLineEdit()
        self.record_bitrate.setPlaceholderText("Bit rate in bps, e.g. 8000000")
        record_form.addRow("Bit rate", self.record_bitrate)
        self.record_time_limit = QSpinBox()
        self.record_time_limit.setRange(0, 36000)
        self.record_time_limit.setSuffix(" s")
        record_form.addRow("Time limit", self.record_time_limit)
        self.record_size = QLineEdit()
        self.record_size.setPlaceholderText("Width x Height, e.g. 1280x720")
        record_form.addRow("Size", self.record_size)
        self.record_extra_args = QLineEdit()
        self.record_extra_args.setPlaceholderText("Additional screenrecord args")
        record_form.addRow("Extra args", self.record_extra_args)
        self.record_use_hevc = QCheckBox("Use HEVC codec")
        record_form.addRow("Codec", self.record_use_hevc)
        self.record_bugreport = QCheckBox("Include bugreport metadata")
        record_form.addRow("Bugreport", self.record_bugreport)
        self.record_verbose = QCheckBox("Verbose logging")
        record_form.addRow("Verbose", self.record_verbose)
        self.record_display_id = QSpinBox()
        self.record_display_id.setRange(-1, 64)
        record_form.addRow("Display ID", self.record_display_id)
        record_group.setLayout(record_form)
        layout.addWidget(record_group)
        layout.addStretch(1)
        return page

    def _build_apk_install_page(self) -> QWidget:
        page, layout = self._page_layout(
            "APK Install",
            "Choose default flags applied to adb install.",
        )
        form = self._form_layout()
        self.apk_replace_checkbox = QCheckBox("Replace existing app (-r)")
        form.addRow("Replace", self.apk_replace_checkbox)
        self.apk_downgrade_checkbox = QCheckBox("Allow version downgrade (-d)")
        form.addRow("Downgrade", self.apk_downgrade_checkbox)
        self.apk_grant_checkbox = QCheckBox("Grant all runtime permissions (-g)")
        form.addRow("Permissions", self.apk_grant_checkbox)
        self.apk_test_checkbox = QCheckBox("Allow test packages (-t)")
        form.addRow("Test packages", self.apk_test_checkbox)
        self.apk_extra_args = QLineEdit()
        self.apk_extra_args.setPlaceholderText("Additional adb install args")
        form.addRow("Extra args", self.apk_extra_args)
        layout.addLayout(form)
        layout.addStretch(1)
        return page

    def _build_scrcpy_page(self) -> QWidget:
        page, layout = self._page_layout(
            "scrcpy",
            "Customize how scrcpy mirrors devices in future sessions.",
        )
        form = self._form_layout()
        self.scrcpy_stay_awake = QCheckBox("Keep device awake (--stay-awake)")
        form.addRow("Stay awake", self.scrcpy_stay_awake)
        self.scrcpy_turn_screen_off = QCheckBox("Turn device screen off")
        form.addRow("Screen", self.scrcpy_turn_screen_off)
        self.scrcpy_disable_screensaver = QCheckBox("Disable host screensaver")
        form.addRow("Host", self.scrcpy_disable_screensaver)
        self.scrcpy_audio = QCheckBox("Forward audio playback")
        form.addRow("Audio", self.scrcpy_audio)
        self.scrcpy_bitrate = QLineEdit()
        self.scrcpy_bitrate.setPlaceholderText("Example: 12M or 8000000")
        form.addRow("Bit rate", self.scrcpy_bitrate)
        self.scrcpy_max_size = QLineEdit()
        self.scrcpy_max_size.setPlaceholderText("Maximum width in pixels")
        form.addRow("Max size", self.scrcpy_max_size)
        self.scrcpy_extra_args = QLineEdit()
        self.scrcpy_extra_args.setPlaceholderText("Additional scrcpy args")
        form.addRow("Extra args", self.scrcpy_extra_args)
        layout.addLayout(form)
        layout.addStretch(1)
        return page

    def _build_output_page(self) -> QWidget:
        page, layout = self._page_layout(
            "Output",
            "Set the default directory for screenshots, recordings, and downloads.",
        )
        row = QHBoxLayout()
        self.output_path_edit = QLineEdit()
        self.output_path_edit.setPlaceholderText("Select output directory...")
        row.addWidget(self.output_path_edit, stretch=1)
        browse = QPushButton("Browse...")
        browse.clicked.connect(self._browse_output_path)
        row.addWidget(browse)
        layout.addLayout(row)
        layout.addStretch(1)
        return page

    def _build_updates_page(self) -> QWidget:
        page, layout = self._page_layout(
            "Updates",
            "Manage background update checks and download location.",
        )
        form = self._form_layout()
        self.update_auto_check = QCheckBox("Automatically check for updates")
        form.addRow("Auto-check", self.update_auto_check)
        self.update_interval_hours = QSpinBox()
        self.update_interval_hours.setRange(1, 720)
        self.update_interval_hours.setSuffix(" h")
        form.addRow("Interval", self.update_interval_hours)

        download_row = QHBoxLayout()
        self.update_download_dir = QLineEdit()
        self.update_download_dir.setPlaceholderText("Default download location")
        download_row.addWidget(self.update_download_dir, stretch=1)
        browse = QPushButton("Browse...")
        browse.clicked.connect(self._browse_update_download_dir)
        download_row.addWidget(browse)
        form.addRow("Download dir", download_row)

        skip_row = QHBoxLayout()
        self.update_skipped_version = QLabel("No skipped version.")
        skip_row.addWidget(self.update_skipped_version, stretch=1)
        clear = QPushButton("Clear")
        clear.clicked.connect(self._clear_skipped_version)
        skip_row.addWidget(clear)
        form.addRow("Skipped version", skip_row)
        layout.addLayout(form)
        layout.addStretch(1)
        return page

    def _build_advanced_page(self) -> QWidget:
        page, layout = self._page_layout(
            "Advanced",
            "Safe workspace behavior settings that do not perform device operations.",
        )
        form = self._form_layout()
        self.advanced_show_console = QCheckBox("Show console panel on launch")
        form.addRow("Console", self.advanced_show_console)
        self.advanced_single_selection = QCheckBox("Use single-select device list")
        form.addRow("Selection", self.advanced_single_selection)
        layout.addLayout(form)
        layout.addStretch(1)
        return page

    def _add_radio_group(self, layout: QVBoxLayout, title: str, options) -> Dict[object, QRadioButton]:
        group_box = QGroupBox(title)
        row = QHBoxLayout(group_box)
        row.setSpacing(12)
        buttons: Dict[object, QRadioButton] = {}
        button_group = QButtonGroup(group_box)
        button_group.setExclusive(True)
        for label, value in options:
            button = QRadioButton(label)
            button_group.addButton(button)
            row.addWidget(button)
            buttons[value] = button
        row.addStretch(1)
        layout.addWidget(group_box)
        return buttons

    @staticmethod
    def _form_layout() -> QFormLayout:
        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
        form.setFormAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        form.setHorizontalSpacing(16)
        form.setVerticalSpacing(10)
        return form

    def _stack_row_changed(self, row: int) -> None:
        if row >= 0:
            self._stack.setCurrentIndex(row)

    def _populate_all(self, config: AppConfig) -> None:
        self._populate_appearance(config.ui)
        self._populate_devices(config.device)
        self._populate_capture(config.screenshot, config.screen_record)
        self._populate_apk_install(config.apk_install)
        self._populate_scrcpy(config.scrcpy)
        self._populate_output(config.ui)
        self._populate_updates(config.update)
        self._populate_advanced(config.ui)

    def _populate_appearance(self, settings: UISettings) -> None:
        theme = settings.theme if settings.theme in VALID_THEMES else "dark"
        density = settings.density if settings.density in VALID_DENSITIES else "cozy"
        self._set_checked(self._theme_buttons, theme)
        self._set_checked(self._scale_buttons, self._nearest_scale(settings.ui_scale))
        self._set_checked(self._density_buttons, density)

    def _populate_devices(self, settings: DeviceSettings) -> None:
        self.refresh_interval_spin.setValue(max(5, int(settings.refresh_interval or 30)))
        self.auto_connect_checkbox.setChecked(bool(settings.auto_connect))
        self.show_offline_checkbox.setChecked(bool(settings.show_offline_devices))

    def _populate_capture(
        self,
        screenshot: ScreenshotSettings,
        record: ScreenRecordSettings,
    ) -> None:
        self.screenshot_extra_args.setText(screenshot.extra_args)
        self.screenshot_display_id.setValue(int(getattr(screenshot, "display_id", -1)))
        self.record_bitrate.setText(record.bit_rate)
        self.record_time_limit.setValue(max(0, int(record.time_limit_sec or 0)))
        self.record_size.setText(record.size)
        self.record_extra_args.setText(record.extra_args)
        self.record_use_hevc.setChecked(bool(record.use_hevc))
        self.record_bugreport.setChecked(bool(record.bugreport))
        self.record_verbose.setChecked(bool(record.verbose))
        self.record_display_id.setValue(int(getattr(record, "display_id", -1)))

    def _populate_apk_install(self, settings: ApkInstallSettings) -> None:
        self.apk_replace_checkbox.setChecked(settings.replace_existing)
        self.apk_downgrade_checkbox.setChecked(settings.allow_downgrade)
        self.apk_grant_checkbox.setChecked(settings.grant_permissions)
        self.apk_test_checkbox.setChecked(settings.allow_test_packages)
        self.apk_extra_args.setText(settings.extra_args)

    def _populate_scrcpy(self, settings: ScrcpySettings) -> None:
        self.scrcpy_stay_awake.setChecked(settings.stay_awake)
        self.scrcpy_turn_screen_off.setChecked(settings.turn_screen_off)
        self.scrcpy_disable_screensaver.setChecked(settings.disable_screensaver)
        self.scrcpy_audio.setChecked(settings.enable_audio_playback)
        self.scrcpy_bitrate.setText(settings.bitrate)
        self.scrcpy_max_size.setText(str(settings.max_size) if settings.max_size > 0 else "")
        self.scrcpy_extra_args.setText(settings.extra_args)

    def _populate_output(self, settings: UISettings) -> None:
        self.output_path_edit.setText(settings.default_output_path)

    def _populate_updates(self, settings: UpdateSettings) -> None:
        self.update_auto_check.setChecked(bool(settings.auto_check_enabled))
        self.update_interval_hours.setValue(max(1, int(settings.check_interval_hours or 24)))
        self.update_download_dir.setText(settings.download_dir)
        skipped = settings.skipped_version.strip()
        self.update_skipped_version.setText(skipped or "No skipped version.")

    def _populate_advanced(self, settings: UISettings) -> None:
        self.advanced_show_console.setChecked(bool(settings.show_console_panel))
        self.advanced_single_selection.setChecked(bool(settings.single_selection))

    def _collect_result(self) -> Optional[PreferencesResult]:
        scrcpy = self._collect_scrcpy()
        if scrcpy is None:
            return None

        return PreferencesResult(
            ui=self._collect_ui(),
            device=self._collect_device(),
            screenshot=self._collect_screenshot(),
            screen_record=self._collect_screen_record(),
            apk_install=self._collect_apk_install(),
            scrcpy=scrcpy,
            update=self._collect_update(),
        )

    def _collect_ui(self) -> UISettings:
        current = copy.deepcopy(self._source_config.ui)
        current.theme = self._checked_value(self._theme_buttons, "dark")
        current.ui_scale = float(self._checked_value(self._scale_buttons, 1.0))
        current.density = self._checked_value(self._density_buttons, "cozy")
        current.default_output_path = self.output_path_edit.text().strip()
        current.show_console_panel = self.advanced_show_console.isChecked()
        current.single_selection = self.advanced_single_selection.isChecked()
        return current

    def _collect_device(self) -> DeviceSettings:
        current = copy.deepcopy(self._source_config.device)
        current.refresh_interval = int(self.refresh_interval_spin.value())
        current.auto_connect = self.auto_connect_checkbox.isChecked()
        current.show_offline_devices = self.show_offline_checkbox.isChecked()
        return current

    def _collect_screenshot(self) -> ScreenshotSettings:
        return ScreenshotSettings(
            extra_args=self.screenshot_extra_args.text().strip(),
            display_id=int(self.screenshot_display_id.value()),
        )

    def _collect_screen_record(self) -> ScreenRecordSettings:
        return ScreenRecordSettings(
            bit_rate=self.record_bitrate.text().strip(),
            time_limit_sec=int(self.record_time_limit.value()),
            size=self.record_size.text().strip(),
            extra_args=self.record_extra_args.text().strip(),
            use_hevc=self.record_use_hevc.isChecked(),
            bugreport=self.record_bugreport.isChecked(),
            verbose=self.record_verbose.isChecked(),
            display_id=int(self.record_display_id.value()),
        )

    def _collect_apk_install(self) -> ApkInstallSettings:
        return ApkInstallSettings(
            replace_existing=self.apk_replace_checkbox.isChecked(),
            allow_downgrade=self.apk_downgrade_checkbox.isChecked(),
            grant_permissions=self.apk_grant_checkbox.isChecked(),
            allow_test_packages=self.apk_test_checkbox.isChecked(),
            extra_args=self.apk_extra_args.text().strip(),
        )

    def _collect_scrcpy(self) -> Optional[ScrcpySettings]:
        bitrate = self.scrcpy_bitrate.text().strip()
        if bitrate and not re.fullmatch(r"\d+[kKmMgG]?", bitrate):
            self._show_validation_error(
                "Bit rate must be numeric optionally followed by K, M, or G."
            )
            return None

        max_size_text = self.scrcpy_max_size.text().strip()
        max_size = 0
        if max_size_text:
            try:
                max_size = int(max_size_text)
            except ValueError:
                self._show_validation_error("Max size must be a positive integer.")
                return None
            if max_size <= 0:
                self._show_validation_error("Max size must be greater than zero.")
                return None

        return ScrcpySettings(
            stay_awake=self.scrcpy_stay_awake.isChecked(),
            turn_screen_off=self.scrcpy_turn_screen_off.isChecked(),
            disable_screensaver=self.scrcpy_disable_screensaver.isChecked(),
            enable_audio_playback=self.scrcpy_audio.isChecked(),
            bitrate=bitrate,
            max_size=max_size,
            extra_args=self.scrcpy_extra_args.text().strip(),
        )

    def _collect_update(self) -> UpdateSettings:
        return UpdateSettings(
            auto_check_enabled=self.update_auto_check.isChecked(),
            check_interval_hours=int(self.update_interval_hours.value()),
            last_check_at=self._source_config.update.last_check_at,
            skipped_version=self._skipped_version_value(),
            download_dir=self.update_download_dir.text().strip(),
            channel="stable",
        )

    def _browse_output_path(self) -> None:
        selected = self._choose_directory(self.output_path_edit.text().strip())
        if selected:
            self.output_path_edit.setText(selected)

    def _browse_update_download_dir(self) -> None:
        selected = self._choose_directory(self.update_download_dir.text().strip())
        if selected:
            self.update_download_dir.setText(selected)

    def _choose_directory(self, current: str) -> str:
        if not current or not os.path.isdir(current):
            current = os.path.expanduser("~")
        return QFileDialog.getExistingDirectory(self, "Select Directory", current)

    def _clear_skipped_version(self) -> None:
        self.update_skipped_version.setText("No skipped version.")

    def _skipped_version_value(self) -> str:
        value = self.update_skipped_version.text().strip()
        return "" if value == "No skipped version." else value

    @staticmethod
    def _set_checked(buttons: Dict[object, QRadioButton], value: object) -> None:
        button = buttons.get(value)
        if button is None and buttons:
            button = next(iter(buttons.values()))
        if button is not None:
            button.setChecked(True)

    @staticmethod
    def _checked_value(buttons: Dict[object, QRadioButton], default: object) -> object:
        for value, button in buttons.items():
            if button.isChecked():
                return value
        return default

    @staticmethod
    def _nearest_scale(value: float) -> float:
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            return 1.0
        return min((scale for _label, scale in UI_SCALE_OPTIONS), key=lambda scale: abs(scale - numeric))

    def _show_validation_error(self, message: str) -> None:
        QMessageBox.warning(self, "Validation Error", message)

    def _apply_theme_style(self, theme: str) -> None:
        palette = get_palette(theme if theme in VALID_THEMES else "dark")
        self.setStyleSheet(
            f"""
            QDialog {{
                background-color: {palette['bg_canvas']};
                color: {palette['fg_primary']};
            }}
            QLabel {{
                color: {palette['fg_primary']};
            }}
            QListWidget#preferencesSections {{
                background-color: {palette['bg_surface']};
                border: 1px solid {palette['border_subtle']};
                color: {palette['fg_secondary']};
                outline: none;
            }}
            QListWidget#preferencesSections::item {{
                padding: 6px 8px;
            }}
            QListWidget#preferencesSections::item:selected {{
                background-color: {palette['bg_active']};
                color: {palette['fg_primary']};
            }}
            QScrollArea {{
                background: transparent;
                border: none;
            }}
            QWidget {{
                background-color: {palette['bg_canvas']};
                color: {palette['fg_primary']};
            }}
            QGroupBox {{
                border: 1px solid {palette['border_subtle']};
                border-radius: 6px;
                margin-top: 10px;
                padding: 10px;
                color: {palette['fg_primary']};
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 8px;
                padding: 0 4px;
                color: {palette['fg_secondary']};
            }}
            QLineEdit, QSpinBox {{
                background-color: {palette['bg_surface']};
                color: {palette['fg_primary']};
                border: 1px solid {palette['border_subtle']};
                border-radius: 4px;
                padding: 5px 8px;
            }}
            QPushButton {{
                background-color: {palette['bg_surface']};
                color: {palette['fg_primary']};
                border: 1px solid {palette['border_subtle']};
                border-radius: 4px;
                padding: 5px 12px;
            }}
            QPushButton:hover {{
                background-color: {palette['bg_hover']};
            }}
            QRadioButton, QCheckBox {{
                color: {palette['fg_primary']};
            }}
            QRadioButton::indicator, QCheckBox::indicator {{
                width: 14px;
                height: 14px;
                border: 1px solid {palette['fg_muted']};
                background-color: {palette['bg_surface']};
            }}
            QRadioButton::indicator {{
                border-radius: 7px;
            }}
            QCheckBox::indicator {{
                border-radius: 3px;
            }}
            QRadioButton::indicator:checked, QCheckBox::indicator:checked {{
                background-color: {palette['accent_primary']};
                border-color: {palette['accent_primary']};
            }}
            """
        )


__all__ = ["PreferencesDialog", "PreferencesResult"]
