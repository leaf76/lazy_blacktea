# 🧪 Test Suite for Lazy Blacktea

This directory contains comprehensive tests for the Lazy Blacktea Android ADB GUI application.

## 📋 Test Files

### 🔧 Unit Tests
- **`test_all_functions.py`** - Comprehensive unit test suite
  - Tests all core functions individually
  - Validates command generation
  - Checks wrapper function signatures
  - Verifies configuration management

### 🔗 Integration Tests
- **`test_integration.py`** - Complete integration test suite
  - Tests system component integration
  - Validates device detection workflow
  - Tests application startup and imports
  - Verifies end-to-end workflows

### 📱 Functional Tests
- **`test_functional.py`** - Real device functional tests
  - Tests with actual connected Android devices
  - Validates screenshot functionality
  - Tests recording capabilities
  - Performs device control operations

## 🚀 Running Tests

### Quick Test (Unit + Integration)
```bash
# Run unit tests
python3 tests/test_all_functions.py

# Run integration tests
python3 tests/test_integration.py
```

### Full Functional Test (Requires Connected Device)
```bash
# Run functional tests with real device
python3 tests/test_functional.py
```

### Run All Tests
```bash
# Run all tests in sequence
python3 tests/test_all_functions.py && \
python3 tests/test_integration.py && \
python3 tests/test_functional.py
```

## 📊 Test Coverage

### ✅ Device Management
- ADB connectivity
- Device detection and parsing
- Auto-refresh functionality
- Device information retrieval

### ✅ Recording & Screenshots
- Command generation
- Wrapper function integration
- File creation and management
- Start/stop workflows

### ✅ Configuration & Settings
- Configuration loading/saving
- Settings validation
- Default value handling

### ✅ Error Handling
- Exception handling
- Error message generation
- Recovery mechanisms

### ✅ Performance
- Memory management
- Debounced refresh
- Background processing

## 🎯 Test Results

All tests should pass with the message:
- **Unit Tests**: `🎉 ALL TESTS PASSED - Application is ready!`
- **Integration Tests**: `🎉 ALL INTEGRATION TESTS PASSED!`
- **Functional Tests**: `🎉 ALL FUNCTIONAL TESTS PASSED!`

## 🔧 Prerequisites

### For Unit & Integration Tests
- Python 3.7+
- ADB in system PATH
- Project dependencies installed

### For Functional Tests
- Android device connected via USB
- USB Debugging enabled
- Device authorized for ADB access

## 📝 Test Output

Tests create temporary files in:
- `/tmp/test_recordings/` - Recording test files
- `/tmp/test_screenshots/` - Screenshot test files
- `/tmp/lazy_blacktea_functional_test/` - Functional test output

## 🛠️ Troubleshooting

### No Devices Found
- Connect Android device via USB
- Enable Developer Options
- Enable USB Debugging
- Accept ADB authorization prompt

### Permission Errors
- Check ADB is in PATH: `which adb`
- Verify device connection: `adb devices`
- Restart ADB server: `adb kill-server && adb start-server`

### Test Failures
- Review error messages in console output
- Check log files in `logs/` directory
- Verify all dependencies are installed
- Ensure no other ADB processes are running

## 💡 Adding New Tests

When adding new functionality, create corresponding tests:

1. **Unit tests** in `test_all_functions.py` for individual functions
2. **Integration tests** in `test_integration.py` for component interactions
3. **Functional tests** in `test_functional.py` for real device testing

Follow the existing test patterns and ensure all tests pass before submitting changes.