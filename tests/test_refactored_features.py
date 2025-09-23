#!/usr/bin/env python3
"""
Test suite for refactored features including error handling decorators,
ADB command builders, and device property extraction.
"""

import sys
import os
import unittest
from unittest.mock import Mock, patch, MagicMock
import tempfile
import shutil

# Add the project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils import adb_tools, adb_commands, common
from utils.adb_models import DeviceInfo


class TestErrorHandlingDecorators(unittest.TestCase):
    """Test error handling decorators functionality."""

    def test_adb_operation_decorator_success(self):
        """Test adb_operation decorator with successful operation."""
        @adb_tools.adb_operation(operation_name="test_operation")
        def test_function():
            return "success"

        result = test_function()
        self.assertEqual(result, "success")

    def test_adb_operation_decorator_with_exception(self):
        """Test adb_operation decorator handles exceptions."""
        @adb_tools.adb_operation(operation_name="test_operation", default_return="default")
        def test_function():
            raise Exception("Test exception")

        result = test_function()
        self.assertEqual(result, "default")

    def test_adb_device_operation_decorator_success(self):
        """Test adb_device_operation decorator with successful operation."""
        @adb_tools.adb_device_operation(default_return=None)
        def test_device_function(serial_num, param1):
            return f"success_{serial_num}_{param1}"

        result = test_device_function("test_serial", "param_value")
        self.assertEqual(result, "success_test_serial_param_value")

    def test_adb_device_operation_decorator_with_exception(self):
        """Test adb_device_operation decorator handles exceptions."""
        @adb_tools.adb_device_operation(default_return="device_error")
        def test_device_function(serial_num):
            raise Exception("Device test exception")

        result = test_device_function("test_serial")
        self.assertEqual(result, "device_error")

    def test_decorated_function_preserves_metadata(self):
        """Test that decorators preserve function metadata."""
        @adb_tools.adb_operation()
        def test_function_with_docstring():
            """This is a test function."""
            return "test"

        self.assertEqual(test_function_with_docstring.__name__, "test_function_with_docstring")
        self.assertEqual(test_function_with_docstring.__doc__, "This is a test function.")


class TestADBCommandBuilders(unittest.TestCase):
    """Test ADB command building functions."""

    def setUp(self):
        """Set up test fixtures."""
        self.test_serial = "test_device_12345"

    def test_build_adb_command_no_serial(self):
        """Test building ADB command without device serial."""
        result = adb_commands._build_adb_command(None, 'devices', '-l')
        self.assertIn('adb devices -l', result)

    def test_build_adb_command_with_serial(self):
        """Test building ADB command with device serial."""
        result = adb_commands._build_adb_command(self.test_serial, 'shell', 'ps')
        self.assertIn(f'adb -s {self.test_serial} shell ps', result)

    def test_build_adb_shell_command(self):
        """Test building ADB shell command."""
        result = adb_commands._build_adb_shell_command(self.test_serial, 'getprop ro.build.version.release')
        expected = f'adb -s {self.test_serial} shell getprop ro.build.version.release'
        self.assertIn(expected, result)

    def test_build_setting_getter_command(self):
        """Test building settings getter command."""
        result = adb_commands._build_setting_getter_command(self.test_serial, 'wifi_on')
        expected = f'adb -s {self.test_serial} shell settings get global wifi_on'
        self.assertIn(expected, result)

    def test_build_getprop_command(self):
        """Test building getprop command."""
        result = adb_commands._build_getprop_command(self.test_serial, 'ro.product.model')
        expected = f'adb -s {self.test_serial} shell getprop ro.product.model'
        self.assertIn(expected, result)

    def test_cmd_get_adb_devices(self):
        """Test ADB devices command generation."""
        result = adb_commands.cmd_get_adb_devices()
        self.assertIn('adb devices -l', result)

    def test_cmd_get_android_build_fingerprint(self):
        """Test Android build fingerprint command."""
        result = adb_commands.cmd_get_android_build_fingerprint(self.test_serial)
        self.assertIn(f'adb -s {self.test_serial} shell getprop ro.build.fingerprint', result)

    def test_cmd_kill_adb_server(self):
        """Test ADB server kill command."""
        result = adb_commands.cmd_kill_adb_server()
        self.assertIn('adb kill-server', result)

    def test_cmd_start_adb_server(self):
        """Test ADB server start command."""
        result = adb_commands.cmd_start_adb_server()
        self.assertIn('adb start-server', result)

    def test_cmd_adb_root(self):
        """Test ADB root command."""
        result = adb_commands.cmd_adb_root(self.test_serial)
        self.assertIn(f'adb -s {self.test_serial} root', result)

    def test_cmd_adb_reboot(self):
        """Test ADB reboot command."""
        result = adb_commands.cmd_adb_reboot(self.test_serial)
        self.assertIn(f'adb -s {self.test_serial} reboot', result)

    def test_cmd_adb_install(self):
        """Test ADB install command."""
        apk_path = "/path/to/test.apk"
        result = adb_commands.cmd_adb_install(self.test_serial, apk_path)
        self.assertIn(f'adb -s {self.test_serial} install -d -r -g', result)
        self.assertIn(apk_path, result)

    def test_cmd_get_android_api_level(self):
        """Test Android API level command."""
        result = adb_commands.cmd_get_android_api_level(self.test_serial)
        self.assertIn(f'adb -s {self.test_serial} shell getprop ro.build.version.sdk', result)

    def test_cmd_get_android_version(self):
        """Test Android version command."""
        result = adb_commands.cmd_get_android_version(self.test_serial)
        self.assertIn(f'adb -s {self.test_serial} shell getprop ro.build.version.release', result)

    def test_cmd_get_device_bluetooth(self):
        """Test device Bluetooth status command."""
        result = adb_commands.cmd_get_device_bluetooth(self.test_serial)
        self.assertIn(f'adb -s {self.test_serial} shell settings get global bluetooth_on', result)

    def test_cmd_get_device_wifi(self):
        """Test device WiFi status command."""
        result = adb_commands.cmd_get_device_wifi(self.test_serial)
        self.assertIn(f'adb -s {self.test_serial} shell settings get global wifi_on', result)

    def test_cmd_clear_device_logcat(self):
        """Test clear device logcat command."""
        result = adb_commands.cmd_clear_device_logcat(self.test_serial)
        self.assertIn(f'adb -s {self.test_serial} logcat -b all -c', result)


class TestDevicePropertyExtraction(unittest.TestCase):
    """Test device property extraction functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.test_serial = "test_device_12345"

    @patch('utils.adb_tools.common.run_command')
    @patch('utils.adb_tools.adb_commands.cmd_adb_shell')
    def test_get_device_property_success(self, mock_cmd_shell, mock_run_command):
        """Test successful device property extraction."""
        mock_cmd_shell.return_value = "test_command"
        mock_run_command.return_value = ["Physical density: 420"]

        result = adb_tools._get_device_property(self.test_serial, 'wm density')

        self.assertEqual(result, "Physical density: 420")
        mock_cmd_shell.assert_called_once_with(self.test_serial, 'wm density')
        mock_run_command.assert_called_once_with("test_command")

    @patch('utils.adb_tools.common.run_command')
    @patch('utils.adb_tools.adb_commands.cmd_adb_shell')
    def test_get_device_property_empty_result(self, mock_cmd_shell, mock_run_command):
        """Test device property extraction with empty result."""
        mock_cmd_shell.return_value = "test_command"
        mock_run_command.return_value = []

        result = adb_tools._get_device_property(self.test_serial, 'wm density', 'default_value')

        self.assertEqual(result, "default_value")

    @patch('utils.adb_tools.common.run_command')
    @patch('utils.adb_tools.adb_commands.cmd_adb_shell')
    def test_get_device_property_exception(self, mock_cmd_shell, mock_run_command):
        """Test device property extraction with exception."""
        mock_cmd_shell.return_value = "test_command"
        mock_run_command.side_effect = Exception("Command failed")

        result = adb_tools._get_device_property(self.test_serial, 'wm density', 'error_default')

        self.assertEqual(result, "error_default")

    @patch('utils.adb_tools._get_device_property')
    def test_get_additional_device_info_success(self, mock_get_property):
        """Test get_additional_device_info with successful property extraction."""
        # Mock property responses
        mock_get_property.side_effect = [
            "Physical density: 420",  # screen_density
            "Physical size: 1440x3120",  # screen_size
            "arm64-v8a"  # cpu_arch
        ]

        # Mock battery info
        with patch('utils.adb_tools.common.run_command') as mock_run_command:
            mock_run_command.return_value = [
                "Current Battery Service state:",
                "  level: 85",
                "  scale: 100"
            ]

            result = adb_tools.get_additional_device_info(self.test_serial)

            self.assertEqual(result['screen_density'], "Physical density: 420")
            self.assertEqual(result['screen_size'], "Physical size: 1440x3120")
            self.assertEqual(result['cpu_arch'], "arm64-v8a")
            self.assertEqual(result['battery_level'], "85%")


class TestParallelExecution(unittest.TestCase):
    """Test parallel execution functions."""

    def test_execute_commands_parallel_empty_list(self):
        """Test parallel execution with empty command list."""
        result = adb_tools._execute_commands_parallel([], "test_operation")
        self.assertEqual(result, [])

    @patch('utils.adb_tools.common.run_command')
    def test_execute_commands_parallel_success(self, mock_run_command):
        """Test successful parallel command execution."""
        mock_run_command.side_effect = [["result1"], ["result2"]]
        commands = ["command1", "command2"]

        result = adb_tools._execute_commands_parallel(commands, "test_operation")

        self.assertEqual(len(result), 2)
        self.assertEqual(result[0], ["result1"])
        self.assertEqual(result[1], ["result2"])

    def test_execute_functions_parallel_empty_list(self):
        """Test parallel function execution with empty list."""
        result = adb_tools._execute_functions_parallel([], [], "test_operation")
        self.assertEqual(result, [])

    def test_execute_functions_parallel_success(self):
        """Test successful parallel function execution."""
        def test_func1(arg):
            return f"result1_{arg}"

        def test_func2(arg):
            return f"result2_{arg}"

        functions = [test_func1, test_func2]
        args_list = [("arg1",), ("arg2",)]

        result = adb_tools._execute_functions_parallel(functions, args_list, "test_operation")

        self.assertEqual(len(result), 2)
        self.assertIn("result1_arg1", result)
        self.assertIn("result2_arg2", result)

    def test_execute_functions_parallel_with_exception(self):
        """Test parallel function execution with exception handling."""
        def test_func_success(arg):
            return f"success_{arg}"

        def test_func_error(arg):
            raise Exception("Test error")

        functions = [test_func_success, test_func_error]
        args_list = [("arg1",), ("arg2",)]

        result = adb_tools._execute_functions_parallel(functions, args_list, "test_operation")

        self.assertEqual(len(result), 2)
        self.assertIn("success_arg1", result)
        self.assertIn(None, result)  # Error case returns None


class TestPathValidation(unittest.TestCase):
    """Test unified path validation functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.test_valid_path = self.temp_dir
        self.test_invalid_path = "/nonexistent/path/that/should/not/exist"

    def tearDown(self):
        """Clean up test fixtures."""
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def test_validate_and_create_output_path_empty_input(self):
        """Test path validation with empty input."""
        result = common.validate_and_create_output_path("")
        self.assertIsNone(result)

        result = common.validate_and_create_output_path(None)
        self.assertIsNone(result)

        result = common.validate_and_create_output_path("   ")
        self.assertIsNone(result)

    def test_validate_and_create_output_path_existing_directory(self):
        """Test path validation with existing directory."""
        result = common.validate_and_create_output_path(self.test_valid_path)
        self.assertEqual(result, self.test_valid_path)

    @patch('utils.common.make_gen_dir_path')
    @patch('utils.common.check_exists_dir')
    def test_validate_and_create_output_path_create_new(self, mock_check_exists, mock_make_dir):
        """Test path validation with directory creation."""
        mock_check_exists.return_value = False
        mock_make_dir.return_value = "/created/path"

        result = common.validate_and_create_output_path("/new/path")

        self.assertEqual(result, "/created/path")
        mock_check_exists.assert_called_once_with("/new/path")
        mock_make_dir.assert_called_once_with("/new/path")

    @patch('utils.common.make_gen_dir_path')
    @patch('utils.common.check_exists_dir')
    def test_validate_and_create_output_path_creation_fails(self, mock_check_exists, mock_make_dir):
        """Test path validation when directory creation fails."""
        mock_check_exists.return_value = False
        mock_make_dir.return_value = None

        result = common.validate_and_create_output_path("/failed/path")

        self.assertIsNone(result)


class TestIntegrationRefactoredFeatures(unittest.TestCase):
    """Integration tests for refactored features working together."""

    def setUp(self):
        """Set up test fixtures."""
        self.test_serial = "integration_test_device"

    @patch('utils.adb_tools._get_device_property')
    def test_device_info_extraction_integration(self, mock_get_property):
        """Test integration of device info extraction with new architecture."""
        # Mock the property getter calls
        mock_get_property.side_effect = [
            "Physical density: 320",  # screen_density
            "Physical size: 1080x1920",  # screen_size
            "arm64-v8a"  # cpu_arch
        ]

        # Mock battery info
        with patch('utils.adb_tools.common.run_command') as mock_run_command:
            mock_run_command.return_value = [
                "Current Battery Service state:",
                "  level: 75",
                "  scale: 100"
            ]

            result = adb_tools.get_additional_device_info(self.test_serial)

            # Verify integration results
            self.assertIsInstance(result, dict)
            self.assertEqual(result['screen_density'], "Physical density: 320")
            self.assertEqual(result['screen_size'], "Physical size: 1080x1920")
            self.assertEqual(result['cpu_arch'], "arm64-v8a")
            self.assertEqual(result['battery_level'], "75%")

    def test_command_builder_decorator_integration(self):
        """Test integration of command builders with error handling decorators."""
        # This test verifies that command builders work with decorated functions

        @adb_tools.adb_device_operation(default_return="command_error")
        def test_decorated_command_function(serial_num):
            cmd = adb_commands.cmd_get_android_version(serial_num)
            # Simulate command execution
            if "test_device" in cmd:
                return f"Android 13 via {cmd}"
            else:
                raise Exception("Invalid command")

        # Test with valid scenario
        result = test_decorated_command_function("test_device")
        self.assertIn("Android 13 via", result)
        self.assertIn("adb -s test_device shell getprop", result)


if __name__ == '__main__':
    unittest.main()