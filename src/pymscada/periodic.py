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
                logging.warn(f'{self._func} skipped at {self._time}')
            else:
                await asyncio.sleep(sleep_for)


class RunEvery:
    """Run function every few seconds, starts immediately."""

    def __init__(self, function, period: float):
        """Create with function and time in seconds."""
        self.function = function
        self.period = period
        self.time = time.time()
        asyncio.create_task(self._run())

    async def _run(self):
        """Run forever, every period seconds."""
        while True:
            try:
                self.function()
            except Exception as e:
                raise RuntimeError('RunEvery re-raising', e)
            self.time = self.time + self.period
            sleep_for = self.time - time.time()
            if sleep_for < 0.0:
                missed = int(-sleep_for / self.period + 1)
                if missed > 1000 or missed < 0:
                    print('wtf')
                self.time += missed * self.period
                sleep_for += missed * self.period
                logging.warn(f"RunEvery missed {missed} {self.function}")
            await asyncio.sleep(sleep_for)


class Heartbeat:
    """Run every interval but start at rounded time, i.e. hour on the hour."""

    def __init__(self, function, period: float):
        """Run function when time is is a modulo of period."""
        self.function = function
        self.period = period
        asyncio.create_task(self._run())

    async def _run(self):
        """Run forever."""
        while True:
            sleep_for = self.period - time.time() % self.period
            await asyncio.sleep(sleep_for)
            try:
                self.function()
            except Exception as e:
                raise RuntimeError('Heartbeat re-raising', e)
            # await asyncio.sleep(self.period / 2)
