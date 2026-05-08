''' Template module for creating new modules.'''
import asyncio
import logging
import time
from pymscada import BusClient, BusTask, TagTyped
from pymscada.bus_client_tag import TagInt, TagFloat, TagStr, TagDict, TagBytes
from pymscada.periodic import Periodic

# Show the best practice for a bus module.

class Runner:
    def __init__(self, config: dict):
        # common generic requirements
        self.config = config
        self.queue = asyncio.Queue()
        self.periodic = Periodic(self.periodic_cb, 5.0)
        # examples
        # this busclient is not yet connected to the server
        time_tag = self.config['time_tag']  # reads history
        none_tag = self.config['none_tag']  # always None
        template_tag = self.config['template_tag']  # writes
        # Create tags and age_us here, do NOT set callbacks
        self.time_tag = TagInt(time_tag['name'])
        self.time_tag.age_us = time_tag['age_us']
        self.none_tag = TagBytes(none_tag['name'])
        self.template_tag = TagDict(template_tag['name'])
        self.template_tag.value = {'time': time.time()}

    def time_tag_cb(self, tag: TagInt):
        self.queue.put_nowait({
            'from': "time_tag",
            'value': tag.value,
            'old_value': tag.get(tag.time_us - 60000000)
        })

    def none_tag_cb(self, tag: TagInt):
        self.queue.put_nowait({
            'from': "none_tag",
            'value': tag.value
        })

    def template_tag_cb(self, tag: TagDict):
        self.queue.put_nowait({
            'from': "template_tag",
            'value': tag.value
        })

    async def periodic_cb(self):
        self.queue.put_nowait({'from': 'periodic_cb'})

    async def runner(self):
        while True:
            msg = await self.queue.get()
            logging.info(f"{msg}")

    async def start(self):
        BusTask(self.runner())
        # set callbacks after history is filled
        self.time_tag.add_callback(self.time_tag_cb)
        self.none_tag.add_callback(self.none_tag_cb)
        self.template_tag.add_callback(self.template_tag_cb)
        await self.periodic.start()


class Template:
    def __init__(self, bus_ip: str = '127.0.0.1', bus_port: int = 1324,
                 **kwargs):
        self.busclient = BusClient(bus_ip, bus_port, module='Template')
        self.busclient.history_tag = TagBytes('__history__')
        self.runner = Runner(**kwargs)

    async def start(self):
        await self.busclient.start()  # needed to fill history
        await self.busclient.get_history()  # fill history
        await self.runner.start()  # tags are now ready