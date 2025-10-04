import importlib
import os
import sys
import unittest
from unittest.mock import Mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils import common
from utils.task_dispatcher import TaskContext, _TaskRunnable


class DummySignal:
    def __init__(self):
        self.emissions = []

    def emit(self, *args, **kwargs):
        self.emissions.append((args, kwargs))


class DummyHandle:
    def __init__(self, context):
        self.context = context
        self._cancelled = False
        self.completed = DummySignal()
        self.failed = DummySignal()
        self.finished = DummySignal()
        self.progress = DummySignal()
        self.trace_id = context.trace_id

    def is_cancelled(self):
        return self._cancelled

    def report_progress(self, value, label):
        self.progress.emit(value, label)


class TraceIdLoggingTests(unittest.TestCase):
    def test_task_context_has_trace_id(self):
        context = TaskContext(name='unit-test-task')
        self.assertTrue(hasattr(context, 'trace_id'))
        trace_id = getattr(context, 'trace_id')
        self.assertIsNotNone(trace_id)
        self.assertNotEqual(str(trace_id).strip(), '')

    def test_task_runnable_sets_trace_id_for_execution(self):
        context = TaskContext(name='unit-test-task', trace_id='trace-xyz')
        handle = DummyHandle(context)
        observed = {}

        def worker():
            observed['trace_id'] = common.get_trace_id()
            return 'done'

        runnable = _TaskRunnable(worker, tuple(), {}, handle, False, False)
        runnable.run()

        self.assertEqual(observed.get('trace_id'), 'trace-xyz')


class ConsoleFallbackLoggingTests(unittest.TestCase):
    def setUp(self):
        self.module = importlib.import_module('ui.command_execution_manager')

    def test_write_to_console_uses_logger_fallback(self):
        class DummyWindow:
            def show_error(self, *args, **kwargs):
                pass

            def show_info(self, *args, **kwargs):
                pass

        fallback_logger = Mock()
        setattr(self.module, '_fallback_logger', fallback_logger)
        setattr(self.module, 'get_task_dispatcher', Mock(return_value=Mock()))

        manager = self.module.CommandExecutionManager(DummyWindow())
        manager._console_connected = False
        manager.write_to_console('fallback-message')

        self.assertTrue(fallback_logger.error.called)
        self.assertEqual(fallback_logger.error.call_args[0][0], 'fallback-message')


if __name__ == '__main__':
    unittest.main()
