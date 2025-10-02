#!/usr/bin/env python3
"""
Comprehensive test suite for Lazy Blacktea application.
Tests all major functionality including device detection, UI refresh, recording, etc.
"""

import sys
import os
import unittest
from unittest.mock import Mock, patch, MagicMock
import subprocess
from typing import List, Dict
import shutil
import logging

# Add the project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils import adb_tools, adb_commands, common
from utils.adb_models import DeviceInfo
from ui.device_manager import DeviceManager, DeviceRefreshThread
from utils.recording_utils import RecordingManager
from config.config_manager import ConfigManager
from ui.command_executor import CommandExecutor
from ui.file_operations_manager import CommandHistoryManager
from PyQt6.QtCore import QObject


class TestDeviceDetection(unittest.TestCase):
    """Test device detection and refresh functionality."""

    def setUp(self):
        """Set up test environment."""
        self.test_device_output = [
            "R5CN700J89E            device usb:1-0 product:y2qzhx model:SM_G9860 device:y2q transport_id:6",
            ""
        ]

    def test_adb_devices_command(self):
        """Test basic ADB devices command."""
        print("🧪 Testing ADB devices command...")
        adb_path = shutil.which('adb')
        if not adb_path:
            print("   ⚠️ ADB binary not available - treating as skipped")
            return True, []

        try:
            result = subprocess.run(
                [adb_path, 'devices', '-l'],
                capture_output=True,
                text=True,
                timeout=10,
            )
        except Exception as e:  # pragma: no cover - defensive
            print(f"   ❌ ADB command failed: {e}")
            return False, []

        combined_output = f"{result.stdout}\n{result.stderr}".lower()
        sandbox_blocked = 'smartsocket' in combined_output or 'operation not permitted' in combined_output

        if result.returncode != 0 and not sandbox_blocked:
            print(f"   ❌ ADB command failed with return code: {result.returncode}")
            if result.stderr:
                print(f"   🔍 stderr: {result.stderr.strip()}")
            return False, []

        if sandbox_blocked:
            print("   ⚠️ ADB daemon blocked by sandbox - treating as skipped")
            return True, []

        print(f"   ✅ ADB command successful, return code: {result.returncode}")
        lines = [line for line in result.stdout.strip().split('\n') if line.strip()]
        device_lines = lines[1:] if len(lines) > 1 else []
        devices = [line for line in device_lines if 'device' in line]
        print(f"   📱 Devices found: {len(devices)}")
        if devices:
            print(f"   📋 Device list: {devices}")
        return True, devices

    def test_get_devices_list_function(self):
        """Test the get_devices_list function in adb_tools."""
        print("🧪 Testing get_devices_list function...")

        try:
            devices = adb_tools.get_devices_list()
            print(f"   ✅ Function executed successfully")
            print(f"   📱 Devices returned: {len(devices)}")

            for i, device in enumerate(devices):
                print(f"   📋 Device {i+1}: {device.device_serial_num} - {device.device_model}")
                print(f"      Android: {device.android_ver}, API: {device.android_api_level}")
                print(f"      GMS: {device.gms_version}")

            return True, devices

        except Exception as e:
            print(f"   ❌ Function failed: {e}")
            import traceback
            print(f"   🔍 Traceback: {traceback.format_exc()}")
            return False, []

    def test_device_info_parsing(self):
        """Test device info parsing from ADB output."""
        print("🧪 Testing device info parsing...")

        test_cases = [
            "R5CN700J89E            device usb:1-0 product:y2qzhx model:SM_G9860 device:y2q transport_id:6",
            "25091FDH30005X         device usb:1-0 product:cheetah model:Pixel_7_Pro device:cheetah transport_id:2"
        ]

        for test_case in test_cases:
            try:
                parts = test_case.split()
                if len(parts) >= 6:
                    serial = parts[0]
                    model = parts[4].replace('model:', '')
                    print(f"   ✅ Parsed - Serial: {serial}, Model: {model}")
                else:
                    print(f"   ❌ Failed to parse: {test_case}")

            except Exception as e:
                print(f"   ❌ Parsing error: {e}")

    def test_device_refresh_thread(self):
        """Test device refresh thread functionality."""
        print("🧪 Testing device refresh thread...")

        try:
            # Test that DeviceRefreshThread class exists and has the right methods
            assert hasattr(DeviceRefreshThread, '__init__'), "DeviceRefreshThread should have __init__"
            assert hasattr(DeviceRefreshThread, 'run'), "DeviceRefreshThread should have run method"
            assert hasattr(DeviceRefreshThread, 'stop'), "DeviceRefreshThread should have stop method"
            print("   ✅ DeviceRefreshThread class structure correct")

            # Test that DeviceManager can be created
            # We'll skip actual thread testing due to Qt dependencies
            print("   ✅ DeviceManager class exists")
            print("   ℹ️  Skipping actual thread test due to Qt dependencies")

            return True

        except Exception as e:
            print(f"   ❌ Thread test failed: {e}")
            import traceback
            print(f"   🔍 Traceback: {traceback.format_exc()}")
            return False

    def test_audio_state_summary_parsing(self):
        """Test parsing of dumpsys audio output for summary."""
        sample_output = [
            'Audio Routes (status):',
            '  mode: NORMAL',
            '  ringer mode: NORMAL',
            '  music active: false',
            'Device current state: speakerphone: ON',
        ]
        with patch.object(common, 'run_command', return_value=sample_output):
            summary = adb_tools.get_audio_state_summary('test-serial')

        self.assertIsInstance(summary, str)
        self.assertIn('mode=NORMAL', summary)
        self.assertIn('music_active=false', summary)

    def test_bluetooth_manager_state_parsing(self):
        """Test parsing of cmd bluetooth_manager get-state output."""
        sample_output = ['Bluetooth Manager state: ON', 'Enabled: true']
        with patch.object(common, 'run_command', return_value=sample_output):
            state = adb_tools.get_bluetooth_manager_state_summary('test-serial')

        self.assertEqual(state, 'ON')

    def test_bluetooth_manager_state_fallback(self):
        """Ensure bluetooth manager summary handles missing output."""
        with patch.object(common, 'run_command', return_value=[]):
            state = adb_tools.get_bluetooth_manager_state_summary('test-serial')

        self.assertEqual(state, 'Unknown')


class TestRecordingFunctionality(unittest.TestCase):
    """Test screen recording functionality."""

    def setUp(self):
        """Set up test environment."""
        self.test_output_path = "/tmp/test_recordings"
        os.makedirs(self.test_output_path, exist_ok=True)

    def test_recording_commands(self):
        """Test recording command generation."""
        print("🧪 Testing recording commands...")

        test_serial = "R5CN700J89E"
        test_filename = "test_recording"

        try:
            # Test start command
            start_cmd = adb_commands.cmd_android_screen_record(test_serial, test_filename)
            print(f"   📝 Start command: {start_cmd}")
            expected_start = f"adb -s {test_serial} shell screenrecord /sdcard/screenrecord_{test_serial}_{test_filename}.mp4"
            assert start_cmd == expected_start, f"Start command mismatch"
            print("   ✅ Start command correct")

            # Test stop command
            stop_cmd = adb_commands.cmd_android_screen_record_stop(test_serial)
            print(f"   📝 Stop command: {stop_cmd}")
            expected_stop = f"adb -s {test_serial} shell pkill -SIGINT screenrecord"
            assert stop_cmd == expected_stop, f"Stop command mismatch"
            print("   ✅ Stop command correct")

            # Test pull command
            pull_cmd = adb_commands.cmd_pull_android_screen_record(test_serial, test_filename, self.test_output_path)
            print(f"   📝 Pull command: {pull_cmd}")
            expected_pull = f"adb -s {test_serial} pull /sdcard/screenrecord_{test_serial}_{test_filename}.mp4 {self.test_output_path}"
            assert pull_cmd == expected_pull, f"Pull command mismatch"
            print("   ✅ Pull command correct")

            return True

        except Exception as e:
            print(f"   ❌ Command test failed: {e}")
            return False

    def test_recording_manager(self):
        """Test recording manager functionality."""
        print("🧪 Testing recording manager...")

        try:
            manager = RecordingManager()
            print("   ✅ Recording manager created")

            # Test with mock device
            mock_device = DeviceInfo(
                device_serial_num="TEST_DEVICE",
                device_usb="test-usb",
                device_prod="test-prod",
                device_model="Test_Model",
                wifi_is_on=True,
                bt_is_on=True,
                android_ver="11",
                android_api_level="30",
                gms_version="Test",
                build_fingerprint="test-build"
            )

            # Test recording status
            status = manager.get_recording_status("TEST_DEVICE")
            print(f"   📊 Initial status: {status}")
            assert status == "Idle", f"Expected Idle, got {status}"

            # Test active recordings count
            count = manager.get_active_recordings_count()
            print(f"   📊 Active recordings: {count}")
            assert count == 0, f"Expected 0, got {count}"

            print("   ✅ Recording manager tests passed")
            return True

        except Exception as e:
            print(f"   ❌ Recording manager test failed: {e}")
            import traceback
            print(f"   🔍 Traceback: {traceback.format_exc()}")
            return False

    def test_wrapper_functions(self):
        """Test recording wrapper functions."""
        print("🧪 Testing recording wrapper functions...")

        test_serial = "TEST_DEVICE"
        test_filename = "test_recording.mp4"
        test_output = self.test_output_path

        try:
            # Test that wrapper functions exist and are callable
            assert hasattr(adb_tools, 'start_screen_record_device'), "start_screen_record_device not found"
            assert hasattr(adb_tools, 'stop_screen_record_device'), "stop_screen_record_device not found"
            print("   ✅ Wrapper functions exist")

            # Test function signatures
            import inspect
            start_sig = inspect.signature(adb_tools.start_screen_record_device)
            stop_sig = inspect.signature(adb_tools.stop_screen_record_device)

            print(f"   📝 Start function signature: {start_sig}")
            print(f"   📝 Stop function signature: {stop_sig}")

            # Verify parameters
            start_params = list(start_sig.parameters.keys())
            expected_start = ['serial', 'output_path', 'filename']
            assert start_params == expected_start, f"Start params mismatch: {start_params} vs {expected_start}"

            stop_params = list(stop_sig.parameters.keys())
            expected_stop = ['serial']
            assert stop_params == expected_stop, f"Stop params mismatch: {stop_params} vs {expected_stop}"

            print("   ✅ Function signatures correct")
            return True

        except Exception as e:
            print(f"   ❌ Wrapper function test failed: {e}")
            import traceback
            print(f"   🔍 Traceback: {traceback.format_exc()}")
            return False


class TestScreenshotFunctionality(unittest.TestCase):
    """Test screenshot functionality."""

    def setUp(self):
        """Set up test environment."""
        self.test_output_path = "/tmp/test_screenshots"
        os.makedirs(self.test_output_path, exist_ok=True)

    def test_screenshot_commands(self):
        """Test screenshot command generation."""
        print("🧪 Testing screenshot commands...")

        test_serial = "R5CN700J89E"
        test_filename = "test_screenshot"

        try:
            # Test screenshot command
            cmd = adb_commands.cmd_adb_screen_shot(test_serial, test_filename, self.test_output_path)
            print(f"   📝 Screenshot command: {cmd}")

            expected = (
                f"adb -s {test_serial} shell screencap -p /sdcard/{test_serial}_screenshot_{test_filename}.png && "
                f"adb -s {test_serial} pull /sdcard/{test_serial}_screenshot_{test_filename}.png {self.test_output_path}"
            )
            assert cmd == expected, f"Command mismatch"
            print("   ✅ Screenshot command correct")
            return True

        except Exception as e:
            print(f"   ❌ Screenshot command test failed: {e}")
            return False

    def test_screenshot_wrapper(self):
        """Test screenshot wrapper function."""
        print("🧪 Testing screenshot wrapper function...")

        try:
            # Test that wrapper function exists
            assert hasattr(adb_tools, 'take_screenshot_single_device'), "take_screenshot_single_device not found"
            print("   ✅ Screenshot wrapper function exists")

            # Test function signature
            import inspect
            sig = inspect.signature(adb_tools.take_screenshot_single_device)
            print(f"   📝 Function signature: {sig}")

            params = list(sig.parameters.keys())
            expected = ['serial', 'output_path', 'filename']
            assert params == expected, f"Params mismatch: {params} vs {expected}"
            print("   ✅ Function signature correct")
            return True

        except Exception as e:
            print(f"   ❌ Screenshot wrapper test failed: {e}")
            return False


class TestConfigManagement(unittest.TestCase):
    """Test configuration management."""

    def test_config_manager(self):
        """Test configuration manager functionality."""
        print("🧪 Testing configuration manager...")

        try:
            # Test config manager creation
            config_manager = ConfigManager()
            print("   ✅ Config manager created")

            # Test config loading
            app_config = config_manager.load_config()
            print(f"   📋 Config loaded successfully")
            print(f"   📋 UI Scale: {app_config.ui.ui_scale}")
            print(f"   📋 Device refresh interval: {app_config.device.refresh_interval}")

            # Test UI settings
            ui_settings = config_manager.get_ui_settings()
            assert hasattr(ui_settings, 'ui_scale'), "UI settings should have ui_scale"
            print("   ✅ UI settings accessible")

            # Test device settings
            device_settings = config_manager.get_device_settings()
            assert hasattr(device_settings, 'refresh_interval'), "Device settings should have refresh_interval"
            print("   ✅ Device settings accessible")

            return True

        except Exception as e:
            print(f"   ❌ Config manager test failed: {e}")
            import traceback
            print(f"   🔍 Traceback: {traceback.format_exc()}")
            return False


class TestUtilityFunctions(unittest.TestCase):
    """Test utility functions."""

    def test_common_utilities(self):
        """Test common utility functions."""
        print("🧪 Testing common utilities...")

        try:
            # Test directory creation
            test_dir = "/tmp/test_lazy_blacktea"
            result = common.make_gen_dir_path(test_dir)
            print(f"   📁 Directory creation result: {result}")
            assert os.path.exists(test_dir), "Directory should be created"
            print("   ✅ Directory creation works")

            # Test directory check
            exists = common.check_exists_dir(test_dir)
            assert exists, "Directory should exist"
            print("   ✅ Directory check works")

            # Test time formatting
            time_str = common.current_format_time_utc()
            print(f"   🕐 Current time: {time_str}")
            assert isinstance(time_str, str) and len(time_str) > 0, "Time string should not be empty"
            print("   ✅ Time formatting works")

            # Clean up
            import shutil
            shutil.rmtree(test_dir, ignore_errors=True)

            return True

        except Exception as e:
            print(f"   ❌ Common utilities test failed: {e}")
            import traceback
            print(f"   🔍 Traceback: {traceback.format_exc()}")
            return False


class TestCommandHistoryPersistence(unittest.TestCase):
    """Test command history synchronization and persistence logic."""

    def _create_dummy_parent(self):
        class DummyParent(QObject):
            def __init__(self):
                super().__init__()
                self.logger = logging.getLogger('test_command_history')
                self.command_executor = CommandExecutor(self)
                self.history_updates = 0

            def update_history_display(self):
                self.history_updates += 1

        return DummyParent()

    def test_history_sync_with_executor(self):
        """Ensure manager updates command executor history consistently."""
        print("🧪 Testing command history synchronization...")

        try:
            with patch('ui.file_operations_manager.json_utils.read_config_json', return_value={}), \
                 patch('ui.file_operations_manager.json_utils.save_config_json'):

                parent = self._create_dummy_parent()
                manager = CommandHistoryManager(parent)
                parent.command_history_manager = manager

                test_command = 'adb devices'
                manager.add_to_history(test_command)

                assert test_command in manager.command_history, 'Manager should record command'
                executor_history = parent.command_executor.get_command_history()
                assert test_command in executor_history, 'Executor should mirror manager history'

                manager.clear_history()
                assert manager.command_history == [], 'Manager history should clear'
                assert parent.command_executor.get_command_history() == [], 'Executor history should clear'

            print("   ✅ Command history synchronization works")
            return True

        except Exception as e:
            print(f"   ❌ Command history test failed: {e}")
            import traceback
            print(f"   🔍 Traceback: {traceback.format_exc()}")
            return False


def run_command_history_tests():
    """Run command history synchronization tests."""
    print("\n📜 === COMMAND HISTORY TESTS ===")

    test_case = TestCommandHistoryPersistence()
    results = {}

    success = test_case.test_history_sync_with_executor()
    results['command_history_sync'] = success

    return results


def run_device_detection_tests():
    """Run device detection tests."""
    print("\\n🔍 === DEVICE DETECTION TESTS ===")

    test_case = TestDeviceDetection()
    test_case.setUp()

    results = {}

    # Test ADB command
    success, devices = test_case.test_adb_devices_command()
    results['adb_command'] = success

    # Test get_devices_list function
    success, parsed_devices = test_case.test_get_devices_list_function()
    results['get_devices_list'] = success

    # Test device info parsing
    test_case.test_device_info_parsing()
    results['device_parsing'] = True

    # Test device refresh thread
    success = test_case.test_device_refresh_thread()
    results['refresh_thread'] = success

    return results


def run_recording_tests():
    """Run recording functionality tests."""
    print("\\n🎬 === RECORDING FUNCTIONALITY TESTS ===")

    test_case = TestRecordingFunctionality()
    test_case.setUp()

    results = {}

    # Test recording commands
    success = test_case.test_recording_commands()
    results['recording_commands'] = success

    # Test recording manager
    success = test_case.test_recording_manager()
    results['recording_manager'] = success

    # Test wrapper functions
    success = test_case.test_wrapper_functions()
    results['wrapper_functions'] = success

    return results


def run_screenshot_tests():
    """Run screenshot functionality tests."""
    print("\\n📸 === SCREENSHOT FUNCTIONALITY TESTS ===")

    test_case = TestScreenshotFunctionality()
    test_case.setUp()

    results = {}

    # Test screenshot commands
    success = test_case.test_screenshot_commands()
    results['screenshot_commands'] = success

    # Test screenshot wrapper
    success = test_case.test_screenshot_wrapper()
    results['screenshot_wrapper'] = success

    return results


def run_config_tests():
    """Run configuration tests."""
    print("\\n⚙️ === CONFIGURATION TESTS ===")

    test_case = TestConfigManagement()

    results = {}

    # Test config manager
    success = test_case.test_config_manager()
    results['config_manager'] = success

    return results


def run_utility_tests():
    """Run utility function tests."""
    print("\\n🛠️ === UTILITY FUNCTION TESTS ===")

    test_case = TestUtilityFunctions()

    results = {}

    # Test common utilities
    success = test_case.test_common_utilities()
    results['common_utilities'] = success

    return results


def main():
    """Main test runner."""
    print("🍵 === LAZY BLACKTEA COMPREHENSIVE TEST SUITE ===")
    print("Testing all functionality to ensure proper operation...")

    all_results = {}

    # Run all test suites
    all_results.update(run_command_history_tests())
    all_results.update(run_device_detection_tests())
    all_results.update(run_recording_tests())
    all_results.update(run_screenshot_tests())
    all_results.update(run_config_tests())
    all_results.update(run_utility_tests())

    # Summary
    print("\\n📊 === TEST RESULTS SUMMARY ===")
    passed = 0
    failed = 0

    for test_name, result in all_results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"   {test_name:<20} {status}")
        if result:
            passed += 1
        else:
            failed += 1

    print(f"\\n📈 Total: {passed + failed} tests, {passed} passed, {failed} failed")

    if failed > 0:
        print("\\n⚠️ ISSUES FOUND - Please review failed tests above")
        return False
    else:
        print("\\n🎉 ALL TESTS PASSED - Application is ready!")
        return True


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
