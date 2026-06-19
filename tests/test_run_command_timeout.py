"""Regression tests for run_command timeouts (audit finding #3).

A stuck/offline device must not block the worker forever; run_command now bounds
each invocation with a timeout and reclaims the process on expiry.
"""

import os
import sys
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils import common


class RunCommandTimeoutTests(unittest.TestCase):
    def test_run_command_times_out_and_returns_empty(self):
        start = time.perf_counter()
        result = common.run_command(
            [sys.executable, '-c', 'import time; time.sleep(10)'], timeout=0.5
        )
        elapsed = time.perf_counter() - start
        self.assertLess(elapsed, 4.0, 'timeout should kill the process quickly')
        self.assertEqual(result, [])

    def test_run_command_with_status_times_out(self):
        rc, _out, _err = common.run_command_with_status(
            [sys.executable, '-c', 'import time; time.sleep(10)'], timeout=0.5
        )
        self.assertEqual(rc, -1)

    def test_run_command_returns_output_for_quick_command(self):
        result = common.run_command([sys.executable, '-c', "print('hello')"])
        self.assertIn('hello', result)

    def test_ignore_index_still_supported(self):
        result = common.run_command(
            [sys.executable, '-c', "print('a'); print('b')"], ignore_index=1
        )
        self.assertEqual(result, ['b'])


if __name__ == '__main__':
    unittest.main()
