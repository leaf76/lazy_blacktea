import unittest

from utils import adb_tools


class NativeCommandRunnerTests(unittest.TestCase):
    def test_parallel_runner_handles_basic_commands(self) -> None:
        commands = ['/bin/echo alpha', '/bin/echo beta']
        results = adb_tools._execute_commands_parallel_native(commands, 'test_parallel_runner')
        self.assertEqual(results, [['alpha'], ['beta']])


if __name__ == '__main__':
    unittest.main()
