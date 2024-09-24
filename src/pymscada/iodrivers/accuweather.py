"""Poll SNMP OIDs from devices."""
import asyncio
import aiohttp
import logging
from time import time
from pymscada.bus_client import BusClient
from pymscada.periodic import Periodic
from pymscada.tag import Tag


class AccuWeatherClient:
    """Get forecast information from AccuWeather."""

    def __init__(self, bus_ip: str = '127.0.0.1', bus_port: int = 1324,
                 proxy: str = None, api: dict = {}, tags: dict = {}) -> None:
        """
        Connect to bus on bus_ip:bus_port.

        Event loop must be running.
        """
        self.busclient = None
        if bus_ip is not None:
            self.busclient = BusClient(bus_ip, bus_port, module='AccuWeather')
        self.proxy = proxy
        self.map_bus = id(self)
        self.tags = {tagname: Tag(tagname, float) for tagname in tags}
        self.api = api
        self.urls = [[f'{api["url"]}{x}?', api['query']]
                     for x in api['locations'].values()]
        self.session = aiohttp.ClientSession()
        self.queue = asyncio.Queue()
        self.init_run = True

    async def handle_response(self):
        """Unpack the weather values from the json response."""
        while True:
            resp = await self.queue.get()
            site = resp[0]
            json = resp[1]
            time_s = int(time())
            time_mod = time_s - time_s % 3600
            for record in json:
                epoch = record['EpochDateTime']
                hour = int((epoch - time_mod) / 3600)
                logging.info(f'epoch {epoch} time_s {time_s} hour {hour}')
                if hour not in self.api['times']:
                    continue
                suffix = ''
                if hour > 0:
                    suffix = f'_{int(hour)}'
                for parm, key1, key2, key in [
                    ['Temp', 'Temperature', None, 'Value'],
                    ['WindDir', 'Wind', 'Direction', 'Degrees'],
                    ['WindSpeed', 'Wind', 'Speed', 'Value'],
                    ['Rain', 'Rain', None, 'Value'],
                    ['Snow', 'Snow', None, 'Value']
                ]:
                    tagname = f'{site}{parm}{suffix}'
                    tag = self.tags[tagname]
                    if key2 is None:
                        value = record[key1][key]
                    else:
                        value = record[key1][key2][key]
                    logging.info(f'{tagname} was {tag.value} new {value}')
                    if tag.value != value:
                        tag.value = value, int(epoch * 1e6), self.map_bus

    async def fetch_data(self, location, url, query):
        """HTTP get."""
        logging.warning(f'poll {location} {url}')
        try:
            async with self.session.get(url, params=query,
                                        proxy=self.proxy) as resp:
                self.queue.put_nowait([location, await resp.json()])
        except asyncio.TimeoutError as e:
            logging.warning('AccuWeather {e}')

    async def poll(self):
        """Poll the weather site near the start of each hour."""
        now = int(time())
        if now % 3600 != 120 and not self.init_run:
            return
        self.init_run = False
        if not self.queue.empty():
            return
        # Get the weather forecasts
        query = self.api['query']
        for location, location_id in self.api['locations'].items():
            url = f'{self.api["url"]}{location_id}'
            asyncio.create_task(self.fetch_data(location, url, query))

    async def start(self):
        """Start bus connection and PLC polling."""
        if self.busclient is not None:
            await self.busclient.start()
        self.handle = asyncio.create_task(self.handle_response())
        self.periodic = Periodic(self.poll, 1.0)
        await self.periodic.start()
