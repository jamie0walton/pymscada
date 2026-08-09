"""Initialise tag values once after startup using typed tags only."""
import asyncio
import logging
import time
from pymscada.bus_client import BusClient
from pymscada.bus_client_tag import TagTyped, TYPES, CLASSES


def standardise_tag_info(tagname: str, tag: dict):
    """Correct tag dictionary in place to be suitable for web client."""
    tag['name'] = tagname
    if 'multi' in tag:
        tag['type'] = 'int'
    else:
        if 'type' not in tag:
            tag['type'] = 'float'
        else:
            if tag['type'] not in TYPES:
                tag['type'] = 'str'


class Tags:
    """Collection of tags and their init values."""

    def __init__(self, tag_info: dict[str, dict]):
        self.tags: dict[str, TagTyped] = {}
        self.init: dict[str, object] = {}
        for tagname, tag in tag_info.items():
            if 'init' not in tag:
                continue
            standardise_tag_info(tagname, tag)
            tag_cls = CLASSES[tag['type']]
            value_type = TYPES[tag['type']]
            init_type = type(tag['init'])
            if init_type is not value_type:
                logging.warning(f'{tagname} init value type is '
                                f'{init_type} not {value_type}')
            else:
                self.tags[tagname] = tag_cls(tagname)
                self.init[tagname] = tag['init']


class InitValuesLogic:
    """Apply initial tag values after the bus is live."""

    def __init__(self, tags: Tags):
        self.tags = tags

    def apply_init_values(self):
        time_us = int(time.time() * 1e6)
        for tagname in self.tags.tags:
            tag = self.tags.tags[tagname]
            init = self.tags.init[tagname]
            if tag.is_none:
                tag.set_value(init, time_us)
                logging.info(f'{tagname} initialised {init}')
            else:
                logging.info(f'{tagname} already {tag._value}')


class InitValuesBus:
    """Bus connection entry point for init values handling."""

    def __init__(self, bus_ip: str | None, bus_port: int,
                 tag_info: dict[str, dict]):
        self.busclient = BusClient(bus_ip, bus_port, module='InitValues')
        self.tags = InitValuesLogic(Tags(tag_info))

    async def start(self):
        await self.busclient.start()
        await asyncio.sleep(2.0)
        self.tags.apply_init_values()
        await asyncio.sleep(1.0)
