#!/usr/bin/env python3
"""
bugreportz -p 輸出解析測試：涵蓋常見 OEM 變體格式。
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class BugreportzParserTest(unittest.TestCase):
    def setUp(self):
        from utils.adb_tools import parse_bugreportz_line
        self.parse = parse_bugreportz_line

    def test_fraction_progress(self):
        r = self.parse('PROGRESS: 3/10')
        self.assertEqual(r['type'], 'progress')
        self.assertEqual(r['percent'], 30)

        r = self.parse('  progress :  1/4 ')
        self.assertEqual(r['type'], 'progress')
        self.assertEqual(r['percent'], 25)

    def test_percent_progress(self):
        r = self.parse('PROGRESS: 75%')
        self.assertEqual(r['type'], 'progress')
        self.assertEqual(r['percent'], 75)

        r = self.parse('PROGRESS: 42')
        self.assertEqual(r['type'], 'progress')
        self.assertEqual(r['percent'], 42)

    def test_ok_and_fail(self):
        r = self.parse('OK: /data/bugreports/bugreport-abc.zip')
        self.assertEqual(r['type'], 'ok')
        self.assertTrue(r['path'].endswith('.zip'))

        r = self.parse('OK:filename=/data/bugreports/bugreport-xyz.zip')
        self.assertEqual(r['type'], 'ok')
        self.assertIn('/data/bugreports/bugreport-xyz.zip', r['path'])

        r = self.parse('FAIL: device busy')
        self.assertEqual(r['type'], 'fail')
        self.assertIn('busy', r['reason'])


if __name__ == '__main__':
    unittest.main()

