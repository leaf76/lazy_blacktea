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
        self.assertIn('advertising_sets: 1', metrics_text)
        self.assertIn('scanners: 2', metrics_text)

    @patch('ui.bluetooth_monitor_window.adb_tools.is_adb_installed', return_value=True)
    def test_start_monitoring_creates_service(self, _mock_adb):
        fake_service = MagicMock()
        fake_service.start = MagicMock()
        fake_service.stop = MagicMock()
        fake_service.deleteLater = MagicMock()

        self.window._create_service = MagicMock(return_value=fake_service)
        self.window._connect_service = MagicMock()

        self.window._start_monitoring()

        self.assertIs(self.window._service, fake_service)
        self.window._connect_service.assert_called_once_with(fake_service)
        fake_service.start.assert_called_once()
        self.assertFalse(self.window.start_button.isEnabled())
        self.assertTrue(self.window.stop_button.isEnabled())

        self.window._stop_monitoring()
        fake_service.stop.assert_called_once()
        fake_service.deleteLater.assert_called_once()
        self.assertTrue(self.window.start_button.isEnabled())
        self.assertFalse(self.window.stop_button.isEnabled())

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


if __name__ == '__main__':
    unittest.main()
