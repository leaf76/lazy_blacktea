#!/usr/bin/env python3
"""
Test runner for Lazy Blacktea application.
Runs all test suites in sequence and provides a summary.
"""

import sys
import os
import subprocess
import time

def run_test(test_name, test_file):
    """Run a single test file and return the result."""
    print(f"🧪 Running {test_name}...")
    print("=" * 50)

    start_time = time.time()
    try:
        result = subprocess.run([sys.executable, test_file],
                              cwd=os.path.dirname(os.path.abspath(__file__)),
                              capture_output=False,
                              timeout=120)
        end_time = time.time()
        duration = end_time - start_time

        if result.returncode == 0:
            print(f"✅ {test_name} PASSED ({duration:.1f}s)")
            return True
        else:
            print(f"❌ {test_name} FAILED ({duration:.1f}s)")
            return False

    except subprocess.TimeoutExpired:
        print(f"⏰ {test_name} TIMED OUT")
        return False
    except Exception as e:
        print(f"💥 {test_name} ERROR: {e}")
        return False

def main():
    """Run all tests."""
    print("🍵 === LAZY BLACKTEA COMPREHENSIVE TEST RUNNER ===")
    print("Running all test suites...")
    print("")

    tests = [
        ("Unit Tests", "test_all_functions.py"),
        ("Device Manager Tests", "test_device_manager_simple.py"),
        ("Integration Tests", "test_integration.py"),
        # Note: Functional tests require user interaction, run separately
        # ("Functional Tests", "test_functional.py"),
    ]

    results = {}
    total_start = time.time()

    for test_name, test_file in tests:
        success = run_test(test_name, test_file)
        results[test_name] = success
        print("")

        # Short pause between tests
        time.sleep(1)

    total_end = time.time()
    total_duration = total_end - total_start

    # Summary
    print("=" * 50)
    print("📊 === TEST SUMMARY ===")

    passed = 0
    failed = 0

    for test_name, success in results.items():
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"  {test_name:<20} {status}")
        if success:
            passed += 1
        else:
            failed += 1

    print("")
    print(f"📈 Total: {passed + failed} test suites")
    print(f"✅ Passed: {passed}")
    print(f"❌ Failed: {failed}")
    print(f"⏱️  Duration: {total_duration:.1f}s")

    print("")
    if failed == 0:
        print("🎉 ALL TEST SUITES PASSED!")
        print("✨ The application is fully tested and ready for use")
        print("")
        print("💡 To test with real devices, run:")
        print("   python3 tests/test_functional.py")
        return True
    else:
        print("⚠️  SOME TEST SUITES FAILED")
        print("Please review the failed tests above")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)