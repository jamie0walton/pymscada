"""Periodic class."""
import asyncio
import logging
import time


class Periodic:
    """Awaitable periodic function. Tolerates slow periodic functions."""

    def __init__(self, func, period):
        """Create with function and time in seconds."""
        self._func = func
        self.period = period
        self._running = False

    async def start(self):
        """Start the periodic function."""
        if not self._running:
            self._time = time.time()
            self._running = True
            self._task = asyncio.create_task(self._run())

    async def stop(self):
        """Stop the periodic function."""
        self._running = False
        self._task.cancel()

    async def _run(self):
        while True:
            try:
                await self._func()
            except Exception as e:
                raise SystemExit('Periodic failed') from e
            self._time = self._time + self.period
            sleep_for = self._time - time.time()
            if sleep_for < 0.0:
                sleep_for = self.period
                self._time = time.time()
                logging.warning(f'{self._func} skipped at {self._time}')
            else:
                await asyncio.sleep(sleep_for)
