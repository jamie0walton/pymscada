"""Poll OSI PI WebAPI for tag values."""
import asyncio
import aiohttp
from datetime import datetime
import logging
import socket
from time import time
from pymscada.misc import find_nodes
from pymscada.bus_client import BusClient
from pymscada.bus_client_tag import TagFloat
from pymscada.periodic import Periodic


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
        self.instrumenttag = None
        self.zero = None
        self.span = None


class PIWebAPI:
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
            self.tags[tagname] = TagFloat(tagname)
            self.pitag_map[config['pitag']] = tagname
            if 'scale' in config:
                self.scale[tagname] = config['scale']
                
        connector = aiohttp.TCPConnector(ssl=False)
        self.session = aiohttp.ClientSession(connector=connector)
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
                tag.set_value(data[time_us], time_us)

    async def handle_response(self):
        """Handle responses from the API."""
        while True:
            values = await self.queue.get()
            for value in find_nodes('Name' , values):
                if value['Name'] in self.pitag_map:
                    self.update_tags(value['Name'], value['Items'])
            self.queue.task_done()

    async def get_pi_value(self, pointname: str):
        """Get PI value from WebAPI."""
        point = self.points[pointname]
        url = f"{self.base_url}/piwebapi/streams/{point.web_id}/value"
        async with self.session.get(url) as response:
            return await response.json()

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

    async def write_pi_data(self, pointname: str, value: float, time_us: int | None):
        """Write PI data to WebAPI."""
        point = self.points[pointname]
        url = f"{self.base_url}/piwebapi/streams/{point.web_id}/value"
        if time_us is None:
            timestamp = '*'
        else:
            timestamp = datetime.fromtimestamp(time_us / 1e6).isoformat() + 'Z'
        payload = {'Timestamp': timestamp, 'Value': value}
        headers = {'X-Requested-With': 'XmlHttpRequest'}
        async with self.session.post(url, json=payload, headers=headers) as response:
            if response.status in [200, 201, 202]:
                try:
                    return await response.json()
                except Exception:
                    return None
            else:
                error_text = await response.text()
                logging.error(f'PI WebAPI write error: Status {response.status}, Response: {error_text}')
                return None

    async def get_pi_points_ids(self, contains: str | None = None):
        """Get PI points IDs from PI WebAPI."""
        self.points = {}
        start_index = 0
        max_count = 1000
        while True:
            url = f"{self.base_url}/piwebapi/dataservers/{self.points_id}/points?startIndex={start_index}&maxCount={max_count}"
            async with self.session.get(url) as response:
                json_data = await response.json()
            items = json_data.get('Items', [])
            if len(items) == 0:
                break
            for data in items:
                if contains is not None and contains not in data['Name']:
                    continue
                point = PIPoint(data['Name'], data['WebId'])
                self.points[data['Name']] = point
            start_index += max_count

    async def get_pi_points_attributes(self):
        """Get PI point data from PI WebAPI."""
        for tagname in self.points:
            point = self.points[tagname]
            url = f"{self.base_url}/piwebapi/points/{point.web_id}/attributes"
            async with self.session.get(url) as response:
                json_data = await response.json()
                # Parse Items array where each item has Name and Value
                attributes = {item['Name']: item['Value'] for item in json_data.get('Items', [])}
                point.compdev = attributes.get('compdev')
                point.compmax = attributes.get('compmax')
                point.excdev = attributes.get('excdev')
                point.excmax = attributes.get('excmax')
                point.engunits = attributes.get('engunits')
                point.descriptor = attributes.get('descriptor')
                point.instrumenttag = attributes.get('instrumenttag')

    async def get_pi_points_count(self, now: int):
        """Get PI point data from PI WebAPI."""
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
