"""Qt window presenting consolidated Bluetooth monitoring information."""

from __future__ import annotations

import functools
from typing import Iterable, List, Optional

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QPlainTextEdit,
    QTextEdit,
    QVBoxLayout,
    QLineEdit,
)

from utils import adb_models, adb_tools, common

from modules.bluetooth import (
    BluetoothMonitorService,
    BluetoothParser,
    BluetoothState,
    BluetoothStateMachine,
    StateSummary,
)


logger = common.get_logger('bluetooth_window')


class BluetoothMonitorWindow(QDialog):
    """Lightweight dashboard for a device's Bluetooth activity."""

    def __init__(
        self,
        serial: str,
        device: adb_models.DeviceInfo,
        service: Optional[BluetoothMonitorService] = None,
        parent: Optional[QDialog] = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowFlag(Qt.WindowType.WindowContextHelpButtonHint, False)
        self.setWindowFlag(Qt.WindowType.WindowMinMaxButtonsHint, True)
        self.setWindowFlag(Qt.WindowType.WindowMaximizeButtonHint, True)
        self.setSizeGripEnabled(True)
        self.serial = serial
        self.device = device
        self._parser = BluetoothParser()
        self._state_machine = BluetoothStateMachine()
        self._service: Optional[BluetoothMonitorService] = service
        self._snapshot_commands = [
            f'adb -s {self.serial} shell dumpsys bluetooth_manager',
            f'adb -s {self.serial} shell dumpsys bluetooth_adapter',
        ]
        self._events_history: List[str] = []

        self.setWindowTitle(f'Bluetooth Monitor · {device.device_model} ({serial[:8]}…)')
        self.resize(1200, 800)

        self.state_badge = QLabel('UNKNOWN')
        self.state_badge.setObjectName('stateBadge')
        self.state_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.state_badge.setStyleSheet('font-weight: bold; padding: 8px; background: #1c1c1c; color: #f0f0f0;')

        self.snapshot_view = QTextEdit()
        self.snapshot_view.setReadOnly(True)
        self.snapshot_view.setPlaceholderText('Snapshot output will appear here.')

        self.metrics_view = QPlainTextEdit()
        self.metrics_view.setReadOnly(True)
        self.metrics_view.setPlaceholderText('Metrics will appear here.')

        self.event_view = QPlainTextEdit()
        self.event_view.setReadOnly(True)
        self.event_view.setPlaceholderText('Bluetooth events will appear here.')

        self._build_layout()
        self._wire_service()

    # ------------------------------------------------------------------
    # Layout helpers
    # ------------------------------------------------------------------
    def _build_layout(self) -> None:
        info_box = QGroupBox('Device')
        info_layout = QVBoxLayout(info_box)
        info_layout.addWidget(QLabel(f'Model: {self.device.device_model}'))
        info_layout.addWidget(QLabel(f'Serial: {self.serial}'))
        info_layout.addWidget(QLabel(f'Android: {self.device.android_ver} (API {self.device.android_api_level})'))

        state_box = QGroupBox('State')
        state_layout = QVBoxLayout(state_box)
        state_layout.addWidget(self.state_badge)

        metrics_box = QGroupBox('Metrics')
        metrics_layout = QVBoxLayout(metrics_box)
        metrics_layout.addWidget(self.metrics_view)

        snapshot_box = QGroupBox('Latest Snapshot')
        snapshot_layout = QVBoxLayout(snapshot_box)
        snapshot_layout.addWidget(self.snapshot_view)

        event_box = QGroupBox('Event Stream')
        event_layout = QVBoxLayout(event_box)
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText('Search events (case-insensitive)...')
        self.search_input.textChanged.connect(self._refresh_event_view)
        event_layout.addWidget(self.search_input)
        event_layout.addWidget(self.event_view)

        self.start_button = QPushButton('Start Monitoring')
        self.start_button.clicked.connect(self._start_monitoring)

        self.stop_button = QPushButton('Stop Monitoring')
        self.stop_button.clicked.connect(self._stop_monitoring)
        self.stop_button.setEnabled(False)

        self.snapshot_button = QPushButton('Manual Snapshot')
        self.snapshot_button.clicked.connect(self._take_manual_snapshot)

        button_row = QHBoxLayout()
        button_row.addWidget(self.start_button)
        button_row.addWidget(self.stop_button)
        button_row.addWidget(self.snapshot_button)
        button_row.addStretch(1)

        main_layout = QGridLayout(self)
        main_layout.addWidget(info_box, 0, 0)
        main_layout.addWidget(state_box, 0, 1)
        main_layout.addLayout(button_row, 1, 0, 1, 2)
        main_layout.addWidget(metrics_box, 2, 0)
        main_layout.addWidget(snapshot_box, 2, 1)
        main_layout.addWidget(event_box, 3, 0, 1, 2)
        main_layout.setRowStretch(3, 1)

    # ------------------------------------------------------------------
    # Service wiring
    # ------------------------------------------------------------------
    def _wire_service(self) -> None:
        if self._service is not None:
            self._connect_service(self._service, autostart=True)
        else:
            self.metrics_view.setPlainText('Monitoring idle. Click "Start Monitoring" to begin.')
            self._refresh_event_view()

    def _connect_service(self, service: BluetoothMonitorService, autostart: bool = False) -> None:
        service.snapshot_parsed.connect(self.handle_snapshot)
        service.event_parsed.connect(self.handle_event)
        service.state_updated.connect(self.handle_state_update)
        service.error_occurred.connect(self.handle_error)

        if autostart:
            try:
                service.start()
                self._set_monitoring_active(True)
            except Exception as exc:  # pragma: no cover - defensive guard
                logger.error('Failed to start Bluetooth monitor service: %s', exc)
                self.handle_error(str(exc))
                self._service = None

    # ------------------------------------------------------------------
    # Event handlers (slots)
    # ------------------------------------------------------------------
    def handle_snapshot(self, snapshot) -> None:
        self.snapshot_view.setPlainText(snapshot.raw_text)

    def handle_event(self, event) -> None:
        line = f"[{event.timestamp:.1f}] {event.event_type.value}: {event.message}"
        self._events_history.append(line)
        if len(self._events_history) > 1000:
            self._events_history = self._events_history[-1000:]
        self._refresh_event_view()

    def handle_state_update(self, summary: StateSummary) -> None:
        states_text = ' · '.join(sorted(state.value for state in summary.active_states)) or 'UNKNOWN'
        self.state_badge.setText(states_text)

        metrics_lines = [f'{key}: {value}' for key, value in summary.metrics.items()]
        self.metrics_view.setPlainText('\n'.join(metrics_lines))

    def handle_error(self, message: str) -> None:
        logger.error('Bluetooth monitor error: %s', message)
        QMessageBox.warning(self, 'Bluetooth Monitor', message)

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------
    def _take_manual_snapshot(self) -> None:
        if not adb_tools.is_adb_installed():
            self.handle_error('Manual snapshot requires ADB to be available.')
            return

        raw_snapshot = self._run_dump_commands(self._snapshot_commands)
        if not raw_snapshot.strip():
            self.handle_error('Manual snapshot failed: no output returned.')
            return

        snapshot = self._parser.parse_snapshot(self.serial, raw_snapshot)
        self.handle_snapshot(snapshot)
        update = self._state_machine.apply_snapshot(snapshot)
        self.handle_state_update(update.summary)

    def _start_monitoring(self) -> None:
        if self._service is not None:
            return
        if not adb_tools.is_adb_installed():
            self.handle_error('ADB not detected. Install ADB to start monitoring.')
            return

        service = self._create_service()
        if service is None:
            self.handle_error('Failed to initialise Bluetooth monitor service.')
            return

        self._service = service
        self._connect_service(service)
        try:
            service.start()
        except Exception as exc:  # pragma: no cover - defensive guard
            logger.error('Unable to start Bluetooth monitor service: %s', exc)
            self.handle_error(str(exc))
            service.deleteLater()
            self._service = None
            return

        self._set_monitoring_active(True)

    def _create_service(self) -> Optional[BluetoothMonitorService]:
        snapshot_runner = functools.partial(self._run_dump_commands, self._snapshot_commands)
        return BluetoothMonitorService(
            serial=self.serial,
            snapshot_runner=snapshot_runner,
            logcat_runner=None,
            parser=self._parser,
            state_machine=self._state_machine,
        )

    def _stop_monitoring(self) -> None:
        if self._service is None:
            return
        try:
            self._service.stop(wait=False)
        finally:
            self._service.deleteLater()
            self._service = None
            self._set_monitoring_active(False)
            self.metrics_view.setPlainText('Monitoring stopped. Click "Start Monitoring" to resume.')

    def _set_monitoring_active(self, active: bool) -> None:
        self.start_button.setEnabled(not active)
        self.stop_button.setEnabled(active)

    def _refresh_event_view(self, *_args) -> None:
        filter_text = ''
        if hasattr(self, 'search_input') and self.search_input is not None:
            filter_text = self.search_input.text().strip().lower()

        if filter_text:
            filtered = [line for line in self._events_history if filter_text in line.lower()]
        else:
            filtered = self._events_history

        trimmed = list(filtered[-200:])
        self.event_view.setPlainText('\n'.join(trimmed))
        self.event_view.verticalScrollBar().setValue(self.event_view.verticalScrollBar().maximum())

    def _run_dump_commands(self, commands: Iterable[str]) -> str:
        output_lines = []
        for command in commands:
            try:
                output_lines.extend(common.run_command(command))
            except Exception as exc:  # pragma: no cover - defensive guard
                logger.error('Failed to execute command %s: %s', command, exc)
        return '\n'.join(output_lines)

    # ------------------------------------------------------------------
    # Qt overrides
    # ------------------------------------------------------------------
    def closeEvent(self, event) -> None:  # pragma: no cover - UI callback
        self._stop_monitoring()
        super().closeEvent(event)
