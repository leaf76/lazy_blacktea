#!/usr/bin/env python3
"""
Test suite for device search functionality.
Tests the fuzzy search and filtering capabilities.
"""

import sys
import os
import unittest
from unittest.mock import Mock

# Add the project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils import adb_models
from ui.device_search_manager import DeviceSearchManager
from ui.device_selection_manager import DeviceSelectionManager


class MockMainWindow:
    """Mock main window for testing search functionality."""

    def __init__(self):
        self.check_devices = {}
        self.device_selection_manager = DeviceSelectionManager()
        # Initialize the search manager
        self.device_search_manager = DeviceSearchManager(main_window=self)

    def _fuzzy_match_score(self, query: str, text: str) -> float:
        """Calculate fuzzy match score between query and text.
        Returns a score between 0 (no match) and 1 (perfect match).
        """
        if not query:
            return 1.0

        if not text:
            return 0.0

        query = query.lower().strip()
        text = text.lower()

        # Exact substring match gets highest score
        if query in text:
            # Perfect match for equal strings
            if query == text:
                return 1.0
            # High score for substring matches, better for shorter text
            position_factor = 1.0 - (text.find(query) / len(text)) if len(text) > 0 else 1.0
            length_factor = len(query) / len(text) if len(text) > 0 else 0.0
            return 0.8 + (position_factor * 0.1) + (length_factor * 0.1)

        # For non-substring matches, use character-by-character matching
        query_chars = list(query)
        text_chars = list(text)
        matches = 0
        text_index = 0

        # Count sequential character matches
        for query_char in query_chars:
            found = False
            # Find the character in remaining text
            for i in range(text_index, len(text_chars)):
                if text_chars[i] == query_char:
                    matches += 1
                    text_index = i + 1
                    found = True
                    break

            # If we can't find a character, this is a poor match
            if not found:
                break

        # Score based on how many characters matched
        if matches == 0:
            return 0.0

        # Calculate score with emphasis on match completeness
        char_ratio = matches / len(query)  # How much of query was matched

        # Only give partial score if we matched most of the query
        if char_ratio < 0.9:  # Stricter threshold
            return char_ratio * 0.2  # Even lower score for poor matches
        else:
            # Better score for good character matches
            density_factor = matches / len(text) if len(text) > 0 else 0.0
            return char_ratio * 0.6 + density_factor * 0.2

    def _get_device_operation_status(self, device_serial):
        """Mock function for device operation status."""
        _ = device_serial  # Suppress unused parameter warning
        return None

    def _get_device_recording_status(self, device_serial):
        """Mock function for device recording status."""
        _ = device_serial  # Suppress unused parameter warning
        return ""



def create_mock_device(model="TestModel", serial="TEST123", android_ver="13",
                      api_level="33", gms_version="25.35.34", wifi_on=True, bt_on=False):
    """Create a mock device for testing."""
    device = Mock(spec=adb_models.DeviceInfo)
    device.device_model = model
    device.device_serial_num = serial
    device.android_ver = android_ver
    device.android_api_level = api_level
    device.gms_version = gms_version
    device.wifi_is_on = wifi_on
    device.bt_is_on = bt_on
    device.device_brand = model.split()[0] if ' ' in model else model  # Simple brand extraction
    return device


class TestDeviceSearch(unittest.TestCase):
    """Test device search functionality."""

    def setUp(self):
        """Set up test environment."""
        self.main_window = MockMainWindow()

        # Create test devices
        self.devices = [
            create_mock_device("Samsung Galaxy S23", "R5CN700J89E", "13", "33", "25.35.34", True, False),
            create_mock_device("Google Pixel 7", "25091FDH30005X", "13", "33", "23.16.13", True, True),
            create_mock_device("OnePlus 11", "OP11TEST", "14", "34", "N/A", False, True),
            create_mock_device("Xiaomi Mi 13", "MI13SERIAL", "12", "32", "24.10.20", True, False),
            create_mock_device("iPhone 14", "APPLE123", "16", "30", "N/A", True, False),  # Edge case
        ]

    def test_fuzzy_match_score_exact_match(self):
        """Test fuzzy match with exact matches."""
        score = self.main_window.device_search_manager.fuzzy_match_score("samsung", "Samsung Galaxy S23")
        self.assertGreater(score, 0.8, "Exact match should have high score")

    def test_fuzzy_match_score_partial_match(self):
        """Test fuzzy match with partial matches."""
        score = self.main_window.device_search_manager.fuzzy_match_score("gal", "Samsung Galaxy S23")
        self.assertGreater(score, 0.5, "Partial match should have decent score")

    def test_fuzzy_match_score_token_permutation(self):
        """Tokens in different order should still yield a strong score."""
        score = self.main_window.device_search_manager.fuzzy_match_score("pixel google", "Google Pixel 7")
        self.assertGreater(score, 0.75, "Token permutation should remain a strong match")

    def test_fuzzy_match_score_handles_minor_typos(self):
        """Small typos should not drastically reduce the score."""
        score = self.main_window.device_search_manager.fuzzy_match_score("samsng", "Samsung Galaxy S23")
        self.assertGreater(score, 0.7, "Minor typo should still be considered a close match")

    def test_fuzzy_match_score_collapsed_abbreviation(self):
        """Collapsed model abbreviations should still match well."""
        score = self.main_window.device_search_manager.fuzzy_match_score("sgs23", "Samsung Galaxy S23")
        self.assertGreater(score, 0.7, "Common abbreviation should map to the device name")

    def test_fuzzy_match_score_no_match(self):
        """Test fuzzy match with no matches."""
        score = self.main_window.device_search_manager.fuzzy_match_score("xyz", "Samsung Galaxy S23")
        self.assertLess(score, 0.2, "No match should have very low score")

    def test_fuzzy_match_score_empty_query(self):
        """Test fuzzy match with empty query."""
        score = self.main_window.device_search_manager.fuzzy_match_score("", "Samsung Galaxy S23")
        self.assertEqual(score, 1.0, "Empty query should match everything")

    def test_device_search_by_model(self):
        """Test searching by device model."""
        samsung = self.devices[0]
        pixel = self.devices[1]

        # Test Samsung search
        score_samsung = self.main_window.device_search_manager.match_device(samsung, "samsung")
        score_pixel = self.main_window.device_search_manager.match_device(pixel, "samsung")

        print(f"Samsung score for 'samsung': {score_samsung}")
        print(f"Pixel score for 'samsung': {score_pixel}")

        self.assertGreater(score_samsung, score_pixel, "Samsung device should score higher for 'samsung' query")

        # Test Pixel search
        score_samsung_pixel = self.main_window.device_search_manager.match_device(samsung, "pixel")
        score_pixel_pixel = self.main_window.device_search_manager.match_device(pixel, "pixel")

        print(f"Samsung score for 'pixel': {score_samsung_pixel}")
        print(f"Pixel score for 'pixel': {score_pixel_pixel}")

        self.assertGreater(score_pixel_pixel, score_samsung_pixel, "Pixel device should score higher for 'pixel' query")

    def test_device_search_by_android_version(self):
        """Test searching by Android version."""
        android13_device1 = self.devices[0]  # Samsung with Android 13
        android13_device2 = self.devices[1]  # Pixel with Android 13
        android14_device = self.devices[2]   # OnePlus with Android 14
        android12_device = self.devices[3]   # Xiaomi with Android 12

        # Test Android 13 search
        scores_13 = [
            self.main_window.device_search_manager.match_device(android13_device1, "android 13"),
            self.main_window.device_search_manager.match_device(android13_device2, "android 13"),
            self.main_window.device_search_manager.match_device(android14_device, "android 13"),
            self.main_window.device_search_manager.match_device(android12_device, "android 13"),
        ]

        print(f"Android 13 search scores: {scores_13}")

        # Android 13 devices should score higher
        self.assertGreater(scores_13[0], 0.8, "Samsung Android 13 should match strongly")
        self.assertGreater(scores_13[1], 0.8, "Pixel Android 13 should match strongly")
        self.assertLess(scores_13[2], 0.7, "OnePlus Android 14 should score lower")
        self.assertLess(scores_13[3], 0.7, "Xiaomi Android 12 should score lower")

    def test_device_search_by_api_level(self):
        """Test searching by API level."""
        api33_device = self.devices[0]  # Samsung with API 33
        api34_device = self.devices[2]  # OnePlus with API 34

        score_33_on_33 = self.main_window.device_search_manager.match_device(api33_device, "api 33")
        score_34_on_33 = self.main_window.device_search_manager.match_device(api34_device, "api 33")

        print(f"API 33 device score for 'api 33': {score_33_on_33}")
        print(f"API 34 device score for 'api 33': {score_34_on_33}")

        self.assertGreater(score_33_on_33, score_34_on_33, "API 33 device should score higher for 'api 33' query")

    def test_device_search_by_connectivity(self):
        """Test searching by WiFi/Bluetooth status."""
        wifi_on_bt_off = self.devices[0]    # Samsung: WiFi ON, BT OFF
        wifi_on_bt_on = self.devices[1]     # Pixel: WiFi ON, BT ON
        wifi_off_bt_on = self.devices[2]    # OnePlus: WiFi OFF, BT ON

        # Test WiFi on search
        wifi_on_scores = [
            self.main_window.device_search_manager.match_device(wifi_on_bt_off, "wifi on"),
            self.main_window.device_search_manager.match_device(wifi_on_bt_on, "wifi on"),
            self.main_window.device_search_manager.match_device(wifi_off_bt_on, "wifi on"),
        ]

        print(f"WiFi on search scores: {wifi_on_scores}")

        self.assertGreater(wifi_on_scores[0], 0.8, "Samsung (WiFi ON) should match 'wifi on'")
        self.assertGreater(wifi_on_scores[1], 0.8, "Pixel (WiFi ON) should match 'wifi on'")
        self.assertLess(wifi_on_scores[2], 0.8, "OnePlus (WiFi OFF) should not match 'wifi on'")

        # Test Bluetooth on search
        bt_on_scores = [
            self.main_window.device_search_manager.match_device(wifi_on_bt_off, "bt on"),
            self.main_window.device_search_manager.match_device(wifi_on_bt_on, "bt on"),
            self.main_window.device_search_manager.match_device(wifi_off_bt_on, "bt on"),
        ]

        print(f"Bluetooth on search scores: {bt_on_scores}")

        self.assertLess(bt_on_scores[0], 0.8, "Samsung (BT OFF) should not match 'bt on'")
        self.assertGreater(bt_on_scores[1], 0.8, "Pixel (BT ON) should match 'bt on'")
        self.assertGreater(bt_on_scores[2], 0.8, "OnePlus (BT ON) should match 'bt on'")

    def test_device_search_by_gms_version(self):
        """Test searching by GMS version."""
        gms_device = self.devices[0]    # Samsung with GMS 25.35.34
        no_gms_device = self.devices[2]  # OnePlus with N/A GMS

        gms_score = self.main_window.device_search_manager.match_device(gms_device, "gms 25")
        no_gms_score = self.main_window.device_search_manager.match_device(no_gms_device, "gms 25")

        print(f"GMS device score for 'gms 25': {gms_score}")
        print(f"No GMS device score for 'gms 25': {no_gms_score}")

        self.assertGreater(gms_score, no_gms_score, "Device with GMS should score higher for GMS query")

    def test_comprehensive_search_scenarios(self):
        """Test realistic search scenarios."""
        print("\n=== Comprehensive Search Test ===")

        test_queries = [
            "samsung",
            "android 13",
            "wifi on",
            "gms 25",
            "api 33",
            "pixel",
            "bt off"
        ]

        for query in test_queries:
            print(f"\nQuery: '{query}'")
            scores = []
            for device in self.devices:
                score = self.main_window.device_search_manager.match_device(device, query)
                scores.append((device.device_model, score))
                print(f"  {device.device_model}: {score:.3f}")

            # Check that we have some matches and some non-matches
            max_score = max(score for _, score in scores)
            min_score = min(score for _, score in scores)

            self.assertGreater(max_score, 0, f"Query '{query}' should match at least one device")
            # Allow some queries to match all devices (like basic terms)
            if query not in ["android"]:  # These might match multiple devices
                self.assertLess(min_score, max_score, f"Query '{query}' should have varying match scores")


def run_search_tests():
    """Run the search functionality tests."""
    print("🧪 Running Device Search Tests...")
    print("=" * 60)

    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    # Add test class
    suite.addTests(loader.loadTestsFromTestCase(TestDeviceSearch))

    # Run tests with high verbosity
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    # Print summary
    print("\n" + "=" * 60)
    if result.wasSuccessful():
        print("✅ All search tests passed!")
        print(f"📊 Ran {result.testsRun} tests successfully")
    else:
        print("❌ Some search tests failed")
        print(f"📊 Tests: {result.testsRun}, Failures: {len(result.failures)}, Errors: {len(result.errors)}")

        if result.failures:
            print("\n🔍 Failures:")
            for test, traceback in result.failures:
                newline = '\n'
                error_msg = traceback.split('AssertionError: ')[-1].split(newline)[0] if 'AssertionError:' in traceback else 'Unknown failure'
                print(f"  - {test}: {error_msg}")

        if result.errors:
            print("\n💥 Errors:")
            for test, traceback in result.errors:
                newline = '\n'
                error_msg = traceback.split(newline)[-2] if newline in traceback else 'Unknown error'
                print(f"  - {test}: {error_msg}")

    return result.wasSuccessful()


if __name__ == '__main__':
    success = run_search_tests()
    sys.exit(0 if success else 1)
