"""Poll OSI PI WebAPI for tag values."""
import asyncio
import aiohttp
from datetime import datetime
import logging
import socket
from time import time
from pymscada.misc import find_nodes
from pymscada.bus_client import BusClient
from pymscada.periodic import Periodic
from pymscada.tag import Tag

class PIWebAPIClient:
    """Get tag data from OSI PI WebAPI."""

    def __init__(
        self,
        bus_ip: str | None = '127.0.0.1',
        bus_port: int = 1324,
        proxy: str | None = None,
        api: dict = {},
        tags: dict = {}
    ) -> None:
        """
        Connect to bus on bus_ip:bus_port.

        api dict should contain:
        - url: PI WebAPI base URL
        - webid: PI WebID for the stream set
        - averaging: averaging period in seconds
        
        tags dict should contain:
        - tagname: pitag mapping for each tag
        """
        if bus_ip is not None:
            try:
                socket.gethostbyname(bus_ip)
            except socket.gaierror:
                raise ValueError(f"Invalid bus_ip: {bus_ip}")
        if not isinstance(proxy, str) and proxy is not None:
            raise ValueError("proxy must be a string or None")
        if not isinstance(api, dict):
            raise ValueError("api must be a dictionary")
        if not isinstance(tags, dict):
            raise ValueError("tags must be a dictionary")

        self.busclient = None
        if bus_ip is not None:
            self.busclient = BusClient(bus_ip, bus_port, module='PIWebAPI')
        self.proxy = proxy
        self.base_url = api['url'].rstrip('/')
        self.webid = api['webid']
        self.averaging = api.get('averaging', 300)
        self.tags = {}
        self.pitag_map = {}
        self.scale = {}
        for tagname, config in tags.items():
            self.tags[tagname] = Tag(tagname, float)
            self.pitag_map[config['pitag']] = tagname
            if 'scale' in config:
                self.scale[tagname] = config['scale']
        self.session = None
        self.handle = None
        self.periodic = None
        self.queue = asyncio.Queue()

    def update_tags(self, pitag: str, values: list):
        tag = self.tags[self.pitag_map[pitag]]
        scale = None
        if tag.name in self.scale:
            scale = self.scale[tag.name]
        data = {}
        for item in values:
            value = item['Value']
            dt = datetime.fromisoformat(value['Timestamp'].replace('Z', '+00:00'))
            time_us = int(dt.timestamp() * 1e6)
            data[time_us] = value['Value']
        times_us = sorted(data.keys())
        for time_us in times_us:
            if time_us > tag.time_us:
                if data[time_us] is None:
                    logging.error(f'{tag.name} is None at {time_us}')
                    continue
                if scale is not None:
                    data[time_us] = data[time_us] / scale
                tag.value = data[time_us], time_us

    async def handle_response(self):
        """Handle responses from the API."""
        while True:
            values = await self.queue.get()
            for value in find_nodes('Name' , values):
                if value['Name'] in self.pitag_map:
                    self.update_tags(value['Name'], value['Items'])
            self.queue.task_done()

    async def get_pi_data(self, now):
        """Get PI data from WebAPI."""
        time = now - (now % self.averaging)
        start_time = datetime.fromtimestamp(time - self.averaging * 12).isoformat()
        end_time = datetime.fromtimestamp(time).isoformat()
        url = f"{self.base_url}/piwebapi/streamsets/{self.webid}/summary?" \
            f"startTime={start_time}&endTime={end_time}" \
            "&summaryType=Average&calculationBasis=TimeWeighted" \
            f"&summaryDuration={self.averaging}s"
        async with self.session.get(url) as response:
            return await response.json()

    async def fetch_data(self, now):
        """Fetch values from PI Web API."""
        try:
            if self.session is None:
                connector = aiohttp.TCPConnector(ssl=False)
                self.session = aiohttp.ClientSession(connector=connector)
            json_data = await self.get_pi_data(now)
            if json_data:
                await self.queue.put(json_data)
        except Exception as e:
            logging.error(f'Error fetching data: {type(e).__name__} - {str(e)}')

    async def poll(self):
        """Poll PI API."""
        now = int(time())
        if now % self.averaging == 15:
            asyncio.create_task(self.fetch_data(now))

    async def start(self):
        """Start bus connection and API polling."""
        if self.busclient is not None:
            await self.busclient.start()
        self.handle = asyncio.create_task(self.handle_response())
        self.periodic = Periodic(self.poll, 1.0)
        await self.periodic.start()
