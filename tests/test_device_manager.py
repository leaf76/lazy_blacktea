#!/usr/bin/env python3
"""
Comprehensive test suite for the refactored device_manager module.
Tests all new classes and functionality including DeviceCache, StatusMessages,
DeviceRefreshThread, and DeviceManager.
"""

import sys
import os
import unittest
import time
import threading
from unittest.mock import Mock, patch, MagicMock, call

# Add the project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ['HOME'] = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.test_home')

# Import Qt modules for testing
from PyQt6.QtCore import QCoreApplication, QThread, pyqtSignal, QObject
from PyQt6.QtWidgets import QApplication, QWidget

from utils import adb_models
from ui.device_manager import (
    DeviceManagerConfig,
    DeviceCache,
    StatusMessages,
    DeviceRefreshThread,
    DeviceManager,
    get_devices_cached
)


class TestDeviceManagerConfig(unittest.TestCase):
    """Test DeviceManagerConfig constants."""

    def test_config_constants_exist(self):
        """Test that all configuration constants exist."""
        self.assertIsInstance(DeviceManagerConfig.DEFAULT_CACHE_TTL, float)
        self.assertIsInstance(DeviceManagerConfig.DEFAULT_REFRESH_INTERVAL, int)
        self.assertIsInstance(DeviceManagerConfig.SHUTDOWN_TIMEOUT, int)
        self.assertIsInstance(DeviceManagerConfig.ERROR_RETRY_DELAY, int)
        self.assertIsInstance(DeviceManagerConfig.PROGRESSIVE_DELAY, int)
        self.assertIsInstance(DeviceManagerConfig.FULL_UPDATE_INTERVAL, int)

    def test_config_values_reasonable(self):
        """Test that configuration values are reasonable."""
        self.assertGreater(DeviceManagerConfig.DEFAULT_CACHE_TTL, 0)
        self.assertGreater(DeviceManagerConfig.DEFAULT_REFRESH_INTERVAL, 0)
        self.assertGreater(DeviceManagerConfig.SHUTDOWN_TIMEOUT, 0)
        self.assertGreater(DeviceManagerConfig.ERROR_RETRY_DELAY, 0)
        self.assertGreater(DeviceManagerConfig.PROGRESSIVE_DELAY, 0)
        self.assertGreater(DeviceManagerConfig.FULL_UPDATE_INTERVAL, 0)


class TestStatusMessages(unittest.TestCase):
    """Test StatusMessages constants."""

    def test_status_messages_exist(self):
        """Test that all status messages exist."""
        self.assertIsInstance(StatusMessages.SCANNING, str)
        self.assertIsInstance(StatusMessages.NO_DEVICES, str)
        self.assertIsInstance(StatusMessages.DEVICES_CONNECTED, str)
        self.assertIsInstance(StatusMessages.DEVICES_FOUND, str)
        self.assertIsInstance(StatusMessages.DEVICE_FOUND, str)
        self.assertIsInstance(StatusMessages.SCAN_ERROR, str)

    def test_status_messages_formatting(self):
        """Test that status messages can be formatted correctly."""
        # Test DEVICES_CONNECTED formatting
        message = StatusMessages.DEVICES_CONNECTED.format(count=1, s='')
        self.assertEqual(message, "📱 1 device connected")

        message = StatusMessages.DEVICES_CONNECTED.format(count=2, s='s')
        self.assertEqual(message, "📱 2 devices connected")

        # Test DEVICES_FOUND formatting
        message = StatusMessages.DEVICES_FOUND.format(count=1, s='')
        self.assertEqual(message, "✅ 1 device connected")

        # Test DEVICE_FOUND formatting
        message = StatusMessages.DEVICE_FOUND.format(serial="TEST123")
        self.assertEqual(message, "📱 Found device: TEST123")

        # Test SCAN_ERROR formatting
        message = StatusMessages.SCAN_ERROR.format(error="Test error")
        self.assertEqual(message, "❌ Device scan error: Test error")


class TestDeviceCache(unittest.TestCase):
    """Test DeviceCache functionality."""

    def setUp(self):
        """Set up test environment."""
        self.cache = DeviceCache(cache_ttl=0.1)  # Short TTL for testing

        # Mock device for testing
        self.mock_device = Mock(spec=adb_models.DeviceInfo)
        self.mock_device.device_serial_num = "TEST123"
        self.mock_device.device_model = "TestModel"

    @patch('ui.device_manager.adb_tools.get_devices_list')
    def test_cache_initial_load(self, mock_get_devices):
        """Test initial cache loading."""
        mock_get_devices.return_value = [self.mock_device]

        devices = self.cache.get_devices()

        self.assertEqual(len(devices), 1)
        self.assertEqual(devices[0], self.mock_device)
        mock_get_devices.assert_called_once()

    @patch('ui.device_manager.adb_tools.get_devices_list')
    def test_cache_ttl_behavior(self, mock_get_devices):
        """Test cache TTL behavior."""
        mock_get_devices.return_value = [self.mock_device]

        # First call should hit the backend
        devices1 = self.cache.get_devices()
        self.assertEqual(len(devices1), 1)
        self.assertEqual(mock_get_devices.call_count, 1)

        # Second call within TTL should use cache
        devices2 = self.cache.get_devices()
        self.assertEqual(len(devices2), 1)
        self.assertEqual(mock_get_devices.call_count, 1)  # No additional call

        # Wait for cache to expire
        time.sleep(0.2)

        # Third call should hit backend again
        devices3 = self.cache.get_devices()
        self.assertEqual(len(devices3), 1)
        self.assertEqual(mock_get_devices.call_count, 2)  # Additional call

    @patch('ui.device_manager.adb_tools.get_devices_list')
    def test_cache_force_refresh(self, mock_get_devices):
        """Test force refresh functionality."""
        mock_get_devices.return_value = [self.mock_device]

        # Load cache
        devices1 = self.cache.get_devices()
        self.assertEqual(mock_get_devices.call_count, 1)

        # Force refresh
        self.cache.force_refresh()
        devices2 = self.cache.get_devices()
        self.assertEqual(mock_get_devices.call_count, 2)

    @patch('ui.device_manager.adb_tools.get_devices_list')
    def test_cache_error_handling(self, mock_get_devices):
        """Test cache error handling."""
        # First load some devices
        mock_get_devices.return_value = [self.mock_device]
        devices1 = self.cache.get_devices()
        self.assertEqual(len(devices1), 1)

        # Simulate error on refresh
        mock_get_devices.side_effect = Exception("Test error")

        # Wait for cache to expire
        time.sleep(0.2)

        # Should return cached devices on error
        devices2 = self.cache.get_devices()
        self.assertEqual(len(devices2), 1)
        self.assertEqual(devices2[0], self.mock_device)

    def test_calculate_hash(self):
        """Test hash calculation."""
        devices = [self.mock_device]
        hash1 = self.cache._calculate_hash(devices)
        hash2 = self.cache._calculate_hash(devices)

        # Same devices should produce same hash
        self.assertEqual(hash1, hash2)

        # Different devices should produce different hash
        mock_device2 = Mock(spec=adb_models.DeviceInfo)
        mock_device2.device_serial_num = "TEST456"
        devices2 = [self.mock_device, mock_device2]
        hash3 = self.cache._calculate_hash(devices2)

        self.assertNotEqual(hash1, hash3)


class MockQApplication:
    """Mock QApplication for testing without full Qt setup."""

    def __init__(self):
        pass

    def processEvents(self):
        pass


class TestDeviceRefreshThread(unittest.TestCase):
    """Test DeviceRefreshThread functionality."""

    def setUp(self):
        """Set up test environment."""
        # Create a minimal Qt application for signal testing
        if not QCoreApplication.instance():
            self.app = QCoreApplication([])
        else:
            self.app = QCoreApplication.instance()

        # Create a real QObject for the parent since QThread requires it
        self.parent_widget = QObject()
        self.thread = DeviceRefreshThread(None, refresh_interval=1)  # Use None as parent for testing

        # Mock device
        self.mock_device = Mock(spec=adb_models.DeviceInfo)
        self.mock_device.device_serial_num = "TEST123"
        self.mock_device.device_model = "TestModel"

    def tearDown(self):
        """Clean up after tests."""
        if hasattr(self, 'thread') and self.thread.isRunning():
            self.thread.stop()
            self.thread.wait(1000)

    def test_thread_initialization(self):
        """Test thread initialization."""
        self.assertEqual(self.thread.refresh_interval, 1)
        self.assertTrue(self.thread.running)
        self.assertEqual(len(self.thread.known_devices), 0)

    def test_should_stop(self):
        """Test stop condition checking."""
        self.assertFalse(self.thread._should_stop())

        self.thread.stop()
        self.assertTrue(self.thread._should_stop())

    @patch('ui.device_manager.get_devices_cached')
    def test_process_new_devices(self, mock_get_devices):
        """Test new device processing."""
        mock_get_devices.return_value = [self.mock_device]
        devices = [self.mock_device]
        current_serials = {"TEST123"}

        # Track emitted signals
        device_found_calls = []
        status_updated_calls = []

        def device_found_handler(serial, device_info):
            device_found_calls.append((serial, device_info))

        def status_updated_handler(status):
            status_updated_calls.append(status)

        self.thread.device_found.connect(device_found_handler)
        self.thread.status_updated.connect(status_updated_handler)

        # Process new devices
        new_devices = self.thread._process_new_devices(devices, current_serials)

        # Check results
        self.assertEqual(new_devices, {"TEST123"})
        self.assertEqual(self.thread.known_devices, {"TEST123"})
        self.assertEqual(len(device_found_calls), 1)
        self.assertEqual(device_found_calls[0], ("TEST123", self.mock_device))

    def test_process_lost_devices(self):
        """Test lost device processing."""
        # Setup known devices
        self.thread.known_devices = {"TEST123", "TEST456"}
        current_serials = {"TEST123"}  # TEST456 is lost

        # Track emitted signals
        device_lost_calls = []

        def device_lost_handler(serial):
            device_lost_calls.append(serial)

        self.thread.device_lost.connect(device_lost_handler)

        # Process lost devices
        lost_devices = self.thread._process_lost_devices(current_serials)

        # Check results
        self.assertEqual(lost_devices, {"TEST456"})
        self.assertEqual(self.thread.known_devices, {"TEST123"})
        self.assertEqual(device_lost_calls, ["TEST456"])

    def test_update_status_message(self):
        """Test status message updates."""
        status_calls = []

        def status_handler(status):
            status_calls.append(status)

        self.thread.status_updated.connect(status_handler)

        # Test no devices
        self.thread.known_devices = set()
        self.thread._update_status_message(set(), set())
        self.assertIn(StatusMessages.NO_DEVICES, status_calls)

        # Test devices found
        self.thread.known_devices = {"TEST123"}
        status_calls.clear()
        self.thread._update_status_message({"TEST123"}, set())
        self.assertTrue(any("✅" in status for status in status_calls))

        # Test stable state
        status_calls.clear()
        self.thread._update_status_message(set(), set())
        self.assertTrue(any("📱" in status for status in status_calls))

    def test_handle_scan_error(self):
        """Test error handling during scan."""
        status_calls = []

        def status_handler(status):
            status_calls.append(status)

        self.thread.status_updated.connect(status_handler)

        # Test error handling
        test_error = Exception("Test error")
        self.thread._handle_scan_error(test_error)

        # Check error message was emitted
        self.assertTrue(any("❌" in status and "Test error" in status for status in status_calls))

    def test_force_refresh(self):
        """Test force refresh functionality."""
        self.thread.known_devices = {"TEST123"}
        self.thread.force_refresh()
        self.assertEqual(len(self.thread.known_devices), 0)


class TestDeviceManager(unittest.TestCase):
    """Test DeviceManager functionality."""

    def setUp(self):
        """Set up test environment."""
        if not QCoreApplication.instance():
            self.app = QCoreApplication([])
        else:
            self.app = QCoreApplication.instance()

        # Create a real QWidget for testing since DeviceManager expects a widget parent
        self.parent_widget = QWidget()

        # Mock the DeviceManager to avoid Qt thread issues in tests
        with patch('ui.device_manager.DeviceRefreshThread'):
            self.device_manager = DeviceManager(self.parent_widget)

        # Mock device
        self.mock_device = Mock(spec=adb_models.DeviceInfo)
        self.mock_device.device_serial_num = "TEST123"
        self.mock_device.device_model = "TestModel"

    def tearDown(self):
        """Clean up after tests."""
        self.device_manager.cleanup()

    def test_initialization(self):
        """Test DeviceManager initialization."""
        self.assertEqual(self.device_manager.parent, self.parent_widget)
        self.assertIsInstance(self.device_manager.device_dict, dict)
        self.assertIsInstance(self.device_manager.check_devices, dict)
        self.assertIsInstance(self.device_manager.device_operations, dict)
        self.assertIsInstance(self.device_manager.device_recording_status, dict)

    def test_safe_execute(self):
        """Test safe execution wrapper."""
        # Test successful operation
        result = []
        def success_op():
            result.append("success")

        self.device_manager._safe_execute("test_op", success_op)
        self.assertEqual(result, ["success"])

        # Test operation with exception
        def error_op():
            raise Exception("Test error")

        # Should not raise exception
        self.device_manager._safe_execute("test_op", error_op)

    def test_remove_from_dict(self):
        """Test dictionary removal helper."""
        test_dict = {"key1": "value1", "key2": "value2"}

        # Remove existing key
        result = self.device_manager._remove_from_dict(test_dict, "key1")
        self.assertTrue(result)
        self.assertNotIn("key1", test_dict)

        # Try to remove non-existing key
        result = self.device_manager._remove_from_dict(test_dict, "key3")
        self.assertFalse(result)

    def test_cleanup_device_data(self):
        """Test device data cleanup."""
        serial = "TEST123"

        # Setup test data
        self.device_manager.device_dict[serial] = self.mock_device
        self.device_manager.device_operations[serial] = "testing"
        self.device_manager.device_recording_status[serial] = {"status": "active"}

        # Cleanup
        self.device_manager._cleanup_device_data(serial)

        # Verify cleanup
        self.assertNotIn(serial, self.device_manager.device_dict)
        self.assertNotIn(serial, self.device_manager.device_operations)
        self.assertNotIn(serial, self.device_manager.device_recording_status)

    def test_device_operation_management(self):
        """Test device operation status management."""
        serial = "TEST123"
        operation = "screenshot"

        # Set operation
        self.device_manager.set_device_operation_status(serial, operation)
        self.assertEqual(self.device_manager.get_device_operation_status(serial), operation)

        # Clear single operation
        self.device_manager.clear_device_operation_status(serial)
        self.assertEqual(self.device_manager.get_device_operation_status(serial), "idle")

        # Test bulk clear
        self.device_manager.device_operations["TEST1"] = "op1"
        self.device_manager.device_operations["TEST2"] = "op2"
        self.device_manager.clear_device_operations(["TEST1", "TEST2"])

        self.assertEqual(self.device_manager.get_device_operation_status("TEST1"), "idle")
        self.assertEqual(self.device_manager.get_device_operation_status("TEST2"), "idle")

    def test_device_recording_status_management(self):
        """Test device recording status management."""
        serial = "TEST123"
        status = {"recording": True, "file": "test.mp4"}

        self.device_manager.set_device_recording_status(serial, status)
        retrieved_status = self.device_manager.get_device_recording_status(serial)

        self.assertEqual(retrieved_status, status)

    def test_on_device_found(self):
        """Test device found event handling."""
        serial = "TEST123"

        # Add mock method to parent widget
        self.parent_widget.add_device_to_ui = Mock()

        self.device_manager._on_device_found(serial, self.mock_device)

        # Verify device added to dict
        self.assertEqual(self.device_manager.device_dict[serial], self.mock_device)

        # Verify parent method called
        self.parent_widget.add_device_to_ui.assert_called_once_with(serial, self.mock_device)

    def test_on_device_lost(self):
        """Test device lost event handling."""
        serial = "TEST123"

        # Setup device data
        self.device_manager.device_dict[serial] = self.mock_device
        self.device_manager.device_operations[serial] = "test"

        # Mock checkbox
        mock_checkbox = Mock()
        self.device_manager.check_devices[serial] = mock_checkbox

        # Add mock method to parent widget
        self.parent_widget.remove_device_from_ui = Mock()

        self.device_manager._on_device_lost(serial)

        # Verify cleanup
        self.assertNotIn(serial, self.device_manager.device_dict)
        self.assertNotIn(serial, self.device_manager.device_operations)
        self.assertNotIn(serial, self.device_manager.check_devices)

        # Verify UI cleanup
        mock_checkbox.setParent.assert_called_once_with(None)
        mock_checkbox.deleteLater.assert_called_once()

        # Verify parent method called
        self.parent_widget.remove_device_from_ui.assert_called_once_with(serial)

    def test_on_status_updated(self):
        """Test status update event handling."""
        test_status = "Test status message"

        # Add mock method to parent widget
        self.parent_widget.update_status_message = Mock()

        self.device_manager._on_status_updated(test_status)

        self.parent_widget.update_status_message.assert_called_once_with(test_status)

    def test_force_refresh(self):
        """Test force refresh functionality."""
        # Mock the refresh thread
        self.device_manager.refresh_thread.force_refresh = Mock()

        self.device_manager.force_refresh()

        self.device_manager.refresh_thread.force_refresh.assert_called_once()


def run_device_manager_tests():
    """Run all device manager tests."""
    print("🧪 Running Device Manager Tests...")
    print("=" * 50)

    # Test DeviceManagerConfig
    suite = unittest.TestLoader().loadTestsFromTestCase(TestDeviceManagerConfig)
    result = unittest.TextTestRunner(verbosity=2).run(suite)

    # Test StatusMessages
    suite = unittest.TestLoader().loadTestsFromTestCase(TestStatusMessages)
    result = unittest.TextTestRunner(verbosity=2).run(suite)

    # Test DeviceCache
    suite = unittest.TestLoader().loadTestsFromTestCase(TestDeviceCache)
    result = unittest.TextTestRunner(verbosity=2).run(suite)

    # Test DeviceRefreshThread
    suite = unittest.TestLoader().loadTestsFromTestCase(TestDeviceRefreshThread)
    result = unittest.TextTestRunner(verbosity=2).run(suite)

    # Test DeviceManager
    suite = unittest.TestLoader().loadTestsFromTestCase(TestDeviceManager)
    result = unittest.TextTestRunner(verbosity=2).run(suite)

    print("=" * 50)
    print("✅ Device Manager Tests Complete!")


if __name__ == '__main__':
    run_device_manager_tests()
