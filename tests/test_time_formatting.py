import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils import time_formatting


class TestTimeFormatting(unittest.TestCase):
    def test_format_seconds_to_clock_converts_positive_seconds(self):
        self.assertEqual(time_formatting.format_seconds_to_clock(3723), "01:02:03")

    def test_format_seconds_to_clock_handles_negative_values(self):
        self.assertEqual(time_formatting.format_seconds_to_clock(-5), "00:00:00")

    def test_parse_duration_to_seconds_parses_valid_string(self):
        self.assertEqual(time_formatting.parse_duration_to_seconds("01:02:03"), 3723)

    def test_parse_duration_to_seconds_handles_invalid(self):
        self.assertEqual(time_formatting.parse_duration_to_seconds("invalid"), 0.0)


if __name__ == "__main__":
    unittest.main()
