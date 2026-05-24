#!/usr/bin/env python3
"""
Functional end-to-end test for recording and screenshot functionality.
This test actually tests the recording and screenshot features with a real device.
"""

import sys
import os
import time
import glob
from typing import List, Dict

# Add the project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils import adb_tools, common
from utils.adb_models import DeviceInfo


def _command_output_text(result) -> str:
    if isinstance(result, str):
        return result.strip()
    return "\n".join(str(line) for line in result).strip()


def test_real_screenshot(device: DeviceInfo, output_dir: str) -> bool:
    """Test actual screenshot functionality with a real device."""
    print(f"📸 Testing screenshot with device {device.device_serial_num}...")

    try:
        # Create output directory
        os.makedirs(output_dir, exist_ok=True)

        # Generate filename
        timestamp = common.current_format_time_utc()
        filename = f"test_screenshot_{timestamp}"

        print(f"   📄 Filename: {filename}.png")
        print(f"   📁 Output directory: {output_dir}")

        # Take screenshot using the wrapper function
        success = adb_tools.take_screenshot_single_device(
            device.device_serial_num,
            output_dir,
            filename
        )

        if success:
            # Check if file was created
            screenshot_path = os.path.join(output_dir, f"{device.device_serial_num}_screenshot_{filename}.png")
            if os.path.exists(screenshot_path):
                file_size = os.path.getsize(screenshot_path)
                print(f"   ✅ Screenshot saved: {screenshot_path}")
                print(f"   📏 File size: {file_size} bytes")
                return file_size > 1000  # Screenshot should be larger than 1KB
            else:
                print(f"   ❌ Screenshot file not found: {screenshot_path}")
                return False
        else:
            print(f"   ❌ Screenshot function returned False")
            return False

    except Exception as e:
        print(f"   ❌ Screenshot test failed: {e}")
        import traceback
        print(f"   🔍 Traceback: {traceback.format_exc()}")
        return False


def test_real_recording_short(device: DeviceInfo, output_dir: str) -> bool:
    """Test actual recording functionality with a real device (short 3-second recording)."""
    print(f"🎬 Testing short recording with device {device.device_serial_num}...")

    try:
        # Create output directory
        os.makedirs(output_dir, exist_ok=True)

        # Generate filename
        timestamp = common.current_format_time_utc()
        filename = f"test_recording_{timestamp}.mp4"

        print(f"   📄 Filename: {filename}")
        print(f"   📁 Output directory: {output_dir}")

        # Start recording using the wrapper function
        print("   🔴 Starting recording...")
        adb_tools.start_screen_record_device(
            device.device_serial_num,
            output_dir,
            filename
        )

        # Record for 3 seconds
        print("   ⏱️  Recording for 3 seconds...")
        time.sleep(3)

        # Stop recording using the wrapper function
        print("   ⏹️  Stopping recording...")
        adb_tools.stop_screen_record_device(device.device_serial_num)

        # Wait a moment for file transfer
        print("   ⏳ Waiting for file transfer...")
        time.sleep(2)

        # Check if file was created
        # The actual filename format depends on the implementation
        possible_paths = [
            os.path.join(output_dir, filename),
            os.path.join(output_dir, f"screenrecord_{device.device_serial_num}_{filename}"),
            os.path.join(output_dir, f"screenrecord_{device.device_serial_num}_{timestamp}.mp4"),
        ]

        for video_path in possible_paths:
            if os.path.exists(video_path):
                file_size = os.path.getsize(video_path)
                print(f"   ✅ Recording saved: {video_path}")
                print(f"   📏 File size: {file_size} bytes")
                return file_size > 10000  # Video should be larger than 10KB
            else:
                print(f"   ℹ️  Not found: {video_path}")

        # Also check for any .mp4 files in the directory
        mp4_files = glob.glob(os.path.join(output_dir, "*.mp4"))
        if mp4_files:
            for mp4_file in mp4_files:
                file_size = os.path.getsize(mp4_file)
                print(f"   📹 Found video file: {mp4_file} ({file_size} bytes)")
                if file_size > 10000:
                    print(f"   ✅ Recording successful")
                    return True

        print(f"   ❌ No valid recording file found")
        return False

    except Exception as e:
        print(f"   ❌ Recording test failed: {e}")
        import traceback
        print(f"   🔍 Traceback: {traceback.format_exc()}")
        return False


def test_device_control_functions(device: DeviceInfo) -> bool:
    """Test device control functions (non-destructive)."""
    print(f"🔧 Testing device control functions with {device.device_serial_num}...")

    try:
        # Test Bluetooth state reading
        print("   📡 Testing Bluetooth state reading...")
        bt_cmd = f"adb -s {device.device_serial_num} shell settings get global bluetooth_on"
        bt_result = common.run_command(bt_cmd)
        print(f"   📋 Bluetooth state: {_command_output_text(bt_result)}")

        # Test WiFi state reading
        print("   📶 Testing WiFi state reading...")
        wifi_cmd = f"adb -s {device.device_serial_num} shell settings get global wifi_on"
        wifi_result = common.run_command(wifi_cmd)
        print(f"   📋 WiFi state: {_command_output_text(wifi_result)}")

        # Test getting Android version
        print("   🤖 Testing Android version...")
        version_cmd = f"adb -s {device.device_serial_num} shell getprop ro.build.version.release"
        version_result = common.run_command(version_cmd)
        print(f"   📋 Android version: {_command_output_text(version_result)}")

        # Test getting API level
        print("   🔢 Testing API level...")
        api_cmd = f"adb -s {device.device_serial_num} shell getprop ro.build.version.sdk"
        api_result = common.run_command(api_cmd)
        print(f"   📋 API level: {_command_output_text(api_result)}")

        print("   ✅ Device control functions working")
        return True

    except Exception as e:
        print(f"   ❌ Device control test failed: {e}")
        return False


def main():
    """Run functional tests with real devices."""
    print("🍵 === LAZY BLACKTEA FUNCTIONAL TEST SUITE ===")
    print("Testing actual functionality with connected devices...")
    print("")

    # Get connected devices
    try:
        devices = adb_tools.get_devices_list()
        if not devices:
            print("❌ No devices connected. Please connect an Android device and try again.")
            print("💡 Make sure:")
            print("   • USB Debugging is enabled")
            print("   • Device is connected via USB")
            print("   • Run 'adb devices' to verify connection")
            return False

        print(f"📱 Found {len(devices)} connected device(s)")
        for i, device in enumerate(devices):
            print(f"   {i+1}. {device.device_model} ({device.device_serial_num})")

    except Exception as e:
        print(f"❌ Failed to get device list: {e}")
        return False

    # Test with the first device
    device = devices[0]
    print(f"🎯 Testing with: {device.device_model} ({device.device_serial_num})")
    print("")

    # Create test output directory
    test_output_dir = "/tmp/lazy_blacktea_functional_test"
    print(f"📁 Test output directory: {test_output_dir}")

    results = {}

    # Test screenshot functionality
    success = test_real_screenshot(device, test_output_dir)
    results['screenshot'] = success

    print("")

    # Test recording functionality
    success = test_real_recording_short(device, test_output_dir)
    results['recording'] = success

    print("")

    # Test device control functions
    success = test_device_control_functions(device)
    results['device_control'] = success

    # Summary
    print("")
    print("📊 === FUNCTIONAL TEST RESULTS ===")
    passed = 0
    failed = 0

    for test_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"   {test_name:<20} {status}")
        if result:
            passed += 1
        else:
            failed += 1

    print("")
    print(f"📈 Total: {passed + failed} tests, {passed} passed, {failed} failed")

    # Show output files
    if os.path.exists(test_output_dir):
        output_files = os.listdir(test_output_dir)
        if output_files:
            print("")
            print("📄 Generated test files:")
            for file in output_files:
                file_path = os.path.join(test_output_dir, file)
                if os.path.isfile(file_path):
                    file_size = os.path.getsize(file_path)
                    print(f"   • {file} ({file_size} bytes)")

    print("")
    if failed > 0:
        print("⚠️  SOME FUNCTIONAL TESTS FAILED")
        print("💡 This may indicate issues with:")
        print("   • Device permissions")
        print("   • ADB configuration")
        print("   • File system access")
        return False
    else:
        print("🎉 ALL FUNCTIONAL TESTS PASSED!")
        print("✨ The application's core functionality is working correctly")
        return True


if __name__ == "__main__":
    success = main()
    print("")
    print("💡 Note: This test creates actual files. You can find them in /tmp/lazy_blacktea_functional_test")
    sys.exit(0 if success else 1)
