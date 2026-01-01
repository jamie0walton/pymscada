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


class PIPoint:
    """PI Point."""

    def __init__(self, tagname: str, web_id: str):
        self.tagname = tagname
        self.web_id = web_id
        self.pointid = None
        self.count = None
        self.compdev = None
        self.compmax = None
        self.excdev = None
        self.excmax = None
        self.engunits = None
        self.descriptor = None
        self.zero = None
        self.span = None


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
        self.web_id = api['webid']
        self.points_id = api.get('points_id', None)
        self.averaging = api.get('averaging', 300)
        self.tags = {}
        self.points: dict[str, PIPoint] = {}
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
        url = f"{self.base_url}/piwebapi/streamsets/{self.web_id}/summary?" \
            f"startTime={start_time}&endTime={end_time}" \
            "&summaryType=Average&calculationBasis=TimeWeighted" \
            f"&summaryDuration={self.averaging}s"
        async with self.session.get(url) as response:
            return await response.json()


    def set_session(self):
        """Get or create a session."""
        if self.session is None:
            connector = aiohttp.TCPConnector(ssl=False)
            self.session = aiohttp.ClientSession(connector=connector)


    async def get_pi_points_ids(self):
        """Get PI points IDs from PI WebAPI."""
        self.set_session()
        url = f"{self.base_url}/piwebapi/dataservers/{self.points_id}/points"
        async with self.session.get(url) as response:
            json_data = await response.json()
        self.points = {}
        for data in json_data['Items']:
            point = PIPoint(data['Name'], data['WebId'])
            self.points[data['Name']] = point


    async def get_pi_points_attributes(self):
        """Get PI point data from PI WebAPI."""
        self.set_session()
        for tagname in self.points:
            point = self.points[tagname]
            url = f"{self.base_url}/piwebapi/points/{point.web_id}/attributes"
            async with self.session.get(url) as response:
                json_data = await response.json()
                # Parse Items array where each item has Name and Value
                attributes = {item['Name']: item['Value'] for item in json_data.get('Items', [])}
                point.compdev = attributes.get('CompDev')
                point.compmax = attributes.get('CompMax')
                point.excdev = attributes.get('ExcDev')
                point.excmax = attributes.get('ExcMax')
                point.engunits = attributes.get('EngUnits')
                point.descriptor = attributes.get('Descriptor')


    async def get_pi_points_count(self, now: int):
        """Get PI point data from PI WebAPI."""
        self.set_session()
        start_time = datetime.fromtimestamp(now - 86400).isoformat()
        end_time = datetime.fromtimestamp(now).isoformat()
        for tagname in self.points:
            point = self.points[tagname]
            url = f"{self.base_url}/piwebapi/streams/{point.web_id}/summary?" \
                f"startTime={start_time}&endTime={end_time}" \
                "&summaryType=Count&calculationBasis=EventWeighted"
            async with self.session.get(url) as r2:
                json_data = await r2.json()
                point.count = json_data['Items'][0]['Value']['Value']


    async def fetch_data(self, now):
        """Fetch values from PI Web API."""
        self.set_session()
        try:
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
