#!/usr/bin/env python3
"""
Simplified test suite for the refactored device_manager module.
Focuses on core functionality without complex Qt dependencies.
"""

import sys
import os
import unittest
import time
from unittest.mock import Mock, patch

# Add the project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils import adb_models
from ui.device_manager import (
    DeviceManagerConfig,
    DeviceCache,
    StatusMessages
)


class TestDeviceManagerConfig(unittest.TestCase):
    """Test DeviceManagerConfig constants."""

    def test_config_constants_exist(self):
        """Test that all configuration constants exist and are reasonable."""
        self.assertIsInstance(DeviceManagerConfig.DEFAULT_CACHE_TTL, float)
        self.assertIsInstance(DeviceManagerConfig.DEFAULT_REFRESH_INTERVAL, int)
        self.assertIsInstance(DeviceManagerConfig.SHUTDOWN_TIMEOUT, int)
        self.assertIsInstance(DeviceManagerConfig.ERROR_RETRY_DELAY, int)
        self.assertIsInstance(DeviceManagerConfig.PROGRESSIVE_DELAY, int)
        self.assertIsInstance(DeviceManagerConfig.FULL_UPDATE_INTERVAL, int)

        # Check values are positive
        self.assertGreater(DeviceManagerConfig.DEFAULT_CACHE_TTL, 0)
        self.assertGreater(DeviceManagerConfig.DEFAULT_REFRESH_INTERVAL, 0)
        self.assertGreater(DeviceManagerConfig.SHUTDOWN_TIMEOUT, 0)


class TestStatusMessages(unittest.TestCase):
    """Test StatusMessages constants."""

    def test_status_messages_formatting(self):
        """Test that status messages can be formatted correctly."""
        # Test DEVICES_CONNECTED formatting
        message = StatusMessages.DEVICES_CONNECTED.format(count=1, s='')
        self.assertEqual(message, "📱 1 device connected")

        message = StatusMessages.DEVICES_CONNECTED.format(count=2, s='s')
        self.assertEqual(message, "📱 2 devices connected")

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

    def create_mock_device(self, serial: str, model: str = "TestModel"):
        """Create a mock device for testing."""
        device = Mock(spec=adb_models.DeviceInfo)
        device.device_serial_num = serial
        device.device_model = model
        return device

    @patch('ui.device_manager.adb_tools.get_devices_list')
    def test_cache_basic_functionality(self, mock_get_devices):
        """Test basic cache functionality."""
        mock_device = self.create_mock_device("TEST123")
        mock_get_devices.return_value = [mock_device]

        # First call should hit the backend
        devices = self.cache.get_devices()
        self.assertEqual(len(devices), 1)
        self.assertEqual(devices[0].device_serial_num, "TEST123")
        self.assertEqual(mock_get_devices.call_count, 1)

        # Second call within TTL should use cache
        devices = self.cache.get_devices()
        self.assertEqual(len(devices), 1)
        self.assertEqual(mock_get_devices.call_count, 1)  # No additional call

    @patch('ui.device_manager.adb_tools.get_devices_list')
    def test_cache_ttl_expiration(self, mock_get_devices):
        """Test cache TTL expiration."""
        mock_device = self.create_mock_device("TEST123")
        mock_get_devices.return_value = [mock_device]

        # Load cache
        self.cache.get_devices()
        self.assertEqual(mock_get_devices.call_count, 1)

        # Wait for cache to expire
        time.sleep(0.2)

        # Should hit backend again after TTL
        self.cache.get_devices()
        self.assertEqual(mock_get_devices.call_count, 2)

    @patch('ui.device_manager.adb_tools.get_devices_list')
    def test_cache_error_handling(self, mock_get_devices):
        """Test cache error handling returns cached data."""
        mock_device = self.create_mock_device("TEST123")

        # First successful load
        mock_get_devices.return_value = [mock_device]
        devices = self.cache.get_devices()
        self.assertEqual(len(devices), 1)

        # Simulate error on refresh
        mock_get_devices.side_effect = Exception("Network error")
        time.sleep(0.2)  # Wait for cache to expire

        # Should return cached devices on error
        devices = self.cache.get_devices()
        self.assertEqual(len(devices), 1)
        self.assertEqual(devices[0].device_serial_num, "TEST123")

    def test_calculate_hash(self):
        """Test hash calculation consistency."""
        device1 = self.create_mock_device("TEST123")
        device2 = self.create_mock_device("TEST456")

        # Same devices should produce same hash
        hash1 = self.cache._calculate_hash([device1])
        hash2 = self.cache._calculate_hash([device1])
        self.assertEqual(hash1, hash2)

        # Different devices should produce different hash
        hash3 = self.cache._calculate_hash([device1, device2])
        self.assertNotEqual(hash1, hash3)

    def test_force_refresh(self):
        """Test force refresh clears cache."""
        # Cache should have last_update = 0 after force_refresh
        initial_time = self.cache.last_update
        self.cache.force_refresh()
        self.assertEqual(self.cache.last_update, 0)


class TestDeviceManagerHelpers(unittest.TestCase):
    """Test helper functions and basic functionality."""

    @patch('ui.device_manager.adb_tools.get_devices_list')
    def test_get_devices_cached_function(self, mock_get_devices):
        """Test the global get_devices_cached function."""
        from ui.device_manager import get_devices_cached

        mock_device = Mock(spec=adb_models.DeviceInfo)
        mock_device.device_serial_num = "TEST123"
        mock_get_devices.return_value = [mock_device]

        devices = get_devices_cached()
        self.assertEqual(len(devices), 1)
        self.assertEqual(devices[0].device_serial_num, "TEST123")


def run_simple_tests():
    """Run simplified device manager tests."""
    print("🧪 Running Simplified Device Manager Tests...")
    print("=" * 55)

    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    # Add test classes
    suite.addTests(loader.loadTestsFromTestCase(TestDeviceManagerConfig))
    suite.addTests(loader.loadTestsFromTestCase(TestStatusMessages))
    suite.addTests(loader.loadTestsFromTestCase(TestDeviceCache))
    suite.addTests(loader.loadTestsFromTestCase(TestDeviceManagerHelpers))

    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    # Print summary
    print("\n" + "=" * 55)
    if result.wasSuccessful():
        print("✅ All tests passed!")
        print(f"📊 Ran {result.testsRun} tests successfully")
    else:
        print("❌ Some tests failed")
        print(f"📊 Tests: {result.testsRun}, Failures: {len(result.failures)}, Errors: {len(result.errors)}")

    return result.wasSuccessful()


if __name__ == '__main__':
    success = run_simple_tests()
    sys.exit(0 if success else 1)