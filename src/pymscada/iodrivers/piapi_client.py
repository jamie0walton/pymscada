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


class PILink():
    """PI Link."""

    def __init__(self, tagname: str, tagconf: dict):
        self.pi_point = tagconf['pi_point']
        self.webid_name = tagconf['webid_name']
        self.web_id: str | None = None
        self.read_tag: TagFloat | None = None
        self.write_tag: TagFloat | None = None
        mode = tagconf.get('mode', 'r')
        if 'r' in mode:
            self.read_tag = TagFloat(tagname)
        if 'w' in mode:
            self.write_tag = TagFloat(tagname)
        self.scale = tagconf.get('scale', 1)
        self.manual_entry: bool = False
        self.eng_units: str = ''
        self.description: str = ''
        self.zero: float = 0.0
        self.span: float = 100.0
        self.pi_value_received: bool = False


class PIWebAPIClientMaps():
    """Shared PI mapping."""

    def __init__(self, tag_config, write_handler: Callable[[str, float],
                 None]):
        """Create tag mappings from config."""
        self.pi_links: dict[str, PILink] = {}
        self.pi_link_lookup: dict[str, PILink] = {}
        self.write_handler = write_handler
        for tagname, tagconf in tag_config.items():
            self.pi_links[tagname] = PILink(tagname, tagconf)
            pi_link = self.pi_links[tagname]
            self.pi_link_lookup[pi_link.pi_point] = pi_link
            if pi_link.write_tag is not None:
                pi_link.write_tag.add_callback(self.write_callback)

    def write_callback(self, tag: TagFloat):
        """Handle tag write callback."""
        pi_link = self.pi_links[tag.name]
        if not pi_link.pi_value_received or pi_link.web_id is None:
            logging.warning(f'{pi_link.pi_point} PI write not permitted')
            return
        self.write_handler(pi_link.pi_point, tag.value)

    def add_pi_link_attributes(self, data: dict, webid_name: str):
        """Update PI link attributes from API response."""
        if 'Items' not in data:
            return
        for item in data['Items']:
            pi_point = item['Name']
            if pi_point not in self.pi_link_lookup:
                continue
            pi_link = self.pi_link_lookup[pi_point]
            pi_link.web_id = item['WebId']
            pi_link.manual_entry = item['IsManualDataEntry']
            pi_link.eng_units = item['DefaultUnitsNameAbbreviation']
            pi_link.description = item['Description']
            pi_link.zero = item['Zero']
            pi_link.span = item['Span']

    def set_tag_value(self, pi_point: str, data: dict, webid_name: str):
        """Update tag value from PI WebAPI value response."""
        pi_link = self.pi_link_lookup[pi_point]
        if pi_link.webid_name != webid_name or pi_link.read_tag is None:
            return
        pi_link.read_tag.value = data['Value']
        pi_link.pi_value_received = True

    def set_tag_values(self, data: dict, webid_name: str):
        """Update tag values from PI WebAPI summary response."""
        if 'Items' not in data:
            return
        for pi_point_item in data['Items']:
            pi_point = pi_point_item['Name']
            if pi_point not in self.pi_link_lookup:
                continue
            pi_link = self.pi_link_lookup[pi_point]
            if pi_link.webid_name != webid_name:
                continue
            if pi_link.read_tag is None:
                continue
            scale = pi_link.scale
            tag = pi_link.read_tag
            tag_values = {}
            if 'Value' in pi_point_item:
                value_obj = pi_point_item['Value']
                dt = datetime.fromisoformat(value_obj['Timestamp'].replace('Z', '+00:00'))
                time_us = int(dt.timestamp() * 1e6)
                tag_values[time_us] = value_obj['Value']
            elif 'Items' in pi_point_item:
                for value_item in pi_point_item['Items']:
                    value_obj = value_item['Value']
                    dt = datetime.fromisoformat(value_obj['Timestamp'].replace('Z', '+00:00'))
                    time_us = int(dt.timestamp() * 1e6)
                    tag_values[time_us] = value_obj['Value']
            else:
                logging.warning(f"set_tag_values {webid_name} no valid values")
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
            pi_link.pi_value_received = True


class PIWebAPIClientConnector:
    """Poll PI WebAPI for tag values, write on change."""

    def __init__(self, api: dict, mapping: PIWebAPIClientMaps):
        """Set up polling client."""
        self.url = api['url']
        self.webids = {webid['name']: webid for webid in api['webids']}
        self.mapping = mapping
        self.periodic = Periodic(self.poll, 1.0)
        connector = aiohttp.TCPConnector(ssl=False)
        self.session = aiohttp.ClientSession(connector=connector)
        self.first = {webid['name']: True for webid in api['webids']}

    async def api_request(self, method: str, endpoint: str,
                          webid_name: str = '', payload: dict | None = None,
                          headers: dict | None = None):
        """Make API request and return parsed JSON data."""
        url = f"{self.url}{endpoint}"
        try:
            if method == 'GET':
                response = await self.session.get(url)
            elif method == 'POST':
                if headers is None:
                    headers = {'X-Requested-With': 'XmlHttpRequest'}
                response = await self.session.post(url, json=payload,
                                                   headers=headers)
            else:
                logging.error(f'PI WebAPI unsupported method: {method}')
                return None
            if response.status not in [200, 201, 202]:
                error_text = await response.text()
                logging.error(f"PI WebAPI {method} {endpoint}: Status"
                              f" {response.status}, Response: {error_text}")
                return None
            data = await response.json()
            if webid_name and isinstance(data, dict):
                logging.info(f'{webid_name} {url} {list(data.keys())}')
            return data
        except Exception:
            logging.error(f'PI WebAPI {method} {endpoint}: Request failed')
            return None

    async def get_attributes(self):
        """Fetch and update PI link attributes."""
        for webid_name, webid_config in self.webids.items():
            endpoint = f"piwebapi/elements/{webid_config['webid']}/attributes"
            data = await self.api_request('GET', endpoint, webid_name)
            if data:
                self.mapping.add_pi_link_attributes(data, webid_name)

    async def write_pi_value(self, pi_point: str, value: float):
        """Write PI value to WebAPI."""
        if pi_point not in self.mapping.pi_link_lookup:
            return None
        pi_link = self.mapping.pi_link_lookup[pi_point]
        endpoint = f"piwebapi/streams/{pi_link.web_id}/value"
        payload = {'Timestamp': '*', 'Value': value}
        return await self.api_request('POST', endpoint, pi_point, payload)

    async def get_pi_averaged_values(self, time_s: int, webid_name: str):
        """Get PI averaged data from WebAPI."""
        webid_config = self.webids[webid_name]
        avg = webid_config['averaging']
        web_id = webid_config['webid']
        start_time = datetime.fromtimestamp(time_s - avg * 12).isoformat()
        end_time = datetime.fromtimestamp(time_s).isoformat()
        endpoint = f"piwebapi/streamsets/{web_id}/summary?" \
            f"startTime={start_time}&endTime={end_time}" \
            "&summaryType=Average&calculationBasis=TimeWeighted" \
            f"&summaryDuration={avg}s"
        data = await self.api_request('GET', endpoint, webid_name)
        if data:
            self.mapping.set_tag_values(data, webid_name)

    async def get_pi_realtime_values(self, webid_name: str):
        """Get PI realtime values from WebAPI."""
        web_id = self.webids[webid_name]['webid']
        endpoint = f"piwebapi/streamsets/{web_id}/value"
        data = await self.api_request('GET', endpoint, webid_name)
        if data:
            self.mapping.set_tag_values(data, webid_name)

    async def get_pi_value(self, pi_point: str,
                           webid_name: str | None = None):
        """Get PI value from WebAPI."""
        if pi_point not in self.mapping.pi_link_lookup:
            return
        pi_link = self.mapping.pi_link_lookup[pi_point]
        webid_name_str = pi_link.webid_name if webid_name is None else webid_name
        endpoint = f"piwebapi/streams/{pi_link.web_id}/value"
        data = await self.api_request('GET', endpoint, webid_name_str)
        if data:
            self.mapping.set_tag_value(pi_point, data, webid_name_str)

    async def poll(self):
        """Poll PI WebAPI for tag values."""
        time_s = int(time.time())
        for webid_name, webid_config in self.webids.items():
            averaging = webid_config['averaging']
            if averaging == 0:
                if self.first[webid_name] or time_s % 5 == 0:
                    await self.get_pi_realtime_values(webid_name)
                    self.first[webid_name] = False
            else:
                if self.first[webid_name] or time_s % averaging == 15:
                    await self.get_pi_averaged_values(time_s, webid_name)
                    self.first[webid_name] = False

    async def start(self):
        """Start polling."""
        await self.periodic.start()


class PIWebAPIClient:
    """Connect to bus. Map to PI."""

    def __init__(self, bus_ip: str | None = '127.0.0.1', bus_port: int | None = 1324,
                 proxy: str | None = None, api: dict = {}, tags: dict = {}) -> None:
        """Set up PI client."""
        self.busclient = BusClient(bus_ip, bus_port, module='PIWebAPIClient')
        self.proxy = proxy
        self.mapping = PIWebAPIClientMaps(tags, self._write_handler)
        self.api = api

    def _write_handler(self, pi_point: str, value: float):
        """Handle tag write by creating async task."""
        asyncio.create_task(self.connector.write_pi_value(pi_point, value))

    async def start(self):
        """Start polling."""
        if self.busclient is not None:
            await self.busclient.start()
        self.connector = PIWebAPIClientConnector(self.api, self.mapping)
        await self.connector.get_attributes()
        await self.connector.start()
