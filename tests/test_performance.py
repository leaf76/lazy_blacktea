#!/usr/bin/env python3
"""
Performance tests for refactored parallel execution features.
"""

import sys
import os
import unittest
import time
from unittest.mock import Mock, patch
import threading
from concurrent.futures import ThreadPoolExecutor

# Add the project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils import adb_tools


class TestParallelExecutionPerformance(unittest.TestCase):
    """Test performance characteristics of parallel execution."""

    def test_parallel_vs_sequential_commands_performance(self):
        """Test that parallel execution is faster than sequential for multiple commands."""

        def mock_slow_command(cmd):
            """Mock a slow ADB command."""
            time.sleep(0.1)  # Simulate 100ms command
            return [f"result_for_{cmd}"]

        commands = [f"test_command_{i}" for i in range(5)]

        # Test sequential execution time
        start_time = time.time()
        with patch('utils.adb_tools.common.run_command', side_effect=mock_slow_command):
            sequential_results = []
            for cmd in commands:
                result = adb_tools.common.run_command(cmd)
                sequential_results.append(result)
        sequential_time = time.time() - start_time

        # Test parallel execution time
        start_time = time.time()
        with patch('utils.adb_tools.common.run_command', side_effect=mock_slow_command):
            parallel_results = adb_tools._execute_commands_parallel(commands, "performance_test")
        parallel_time = time.time() - start_time

        # Verify results are equivalent
        self.assertEqual(len(sequential_results), len(parallel_results))

        # Verify parallel is significantly faster (should be ~5x faster with 5 commands)
        # Allow some overhead, so we expect at least 2x improvement
        self.assertLess(parallel_time, sequential_time / 2,
                       f"Parallel execution ({parallel_time:.3f}s) should be faster than sequential ({sequential_time:.3f}s)")

        print(f"📊 Performance test results:")
        print(f"   Sequential: {sequential_time:.3f}s")
        print(f"   Parallel:   {parallel_time:.3f}s")
        print(f"   Speedup:    {sequential_time/parallel_time:.1f}x")

    def test_parallel_function_execution_performance(self):
        """Test performance of parallel function execution."""

        def slow_function(arg):
            """Mock a slow function."""
            time.sleep(0.05)  # 50ms per function
            return f"processed_{arg}"

        functions = [slow_function] * 6
        args_list = [(i,) for i in range(6)]

        # Test sequential execution
        start_time = time.time()
        sequential_results = []
        for func, args in zip(functions, args_list):
            result = func(*args)
            sequential_results.append(result)
        sequential_time = time.time() - start_time

        # Test parallel execution
        start_time = time.time()
        parallel_results = adb_tools._execute_functions_parallel(functions, args_list, "performance_test")
        parallel_time = time.time() - start_time

        # Verify results
        self.assertEqual(len(sequential_results), len(parallel_results))
        self.assertLess(parallel_time, sequential_time / 2)

        print(f"📊 Function execution performance:")
        print(f"   Sequential: {sequential_time:.3f}s")
        print(f"   Parallel:   {parallel_time:.3f}s")
        print(f"   Speedup:    {sequential_time/parallel_time:.1f}x")

    def test_parallel_execution_scalability(self):
        """Test how parallel execution scales with different numbers of tasks."""

        def mock_task(task_id):
            time.sleep(0.02)  # 20ms per task
            return f"task_{task_id}_completed"

        task_counts = [2, 5, 10, 20]
        results = {}

        for count in task_counts:
            functions = [mock_task] * count
            args_list = [(i,) for i in range(count)]

            start_time = time.time()
            parallel_results = adb_tools._execute_functions_parallel(functions, args_list, f"scalability_test_{count}")
            execution_time = time.time() - start_time

            results[count] = execution_time
            self.assertEqual(len(parallel_results), count)

        print(f"📊 Scalability test results:")
        for count, exec_time in results.items():
            print(f"   {count:2d} tasks: {exec_time:.3f}s ({exec_time/count*1000:.1f}ms per task)")

        # Verify that execution time doesn't scale linearly (benefit of parallelism)
        # With proper parallelism, 20 tasks shouldn't take 10x longer than 2 tasks
        if len(results) >= 2:
            min_tasks = min(task_counts)
            max_tasks = max(task_counts)
            time_ratio = results[max_tasks] / results[min_tasks]
            task_ratio = max_tasks / min_tasks

            self.assertLess(time_ratio, task_ratio * 0.7,
                           f"Parallel execution should scale better than linear: {time_ratio:.1f}x time vs {task_ratio:.1f}x tasks")

    def test_parallel_execution_error_handling_performance(self):
        """Test that error handling doesn't significantly impact performance."""

        def mixed_function(arg):
            if arg % 3 == 0:  # Every 3rd function fails
                raise Exception(f"Error in task {arg}")
            time.sleep(0.01)  # 10ms per successful task
            return f"success_{arg}"

        functions = [mixed_function] * 12  # 4 will fail, 8 will succeed
        args_list = [(i,) for i in range(12)]

        start_time = time.time()
        results = adb_tools._execute_functions_parallel(functions, args_list, "error_handling_performance")
        execution_time = time.time() - start_time

        # Verify mixed results (some success, some None for errors)
        success_count = sum(1 for r in results if r is not None and r.startswith("success_"))
        error_count = sum(1 for r in results if r is None)

        self.assertEqual(success_count, 8)  # 8 successful tasks
        self.assertEqual(error_count, 4)   # 4 failed tasks

        # Should still be reasonably fast despite errors
        self.assertLess(execution_time, 0.5, "Error handling shouldn't significantly slow down execution")

        print(f"📊 Error handling performance:")
        print(f"   Total tasks: 12")
        print(f"   Successful:  {success_count}")
        print(f"   Failed:      {error_count}")
        print(f"   Time:        {execution_time:.3f}s")


class TestMemoryUsageOptimization(unittest.TestCase):
    """Test memory usage characteristics of refactored code."""

    def test_large_batch_processing_memory_efficiency(self):
        """Test memory efficiency with large batches of operations."""

        def memory_efficient_task(task_id):
            # Simulate processing that creates and releases memory
            data = [i for i in range(100)]  # Small data processing
            result = f"processed_{task_id}_{len(data)}"
            del data  # Explicit cleanup
            return result

        # Test with a large number of tasks
        large_task_count = 50
        functions = [memory_efficient_task] * large_task_count
        args_list = [(i,) for i in range(large_task_count)]

        start_time = time.time()
        results = adb_tools._execute_functions_parallel(functions, args_list, "memory_test")
        execution_time = time.time() - start_time

        # Verify all tasks completed
        self.assertEqual(len(results), large_task_count)
        self.assertTrue(all(r is not None for r in results))

        print(f"📊 Memory efficiency test:")
        print(f"   Tasks processed: {large_task_count}")
        print(f"   Execution time:  {execution_time:.3f}s")
        print(f"   Avg per task:    {execution_time/large_task_count*1000:.1f}ms")

    def test_resource_cleanup_after_parallel_execution(self):
        """Test that resources are properly cleaned up after parallel execution."""

        initial_thread_count = threading.active_count()

        def resource_using_task(task_id):
            # Simulate resource usage
            return f"resource_task_{task_id}"

        functions = [resource_using_task] * 10
        args_list = [(i,) for i in range(10)]

        # Execute parallel operations
        results = adb_tools._execute_functions_parallel(functions, args_list, "resource_cleanup_test")

        # Allow some time for cleanup
        time.sleep(0.1)

        final_thread_count = threading.active_count()

        # Verify results
        self.assertEqual(len(results), 10)

        # Thread count should not have significantly increased
        # (allowing for some variance in thread pool management)
        self.assertLessEqual(final_thread_count - initial_thread_count, 2,
                            f"Thread count increased from {initial_thread_count} to {final_thread_count}")

        print(f"📊 Resource cleanup test:")
        print(f"   Initial threads: {initial_thread_count}")
        print(f"   Final threads:   {final_thread_count}")
        print(f"   Thread delta:    {final_thread_count - initial_thread_count}")


if __name__ == '__main__':
    # Run with verbose output to see performance metrics
    unittest.main(verbosity=2)