"""Math module for simple mathematical functions."""
import asyncio
import logging
import time
from datetime import datetime
from pymscada.bus_client import BusClient
from pymscada.bus_client_tag import TagFloat, TagInt, TagBytes
from pymscada.periodic import Periodic


class MathElement:

    def calculate(self, time_s: int, dt: datetime):
        pass

    async def start(self):
        pass


class MathSum(MathElement):
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
        else:
            self.dst_tag.value = value

    async def start(self):
        for tag in self.sum_tags:
            tag.add_callback(self.tag_callback)


class MathMean(MathElement):
    def __init__(self, dsttagname: str, srctagname: str,
                 age: int, interval: int):
        self.dst_tag = TagFloat(dsttagname)
        self.dst_tag.deadband = 0.1
        self.src_tag = TagFloat(srctagname)
        self.src_tag.age_us = age * 1000000
        self.age = age
        self.interval = interval
 
    def calculate(self, time_s: int, dt: datetime):
        if time_s % self.interval != 0:
            return
        values = []
        for t in range(time_s, time_s - self.age, -self.interval):
            values.append(self.src_tag.get(int(t * 1e6)))
        mean = sum(values) / len(values)
        self.dst_tag.value = mean
        logging.warning(f"Mean {self.dst_tag.name} {mean}")


class MathAccumulate(MathElement):
    def __init__(self, dsttagname: str, srctagname: str,
                 hour: int, interval: int):
        self.dst_tag = TagFloat(dsttagname)
        self.src_tag = TagFloat(srctagname)
        self.hour = hour
        self.interval = interval
        self.time_s = 0
        self.acc = 0
 
    def calculate(self, time_s: int, dt: datetime):
        # needs to accumulate, reseting according to time
        if self.time_s == 0:
            if self.dst_tag.is_none:
                self.dst_tag.value = 0
                return
            self.time_s = time_s
            self.acc = self.dst_tag.value
        if dt.hour == self.hour and dt.minute == 0 and dt.second == 0:
            logging.warning(f"Acc zero {self.dst_tag.name}")
            self.acc = 0
            self.dst_tag.value = 0
            return
        step_s = time_s - self.time_s
        if step_s < self.interval:
            return
        self.acc += self.src_tag.value * step_s / 3600
        self.time_s = time_s
        self.dst_tag.value = self.acc


class MathRunner:
    """Math module for performing calculations on tag inputs."""

    def __init__(self, config: dict = {}):
        self.actions: dict[str, MathElement] = {}
        for k, v in config.items():
            if v['action'] == 'sum':
                self.actions[k] = MathSum(k, v['tagnames'])
            elif v['action'] == 'mean':
                self.actions[k] = MathMean(k, v['tagname'], v['age'],
                                           v['interval'])
            elif v['action'] == 'accumulate':
                self.actions[k] = MathAccumulate(k, v['tagname'],
                    v['hour'], v['interval'])
        self.periodic = Periodic(self.periodic_cb, 1.0)

    async def periodic_cb(self):
        time_s = int(time.time())
        dt = datetime.fromtimestamp(time_s)
        for e in self.actions.values():
            e.calculate(time_s, dt)

    async def start(self):
        """Start the math module."""
        for e in self.actions.values():
            await e.start()
        await asyncio.sleep(2)
        await self.periodic.start()


class Math:
    def __init__(self, bus_ip: str = '127.0.0.1', bus_port: int = 1324,
                 config: dict = {}, tag_info: dict[str, dict] = {}) -> None:
        self.busclient = BusClient(bus_ip, bus_port, module='Math')
        self.busclient.history_tag = TagBytes('__history__')
        self.runner = MathRunner(config)

    async def start(self):
        await self.busclient.start()
        await self.busclient.get_history()
        await self.runner.start()