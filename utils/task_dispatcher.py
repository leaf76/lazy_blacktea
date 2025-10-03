"""Centralized task dispatcher built on QThreadPool with progress support."""

from __future__ import annotations

import inspect
from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional, Tuple

from PyQt6.QtCore import QObject, QMutex, QMutexLocker, QRunnable, QThreadPool, pyqtSignal

from utils import common


logger = common.get_logger('task_dispatcher')


TaskCallable = Callable[..., Any]


@dataclass(frozen=True)
class TaskContext:
    """Metadata describing the submitted task."""

    name: str
    device_serial: Optional[str] = None
    category: Optional[str] = None


class TaskHandle(QObject):
    """Provides signals, progress updates and cancellation for a task."""

    completed = pyqtSignal(object)
    failed = pyqtSignal(Exception)
    finished = pyqtSignal()
    progress = pyqtSignal(int, str)

    def __init__(self, context: TaskContext, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._context = context
        self._cancelled = False
        self._mutex = QMutex()

    @property
    def context(self) -> TaskContext:
        return self._context

    def cancel(self) -> None:
        with QMutexLocker(self._mutex):
            self._cancelled = True
            logger.debug('Cancellation requested for task %s', self._context)

    def is_cancelled(self) -> bool:
        with QMutexLocker(self._mutex):
            return self._cancelled

    def report_progress(self, value: int, label: str) -> None:
        self.progress.emit(value, label)


class _TaskRunnable(QRunnable):
    """Internal runnable submitting work to QThreadPool."""

    def __init__(
        self,
        fn: TaskCallable,
        args: Tuple[Any, ...],
        kwargs: Dict[str, Any],
        handle: TaskHandle,
        inject_handle: bool,
        inject_progress: bool,
    ):
        super().__init__()
        self.fn = fn
        self.args = args
        self.kwargs = kwargs
        self.handle = handle
        self.inject_handle = inject_handle
        self.inject_progress = inject_progress

    def run(self) -> None:  # pragma: no cover - executed in thread pool
        if self.handle.is_cancelled():
            logger.debug('Skipping task %s because it was cancelled prior to start', self.handle.context)
            self.handle.finished.emit()
            return

        kwargs = dict(self.kwargs)
        if self.inject_handle and 'task_handle' not in kwargs:
            kwargs['task_handle'] = self.handle
        if self.inject_progress and 'progress_callback' not in kwargs:
            kwargs['progress_callback'] = self.handle.report_progress

        try:
            result = self.fn(*self.args, **kwargs)
        except Exception as exc:  # pragma: no cover - defensive path
            logger.exception('Task %s failed: %s', self.handle.context, exc)
            self.handle.failed.emit(exc)
        else:
            self.handle.completed.emit(result)
        finally:
            self.handle.finished.emit()


class TaskDispatcher(QObject):
    """Submit CPU/IO bound work to a shared QThreadPool with observability."""

    task_started = pyqtSignal(TaskContext)
    task_finished = pyqtSignal(TaskContext)

    def __init__(self, max_thread_count: Optional[int] = None, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._pool = QThreadPool.globalInstance()
        if max_thread_count:
            logger.info('Configuring task dispatcher max thread count to %s', max_thread_count)
            self._pool.setMaxThreadCount(max_thread_count)

    def submit(
        self,
        fn: TaskCallable,
        *args: Any,
        context: Optional[TaskContext] = None,
        **kwargs: Any,
    ) -> TaskHandle:
        """Submit a function to the pool and return a handle for observation."""

        if context is None:
            context = TaskContext(name=getattr(fn, '__name__', 'task'))

        handle = TaskHandle(context, parent=self)

        inject_handle = False
        inject_progress = False

        try:
            signature = inspect.signature(fn)
            inject_handle = 'task_handle' in signature.parameters
            inject_progress = 'progress_callback' in signature.parameters
        except (TypeError, ValueError):  # pragma: no cover - builtins etc.
            pass

        runnable = _TaskRunnable(fn, args, kwargs, handle, inject_handle, inject_progress)
        handle.finished.connect(lambda: self.task_finished.emit(context))
        self.task_started.emit(context)
        self._pool.start(runnable)
        return handle


_dispatcher: Optional[TaskDispatcher] = None


def get_task_dispatcher() -> TaskDispatcher:
    """Return the shared TaskDispatcher instance."""

    global _dispatcher
    if _dispatcher is None:
        _dispatcher = TaskDispatcher()
    return _dispatcher


__all__ = ['TaskDispatcher', 'TaskHandle', 'TaskContext', 'get_task_dispatcher']
