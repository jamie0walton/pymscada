"""Interactive console."""
import asyncio
import sys
from .bus_client import BusClient


class Console:
    """Console."""

    def __init__(self, bus_ip: str = '127.0.0.1', bus_port: int = 1324
                 ) -> None:
        """Console."""
        self.busclient = BusClient(bus_ip, bus_port)

    async def interact(self):
        """Interact with the keyboard."""
        reader = asyncio.StreamReader()
        pipe = sys.stdin
        loop = asyncio.get_event_loop()
        await loop.connect_read_pipe(
            lambda: asyncio.StreamReaderProtocol(reader), pipe)
        async for line in reader:
            print(f'Got: {line.decode()!r}')

    async def start(self):
        """Provide a console server."""
        await self.busclient.connect()
        await self.interact()

    async def run_forever(self):
        """Run forever."""
        await self.start()
        await asyncio.get_event_loop().create_future()
