"""PI WebAPI Client."""
import aiohttp
import asyncio
from collections.abc import Callable
from datetime import datetime
import logging
import time
from pymscada.bus_client import BusClient
from pymscada.bus_client_tag import TagFloat
from pymscada.periodic import Periodic


class PIPoint():
    """PI Point."""

    def __init__(self, pi_tagname: str):
        self.pi_tagname = pi_tagname
        self.web_id: str | None = None
        self.read_tag: TagFloat | None = None
        self.write_tag: TagFloat | None = None
        self.scale: float = 1
        self.manual_entry: bool = False
        self.eng_units: str = ''
        self.description: str = ''
        self.zero: float = 0.0
        self.span: float = 100.0


class PIWebAPIClientMaps():
    """Shared PI mapping."""

    def __init__(self, tag_config, connector):
        """Singular please."""
        self.pi_tags: dict[str, PIPoint] = {}
        self.pi_tag_lookup: dict[str, str] = {}
        self.connector = connector
        self.connector.set_mapping(self)
        for tagname, tag in tag_config.items():
            scale = 1
            if 'scale' in tag:
                scale = tag['scale']
            if 'read' in tag:
                if tag['read'] not in self.pi_tags:
                    self.pi_tags[tag['read']] = PIPoint(tag['read'])
                self.pi_tags[tag['read']].read_tag = TagFloat(tagname)
                self.pi_tags[tag['read']].scale = scale
            if 'write' in tag:
                if tag['write'] not in self.pi_tags:
                    self.pi_tags[tag['write']] = PIPoint(tag['write'])
                write_tag = TagFloat(tagname)
                write_tag.add_callback(self.write_callback)
                self.pi_tags[tag['write']].write_tag = write_tag
                self.pi_tags[tag['write']].scale = scale
                self.pi_tag_lookup[tagname] = tag['write']

    def write_callback(self, tag: TagFloat):
        pi_tagname = self.pi_tag_lookup[tag.name]
        asyncio.create_task(self.connector.write_pi_tag_value(pi_tagname, tag.value))

    def add_pi_tag_attributes(self, data: dict):
        if 'Items' not in data:
            return
        for item in data['Items']:
            pi_tagname = item['Name']
            if pi_tagname not in self.pi_tags:
                continue
            self.pi_tags[pi_tagname].web_id = item['WebId']
            self.pi_tags[pi_tagname].manual_entry = item['IsManualDataEntry']
            self.pi_tags[pi_tagname].eng_units = item['DefaultUnitsNameAbbreviation']
            self.pi_tags[pi_tagname].description = item['Description']
            self.pi_tags[pi_tagname].zero = item['Zero']
            self.pi_tags[pi_tagname].span = item['Span']

    def get_pi_tag_values(self, data: dict):
        """Update tag values from PI WebAPI summary response."""
        if 'Items' not in data:
            return
        for item in data['Items']:
            pi_tagname = item['Name']
            if pi_tagname not in self.pi_tags:
                continue
            pi_tag = self.pi_tags[pi_tagname]
            if pi_tag.read_tag is None:
                continue
            scale = pi_tag.scale
            tag = pi_tag.read_tag
            tag_values = {}
            for item in item['Items']:
                value_obj = item['Value']
                dt = datetime.fromisoformat(value_obj['Timestamp'].replace('Z', '+00:00'))
                time_us = int(dt.timestamp() * 1e6)
                tag_values[time_us] = value_obj['Value']
            times_us = sorted(tag_values.keys())
            for time_us in times_us:
                if time_us > tag.time_us:
                    if tag_values[time_us] is None:
                        logging.error(f'{tag.name} is None at {time_us}')
                        continue
                    val = tag_values[time_us]
                    if scale != 1:
                        val = val / scale
                    tag.set_value(val, time_us)

class PIWebAPIClientConnector:
    """Poll PI WebAPI for tag values, write on change."""

    def __init__(self, api: dict):
        """Set up polling client."""
        self.url = api['url']
        self.web_id = api['webid']
        self.averaging = api['averaging']
        self.mapping: PIWebAPIClientMaps
        self.periodic = Periodic(self.poll, 1.0)
        connector = aiohttp.TCPConnector(ssl=False)
        self.session = aiohttp.ClientSession(connector=connector)

    def set_mapping(self, mapping: PIWebAPIClientMaps):
        self.mapping = mapping

    async def get_attributes(self):
        url = f"{self.url}/piwebapi/elements/{self.web_id}/attributes"
        async with self.session.get(url) as response:
            data = await response.json()
            self.mapping.add_pi_tag_attributes(data)

    async def write_pi_tag_value(self, pi_tagname: str, value: float):
        """Write PI data to WebAPI."""
        url = f"{self.url}/piwebapi/streams/{self.mapping.pi_tags[pi_tagname].web_id}/value"
        payload = {'Timestamp': '*', 'Value': value}
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

    async def get_pi_data(self, time_s: int):
        """Get PI data from WebAPI."""
        start_time = datetime.fromtimestamp(time_s - self.averaging * 12).isoformat()
        end_time = datetime.fromtimestamp(time_s).isoformat()
        url = f"{self.url}/piwebapi/streamsets/{self.web_id}/summary?" \
            f"startTime={start_time}&endTime={end_time}" \
            "&summaryType=Average&calculationBasis=TimeWeighted" \
            f"&summaryDuration={self.averaging}s"
        async with self.session.get(url) as response:
            data = await response.json()
            self.mapping.get_pi_tag_values(data)

    async def poll(self):
        """Poll PI WebAPI for tag values."""
        time_s = int(time.time())
        if time_s % self.averaging == 15:
            await self.get_pi_data(time_s)

    async def start(self):
        """Start polling."""
        await self.periodic.start()


class PIWebAPIClient:
    """Connect to bus. Map to PI."""

    def __init__(self, bus_ip: str = '127.0.0.1', bus_port: int = 1324,
                 api: dict = {}, tag_config: dict = {}) -> None:
        """Set up PI client."""
        self.busclient = BusClient(bus_ip, bus_port, module='PIWebAPI')
        self.connector = PIWebAPIClientConnector(api)
        self.mapping = PIWebAPIClientMaps(tag_config, self.connector)

    async def start(self):
        """Start polling."""
        await self.connector.start()
