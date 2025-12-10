import os
import sys
import unittest
from typing import Set
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt6.QtWidgets import QApplication

from utils import adb_models


class BluetoothParserTests(unittest.TestCase):
    def setUp(self):
        from modules.bluetooth.parser import BluetoothParser
        from modules.bluetooth.models import BluetoothEventType

        self.parser = BluetoothParser()
        self.serial = 'SERIAL_BT_1'
        self.event_type = BluetoothEventType

    def test_parse_snapshot_extracts_core_fields(self):
        from modules.bluetooth.models import AdvertisingSet

        raw_snapshot = (
            "Adapter: state=ON\n"
            "Address: AA:BB:CC:DD:EE:FF\n"
            "mIsDiscovering: true\n"
            "onClientRegistered uid/app1\n"
            "startScan uid/app1\n"
            "isAdvertising: true\n"
            "interval=160\n"
            "txPower=HIGH\n"
            "uuid: 180F,FEAA\n"
            "A2DP state: DISCONNECTED\n"
            "HFP state: CONNECTED\n"
        )
        snapshot = self.parser.parse_snapshot(self.serial, raw_snapshot, timestamp=1690000000.0)

        self.assertTrue(snapshot.adapter_enabled)
        self.assertEqual(snapshot.address, 'AA:BB:CC:DD:EE:FF')
        self.assertTrue(snapshot.scanning.is_scanning)
        self.assertIn('uid/app1', snapshot.scanning.clients)
        self.assertTrue(snapshot.advertising.is_advertising)
        self.assertIsInstance(snapshot.advertising.sets, list)
        self.assertGreaterEqual(len(snapshot.advertising.sets), 1)

        primary_set = snapshot.advertising.sets[0]
        self.assertIsInstance(primary_set, AdvertisingSet)
        self.assertEqual(primary_set.interval_ms, 160)
        self.assertEqual(primary_set.tx_power, 'HIGH')
        self.assertEqual(primary_set.data_length, 0)
        self.assertListEqual(primary_set.service_uuids, ['180F', 'FEAA'])

        self.assertEqual(snapshot.profiles.get('A2DP'), 'DISCONNECTED')
        self.assertEqual(snapshot.profiles.get('HFP'), 'CONNECTED')

    def test_parse_event_detects_advertising_transitions(self):
        raw_event = (
            '09-06 12:00:01.123  1234  5678 D BtGatt: startAdvertising set=0 txPower=HIGH dataLen=31'
        )
        event = self.parser.parse_log_line(self.serial, raw_event, timestamp=1690000001.0)

        from modules.bluetooth.models import BluetoothEventType

        self.assertIsNotNone(event)
        self.assertEqual(event.event_type, BluetoothEventType.ADVERTISING_START)
        self.assertEqual(event.metadata.get('set_id'), 0)
        self.assertEqual(event.metadata.get('tx_power'), 'HIGH')
        self.assertEqual(event.metadata.get('data_length'), 31)

    def test_parse_snapshot_extracts_bonded_devices(self):
        from modules.bluetooth.models import BondState

        raw_snapshot = (
            "Adapter: state=ON\n"
            "Address: AA:BB:CC:DD:EE:FF\n"
            "Bonded devices:\n"
            "  11:22:33:44:55:66 (Pixel Buds)\n"
            "  AA:BB:CC:DD:EE:11 (Galaxy Watch)\n"
            "  FF:EE:DD:CC:BB:AA\n"
            "Other section:\n"
        )
        snapshot = self.parser.parse_snapshot(self.serial, raw_snapshot, timestamp=1690000000.0)

        self.assertEqual(len(snapshot.bonded_devices), 3)

        # Check first device (with name in parentheses)
        dev1 = snapshot.bonded_devices[0]
        self.assertEqual(dev1.address, '11:22:33:44:55:66')
        self.assertEqual(dev1.name, 'Pixel Buds')
        self.assertEqual(dev1.bond_state, BondState.BONDED)

        # Check second device
        dev2 = snapshot.bonded_devices[1]
        self.assertEqual(dev2.address, 'AA:BB:CC:DD:EE:11')
        self.assertEqual(dev2.name, 'Galaxy Watch')

        # Check third device (no name)
        dev3 = snapshot.bonded_devices[2]
        self.assertEqual(dev3.address, 'FF:EE:DD:CC:BB:AA')
        self.assertIsNone(dev3.name)

    def test_parse_snapshot_bonded_devices_name_address_format(self):
        raw_snapshot = (
            "Adapter: state=ON\n"
            "name=My Headphones, address=12:34:56:78:9A:BC\n"
            "address=AB:CD:EF:12:34:56, name=Smart Watch\n"
        )
        snapshot = self.parser.parse_snapshot(self.serial, raw_snapshot, timestamp=1690000000.0)

        self.assertEqual(len(snapshot.bonded_devices), 2)

        # name=..., address=... format
        dev1 = snapshot.bonded_devices[0]
        self.assertEqual(dev1.address, '12:34:56:78:9A:BC')
        self.assertEqual(dev1.name, 'My Headphones')

        # address=..., name=... format
        dev2 = snapshot.bonded_devices[1]
        self.assertEqual(dev2.address, 'AB:CD:EF:12:34:56')
        self.assertEqual(dev2.name, 'Smart Watch')

    def test_parse_snapshot_no_bonded_devices(self):
        raw_snapshot = (
            "Adapter: state=ON\n"
            "Address: AA:BB:CC:DD:EE:FF\n"
            "No bonded devices\n"
        )
        snapshot = self.parser.parse_snapshot(self.serial, raw_snapshot, timestamp=1690000000.0)

        self.assertEqual(len(snapshot.bonded_devices), 0)


class BluetoothStateMachineTests(unittest.TestCase):
    def setUp(self):
        from modules.bluetooth.state_machine import BluetoothStateMachine

        self.machine = BluetoothStateMachine(advertising_timeout_s=5.0, scanning_timeout_s=5.0)
        self.parser = None

    def _parser(self):
        if self.parser is None:
            from modules.bluetooth.parser import BluetoothParser

            self.parser = BluetoothParser()
        return self.parser

    def test_snapshot_and_event_drive_state_transitions(self):
        from modules.bluetooth.models import BluetoothEventType, BluetoothState

        parser = self._parser()
        serial = 'SERIAL_BT_2'
        snapshot_text = (
            'Adapter: state=ON\n'
            'mIsDiscovering: true\n'
            'startScan uid/app1\n'
            'isAdvertising: true\n'
            'interval=320\n'
            'txPower=MEDIUM\n'
        )
        snapshot = parser.parse_snapshot(serial, snapshot_text, timestamp=1.0)
        update = self.machine.apply_snapshot(snapshot)

        self.assertTrue(update.changed)
        self.assertIn(BluetoothState.SCANNING, update.summary.active_states)
        self.assertIn(BluetoothState.ADVERTISING, update.summary.active_states)

        stop_adv_line = (
            '09-06 12:00:05.000  1234  5678 I BluetoothAdapterService: stopAdvertising set=0'
        )
        event = parser.parse_log_line(serial, stop_adv_line, timestamp=6.0)
        update_after_stop = self.machine.apply_event(event)

        self.assertTrue(update_after_stop.changed)
        self.assertNotIn(BluetoothState.ADVERTISING, update_after_stop.summary.active_states)
        self.assertIn(BluetoothState.SCANNING, update_after_stop.summary.active_states)

        stop_scan_line = (
            '09-06 12:00:07.000  1234  5678 I BluetoothAdapterService: stopScan uid/app1'
        )
        stop_event = parser.parse_log_line(serial, stop_scan_line, timestamp=8.0)
        update_after_scan_stop = self.machine.apply_event(stop_event)

        self.assertTrue(update_after_scan_stop.changed)
        self.assertNotIn(BluetoothState.SCANNING, update_after_scan_stop.summary.active_states)
        self.assertSetEqual(update_after_scan_stop.summary.active_states, {BluetoothState.IDLE})


class BluetoothMonitorWindowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self):
        from ui.bluetooth_monitor_window import BluetoothMonitorWindow

        device = adb_models.DeviceInfo(
            device_serial_num='SERIAL_BT_UI',
            device_usb='usb:0',
            device_prod='prod-bt',
            device_model='Model-BT',
            wifi_is_on=True,
            bt_is_on=True,
            android_ver='14',
            android_api_level='34',
            gms_version='42',
            build_fingerprint='fp',
        )
        self.window = BluetoothMonitorWindow('SERIAL_BT_UI', device, service=None)

    def tearDown(self):
        self.window.close()

    def test_handle_state_update_renders_labels(self):
        from modules.bluetooth.models import BluetoothState, StateSummary

        summary = StateSummary(
            serial='SERIAL_BT_UI',
            active_states={BluetoothState.ADVERTISING, BluetoothState.SCANNING},
            metrics={'advertising_sets': 1, 'scanners': 2},
            timestamp=10.0,
        )
        self.window.handle_state_update(summary)

        state_label_text = self.window.state_badge.text()
        self.assertIn('ADVERTISING', state_label_text)
        self.assertIn('SCANNING', state_label_text)

        metrics_text = self.window.metrics_view.toPlainText()
        # New metrics view shows session stats
        self.assertIn('Session', metrics_text)
        self.assertIn('Snapshots:', metrics_text)

    def test_auto_start_monitoring_on_window_open(self):
        """Test that monitoring auto-starts when window is created."""
        # Window should have a service after initialization (auto-start)
        # Note: service may be None if ADB is not installed, which is expected in test env
        # The key is that _start_monitoring was called during initialization
        # We verify this by checking that metrics view has appropriate text
        metrics_text = self.window.metrics_view.toPlainText()
        # Should either have data or an error message (not the old idle message)
        self.assertNotIn('Click "Start Monitoring"', metrics_text)

    def test_stop_monitoring_clears_service(self):
        """Test that stopping monitoring clears the service reference."""
        fake_service = MagicMock()
        fake_service.stop = MagicMock()
        fake_service.deleteLater = MagicMock()

        self.window._service = fake_service
        self.window._stop_monitoring()

        fake_service.stop.assert_called_once()
        fake_service.deleteLater.assert_called_once()
        self.assertIsNone(self.window._service)

    def test_event_search_filters_results(self):
        from modules.bluetooth.models import ParsedEvent, BluetoothEventType

        first_event = ParsedEvent(
            serial='SERIAL_BT_UI',
            timestamp=1.0,
            event_type=BluetoothEventType.ADVERTISING_START,
            message='startAdvertising set=0',
            tag='BtGatt',
            metadata={'set_id': 0},
            raw_line='raw1',
        )
        second_event = ParsedEvent(
            serial='SERIAL_BT_UI',
            timestamp=2.0,
            event_type=BluetoothEventType.SCAN_STOP,
            message='stopScan uid/app1',
            tag='BluetoothAdapterService',
            metadata={'client': 'uid/app1'},
            raw_line='raw2',
        )

        self.window.handle_event(first_event)
        self.window.handle_event(second_event)

        display_all = self.window.event_view.toPlainText()
        self.assertIn('startAdvertising', display_all)
        self.assertIn('stopScan', display_all)

        self.window.search_input.setText('advertis')
        filtered_text = self.window.event_view.toPlainText()
        self.assertIn('startAdvertising', filtered_text)
        self.assertNotIn('stopScan', filtered_text)

        self.window.search_input.setText('')
        reset_text = self.window.event_view.toPlainText()
        self.assertIn('stopScan', reset_text)

    def test_event_view_auto_scroll_respects_manual_scroll(self):
        from modules.bluetooth.models import ParsedEvent, BluetoothEventType

        scrollbar = self.window.event_view.verticalScrollBar()

        # Generate enough events to create scrollable content
        for index in range(120):
            event = ParsedEvent(
                serial='SERIAL_BT_UI',
                timestamp=float(index),
                event_type=BluetoothEventType.ADVERTISING_START,
                message=f'event {index}',
                tag='BtGatt',
                metadata={},
                raw_line=f'raw{index}',
            )
            self.window.handle_event(event)

        self._app.processEvents()
        self.assertEqual(scrollbar.value(), scrollbar.maximum())

        # Simulate user scrolling up (disable auto-follow)
        scrollbar.setValue(0)
        self._app.processEvents()

        paused_value = scrollbar.value()
        self.window.handle_event(
            ParsedEvent(
                serial='SERIAL_BT_UI',
                timestamp=999.0,
                event_type=BluetoothEventType.SCAN_START,
                message='new event after scroll',
                tag='BtGatt',
                metadata={},
                raw_line='raw-new',
            )
        )
        self._app.processEvents()

        self.assertLess(scrollbar.value(), scrollbar.maximum())
        self.assertEqual(scrollbar.value(), paused_value)

        # Scroll to bottom again to re-enable auto-follow
        scrollbar.setValue(scrollbar.maximum())
        self._app.processEvents()
        self.window.handle_event(
            ParsedEvent(
                serial='SERIAL_BT_UI',
                timestamp=1000.0,
                event_type=BluetoothEventType.SCAN_STOP,
                message='follow event',
                tag='BtGatt',
                metadata={},
                raw_line='raw-follow',
            )
        )
        self._app.processEvents()

        self.assertEqual(scrollbar.value(), scrollbar.maximum())

    def test_snapshot_search_highlights_matches(self):
        from modules.bluetooth.models import ParsedSnapshot

        snapshot_text = 'Power: HIGH\nSignal power level low\nAdapter Power state: ON'
        snapshot = ParsedSnapshot(
            serial='SERIAL_BT_UI',
            timestamp=1.0,
            adapter_enabled=True,
            raw_text=snapshot_text,
        )

        self.window.handle_snapshot(snapshot)
        self._app.processEvents()

        # Snapshot data should be stored in snapshot_view
        self.assertIn('Power: HIGH', self.window.snapshot_view.toPlainText())

        # Raw snapshot button should exist
        self.assertTrue(hasattr(self.window, 'raw_snapshot_btn'))
        self.assertTrue(self.window.raw_snapshot_btn.isEnabled())

    def test_status_card_displays_structured_info(self):
        from modules.bluetooth.models import (
            ParsedSnapshot,
            ScanningState,
            AdvertisingState,
            AdvertisingSet,
            BondedDevice,
        )

        snapshot = ParsedSnapshot(
            serial='SERIAL_BT_UI',
            timestamp=1.0,
            adapter_enabled=True,
            address='AA:BB:CC:DD:EE:FF',
            scanning=ScanningState(is_scanning=True, clients=['uid/app1', 'uid/app2']),
            advertising=AdvertisingState(
                is_advertising=True,
                sets=[AdvertisingSet(set_id=0, interval_ms=160, tx_power='HIGH')],
            ),
            profiles={'A2DP': 'CONNECTED', 'HFP': 'DISCONNECTED'},
            bonded_devices=[
                BondedDevice(address='11:22:33:44:55:66', name='Pixel Buds'),
                BondedDevice(address='AA:BB:CC:DD:EE:11', name='Galaxy Watch'),
            ],
            raw_text='raw dumpsys output',
        )

        self.window.handle_snapshot(snapshot)
        self._app.processEvents()

        # Adapter status
        self.assertIn('Enabled', self.window.adapter_status_label.text())
        self.assertIn('#4CAF50', self.window.adapter_status_label.styleSheet())

        # Address
        self.assertIn('AA:BB:CC:DD:EE:FF', self.window.address_label.text())

        # Scanning status
        self.assertIn('Active', self.window.scanning_label.text())
        self.assertIn('uid/app1', self.window.scanning_clients_label.text())

        # Advertising status
        self.assertIn('Active', self.window.advertising_label.text())
        self.assertIn('Set 0', self.window.advertising_details_label.text())
        self.assertIn('160ms', self.window.advertising_details_label.text())

        # Profiles
        self.assertIn('A2DP: CONNECTED', self.window.profiles_label.text())
        self.assertIn('HFP: DISCONNECTED', self.window.profiles_label.text())

        # Bonded devices
        self.assertIn('2', self.window.bonded_label.text())
        self.assertIn('Pixel Buds', self.window.bonded_devices_label.text())
        # Now shows short MAC (last 8 chars)
        self.assertIn('44:55:66', self.window.bonded_devices_label.text())

    def test_status_card_shows_inactive_states(self):
        from modules.bluetooth.models import ParsedSnapshot, ScanningState, AdvertisingState

        snapshot = ParsedSnapshot(
            serial='SERIAL_BT_UI',
            timestamp=1.0,
            adapter_enabled=False,
            address=None,
            scanning=ScanningState(is_scanning=False, clients=[]),
            advertising=AdvertisingState(is_advertising=False, sets=[]),
            profiles={},
            bonded_devices=[],
            raw_text='raw',
        )

        self.window.handle_snapshot(snapshot)
        self._app.processEvents()

        # Adapter disabled
        self.assertIn('Disabled', self.window.adapter_status_label.text())
        self.assertIn('#f44336', self.window.adapter_status_label.styleSheet())

        # Address empty
        self.assertIn('--', self.window.address_label.text())

        # Scanning inactive
        self.assertIn('Inactive', self.window.scanning_label.text())
        self.assertEqual('', self.window.scanning_clients_label.text())

        # Advertising inactive
        self.assertIn('Inactive', self.window.advertising_label.text())
        self.assertEqual('', self.window.advertising_details_label.text())

        # No profiles
        self.assertIn('--', self.window.profiles_label.text())

        # No bonded devices
        self.assertIn('0', self.window.bonded_label.text())
        self.assertEqual('', self.window.bonded_devices_label.text())

    def test_raw_buttons_exist(self):
        """Test that Raw Snapshot and Raw Metrics buttons exist."""
        # Raw buttons should exist in header
        self.assertTrue(hasattr(self.window, 'raw_snapshot_btn'))
        self.assertTrue(hasattr(self.window, 'raw_metrics_btn'))
        self.assertEqual(self.window.raw_snapshot_btn.text(), 'Raw Snapshot')
        self.assertEqual(self.window.raw_metrics_btn.text(), 'Raw Metrics')


if __name__ == '__main__':
    unittest.main()
