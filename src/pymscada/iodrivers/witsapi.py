"""Poll WITS GXP pricing real time dispatch and forecast."""
import asyncio
import aiohttp
import datetime
import logging
import socket
from time import time
from pymscada.bus_client import BusClient
from pymscada.periodic import Periodic
from pymscada.tag import Tag

class WitsAPIClient:
    """Get pricing data from WITS GXP APIs."""

    def __init__(
        self,
        bus_ip: str | None = '127.0.0.1',
        bus_port: int = 1324,
        proxy: str | None = None,
        api: dict = {},
        tags: list = []
    ) -> None:
        """
        Connect to bus on bus_ip:bus_port.

        api dict should contain:
        - client_id: WITS API client ID
        - client_secret: WITS API client secret
        - url: WITS API base URL
        - gxp_list: list of GXP nodes to fetch prices for
        - schedules: list of schedule types to fetch
        - back: number of periods to look back
        - forward: number of periods to look forward
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
        if not isinstance(tags, list):
            raise ValueError("tags must be a list")

        self.busclient = None
        if bus_ip is not None:
            self.busclient = BusClient(bus_ip, bus_port, module='WitsAPI')
        self.proxy = proxy
        self.map_bus = id(self)
        self.tags = {tagname: Tag(tagname, float) for tagname in tags}
        
        # API configuration
        self.client_id = api['client_id']
        self.client_secret = api['client_secret']
        self.base_url = api['url']
        self.gxp_list = api.get('gxp_list', [])
        self.back = api.get('back', 2)
        self.forward = api.get('forward', 72)
        
        self.session = None
        self.handle = None
        self.periodic = None
        self.queue = asyncio.Queue()

    async def get_token(self):
        """Get a new OAuth token"""
        auth_url = f"{self.base_url}/login/oauth2/token"
        data = {
            "grant_type": "client_credentials",
            "client_id": self.client_id,
            "client_secret": self.client_secret
        }
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        try:
            async with self.session.post(auth_url, data=data, headers=headers) as response:
                if response.status == 200:
                    result = await response.json()
                    self.session.headers.update({
                        "Authorization": f"Bearer {result['access_token']}"
                    })
                    return result["access_token"]
                else:
                    error_text = await response.text()
                    logging.error(f'WITS API auth error: {error_text}')
                    return None
        except Exception as e:
            logging.error(f'WITS API auth error: {type(e).__name__} - {str(e)}')
            return None

    async def get_multi_schedule_prices(self):
        """Get prices across multiple schedules"""
        endpoint = "api/market-prices/v1/prices"
        params = {
            'schedules': 'RTD,PRSS,PRSL',
            'marketType': 'E',
            'offset': 0
        }
        if self.gxp_list:
            params['nodes'] = ','.join(self.gxp_list)
        if self.back:
            params['back'] = min(self.back, 48)
        if self.forward:
            params['forward'] = min(self.forward, 48)
            
        query = '&'.join(f"{k}={v}" for k, v in params.items())
        url = f"{self.base_url}/{endpoint}?{query}"
        
        try:
            async with self.session.get(url, proxy=self.proxy) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    error_text = await response.text()
                    logging.error(f'WITS API error: {error_text}')
                    return None
        except Exception as e:
            logging.error(f'WITS API error: {type(e).__name__} - {str(e)}')
            return None

    def parse_prices(self, response):
        """Parse API response into structured price dictionary"""
        if not response:
            return {}
        prices = {}
        for schedule_data in response:
            schedule = schedule_data['schedule']
            if 'prices' not in schedule_data:
                continue
            for price in schedule_data['prices']:
                node = price['node']
                trading_time = int(datetime.datetime.fromisoformat(
                    price['tradingDateTime'].replace('Z', '+00:00')
                ).timestamp())
                last_run = int(datetime.datetime.fromisoformat(
                    price['lastRunTime'].replace('Z', '+00:00')
                ).timestamp())
                
                if node not in prices:
                    prices[node] = {}
                if trading_time not in prices[node]:
                    prices[node][trading_time] = {}
                prices[node][trading_time][schedule] = [price['price'], last_run]
        return prices

    def update_tags(self, prices):
        """Update tags with price data"""
        for node in prices:
            rtd = {}
            for trading_time in prices[node]:
                if 'RTD' in prices[node][trading_time]:
                    rtd_price, _ = prices[node][trading_time]['RTD']
                    rtd[trading_time] = rtd_price
                    continue
                prss_price = None
                prsl_price = None
                if 'PRSS' in prices[node][trading_time]:
                    prss_price, prss_last_run = prices[node][trading_time]['PRSS']
                if 'PRSL' in prices[node][trading_time]:
                    prsl_price, prsl_last_run = prices[node][trading_time]['PRSL']
                if prsl_price is not None and prss_price is not None:
                    if prss_last_run > prsl_last_run:
                        rtd[trading_time] = prss_price
                    else:
                        rtd[trading_time] = prsl_price
                    continue
                if prss_price is not None:
                    rtd[trading_time] = prss_price
                elif prsl_price is not None:
                    rtd[trading_time] = prsl_price
            tagname = f"{node}_RTD"
            if tagname in self.tags:
                for trading_time in sorted(rtd.keys()):
                    time_us = int(trading_time * 1_000_000)
                    self.tags[tagname].value = rtd[trading_time], time_us, self.map_bus

    async def handle_response(self):
        """Handle responses from the API."""
        while True:
            try:
                prices = await self.queue.get()
                if prices:
                    parsed_prices = self.parse_prices(prices)
                    self.update_tags(parsed_prices)
                self.queue.task_done()
            except Exception as e:
                logging.error(f'Error handling response: {type(e).__name__} - {str(e)}')

    async def fetch_data(self):
        """Fetch price data from WITS API."""
        try:
            if self.session is None:
                self.session = aiohttp.ClientSession()
            token = await self.get_token()
            if token:
                prices = await self.get_multi_schedule_prices()
                if prices:
                    await self.queue.put(prices)
        except Exception as e:
            logging.error(f'Error fetching data: {type(e).__name__} - {str(e)}')

    async def poll(self):
        """Poll WITS API every 5 minutes."""
        now = int(time())
        if now % 300 == 0:  # Every 5 minutes
            asyncio.create_task(self.fetch_data())

    async def start(self):
        """Start bus connection and API polling."""
        if self.busclient is not None:
            await self.busclient.start()
        self.handle = asyncio.create_task(self.handle_response())
        self.periodic = Periodic(self.poll, 1.0)
        await self.periodic.start()


