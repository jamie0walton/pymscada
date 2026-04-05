"""Periodic class."""
import asyncio
import logging
import time


class Periodic:
    """Awaitable periodic function. Tolerates slow periodic functions."""

    def __init__(self, func, period):
        """Create with function and time in seconds."""
        self.func = func
        self.period = period
        self.running = False

    async def start(self):
        """Start the periodic function."""
        if not self.running:
            self.time = time.time()
            self.running = True
            self.task = asyncio.create_task(self.run())

    async def stop(self):
        """Stop the periodic function."""
        if self.running:
            self.running = False
            self.task.cancel()

    async def run(self):
        while True:
            try:
                await self.func()
            except Exception as e:
                raise SystemExit('Periodic failed') from e
            self.time = self.time + self.period
            sleep_for = self.time - time.time()
            if sleep_for < 0.0:
                sleep_for = self.period
                self.time = time.time()
                logging.warning(f'{self.func} skipped at {self.time}')
            else:
                try:
                    await asyncio.sleep(sleep_for)
                except asyncio.CancelledError:
                    return