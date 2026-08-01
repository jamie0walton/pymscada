"""Initialise tag values once after startup using typed tags only."""
import asyncio
import logging
import time
from pymscada.bus_client import BusClient
from pymscada.bus_client_tag import TagBytes, TagDict, TagFloat, TagInt, \
    TagList, TagStr, TagTyped, TYPES, CLASSES


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


def declared_type(meta: dict[str, dict]) -> str:
    # Multi-select style metadata maps to int in existing behavior.
    if 'multi' in meta:
        return 'int'
    type_name = meta.get('type', 'float')
    if type_name not in CLASSES:
        return 'str'
    return type_name


def matches_declared_type(value, declared_type: str) -> bool:
    if declared_type == 'int':
        return type(value) is int
    if declared_type == 'float':
        return type(value) is float
    if declared_type == 'str':
        return type(value) is str
    if declared_type == 'dict':
        return type(value) is dict
    if declared_type == 'list':
        return type(value) is list
    if declared_type == 'bytes':
        return type(value) is bytes
    return False


def coerce_init_value(value, declared_type: str):
    # Keep coercion minimal and explicit.
    if declared_type == 'float' and type(value) is int:
        return float(value)
    return value


class Tags:
    """Simple collection of typed tags built from tag metadata."""

    def __init__(self, tag_info: dict[str, dict]):
        self.tag_info = tag_info
        self.tags: dict[str, TagTyped] = {}
        for tagname, tag in self.tag_info.items():
            if 'init' not in tag:
                continue
            standardise_tag_info(tagname, tag)
            tag_cls = CLASSES[tag['type']]
            self.tags[tagname] = tag_cls(tagname)
        pass

    def items(self):
        return self.tags.items()

class InitValuesLogic:
    """Apply initial tag values after the bus is live."""

    def __init__(self, tag_info: dict[str, dict]):
        self.tags = Tags(tag_info)
        pass
    def apply_initial_values(self) -> tuple[int, int]:
        """Apply/correct values and return (initialised, corrected) counts."""
        initialised = 0
        corrected = 0

        tags = Tags(self.tag_info)

        for tagname, tag in tags.items():
            meta = tags.tag_info.get(tagname, {})
            tag_type = declared_type(meta)
            init_value = meta.get('init')
            if init_value is None:
                continue
            if tag.is_none:
                if self.set_to_init(tag, init_value, tag_type, reason='none'):
                    initialised += 1
                continue

            value = tag._value
            if matches_declared_type(value, tag_type):
                continue
            logging.warning(
                f'initvalues: {tagname} type mismatch declared={tag_type} '
                f'actual={type(value).__name__}; overwriting with init'
            )


        return initialised, corrected

    def set_to_init(self, tag: TagTyped, init_value, declared_type: str,
                    reason: str):
        value = coerce_init_value(init_value, declared_type)
        try:
            tag.set_value(value, int(time.time() * 1e6), 0)
        except Exception as exc:
            logging.warning(
                f'initvalues: failed to set {tag.name} to init value '
                f'{value!r} ({reason}): {exc}'
            )
            return False
        logging.info(f'initvalues {tag.name} to {value} for {reason}')
        return True

    async def start(self):
        await asyncio.sleep(2.0)
        for tagname, tag in Tags(self.tag_info).items():
            pass

class InitValuesBus:
    """Bus connection entry point for init values handling."""

    def __init__(self, bus_ip: str | None = '127.0.0.1', bus_port: int = 1324,
                 tag_info: dict[str, dict] = {}):
        self.busclient = BusClient(bus_ip, bus_port, module='InitValues')
        self.tag_info = tag_info or {}

    async def start(self):
        await self.busclient.start()
        init = InitValuesLogic(self.tag_info)
        await init.start()
