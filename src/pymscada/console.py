"""Interactive console."""
import asyncio
import sys
from pymscada.bus_client import BusClient


class Console:
    """Provide a text console to interact with a Bus."""

    def __init__(self, bus_ip: str = '127.0.0.1', bus_port: int = 1324):
        """
        Connect to bus_ip:bus_port and provide console interaction with a Bus.

        TO DO.

        Event loop must be running.
        """
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
        await self.busclient.start()
        await self.interact()
