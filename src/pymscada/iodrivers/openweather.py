"""Poll OpenWeather current and forecast APIs."""
import asyncio
import aiohttp
import logging
from time import time
from pymscada.bus_client import BusClient
from pymscada.periodic import Periodic
from pymscada.tag import Tag

class OpenWeatherClient:
    """Get weather data from OpenWeather Current and Forecast APIs."""

    def __init__(self, bus_ip: str = '127.0.0.1', bus_port: int = 1324,
                 proxy: str = None, api: dict = {}, tags: dict = {}) -> None:
        """
        Connect to bus on bus_ip:bus_port.

        api dict should contain:
        - api_key: OpenWeatherMap API key
        - locations: dict of location names and coordinates
        - times: list of hours ahead to fetch forecast data for
        - units: optional units (standard, metric, imperial)
        """
        self.busclient = None
        if bus_ip is not None:
            self.busclient = BusClient(bus_ip, bus_port, module='OpenWeather')
        self.proxy = proxy
        self.map_bus = id(self)
        self.tags = {tagname: Tag(tagname, float) for tagname in tags}
        self.api_key = api['api_key']
        self.units = api.get('units', 'standard')
        self.locations = api.get('locations', {})
        self.parameters = api.get('parameters', {})
        self.times = api.get('times', [3, 6, 12, 24, 48])
        self.current_url = "https://api.openweathermap.org/data/2.5/weather"
        self.forecast_url = "https://api.openweathermap.org/data/2.5/forecast"
        self.queue = asyncio.Queue()
        self.session = None
        self.handle = None
        self.periodic = None

    def update_tags(self, location, data, suffix):
        """Update tags for forecast weather."""
        for parameter in self.parameters:
            tagname = f"{location}_{parameter}{suffix}"
            if parameter == 'Temp':
                value = data['main']['temp']
            elif parameter == 'WindSpeed':
                value = data['wind']['speed']
            elif parameter == 'WindDir':
                value = data['wind'].get('deg', 0)
            elif parameter == 'Rain':
                value = data.get('rain', {}).get('1h', 0)
            try:
                self.tags[tagname].value = value
            except KeyError:
                logging.warning(f'{tagname} not found setting weather value')

    async def handle_response(self):
        """Handle responses from the API."""
        while True:
            location, data = await self.queue.get()
            now = int(time())
            if 'dt' in data:
                self.update_tags(location, data, '')
            elif 'list' in data:
                for forecast in data['list']:
                    hours_ahead = int((forecast['dt'] - now) / 3600)
                    if hours_ahead not in self.times:
                        continue
                    suffix = f'_{hours_ahead:02d}'
                    self.update_tags(location, forecast, suffix)

    async def fetch_current_data(self):
        """Fetch current weather data for all locations."""
        logging.info('fetching current')
        if self.session is None:
            self.session = aiohttp.ClientSession()
        for location, coords in self.locations.items():
            base_params = {'lat': coords['lat'], 'lon': coords['lon'],
                'appid': self.api_key, 'units': self.units }
            try:
                async with self.session.get(self.current_url,
                        params=base_params, proxy=self.proxy) as resp:
                    if resp.status == 200:
                        self.queue.put_nowait((location, await resp.json()))
                    else:
                        logging.warning('OpenWeather current API error for '
                            f'{location}: {resp.status}')
            except Exception as e:
                logging.warning('OpenWeather current API error for '
                    f'{location}: {e}')

    async def fetch_forecast_data(self):
        """Fetch forecast weather data for all locations."""
        logging.info('fetching forecast')
        if self.session is None:
            self.session = aiohttp.ClientSession()
        for location, coords in self.locations.items():
            base_params = {'lat': coords['lat'], 'lon': coords['lon'],
                'appid': self.api_key, 'units': self.units }
            try:
                async with self.session.get(self.forecast_url,
                        params=base_params, proxy=self.proxy) as resp:
                    if resp.status == 200:
                        self.queue.put_nowait((location, await resp.json()))
                    else:
                        logging.warning('OpenWeather forecast API error '
                            f'for {location}: {resp.status}')
            except Exception as e:
                logging.warning('OpenWeather forecast API error for '
                    f'{location}: {e}')

    async def poll(self):
        """Poll OpenWeather APIs every 10 minutes."""
        now = int(time())
        if now % 600 == 0:  # Every 10 minutes
            asyncio.create_task(self.fetch_current_data())
        if now % 10800 == 60:  # Every 3 hours, offset by 1 minute
            asyncio.create_task(self.fetch_forecast_data())

    async def start(self):
        """Start bus connection and API polling."""
        if self.busclient is not None:
            await self.busclient.start()
        self.handle = asyncio.create_task(self.handle_response())
        self.periodic = Periodic(self.poll, 1.0)
        await self.periodic.start()
