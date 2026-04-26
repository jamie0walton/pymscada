"""Math module for simple mathematical functions."""
import asyncio
import logging
from pymscada.bus_client import BusClient
from pymscada.bus_client_tag import TagFloat, TagInt
from pymscada.periodic import Periodic


class MathElement:
    """Math element performs calculations on inputs."""

    def __init__(self, name: str, calc: list[dict] = []):
        self.name = name
        self.output_tag = TagFloat(name)
        self.input_tags: list[TagFloat] = []
        self.recalc_required = False
        for action in calc:
            if action.get('action') == 'add':
                input_tag = TagFloat(action['tagname'])
                input_tag.add_callback(self.tag_callback)
                self.input_tags.append(input_tag)
        self.value = 0.0

    def tag_callback(self, tag: TagFloat | TagInt):
        self.recalc_required = True

    def recalc(self):
        value = 0.0
        values = []
        for tag in self.input_tags:
            if not tag.is_none:
                value += tag.value
                values.append(tag.value)
        self.output_tag.value = value
        if abs(self.value - value) > 0.2:
            logging.info(f"{self.name} = {value:.1f} from {" ".join([f'{v:.1f}' for v in values])}")
        self.value = value

    def follow_step(self):
        if self.recalc_required:
            self.recalc()
            self.recalc_required = False


class Math:
    """Math module for performing calculations on tag inputs."""

    def __init__(self, bus_ip: str = '127.0.0.1', bus_port: int = 1324,
                 config: dict = {}) -> None:
        self.busclient = None
        if bus_ip is not None:
            self.busclient = BusClient(bus_ip, bus_port, module='Math')
        self.config = config
        self.elements = {}
        self.input_tags = {}
        self.periodic = Periodic(self.periodic_cb, 1.0)

    async def periodic_cb(self):
        for e in self.elements.values():
            e.follow_step()

    async def start(self):
        """Start the math module."""
        if self.busclient is not None:
            await self.busclient.start()
        for name, calc_config in self.config.items():
            element = MathElement(name, calc_config)
            self.elements[name] = element
            for tag in element.input_tags:
                if tag.name not in self.input_tags:
                    self.input_tags[tag.name] = tag
        if self.busclient is not None and len(self.input_tags) > 0:
            while any(tag.is_none for tag in self.input_tags.values()):
                await asyncio.sleep(1)
        await self.periodic.start()
