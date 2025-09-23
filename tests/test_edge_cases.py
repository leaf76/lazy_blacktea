#!/usr/bin/env python3
"""
Edge case tests for refactored features.
Tests unusual scenarios, error conditions, and boundary cases.
"""

import sys
import os
import unittest
from unittest.mock import Mock, patch, MagicMock
import tempfile
import time

# Add the project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils import adb_tools, adb_commands, common


class TestErrorHandlingEdgeCases(unittest.TestCase):
    """Test edge cases in error handling decorators."""

    def test_decorator_with_none_operation_name(self):
        """Test decorator behavior when operation_name is None."""
        @adb_tools.adb_operation(operation_name=None, default_return="default")
        def test_function():
            raise Exception("Test error")

        result = test_function()
        self.assertEqual(result, "default")

    def test_decorator_with_nested_exceptions(self):
        """Test decorator handling nested exceptions."""
        @adb_tools.adb_operation(default_return="nested_error")
        def test_function():
            try:
                raise ValueError("Inner exception")
            except ValueError:
                raise RuntimeError("Outer exception")

        result = test_function()
        self.assertEqual(result, "nested_error")

    def test_decorator_with_keyboard_interrupt(self):
        """Test decorator behavior with KeyboardInterrupt (should not catch)."""
        @adb_tools.adb_operation(default_return="should_not_reach")
        def test_function():
            raise KeyboardInterrupt("User interrupt")

        with self.assertRaises(KeyboardInterrupt):
            test_function()

    def test_decorator_with_system_exit(self):
        """Test decorator behavior with SystemExit (should not catch)."""
        @adb_tools.adb_operation(default_return="should_not_reach")
        def test_function():
            raise SystemExit("System exit")

        with self.assertRaises(SystemExit):
            test_function()

    def test_device_operation_decorator_with_no_serial(self):
        """Test device operation decorator when no serial number provided."""
        @adb_tools.adb_device_operation(default_return="no_serial_error")
        def test_function(serial_num):
            # Simulate missing serial number
            raise TypeError("Missing required argument: serial_num")

        result = test_function("test_serial")
        self.assertEqual(result, "no_serial_error")

    def test_decorator_log_errors_disabled(self):
        """Test decorator with error logging disabled."""
        @adb_tools.adb_operation(default_return="silent_error", log_errors=False)
        def test_function():
            raise Exception("This should not be logged")

        # The test mainly ensures no exception is raised and logging is suppressed
        result = test_function()
        self.assertEqual(result, "silent_error")


class TestADBCommandBuilderEdgeCases(unittest.TestCase):
    """Test edge cases in ADB command building."""

    def test_build_command_with_empty_serial(self):
        """Test command building with empty serial number."""
        result = adb_commands._build_adb_command("", 'shell', 'ps')
        # Should handle empty serial by omitting the -s flag
        self.assertIn('adb shell ps', result)

    def test_build_command_with_special_characters_in_serial(self):
        """Test command building with special characters in serial."""
        special_serial = "device-123_test.serial"
        result = adb_commands._build_adb_command(special_serial, 'shell', 'ps')
        self.assertIn(f'adb -s {special_serial} shell ps', result)

    def test_build_command_with_no_parts(self):
        """Test command building with no command parts."""
        result = adb_commands._build_adb_command("test_serial")
        self.assertIn('adb -s test_serial', result)

    def test_build_command_with_many_parts(self):
        """Test command building with many command parts."""
        parts = ['shell', 'dumpsys', 'activity', 'service', 'com.example.service']
        result = adb_commands._build_adb_command("test_serial", *parts)
        for part in parts:
            self.assertIn(part, result)

    def test_build_shell_command_with_complex_shell_command(self):
        """Test building shell command with complex shell syntax."""
        complex_command = "find /system -name '*.apk' | head -5"
        result = adb_commands._build_adb_shell_command("test_serial", complex_command)
        self.assertIn(complex_command, result)

    def test_build_command_with_quotes_in_arguments(self):
        """Test command building with quoted arguments."""
        quoted_path = '"/path/with spaces/file.apk"'
        result = adb_commands.cmd_adb_install("test_serial", quoted_path)
        self.assertIn(quoted_path, result)

    def test_getprop_command_with_nonexistent_property(self):
        """Test getprop command building with non-existent property."""
        fake_property = "ro.nonexistent.property.fake"
        result = adb_commands._build_getprop_command("test_serial", fake_property)
        self.assertIn(fake_property, result)

    def test_setting_getter_with_unusual_setting_key(self):
        """Test setting getter with unusual setting key."""
        unusual_key = "very_long_setting_key_that_might_not_exist_but_should_work"
        result = adb_commands._build_setting_getter_command("test_serial", unusual_key)
        self.assertIn(unusual_key, result)


class TestDevicePropertyExtractionEdgeCases(unittest.TestCase):
    """Test edge cases in device property extraction."""

    @patch('utils.adb_tools.common.run_command')
    @patch('utils.adb_tools.adb_commands.cmd_adb_shell')
    def test_get_device_property_with_multiline_output(self, mock_cmd_shell, mock_run_command):
        """Test property extraction with multiline output."""
        mock_cmd_shell.return_value = "test_command"
        mock_run_command.return_value = [
            "Line 1: Some info",
            "Line 2: More info",
            "Line 3: Final info"
        ]

        result = adb_tools._get_device_property("test_serial", 'complex_property')
        # Should return the first line only
        self.assertEqual(result, "Line 1: Some info")

    @patch('utils.adb_tools.common.run_command')
    @patch('utils.adb_tools.adb_commands.cmd_adb_shell')
    def test_get_device_property_with_whitespace_output(self, mock_cmd_shell, mock_run_command):
        """Test property extraction with whitespace in output."""
        mock_cmd_shell.return_value = "test_command"
        mock_run_command.return_value = ["   whitespace value   "]

        result = adb_tools._get_device_property("test_serial", 'whitespace_property')
        # Should be stripped
        self.assertEqual(result, "whitespace value")

    @patch('utils.adb_tools.common.run_command')
    @patch('utils.adb_tools.adb_commands.cmd_adb_shell')
    def test_get_device_property_with_unicode_output(self, mock_cmd_shell, mock_run_command):
        """Test property extraction with Unicode characters."""
        mock_cmd_shell.return_value = "test_command"
        unicode_output = "设备型号: Pixel测试"
        mock_run_command.return_value = [unicode_output]

        result = adb_tools._get_device_property("test_serial", 'unicode_property')
        self.assertEqual(result, unicode_output)

    @patch('utils.adb_tools.common.run_command')
    def test_get_additional_device_info_with_malformed_battery_output(self, mock_run_command):
        """Test additional device info with malformed battery output."""
        mock_run_command.side_effect = [
            ["Physical density: 420"],  # screen_density
            ["Physical size: 1440x3120"],  # screen_size
            ["arm64-v8a"],  # cpu_arch
            # Malformed battery output
            ["Malformed battery output", "no level info", "random: data"]
        ]

        with patch('utils.adb_tools._get_device_property') as mock_get_property:
            mock_get_property.side_effect = [
                "Physical density: 420",
                "Physical size: 1440x3120",
                "arm64-v8a"
            ]

            result = adb_tools.get_additional_device_info("test_serial")

            # Should have defaults for battery info
            self.assertEqual(result['battery_level'], 'Unknown')
            self.assertEqual(result['battery_capacity_mah'], 'Unknown')

    @patch('utils.adb_tools._get_device_property')
    def test_get_additional_device_info_with_partial_battery_data(self, mock_get_property):
        """Test additional device info with partial battery data."""
        mock_get_property.side_effect = [
            "Physical density: 420",  # screen_density
            "Physical size: 1440x3120",  # screen_size
            "arm64-v8a"  # cpu_arch
        ]

        # Mock battery info
        with patch('utils.adb_tools.common.run_command') as mock_run_command:
            mock_run_command.return_value = [
                "Current Battery Service state:",
                "  level: 42",
                "  scale: 100"
            ]

            result = adb_tools.get_additional_device_info("test_serial")

            self.assertEqual(result['battery_level'], '42%')
            # Should have Unknown for missing capacity data
            self.assertEqual(result['battery_capacity_mah'], 'Unknown')
            self.assertEqual(result['battery_dou_hours'], 'Unknown')


class TestParallelExecutionEdgeCases(unittest.TestCase):
    """Test edge cases in parallel execution."""

    def test_parallel_execution_with_single_command(self):
        """Test parallel execution with just one command."""
        with patch('utils.adb_tools.common.run_command') as mock_run_command:
            mock_run_command.return_value = ["single_result"]

            result = adb_tools._execute_commands_parallel(["single_command"], "single_test")

            self.assertEqual(len(result), 1)
            self.assertEqual(result[0], ["single_result"])

    def test_parallel_execution_with_very_fast_functions(self):
        """Test parallel execution with very fast functions (no delay)."""
        def instant_function(arg):
            return f"instant_{arg}"

        functions = [instant_function] * 100
        args_list = [(i,) for i in range(100)]

        start_time = time.time()
        result = adb_tools._execute_functions_parallel(functions, args_list, "instant_test")
        execution_time = time.time() - start_time

        self.assertEqual(len(result), 100)
        # Should complete very quickly
        self.assertLess(execution_time, 1.0)

    def test_parallel_execution_with_mixed_execution_times(self):
        """Test parallel execution with functions of varying execution times."""
        def variable_time_function(delay):
            time.sleep(delay / 1000.0)  # Convert ms to seconds
            return f"completed_after_{delay}ms"

        # Functions with delays: 10ms, 50ms, 100ms, 5ms, 200ms
        delays = [10, 50, 100, 5, 200]
        functions = [variable_time_function] * len(delays)
        args_list = [(delay,) for delay in delays]

        start_time = time.time()
        result = adb_tools._execute_functions_parallel(functions, args_list, "variable_time_test")
        execution_time = time.time() - start_time

        self.assertEqual(len(result), len(delays))
        # Should complete in roughly the time of the slowest function (200ms)
        # Plus some overhead, so should be less than 500ms
        self.assertLess(execution_time, 0.5)

    def test_parallel_execution_all_functions_fail(self):
        """Test parallel execution when all functions fail."""
        def failing_function(arg):
            raise Exception(f"Function {arg} failed")

        functions = [failing_function] * 5
        args_list = [(i,) for i in range(5)]

        result = adb_tools._execute_functions_parallel(functions, args_list, "all_fail_test")

        # All results should be None due to exceptions
        self.assertEqual(len(result), 5)
        self.assertTrue(all(r is None for r in result))

    def test_parallel_execution_with_recursive_calls(self):
        """Test parallel execution with functions that make recursive calls."""
        def recursive_function(depth):
            if depth <= 0:
                return "base_case"
            return f"depth_{depth}_" + recursive_function(depth - 1)

        functions = [recursive_function] * 3
        args_list = [(2,), (3,), (1,)]

        result = adb_tools._execute_functions_parallel(functions, args_list, "recursive_test")

        self.assertEqual(len(result), 3)
        expected_results = [
            "depth_2_depth_1_base_case",
            "depth_3_depth_2_depth_1_base_case",
            "depth_1_base_case"
        ]
        for expected in expected_results:
            self.assertIn(expected, result)


class TestPathValidationEdgeCases(unittest.TestCase):
    """Test edge cases in path validation."""

    def test_validate_path_with_very_long_path(self):
        """Test path validation with extremely long path."""
        # Create a very long path (over 255 characters)
        long_path = "/very/long/path/" + "directory/" * 50 + "final"

        with patch('utils.common.check_exists_dir') as mock_check:
            mock_check.return_value = False
            with patch('utils.common.make_gen_dir_path') as mock_make:
                mock_make.return_value = None  # Simulate failure

                result = common.validate_and_create_output_path(long_path)
                self.assertIsNone(result)

    def test_validate_path_with_special_characters(self):
        """Test path validation with special characters."""
        special_paths = [
            "/path/with spaces/directory",
            "/path/with-dashes/directory",
            "/path/with_underscores/directory",
            "/path/with.dots/directory",
            "/path/with(parentheses)/directory"
        ]

        for path in special_paths:
            with patch('utils.common.check_exists_dir') as mock_check:
                mock_check.return_value = True

                result = common.validate_and_create_output_path(path)
                self.assertEqual(result, path)

    def test_validate_path_with_unicode_characters(self):
        """Test path validation with Unicode characters."""
        unicode_path = "/路径/测试/目录"

        with patch('utils.common.check_exists_dir') as mock_check:
            mock_check.return_value = True

            result = common.validate_and_create_output_path(unicode_path)
            self.assertEqual(result, unicode_path)

    def test_validate_path_with_only_whitespace_variations(self):
        """Test path validation with various whitespace-only inputs."""
        whitespace_inputs = [
            "   ",
            "\t\t",
            "\n\n",
            "\r\r",
            " \t\n\r ",
            ""
        ]

        for whitespace in whitespace_inputs:
            result = common.validate_and_create_output_path(whitespace)
            self.assertIsNone(result, f"Should return None for whitespace input: '{repr(whitespace)}'")


class TestIntegrationEdgeCases(unittest.TestCase):
    """Test edge cases in integration scenarios."""

    def test_device_info_with_disconnected_device_during_execution(self):
        """Test device info extraction when device disconnects during execution."""
        with patch('utils.adb_tools.common.run_command') as mock_run_command:
            # First call succeeds, subsequent calls fail
            mock_run_command.side_effect = [
                ["Physical density: 420"],  # Success
                Exception("device 'test_serial' not found"),  # Device disconnected
                Exception("device 'test_serial' not found"),  # Still disconnected
                Exception("device 'test_serial' not found")   # Still disconnected
            ]

            # Should handle errors gracefully
            result = adb_tools.get_additional_device_info("test_serial")

            # Should have some data from successful calls and defaults for failed ones
            self.assertIsInstance(result, dict)
            self.assertIn('screen_density', result)
            self.assertIn('cpu_arch', result)

    def test_parallel_execution_with_resource_contention(self):
        """Test parallel execution under resource contention simulation."""
        import threading

        # Simulate resource contention with a shared counter
        shared_counter = {'value': 0}
        lock = threading.Lock()

        def contended_function(task_id):
            # Simulate resource contention
            for _ in range(10):
                with lock:
                    shared_counter['value'] += 1
                time.sleep(0.001)  # Small delay to increase contention
            return f"task_{task_id}_final_count_{shared_counter['value']}"

        functions = [contended_function] * 10
        args_list = [(i,) for i in range(10)]

        result = adb_tools._execute_functions_parallel(functions, args_list, "contention_test")

        # All tasks should complete despite contention
        self.assertEqual(len(result), 10)
        self.assertTrue(all(r is not None for r in result))

        # The final counter value should be 100 (10 tasks × 10 increments)
        self.assertEqual(shared_counter['value'], 100)


if __name__ == '__main__':
    unittest.main(verbosity=2)