#!/usr/bin/env python3
"""
Test manufacturer-specific bug report handling
"""

import sys
from pathlib import Path
import tempfile
from unittest.mock import patch, MagicMock

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from utils import adb_models, adb_tools, file_generation_utils


def create_test_device(model_name: str, serial_num: str) -> adb_models.DeviceInfo:
    """Create test device with specific model"""
    return adb_models.DeviceInfo(
        device_serial_num=serial_num,
        device_usb="usb:1",
        device_prod="product_1",
        device_model=model_name,
        android_ver="11.0",
        android_api_level="30",
        gms_version="21.15.16",
        wifi_is_on=True,
        bt_is_on=False,
        build_fingerprint="test/build/1:11/RKQ1.1/user"
    )


def test_samsung_device_detection():
    """Test Samsung device detection and special handling"""
    print("🧪 Testing Samsung device detection")

    try:
        # Mock Samsung device manufacturer info
        with patch('utils.adb_tools._get_device_manufacturer_info') as mock_manufacturer:
            mock_manufacturer.return_value = {'manufacturer': 'samsung', 'model': 'SM-G991B'}

            # Mock permission check to fail (common Samsung issue)
            with patch('utils.adb_tools._check_bug_report_permissions', return_value=False):
                with patch('utils.adb_tools._is_device_available', return_value=True):
                    result = adb_tools.generate_bug_report_device(
                        "samsung-test",
                        "/tmp/samsung_report.zip",
                        timeout=300
                    )

                    if (not result['success'] and
                        'Samsung' in result.get('error', '') and
                        'developer options' in result.get('error', '').lower()):
                        print("✅ Samsung device permission issue correctly detected")
                        print(f"   Error message: {result.get('error')}")
                        return True
                    else:
                        print("❌ Samsung device handling failed")
                        print(f"   Result: {result}")
                        return False

    except Exception as e:
        print(f"❌ Samsung device test failed: {e}")
        return False


def test_manufacturer_specific_guidance():
    """Test manufacturer-specific guidance in batch processing"""
    print("🧪 Testing manufacturer-specific guidance")

    try:
        # Create devices from different manufacturers
        manufacturers = [
            ("Samsung Galaxy S21", "samsung"),
            ("Huawei P40", "huawei"),
            ("Xiaomi Mi 11", "xiaomi"),
            ("OnePlus 9", "oneplus"),
            ("OPPO Find X3", "oppo"),
            ("Vivo X60", "vivo")
        ]

        devices = []
        for model, _ in manufacturers:
            device = create_test_device(model, f"test-{model.lower().replace(' ', '-')}")
            devices.append(device)

        # Capture log messages
        import logging
        log_messages = []

        class TestHandler(logging.Handler):
            def emit(self, record):
                log_messages.append(record.getMessage())

        # Add test handler
        logger = logging.getLogger('file_generation')
        test_handler = TestHandler()
        logger.addHandler(test_handler)
        logger.setLevel(logging.INFO)

        # Mock bug report generation to always fail (to test guidance)
        with patch('utils.adb_tools.generate_bug_report_device') as mock_generate:
            mock_generate.side_effect = Exception("Permission denied")

            with tempfile.TemporaryDirectory() as temp_dir:
                # Run batch processing
                file_generation_utils.generate_bug_report_batch(devices, temp_dir)

                # Wait for completion
                import time
                time.sleep(0.5)

                # Check if manufacturer-specific guidance was logged
                guidance_logs = [msg for msg in log_messages if 'may require' in msg]

                expected_guidance = ['Samsung', 'Huawei', 'Xiaomi', 'OnePlus', 'Vivo']
                found_guidance = sum(1 for guidance in expected_guidance
                                   if any(guidance in log for log in guidance_logs))

                if found_guidance >= 3:  # At least 3 different manufacturers
                    print("✅ Manufacturer-specific guidance provided")
                    print(f"   Guidance for {found_guidance} manufacturers")
                    for log in guidance_logs[:3]:  # Show first 3 examples
                        print(f"   Example: {log}")
                    return True
                else:
                    print("❌ Insufficient manufacturer guidance")
                    print(f"   Found guidance for {found_guidance} manufacturers")
                    print(f"   All logs: {log_messages}")
                    return False

        # Clean up handler
        logger.removeHandler(test_handler)

    except Exception as e:
        print(f"❌ Manufacturer guidance test failed: {e}")
        return False


def test_permission_check_function():
    """Test permission check function with different scenarios"""
    print("🧪 Testing permission check function")

    try:
        # Test successful permission check
        with patch('utils.common.run_command') as mock_command:
            # Mock successful shell commands
            mock_command.side_effect = [
                ['permission_test'],  # Echo test
                ['service.manager', 'service.bluetooth']  # Service list
            ]

            result = adb_tools._check_bug_report_permissions("test-device")
            if result:
                print("✅ Permission check correctly identifies sufficient permissions")
            else:
                print("❌ Permission check failed with good permissions")
                return False

            # Test failed permission check
            mock_command.side_effect = [
                [],  # Failed echo test
                []   # Failed service list
            ]

            result = adb_tools._check_bug_report_permissions("test-device")
            if not result:
                print("✅ Permission check correctly identifies insufficient permissions")
                return True
            else:
                print("❌ Permission check passed with bad permissions")
                return False

    except Exception as e:
        print(f"❌ Permission check test failed: {e}")
        return False


def test_manufacturer_info_extraction():
    """Test manufacturer info extraction"""
    print("🧪 Testing manufacturer info extraction")

    try:
        # Mock getprop commands
        with patch('utils.common.run_command') as mock_command:
            mock_command.side_effect = [
                ['samsung'],  # ro.product.manufacturer
                ['SM-G991B']  # ro.product.model
            ]

            result = adb_tools._get_device_manufacturer_info("test-device")

            if (result.get('manufacturer') == 'samsung' and
                result.get('model') == 'SM-G991B'):
                print("✅ Manufacturer info correctly extracted")
                print(f"   Manufacturer: {result.get('manufacturer')}")
                print(f"   Model: {result.get('model')}")
                return True
            else:
                print("❌ Manufacturer info extraction failed")
                print(f"   Result: {result}")
                return False

    except Exception as e:
        print(f"❌ Manufacturer info test failed: {e}")
        return False


if __name__ == "__main__":
    print("🔧 Manufacturer-Specific Bug Report Tests")
    print("=" * 45)

    tests = [
        ("Samsung Device Detection", test_samsung_device_detection),
        ("Manufacturer Guidance", test_manufacturer_specific_guidance),
        ("Permission Check Function", test_permission_check_function),
        ("Manufacturer Info Extraction", test_manufacturer_info_extraction)
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
        print("🎉 All manufacturer-specific handling tests passed!")
        print("\n💡 Enhanced features:")
        print("  - Samsung/Huawei/Xiaomi/OPPO/Vivo device detection")
        print("  - Manufacturer-specific permission guidance")
        print("  - Pre-flight permission checks")
        print("  - Detailed troubleshooting information")
        print("\n📱 Supported manufacturers:")
        print("  - Samsung (Galaxy series)")
        print("  - Huawei/Honor (EMUI/Magic UI)")
        print("  - Xiaomi/Redmi (MIUI)")
        print("  - OPPO/OnePlus/Realme (ColorOS/OxygenOS)")
        print("  - Vivo (FunTouch OS)")
    else:
        print("⚠️ Some tests failed, check manufacturer handling")
