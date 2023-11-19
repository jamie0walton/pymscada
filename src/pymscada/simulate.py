"""Simulate logic."""
import asyncio
import logging
import math
from pymscada.bus_client import BusClient
from pymscada.misc import find_nodes
from pymscada.tag import Tag, TYPES
from time import monotonic


class Simulate():
    """Modify tag values to simulate a real process."""

    def __init__(self, bus_ip: str = '127.0.0.1', bus_port: int = 1324,
                 tag_info: dict = {}, process: dict = {}) -> None:
        """
        Connect to bus on bus_ip:bus_port, modify tag values per process.

        Event loop must be running.
        """
        self.busclient = BusClient(bus_ip, bus_port, tag_info)
        self.process = process
        self.tags = {}
        for x in ['sub', 'pub']:  # resist the temptation to
            for t in find_nodes(x, self.process):
                for tagname in t[x].values():
                    self.tags[tagname] = Tag(
                        tagname, TYPES[tag_info[tagname]['type']])

    def step(self):
        """Do simulation step."""
        for e in self.process.values():
            time = monotonic()
            tagname = e['pub']['result']
            if e['type'] == 'sine':
                result = e['offset'] + e['amplitude'] * \
                    math.sin(e['frequency'] * time)
            elif e['type'] == 'sawtooth':
                period = 1 / e['frequency']
                result = int(e['offset'] + e['amplitude'] * (time %
                             period) / period)
            else:
                return
            if self.tags[tagname].value is None or \
                    abs(self.tags[tagname].value - result) > 0.01:
                self.tags[tagname].value = result
                logging.warning(f'simulate {tagname} {result}')

    async def periodic(self):
        """Run simulation step every 5 seconds."""
        while True:
            self.next_run += 1.0
            self.step()
            self.last_ran = monotonic()
            sleep_time = self.next_run - self.last_ran
            if sleep_time < 0:
                self.next_run = self.last_ran
                logging.warning(f'Health count skipped at {self.last_ran}')
            else:
                await asyncio.sleep(sleep_time)

    async def start(self):
        """Provide the simulation process."""
        await self.busclient.start()
        self.next_run = monotonic()
        await asyncio.create_task(self.periodic())
