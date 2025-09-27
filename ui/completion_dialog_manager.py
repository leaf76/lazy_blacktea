"""Dialog helpers for completion notifications."""

from __future__ import annotations

import os
from typing import Callable, Dict, List, Optional, TYPE_CHECKING

from PyQt6.QtWidgets import (
    QLabel,
    QPushButton,
    QVBoxLayout,
    QHBoxLayout,
    QDialog,
)

from utils import common
from ui.style_manager import StyleManager, ButtonStyle, LabelStyle

if TYPE_CHECKING:  # pragma: no cover
    from lazy_blacktea_pyqt import WindowMain


logger = common.get_logger("completion_dialog_manager")

ScreenshotBuilder = Callable[["WindowMain", Dict], None]
FileCompletionBuilder = Callable[["WindowMain", Dict], None]


class CompletionDialogManager:
    """Handle rich completion dialogs for screenshots and file generation."""

    def __init__(
        self,
        window: "WindowMain",
        screenshot_builder: Optional[ScreenshotBuilder] = None,
        file_builder: Optional[FileCompletionBuilder] = None,
    ) -> None:
        self.window = window
        self._screenshot_builder = screenshot_builder or self._build_screenshot_dialog
        self._file_builder = file_builder or self._build_file_dialog

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def show_screenshot_summary(self, output_path: str, device_models: List[str]) -> None:
        device_models = device_models or ['Unknown device']
        payload = {
            'title': '⚡ Screenshot Quick Actions',
            'output_path': output_path,
            'device_models': device_models,
            'device_summary': self._build_device_summary(device_models),
            'suggested_actions': self._build_screenshot_actions(output_path),
        }
        logger.debug('Displaying screenshot summary dialog: %s', payload)
        self._screenshot_builder(self.window, payload)

    def show_file_generation_summary(
        self,
        operation_name: str,
        summary_text: str,
        output_path: str,
        success_metric: int,
        icon: str,
    ) -> None:
        payload = {
            'title': f'{icon} {operation_name} Completed',
            'summary_text': summary_text or f'✅ Successfully completed {operation_name.lower()}',
            'processed': success_metric,
            'output_path': output_path,
        }
        logger.debug('Displaying file generation summary dialog: %s', payload)
        self._file_builder(self.window, payload)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _build_device_summary(self, device_models: List[str]) -> str:
        if len(device_models) <= 2:
            return ', '.join(device_models)
        head = ', '.join(device_models[:2])
        return f'{head}, ...'

    def _build_screenshot_actions(self, output_path: str) -> Dict[str, List[str]]:
        supported_suffixes = ('.png', '.jpg', '.jpeg')
        file_count = 0
        try:
            with os.scandir(output_path) as entries:
                for entry in entries:
                    if entry.is_file() and entry.name.lower().endswith(supported_suffixes):
                        file_count += 1
        except FileNotFoundError:
            logger.debug('Screenshot directory does not exist: %s', output_path)
        except Exception as error:  # pragma: no cover - defensive logging
            logger.error('Failed to enumerate screenshots: %s', error)
        return {
            'file_count': file_count,
        }

    # ------------------------------------------------------------------
    # Qt builders (not exercised in unit tests)
    # ------------------------------------------------------------------
    def _build_screenshot_dialog(self, window: "WindowMain", payload: Dict) -> None:  # pragma: no cover
        dialog = QDialog(window)
        dialog.setWindowTitle(payload['title'])
        dialog.setModal(True)
        dialog.resize(350, 250)

        layout = QVBoxLayout(dialog)

        title_label = QLabel('⚡ Quick Actions for Screenshots')
        StyleManager.apply_label_style(title_label, LabelStyle.HEADER)
        layout.addWidget(title_label)

        info_label = QLabel(f"📱 Screenshots from: {payload['device_summary']}")
        StyleManager.apply_label_style(info_label, LabelStyle.INFO)
        layout.addWidget(info_label)

        button_style = StyleManager.get_action_button_style()

        another_screenshot_btn = QPushButton('📷 Take Another Screenshot')
        another_screenshot_btn.setStyleSheet(button_style)
        another_screenshot_btn.clicked.connect(lambda: (dialog.accept(), window.take_screenshot()))
        layout.addWidget(another_screenshot_btn)

        start_recording_btn = QPushButton('🎥 Start Recording Same Devices')
        start_recording_btn.setStyleSheet(button_style)
        start_recording_btn.clicked.connect(lambda: (dialog.accept(), window.start_screen_record()))
        layout.addWidget(start_recording_btn)

        copy_path_btn = QPushButton('📋 Copy Folder Path')
        copy_path_btn.setStyleSheet(button_style)
        copy_path_btn.clicked.connect(lambda: window.system_actions_manager.copy_to_clipboard(payload['output_path']))
        layout.addWidget(copy_path_btn)

        if payload['suggested_actions']['file_count']:
            file_count_label = QLabel(
                f"📁 Found {payload['suggested_actions']['file_count']} screenshot file(s)"
            )
            StyleManager.apply_label_style(file_count_label, LabelStyle.INFO)
            layout.addWidget(file_count_label)

        close_btn = QPushButton('Close')
        StyleManager.apply_button_style(close_btn, ButtonStyle.NEUTRAL)
        close_btn.clicked.connect(dialog.accept)
        layout.addWidget(close_btn)

        dialog.exec()

    def _build_file_dialog(self, window: "WindowMain", payload: Dict) -> None:  # pragma: no cover
        dialog = QDialog(window)
        dialog.setWindowTitle(payload['title'])
        dialog.setModal(True)
        dialog.resize(450, 200)

        layout = QVBoxLayout(dialog)

        success_label = QLabel(payload['summary_text'])
        StyleManager.apply_label_style(success_label, LabelStyle.SUCCESS)
        layout.addWidget(success_label)

        device_label = QLabel(f"📱 Processed: {payload['processed']} item(s)")
        StyleManager.apply_label_style(device_label, LabelStyle.INFO)
        layout.addWidget(device_label)

        path_text = payload['output_path'] or '(not available)'
        path_label = QLabel(f"📁 Location: {path_text}")
        StyleManager.apply_label_style(path_label, LabelStyle.INFO)
        path_label.setWordWrap(True)
        layout.addWidget(path_label)

        button_layout = QHBoxLayout()

        if payload['output_path']:
            open_folder_btn = QPushButton('🗂️ Open Folder')
            StyleManager.apply_button_style(open_folder_btn, ButtonStyle.SECONDARY)
            open_folder_btn.clicked.connect(lambda: window.system_actions_manager.open_folder(payload['output_path']))
            button_layout.addWidget(open_folder_btn)

        close_btn = QPushButton('Close')
        StyleManager.apply_button_style(close_btn, ButtonStyle.NEUTRAL)
        close_btn.clicked.connect(dialog.accept)
        button_layout.addWidget(close_btn)

        layout.addWidget(QLabel())
        layout.addLayout(button_layout)

        dialog.exec()


__all__ = ["CompletionDialogManager"]
