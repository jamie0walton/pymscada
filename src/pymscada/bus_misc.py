"""Async helpers shared by bus-facing modules."""
import asyncio


class BusTask:
    """Create a Task; on fatal failure optionally log then exit the process."""

    def __init__(self, coroutine, *, ignore_cancelled: bool = True,
                 fatal: bool = True):
        self._ignore_cancelled = ignore_cancelled
        self._fatal = fatal
        self.task = asyncio.create_task(coroutine)
        self.task.add_done_callback(self.done)

    def done(self, task: asyncio.Task):
        if task.cancelled():
            if self._ignore_cancelled:
                return
        exc = task.exception()
        if exc is not None:
            if self._fatal:
                raise SystemExit(exc)
