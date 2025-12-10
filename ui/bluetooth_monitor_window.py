"""Qt window presenting consolidated Bluetooth monitoring information."""

from __future__ import annotations

import functools
import json
import re
import time
from typing import Dict, List, Optional

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
    QScrollArea,
    QTextEdit,
    QVBoxLayout,
    QLineEdit,
    QWidget,
)

from utils import adb_models, adb_tools, common

from modules.bluetooth import (
    BluetoothMonitorService,
    BluetoothParser,
    BluetoothState,
    BluetoothStateMachine,
    ParsedSnapshot,
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
        # Use conservative flags to keep native window decorations and resizability
        self.setWindowFlag(Qt.WindowType.WindowContextHelpButtonHint, False)
        self.setWindowFlag(Qt.WindowType.WindowMinMaxButtonsHint, True)
        self.setWindowFlag(Qt.WindowType.WindowMaximizeButtonHint, True)
        self.setWindowFlag(Qt.WindowType.WindowMinimizeButtonHint, True)
        self.setSizeGripEnabled(True)
        self.serial = serial
        self.device = device
        self._parser = BluetoothParser()
        self._state_machine = BluetoothStateMachine()
        self._service: Optional[BluetoothMonitorService] = service
        # Combined into single ADB call to reduce connection overhead
        self._snapshot_command = (
            f'adb -s {self.serial} shell '
            f'"dumpsys bluetooth_manager && echo \'---SEPARATOR---\' && dumpsys bluetooth_adapter"'
        )
        self._events_history: List[str] = []
        self._last_snapshot: Optional[ParsedSnapshot] = None
        self._snapshot_count = 0
        self._event_counts: Dict[str, int] = {}
        self._start_time: Optional[float] = None
        self._raw_metrics: Dict = {}

        self.setWindowTitle(f'Bluetooth Monitor · {device.device_model} ({serial[:8]}…)')
        self.resize(1200, 800)

        self.state_badge = QLabel('UNKNOWN')
        self.state_badge.setObjectName('stateBadge')
        self.state_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.state_badge.setStyleSheet('font-weight: bold; padding: 8px; background: #1c1c1c; color: #f0f0f0;')

        # Structured status card labels
        self.adapter_status_label = QLabel('Adapter: --')
        self.address_label = QLabel('Address: --')
        self.scanning_label = QLabel('Scanning: --')
        self.scanning_clients_label = QLabel('')
        self.scanning_clients_label.setWordWrap(True)
        self.advertising_label = QLabel('Advertising: --')
        self.advertising_details_label = QLabel('')
        self.advertising_details_label.setWordWrap(True)
        self.profiles_label = QLabel('Profiles: --')
        self.profiles_label.setWordWrap(True)
        self.bonded_label = QLabel('Bonded Devices: --')
        self.bonded_devices_label = QLabel('')
        self.bonded_devices_label.setWordWrap(True)

        # Hidden snapshot storage (shown in popup dialog)
        self.snapshot_view = QTextEdit()
        self.snapshot_view.setVisible(False)

        self.metrics_view = QPlainTextEdit()
        self.metrics_view.setReadOnly(True)
        self.metrics_view.setPlaceholderText('Metrics will appear here.')

        self.event_view = QPlainTextEdit()
        self.event_view.setReadOnly(True)
        self.event_view.setPlaceholderText('Bluetooth events will appear here.')

        self._scroll_state = {}
        for name, widget in (
            ('metrics', self.metrics_view),
            ('snapshot', self.snapshot_view),
            ('events', self.event_view),
        ):
            default_auto = name == 'events'
            state = {'widget': widget, 'auto': default_auto, 'updating': False}
            self._scroll_state[name] = state
            widget.verticalScrollBar().valueChanged.connect(
                functools.partial(self._handle_scroll_change, name)
            )

        self._build_layout()
        self._wire_service()

    # ------------------------------------------------------------------
    # Layout helpers
    # ------------------------------------------------------------------
    def _build_layout(self) -> None:
        # === Top header bar with device info and raw data buttons ===
        header_widget = QWidget()
        header_layout = QHBoxLayout(header_widget)
        header_layout.setContentsMargins(0, 0, 0, 0)

        # Device info (left side)
        device_info = QLabel(
            f'{self.device.device_model} · {self.serial[:12]}… · Android {self.device.android_ver}'
        )
        device_info.setStyleSheet('font-size: 12px; color: #aaa;')
        header_layout.addWidget(device_info)

        header_layout.addStretch(1)

        # Raw data buttons (right side)
        self.raw_snapshot_btn = QPushButton('Raw Snapshot')
        self.raw_snapshot_btn.setToolTip('Show raw dumpsys output')
        self.raw_snapshot_btn.clicked.connect(self._show_raw_snapshot)

        self.raw_metrics_btn = QPushButton('Raw Metrics')
        self.raw_metrics_btn.setToolTip('Show raw metrics JSON')
        self.raw_metrics_btn.clicked.connect(self._show_raw_metrics)

        header_layout.addWidget(self.raw_snapshot_btn)
        header_layout.addWidget(self.raw_metrics_btn)

        # === State badge ===
        state_box = QGroupBox('State')
        state_layout = QVBoxLayout(state_box)
        state_layout.addWidget(self.state_badge)

        # === Bluetooth Status card with scroll ===
        bt_status_box = QGroupBox('Bluetooth Status')
        bt_status_box_layout = QVBoxLayout(bt_status_box)
        bt_status_box_layout.setContentsMargins(0, 0, 0, 0)

        bt_scroll = QScrollArea()
        bt_scroll.setWidgetResizable(True)
        bt_scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        bt_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        bt_content = QWidget()
        bt_status_layout = QVBoxLayout(bt_content)
        bt_status_layout.setSpacing(4)
        bt_status_layout.setContentsMargins(10, 10, 10, 10)
        bt_status_layout.addWidget(self.adapter_status_label)
        bt_status_layout.addWidget(self.address_label)
        bt_status_layout.addSpacing(8)
        bt_status_layout.addWidget(self.scanning_label)
        bt_status_layout.addWidget(self.scanning_clients_label)
        bt_status_layout.addSpacing(8)
        bt_status_layout.addWidget(self.advertising_label)
        bt_status_layout.addWidget(self.advertising_details_label)
        bt_status_layout.addSpacing(8)
        bt_status_layout.addWidget(self.profiles_label)
        bt_status_layout.addSpacing(8)
        bt_status_layout.addWidget(self.bonded_label)
        bt_status_layout.addWidget(self.bonded_devices_label)
        bt_status_layout.addStretch(1)

        bt_scroll.setWidget(bt_content)
        bt_status_box_layout.addWidget(bt_scroll)

        # === Metrics box ===
        metrics_box = QGroupBox('Metrics')
        metrics_layout = QVBoxLayout(metrics_box)
        metrics_layout.addWidget(self.metrics_view)

        # === Event stream box ===
        event_box = QGroupBox('Event Stream')
        event_layout = QVBoxLayout(event_box)
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText('Search events (case-insensitive)...')
        self.search_input.textChanged.connect(self._refresh_event_view)
        event_layout.addWidget(self.search_input)
        event_layout.addWidget(self.event_view)

        # === Main layout ===
        # Row 0: Header (device info + raw buttons)
        # Row 1: State badge (spans full width)
        # Row 2: Bluetooth Status + Metrics
        # Row 3: Event Stream
        bt_status_box.setMaximumHeight(220)
        metrics_box.setMaximumHeight(220)

        main_layout = QGridLayout(self)
        main_layout.addWidget(header_widget, 0, 0, 1, 2)
        main_layout.addWidget(state_box, 1, 0, 1, 2)
        main_layout.addWidget(bt_status_box, 2, 0)
        main_layout.addWidget(metrics_box, 2, 1)
        main_layout.addWidget(event_box, 3, 0, 1, 2)
        main_layout.setRowStretch(3, 1)

    def _show_raw_snapshot(self) -> None:
        """Show raw snapshot data in a popup dialog."""
        dialog = QDialog(self)
        dialog.setWindowTitle('Raw Snapshot (dumpsys)')
        dialog.resize(800, 600)

        layout = QVBoxLayout(dialog)

        # Search bar
        search_layout = QHBoxLayout()
        search_input = QLineEdit()
        search_input.setPlaceholderText('Search in snapshot...')
        search_layout.addWidget(search_input)
        layout.addLayout(search_layout)

        # Text view
        text_view = QPlainTextEdit()
        text_view.setReadOnly(True)
        text_view.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        text_view.setPlainText(self.snapshot_view.toPlainText() or 'No snapshot data yet.')
        layout.addWidget(text_view)

        # Simple search highlight
        def do_search():
            text = search_input.text()
            if not text:
                return
            cursor = text_view.document().find(text)
            if not cursor.isNull():
                text_view.setTextCursor(cursor)

        search_input.returnPressed.connect(do_search)

        close_btn = QPushButton('Close')
        close_btn.clicked.connect(dialog.close)
        layout.addWidget(close_btn)

        dialog.show()

    # ------------------------------------------------------------------
    # Service wiring
    # ------------------------------------------------------------------
    def _wire_service(self) -> None:
        if self._service is not None:
            self._connect_service(self._service, autostart=True)
        else:
            # Auto-start monitoring when window opens
            self._update_scrollable_text('metrics', 'Starting monitoring...')
            self._update_scrollable_text('snapshot', '')
            self._refresh_event_view()
            self._start_monitoring()

    def _connect_service(self, service: BluetoothMonitorService, autostart: bool = False) -> None:
        service.snapshot_parsed.connect(self.handle_snapshot)
        service.event_parsed.connect(self.handle_event)
        service.state_updated.connect(self.handle_state_update)
        service.error_occurred.connect(self.handle_error)

        if autostart:
            try:
                service.start()
            except Exception as exc:  # pragma: no cover - defensive guard
                logger.error('Failed to start Bluetooth monitor service: %s', exc)
                self.handle_error(str(exc))
                self._service = None
        else:
            self._update_scrollable_text('metrics', 'Waiting for data...')
            self._update_scrollable_text('snapshot', '')
            self._refresh_event_view()

    # ------------------------------------------------------------------
    # Event handlers (slots)
    # ------------------------------------------------------------------
    def handle_snapshot(self, snapshot: ParsedSnapshot) -> None:
        self._last_snapshot = snapshot
        self._snapshot_count += 1
        if self._start_time is None:
            self._start_time = snapshot.timestamp
        self._update_scrollable_text('snapshot', snapshot.raw_text)
        self._update_status_card(snapshot)
        self._update_metrics_view()

    def _update_status_card(self, snapshot: ParsedSnapshot) -> None:
        """Update the structured Bluetooth status card from parsed snapshot."""
        try:
            self._do_update_status_card(snapshot)
        except Exception as exc:  # pragma: no cover - defensive guard
            logger.error('Error updating status card: %s', exc)

    def _do_update_status_card(self, snapshot: ParsedSnapshot) -> None:
        """Internal method to update status card with parsed data."""
        # Adapter status
        if snapshot.adapter_enabled:
            self.adapter_status_label.setText('Adapter: Enabled')
            self.adapter_status_label.setStyleSheet('color: #4CAF50; font-weight: bold;')
        else:
            self.adapter_status_label.setText('Adapter: Disabled')
            self.adapter_status_label.setStyleSheet('color: #f44336; font-weight: bold;')

        # Bluetooth address
        address = snapshot.address or '--'
        self.address_label.setText(f'Address: {address}')

        # Scanning status
        scanning = snapshot.scanning
        if scanning and scanning.is_scanning:
            self.scanning_label.setText('Scanning: Active')
            self.scanning_label.setStyleSheet('color: #2196F3; font-weight: bold;')
            if scanning.clients:
                clients_text = ', '.join(scanning.clients[:5])
                if len(scanning.clients) > 5:
                    clients_text += f' (+{len(scanning.clients) - 5} more)'
                self.scanning_clients_label.setText(f'  Clients: {clients_text}')
                self.scanning_clients_label.setStyleSheet('color: #666; font-size: 11px;')
            else:
                self.scanning_clients_label.setText('')
        else:
            self.scanning_label.setText('Scanning: Inactive')
            self.scanning_label.setStyleSheet('color: #888;')
            self.scanning_clients_label.setText('')

        # Advertising status
        advertising = snapshot.advertising
        if advertising and advertising.is_advertising:
            self.advertising_label.setText('Advertising: Active')
            self.advertising_label.setStyleSheet('color: #FF9800; font-weight: bold;')
            details = []
            adv_sets = advertising.sets or []
            for adv_set in adv_sets[:3]:
                set_info = []
                if adv_set.set_id is not None:
                    set_info.append(f'Set {adv_set.set_id}')
                if adv_set.interval_ms:
                    set_info.append(f'{adv_set.interval_ms}ms')
                if adv_set.tx_power:
                    set_info.append(f'TX:{adv_set.tx_power}')
                if set_info:
                    details.append(' / '.join(set_info))
            if details:
                self.advertising_details_label.setText('  ' + '; '.join(details))
                self.advertising_details_label.setStyleSheet('color: #666; font-size: 11px;')
            else:
                self.advertising_details_label.setText('')
        else:
            self.advertising_label.setText('Advertising: Inactive')
            self.advertising_label.setStyleSheet('color: #888;')
            self.advertising_details_label.setText('')

        # Profiles - only show connection state profiles (not settings)
        if snapshot.profiles:
            # Only show profiles with connection states, exclude settings like "OFFLOADENABLED"
            connection_states = ['CONNECTED', 'DISCONNECTED', 'CONNECTING', 'DISCONNECTING']
            profile_items = []
            for k, v in snapshot.profiles.items():
                v_upper = str(v).upper()
                # Only include if value looks like a connection state
                if any(state in v_upper for state in connection_states):
                    profile_items.append(f'{k}: {v}')

            if profile_items:
                display_items = profile_items[:4]
                if len(profile_items) > 4:
                    display_items.append(f'(+{len(profile_items) - 4} more)')
                self.profiles_label.setText('Profiles: ' + ', '.join(display_items))
            else:
                self.profiles_label.setText('Profiles: --')
        else:
            self.profiles_label.setText('Profiles: --')

        # Bonded devices - show clean name without UUIDs
        bonded = snapshot.bonded_devices or []
        if bonded:
            count = len(bonded)
            self.bonded_label.setText(f'Bonded Devices: {count}')
            self.bonded_label.setStyleSheet('color: #9C27B0; font-weight: bold;')
            device_items = []
            for dev in bonded[:5]:
                addr = dev.address or 'Unknown'
                # Show short MAC (last 8 chars) for cleaner display
                addr_short = addr[-8:] if len(addr) > 8 else addr
                if dev.name:
                    # Extract clean name - remove UUIDs and service info
                    clean_name = self._clean_device_name(dev.name)
                    device_items.append(f'{clean_name} ({addr_short})')
                else:
                    device_items.append(addr)
            if count > 5:
                device_items.append(f'(+{count - 5} more)')
            self.bonded_devices_label.setText('  ' + '\n  '.join(device_items))
            self.bonded_devices_label.setStyleSheet('color: #666; font-size: 11px;')
        else:
            self.bonded_label.setText('Bonded Devices: 0')
            self.bonded_label.setStyleSheet('color: #888;')
            self.bonded_devices_label.setText('')

    def _clean_device_name(self, name: str) -> str:
        """Extract clean device name, removing UUIDs and service descriptors."""
        if not name:
            return 'Unknown'

        # Extract prefix like [BR/EDR] or [BLE] first
        prefix_match = re.match(r'^(\[[\w/]+\])\s*', name)
        prefix = prefix_match.group(1) + ' ' if prefix_match else ''
        rest = name[prefix_match.end():] if prefix_match else name

        # Remove UUID patterns (xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx)
        cleaned = re.sub(r'[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}', '', rest)

        # Remove common service descriptors (order matters - longer patterns first)
        service_patterns = [
            'Handsfree_AG', 'AudioSource', 'AudioSink', 'Handsfree', 'PANU', 'OBEX',
            'A2DP', 'AVRCP', 'HFP', 'HSP', 'PBAP', 'MAP', 'SPP', 'DUN', 'NAP', 'GN',
        ]
        for pattern in service_patterns:
            cleaned = re.sub(rf'\b{pattern}\b[,\s]*', '', cleaned, flags=re.IGNORECASE)

        # Remove empty parentheses and clean up
        cleaned = re.sub(r'\(\s*[,\s]*\)', '', cleaned)
        cleaned = re.sub(r',+', ',', cleaned)
        cleaned = re.sub(r'\s+', ' ', cleaned)
        cleaned = cleaned.strip(' ,()')

        # If we stripped everything, return a truncated original
        if not cleaned or len(cleaned) < 3:
            # Return first meaningful part before any UUID
            parts = rest.split('(')
            cleaned = parts[0].strip() if parts[0].strip() else rest[:30]

        return prefix + cleaned

    def handle_event(self, event) -> None:
        # Track event counts
        event_type = event.event_type.value
        self._event_counts[event_type] = self._event_counts.get(event_type, 0) + 1

        # Format event with visual indicator based on type
        indicator = self._get_event_indicator(event_type)
        line = f"{indicator} [{event.timestamp:.1f}s] {event_type}: {event.message}"
        self._events_history.append(line)
        if len(self._events_history) > 1000:
            self._events_history = self._events_history[-1000:]
        self._refresh_event_view()
        self._update_metrics_view()

    def _get_event_indicator(self, event_type: str) -> str:
        """Return visual indicator for event type."""
        if 'START' in event_type:
            return '▶'  # Start
        elif 'STOP' in event_type:
            return '■'  # Stop
        elif 'CONNECT' in event_type and 'DISCONNECT' not in event_type:
            return '●'  # Connect
        elif 'DISCONNECT' in event_type:
            return '○'  # Disconnect
        elif 'RESULT' in event_type or 'FOUND' in event_type:
            return '◆'  # Result/Found
        elif 'ERROR' in event_type or 'FAIL' in event_type:
            return '✖'  # Error
        else:
            return '•'  # Default

    def handle_state_update(self, summary: StateSummary) -> None:
        states_text = ' · '.join(sorted(state.value for state in summary.active_states)) or 'UNKNOWN'
        self.state_badge.setText(states_text)

        # Store raw metrics for the "Raw" button
        self._raw_metrics = summary.metrics

        # Color code based on activity level
        state_values = {s.value for s in summary.active_states}
        if 'OFF' in state_values:
            bg_color = '#424242'  # Grey - off
            text_color = '#9e9e9e'
        elif 'CONNECTED' in state_values:
            bg_color = '#1b5e20'  # Dark green - connected
            text_color = '#a5d6a7'
        elif 'ADVERTISING' in state_values or 'SCANNING' in state_values:
            bg_color = '#0d47a1'  # Dark blue - active
            text_color = '#90caf9'
        elif 'IDLE' in state_values:
            bg_color = '#1c1c1c'  # Dark - idle
            text_color = '#f0f0f0'
        else:
            bg_color = '#1c1c1c'
            text_color = '#f0f0f0'
        self.state_badge.setStyleSheet(
            f'font-weight: bold; padding: 8px; background: {bg_color}; color: {text_color};'
        )
        self._update_metrics_view()

    def _update_metrics_view(self) -> None:
        """Update metrics view with comprehensive statistics."""
        lines = []
        m = self._raw_metrics or {}

        # Session stats
        lines.append('─── Session ───')
        lines.append(f'Snapshots: {self._snapshot_count}')
        lines.append(f'Events: {len(self._events_history)}')
        if self._start_time is not None:
            elapsed = time.time() - self._start_time
            mins, secs = divmod(int(elapsed), 60)
            lines.append(f'Elapsed: {mins}m {secs}s')

        # Adapter status from raw metrics
        lines.append('')
        lines.append('─── Adapter ───')
        state = m.get('profiles', {}).get('STATE', 'Unknown') if isinstance(m.get('profiles'), dict) else 'Unknown'
        lines.append(f'State: {state}')
        scanners = m.get('scanners', 0)
        adv_sets = m.get('advertising_sets', 0)
        lines.append(f'Scanners: {scanners}')
        lines.append(f'Adv Sets: {adv_sets}')

        # Extract key info from profiles
        profiles = m.get('profiles', {}) if isinstance(m.get('profiles'), dict) else {}
        if profiles:
            # Connection info
            conn_state = profiles.get('CONNECTION', '')
            if conn_state:
                lines.append(f'Connection: {conn_state.replace("STATE_", "")}')

            # Audio codecs
            codecs = []
            for codec in ['SBC', 'AAC', 'APTX', 'APTX HD', 'LDAC', 'LC3']:
                val = profiles.get(codec)
                if val and val not in ['-1', '0', 'NULL']:
                    codecs.append(codec)
            if codecs:
                lines.append('')
                lines.append('─── Audio Codecs ───')
                lines.append(', '.join(codecs))

            # Device info
            name = profiles.get('NAME')
            if name and name != 'NULL':
                lines.append('')
                lines.append('─── Last Device ───')
                lines.append(f'Name: {name}')
                dev_class = profiles.get('DEVCLASS')
                if dev_class:
                    lines.append(f'Class: {dev_class}')

            # Scan info
            reg_scan = profiles.get('- REGULAR SCAN CLIENTS')
            batch_scan = profiles.get('- BATCH SCAN CLIENTS')
            if reg_scan or batch_scan:
                lines.append('')
                lines.append('─── Scan Clients ───')
                if reg_scan:
                    lines.append(f'Regular: {reg_scan}')
                if batch_scan:
                    lines.append(f'Batch: {batch_scan}')

            # HFP/A2DP status
            hfp_ver = profiles.get('HFPVERSION')
            a2dp_src = profiles.get('A2DP SOURCE')
            if hfp_ver or a2dp_src:
                lines.append('')
                lines.append('─── Profiles ───')
                if a2dp_src:
                    lines.append(f'A2DP: {a2dp_src}')
                if hfp_ver:
                    lines.append(f'HFP: v{hfp_ver}')

        # Event counts
        if self._event_counts:
            lines.append('')
            lines.append('─── Event Counts ───')
            for event_type, count in sorted(self._event_counts.items(), key=lambda x: -x[1]):
                short_type = event_type.replace('BLE_', '')
                lines.append(f'  {short_type}: {count}')

        self._update_scrollable_text('metrics', '\n'.join(lines))

    def handle_error(self, message: str, show_dialog: bool = True) -> None:
        logger.error('Bluetooth monitor error: %s', message)
        # Update metrics view with error message
        self._update_scrollable_text('metrics', f'Error: {message}')
        # Only show dialog for user-initiated actions, not auto-start failures
        if show_dialog and self.isVisible():
            QMessageBox.warning(self, 'Bluetooth Monitor', message)

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------
    def _show_raw_metrics(self) -> None:
        """Show raw metrics data in a popup dialog."""
        dialog = QDialog(self)
        dialog.setWindowTitle('Raw Metrics Data')
        dialog.resize(600, 500)

        layout = QVBoxLayout(dialog)

        text_view = QPlainTextEdit()
        text_view.setReadOnly(True)
        text_view.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)

        # Format as pretty JSON
        try:
            formatted = json.dumps(self._raw_metrics, indent=2, default=str, ensure_ascii=False)
        except Exception:
            formatted = str(self._raw_metrics)

        text_view.setPlainText(formatted)
        layout.addWidget(text_view)

        close_btn = QPushButton('Close')
        close_btn.clicked.connect(dialog.close)
        layout.addWidget(close_btn)

        dialog.show()

    def _take_manual_snapshot(self) -> None:
        if not adb_tools.is_adb_installed():
            self.handle_error('Manual snapshot requires ADB to be available.')
            return

        raw_snapshot = self._run_snapshot_command()
        if not raw_snapshot.strip():
            self.handle_error('Manual snapshot failed: no output returned.')
            return

        snapshot = self._parser.parse_snapshot(self.serial, raw_snapshot)
        self.handle_snapshot(snapshot)
        update = self._state_machine.apply_snapshot(snapshot)
        self.handle_state_update(update.summary)

    def _start_monitoring(self, show_errors: bool = False) -> None:
        """Start monitoring. Set show_errors=False for auto-start to avoid dialog popups."""
        if self._service is not None:
            return
        if not adb_tools.is_adb_installed():
            self.handle_error('ADB not detected. Install ADB to start monitoring.', show_dialog=show_errors)
            return

        service = self._create_service()
        if service is None:
            self.handle_error('Failed to initialise Bluetooth monitor service.', show_dialog=show_errors)
            return

        self._service = service
        self._connect_service(service)
        try:
            service.start()
        except Exception as exc:  # pragma: no cover - defensive guard
            logger.error('Unable to start Bluetooth monitor service: %s', exc)
            self.handle_error(str(exc), show_dialog=show_errors)
            service.deleteLater()
            self._service = None

    def _create_service(self) -> Optional[BluetoothMonitorService]:
        snapshot_runner = self._run_snapshot_command
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
        except Exception as exc:  # pragma: no cover - defensive guard
            logger.error('Error stopping Bluetooth monitor service: %s', exc)
        finally:
            try:
                self._service.deleteLater()
            except Exception:  # pragma: no cover - defensive guard
                pass
            self._service = None
            self._update_scrollable_text('metrics', 'Monitoring stopped.')

    def _refresh_event_view(self, *_args) -> None:
        filter_text = ''
        if hasattr(self, 'search_input') and self.search_input is not None:
            filter_text = self.search_input.text().strip().lower()

        if filter_text:
            filtered = [line for line in self._events_history if filter_text in line.lower()]
        else:
            filtered = self._events_history

        trimmed = list(filtered[-200:])
        self._update_scrollable_text('events', '\n'.join(trimmed))

    def _run_snapshot_command(self) -> str:
        """Execute combined dumpsys command in a single ADB call."""
        try:
            output_lines = common.run_command(self._snapshot_command)
            return '\n'.join(output_lines)
        except Exception as exc:  # pragma: no cover - defensive guard
            logger.error('Failed to execute snapshot command: %s', exc)
            return ''

    # ------------------------------------------------------------------
    # Qt overrides
    # ------------------------------------------------------------------
    def closeEvent(self, event) -> None:  # pragma: no cover - UI callback
        self._stop_monitoring()
        super().closeEvent(event)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _handle_scroll_change(self, name: str, value: int) -> None:
        state = self._scroll_state.get(name)
        if not state or state['updating']:
            return

        widget = state['widget']
        scrollbar = widget.verticalScrollBar()
        state['auto'] = value >= scrollbar.maximum()

    def _update_scrollable_text(self, name: str, text: str) -> None:
        state = self._scroll_state.get(name)
        if not state:
            return

        widget = state['widget']
        scrollbar = widget.verticalScrollBar()
        previous_value = scrollbar.value()

        state['updating'] = True
        try:
            widget.setPlainText(text)
        finally:
            state['updating'] = False

        if state['auto']:
            scrollbar.setValue(scrollbar.maximum())
        else:
            scrollbar.setValue(min(previous_value, scrollbar.maximum()))

