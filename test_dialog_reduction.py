#!/usr/bin/env python3
"""
Test dialog reduction in Bug Report functionality
"""

import sys
import os
import tempfile
from unittest.mock import patch

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils import adb_models, file_generation_utils


def test_single_completion_dialog():
    """Test that bug report generation shows only one completion dialog"""
    print("🧪 Testing single completion dialog")

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

        # Track callback calls
        callback_calls = []

        def mock_callback(title, message, progress, icon):
            callback_calls.append({
                'title': title,
                'message': message,
                'progress': progress,
                'icon': icon
            })

        # Mock successful bug report generation
        with patch('utils.adb_tools.generate_bug_report_device') as mock_generate:
            mock_generate.return_value = {
                'success': True,
                'file_size': 512000,
                'output_path': '/tmp/mock_report.zip',
                'execution_time': 45.2
            }

            # Mock file existence check for completion count
            with patch('os.path.exists', return_value=True):
                # Create temporary directory
                with tempfile.TemporaryDirectory() as temp_dir:
                    # Start batch generation
                    file_generation_utils.generate_bug_report_batch(
                        devices, temp_dir, mock_callback
                    )

                    # Wait for completion
                    import time
                    time.sleep(0.5)

                    # Check callback calls - should only have completion dialog
                    completion_calls = [call for call in callback_calls if 'Complete' in call['title']]
                    progress_calls = [call for call in callback_calls if 'Progress' in call['title']]

                    if len(completion_calls) == 1 and len(progress_calls) == 0:
                        print("✅ Only single completion dialog shown")
                        print(f"   Completion message: {completion_calls[0]['message']}")
                        return True
                    else:
                        print("❌ Multiple dialogs detected")
                        print(f"   Completion dialogs: {len(completion_calls)}")
                        print(f"   Progress dialogs: {len(progress_calls)}")
                        print(f"   All callbacks: {callback_calls}")
                        return False

    except Exception as e:
        print(f"❌ Dialog reduction test failed: {e}")
        return False


def test_log_only_progress():
    """Test that progress is logged instead of shown in dialogs"""
    print("🧪 Testing log-only progress tracking")

    try:
        # Create test device
        device = adb_models.DeviceInfo(
            device_serial_num="test-001",
            device_usb="usb:1",
            device_prod="product_1",
            device_model="TestDevice1",
            android_ver="11.0",
            android_api_level="30",
            gms_version="21.15.16",
            wifi_is_on=True,
            bt_is_on=False,
            build_fingerprint="test/build/1:11/RKQ1.1/user"
        )

        # Capture logs
        import logging
        log_messages = []

        class TestHandler(logging.Handler):
            def emit(self, record):
                log_messages.append(record.getMessage())

        # Add test handler to logger
        logger = logging.getLogger('file_generation')
        test_handler = TestHandler()
        logger.addHandler(test_handler)
        logger.setLevel(logging.INFO)

        # Mock successful generation
        with patch('utils.adb_tools.generate_bug_report_device') as mock_generate:
            mock_generate.return_value = {
                'success': True,
                'file_size': 512000,
                'output_path': '/tmp/mock_report.zip',
                'execution_time': 45.2
            }

            with tempfile.TemporaryDirectory() as temp_dir:
                # Run without callback to test logging only
                file_generation_utils.generate_bug_report_batch([device], temp_dir)

                # Wait for completion
                import time
                time.sleep(0.3)

                # Check if progress was logged
                progress_logs = [msg for msg in log_messages if 'Generating bug report' in msg]
                completion_logs = [msg for msg in log_messages if 'Bug report generated' in msg]

                if len(progress_logs) >= 1 and len(completion_logs) >= 1:
                    print("✅ Progress tracked in logs only")
                    print(f"   Progress logs: {len(progress_logs)}")
                    print(f"   Completion logs: {len(completion_logs)}")
                    return True
                else:
                    print("❌ Progress not properly logged")
                    print(f"   All logs: {log_messages}")
                    return False

        # Clean up handler
        logger.removeHandler(test_handler)

    except Exception as e:
        print(f"❌ Log progress test failed: {e}")
        return False


if __name__ == "__main__":
    print("🔧 Dialog Reduction Test")
    print("=" * 30)

    tests = [
        ("Single Completion Dialog", test_single_completion_dialog),
        ("Log-Only Progress", test_log_only_progress)
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
        print("🎉 Dialog reduction successful!")
        print("\n💡 Improvements:")
        print("  - Single completion dialog instead of multiple progress dialogs")
        print("  - Progress tracked in logs for debugging")
        print("  - Cleaner user experience with fewer interruptions")
    else:
        print("⚠️ Some tests failed, check the implementation")