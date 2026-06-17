"""Math module for simple mathematical functions."""
import asyncio
import logging
import time
from pymscada.bus_client import BusClient
from pymscada.bus_client_tag import TagFloat, TagInt, TagBytes
from pymscada.periodic import Periodic


class MathSum:
    """Math element performs calculations on inputs."""

    def __init__(self, dsttagname: str, tagnames: list[str]):
        self.dst_tag = TagFloat(dsttagname)
        self.dst_tag.deadband = 0.1
        self.sum_tags: list[TagFloat] = []
        self.sum_values = {}
        self.value = None
        for tagname in tagnames:
            sum_tag = TagFloat(tagname)
            self.sum_tags.append(sum_tag)
            self.sum_values[tagname] = None

    def tag_callback(self, tag: TagFloat | TagInt):
        self.sum_values[tag.name] = tag.value
        if None in self.sum_values.values():
            return
        value = sum(self.sum_values.values())
        if self.value is None:
            self.value = value
        elif abs(self.value - value) > 0.2:
            logging.info(f"{self.dst_tag.name} = {value:.1f}")
            self.dst_tag.value = value

    def calculate(self, time_us: int):
        pass

    async def start(self):
        for tag in self.sum_tags:
            tag.add_callback(self.tag_callback)


class MathMean:
    def __init__(self, dsttagname: str, srctagname: str,
                 age: int, interval: int):
        self.dst_tag = TagFloat(dsttagname)
        self.dst_tag.deadband = 0.1
        self.src_tag = TagFloat(srctagname)
        self.src_tag.age_us = age * 1000000
        self.age = age
        self.interval = interval
 
    def calculate(self, time_us: int):
        time_s = int(time_us / 1e6)
        if time_s % self.interval != 0:
            return
        values = []
        for t in range(time_s, time_s - self.age, -self.interval):
            values.append(self.src_tag.get(int(t * 1e6)))
        self.dst_tag.value = sum(values) / len(values)

    async def start(self):
        pass


class MathRunner:
    """Math module for performing calculations on tag inputs."""

    def __init__(self, config: dict = {}):
        self.actions: dict[str, MathSum | MathMean] = {}
        for k, v in config.items():
            if v['action'] == 'sum':
                self.actions[k] = MathSum(k, v['tagnames'])
            elif v['action'] == 'mean':
                self.actions[k] = MathMean(k, v['tagname'], v['age'],
                                           v['interval'])
        self.periodic = Periodic(self.periodic_cb, 1.0)

    async def periodic_cb(self):
        time_us = int(time.time() * 1e6)
        for e in self.actions.values():
            e.calculate(time_us)

    async def start(self):
        """Start the math module."""
        for e in self.actions.values():
            await e.start()
        await self.periodic.start()


class Math:
    def __init__(self, bus_ip: str = '127.0.0.1', bus_port: int = 1324,
                 config: dict = {}) -> None:
        self.busclient = BusClient(bus_ip, bus_port, module='Math')
        self.busclient.history_tag = TagBytes('__history__')
        self.runner = MathRunner(config)

    async def start(self):
        await self.busclient.start()
        await self.busclient.get_history()
        await self.runner.start()