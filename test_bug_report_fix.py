#!/usr/bin/env python3
"""
Test Bug Report functionality fixes
"""

import sys
import os
import tempfile
from unittest.mock import MagicMock, patch

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils import adb_models, adb_commands, adb_tools, file_generation_utils


def test_bug_report_command_format():
    """Test if bug report command uses modern format with .zip extension"""
    print("🧪 Testing bug report command format")

    try:
        # Test with .zip extension
        cmd1 = adb_commands.cmd_output_device_bug_report("test-device", "/tmp/bugreport.zip")
        expected1 = 'adb -s test-device bugreport "/tmp/bugreport.zip"'

        # Test without .zip extension (should be added)
        cmd2 = adb_commands.cmd_output_device_bug_report("test-device", "/tmp/bugreport")
        expected2 = 'adb -s test-device bugreport "/tmp/bugreport.zip"'

        if cmd1 == expected1 and cmd2 == expected2:
            print("✅ Bug report command format is correct")
            print(f"   With .zip: {cmd1}")
            print(f"   Auto .zip: {cmd2}")
            return True
        else:
            print("❌ Bug report command format is incorrect")
            print(f"   Expected: {expected1}")
            print(f"   Got: {cmd1}")
            return False

    except Exception as e:
        print(f"❌ Bug report command test failed: {e}")
        return False


def test_enhanced_bug_report_generation():
    """Test enhanced bug report generation function"""
    print("🧪 Testing enhanced bug report generation")

    try:
        # Mock subprocess.run to simulate successful bug report generation
        with patch('subprocess.run') as mock_run:
            # Mock successful command execution
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = "Bug report captured successfully"
            mock_run.return_value.stderr = ""

            # Mock file creation
            with patch('os.path.exists', return_value=True):
                with patch('os.path.getsize', return_value=1024000):  # 1MB file
                    result = adb_tools.generate_bug_report_device(
                        "test-device",
                        "/tmp/test_bugreport.zip",
                        timeout=300
                    )

            # Verify result structure
            if (result['success'] and
                result.get('file_size') == 1024000 and
                result.get('output_path') == "/tmp/test_bugreport.zip"):
                print("✅ Enhanced bug report generation works correctly")
                print(f"   Success: {result['success']}")
                print(f"   File size: {result.get('file_size')} bytes")
                return True
            else:
                print("❌ Enhanced bug report generation failed")
                print(f"   Result: {result}")
                return False

    except Exception as e:
        print(f"❌ Enhanced bug report generation test failed: {e}")
        return False


def test_file_generation_batch_processing():
    """Test batch bug report generation with enhanced progress tracking"""
    print("🧪 Testing batch bug report generation")

    try:
        # Create test devices
        devices = []
        for i in range(3):
            device = adb_models.DeviceInfo(
                device_serial_num=f"test-{i:03d}",
                device_usb=f"usb:{i}",
                device_prod=f"product_{i}",
                device_model=f"TestDevice{i}",
                android_ver="11.0",
                android_api_level="30",
                gms_version="21.15.16",
                wifi_is_on=True,
                bt_is_on=False,
                build_fingerprint=f"test/build/{i}:11/RKQ1.{i}/user"
            )
            devices.append(device)

        # Mock callback to track progress
        progress_calls = []

        def mock_callback(title, message, progress, icon):
            progress_calls.append({
                'title': title,
                'message': message,
                'progress': progress,
                'icon': icon
            })

        # Mock the enhanced bug report generation
        with patch('utils.adb_tools.generate_bug_report_device') as mock_generate:
            mock_generate.return_value = {
                'success': True,
                'file_size': 512000,
                'output_path': '/tmp/mock_report.zip',
                'execution_time': 45.2
            }

            # Create temporary directory
            with tempfile.TemporaryDirectory() as temp_dir:
                # Start batch generation (in background thread)
                file_generation_utils.generate_bug_report_batch(
                    devices, temp_dir, mock_callback
                )

                # Wait a moment for thread to start and execute
                import time
                time.sleep(0.5)

                # Check if generation was called correctly
                if mock_generate.call_count == len(devices):
                    print("✅ Batch bug report generation called for all devices")
                    print(f"   Generated for {mock_generate.call_count} devices")
                    return True
                else:
                    print("❌ Batch bug report generation incomplete")
                    print(f"   Expected: {len(devices)}, Got: {mock_generate.call_count}")
                    return False

    except Exception as e:
        print(f"❌ Batch bug report generation test failed: {e}")
        return False


def test_error_handling():
    """Test error handling in bug report generation"""
    print("🧪 Testing error handling")

    try:
        # Test with failed command execution
        with patch('subprocess.run') as mock_run:
            # Mock failed command execution
            mock_run.return_value.returncode = 1
            mock_run.return_value.stdout = ""
            mock_run.return_value.stderr = "Permission denied"

            result = adb_tools.generate_bug_report_device(
                "invalid-device",
                "/tmp/failed_report.zip",
                timeout=300
            )

            # Verify error handling
            if (not result['success'] and
                'Permission denied' in result.get('error', '')):
                print("✅ Error handling works correctly")
                print(f"   Error captured: {result.get('error')}")
                return True
            else:
                print("❌ Error handling failed")
                print(f"   Result: {result}")
                return False

    except Exception as e:
        print(f"❌ Error handling test failed: {e}")
        return False


if __name__ == "__main__":
    print("🔧 Bug Report Functionality Fix Tests")
    print("=" * 50)

    tests = [
        ("Bug Report Command Format", test_bug_report_command_format),
        ("Enhanced Bug Report Generation", test_enhanced_bug_report_generation),
        ("Batch Processing", test_file_generation_batch_processing),
        ("Error Handling", test_error_handling)
    ]

    passed = 0
    total = len(tests)

    for test_name, test_func in tests:
        print(f"\n🧪 {test_name}:")
        try:
            if test_func():
                passed += 1
            else:
                print("   Test failed")
        except Exception as e:
            print(f"   Test exception: {e}")

    print(f"\n📊 Test Results: {passed}/{total} passed")

    if passed == total:
        print("🎉 All Bug Report functionality tests passed!")
        print("\n💡 Improvements implemented:")
        print("  - Modern .zip format for bug reports")
        print("  - Enhanced error handling with detailed messages")
        print("  - File size validation and timeout support")
        print("  - Better progress tracking in batch operations")
        print("  - Improved logging with execution time tracking")
    else:
        print("⚠️  Some tests failed, check the implementation")