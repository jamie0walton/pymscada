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
        if 'dt' not in data:
            logging.error(f'No timestamp in data for {location}, skipping update')
            return
        for parameter in self.parameters:
            tagname = f"{location}_{parameter}{suffix}"
            try:
                if parameter == 'Temp':
                    main_data = data.get('main', {})
                    value = main_data.get('temp', 0)
                elif parameter == 'WindSpeed':
                    wind_data = data.get('wind', {})
                    value = wind_data.get('speed', 0)
                elif parameter == 'WindDir':
                    wind_data = data.get('wind', {})
                    value = wind_data.get('deg', 0)
                elif parameter == 'Rain':
                    rain_data = data.get('rain', {})
                    value = rain_data.get('1h', 0)
                else:
                    logging.warning(f'Unknown parameter {parameter} for {tagname}')
                    continue
                time_us = int(data['dt'] * 1_000_000)
                self.tags[tagname].value = value, time_us, self.map_bus
                logging.debug(f'Updated {tagname} = {value} at timestamp {data["dt"]}')
            except Exception as e:
                logging.error(
                    f'Error updating {tagname}: {type(e).__name__} - {str(e)}'
                )

    async def handle_response(self):
        """Handle responses from the API."""
        while True:
            try:
                location, data = await self.queue.get()
                logging.debug(f'Processing data for {location}')
                
                if 'dt' in data:  # Current weather data
                    self.update_tags(location, data, '')
                elif 'list' in data:  # Forecast data
                    now = int(time())
                    for forecast in data['list']:
                        hours_ahead = int((forecast['dt'] - now) / 3600)
                        if hours_ahead in self.times:
                            suffix = f'_{hours_ahead:02d}'
                            self.update_tags(location, forecast, suffix)
                
                self.queue.task_done()
            except Exception as e:
                logging.error(f'Error handling response: {type(e).__name__} - {str(e)}')

    async def fetch_current_data(self):
        """Fetch current weather data for all locations."""
        try:
            if self.session is None:
                self.session = aiohttp.ClientSession()
            
            for location, coords in self.locations.items():
                base_params = {
                    'lat': coords.get('lat'),
                    'lon': coords.get('lon'),
                    'appid': self.api_key,
                    'units': self.units
                }
                
                # Validate required parameters
                if not all(base_params.values()):
                    logging.error(
                        f'Missing required parameters for {location}: '
                        f'{[k for k, v in base_params.items() if not v]}'
                    )
                    continue
                    
                try:
                    async with self.session.get(
                        self.current_url,
                        params=base_params,
                        proxy=self.proxy,
                        timeout=30  # Add timeout
                    ) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            logging.debug(
                                f'Received current weather data for {location}'
                            )
                            await self.queue.put((location, data))
                        else:
                            error_text = await resp.text()
                            logging.error(
                                f'OpenWeather API error for {location}: '
                                f'Status: {resp.status}, Response: {error_text[:200]}'
                            )
                            
                except asyncio.TimeoutError:
                    logging.error(f'Timeout fetching data for {location}')
                except aiohttp.ClientError as e:
                    logging.error(
                        f'Network error for {location}: {type(e).__name__} - {str(e)}'
                    )
                except Exception as e:
                    logging.error(
                        f'Unexpected error for {location}: {type(e).__name__} - {str(e)}'
                    )
                    
        except Exception as e:
            logging.error(f'Fatal error in fetch_current_data: {type(e).__name__} - {str(e)}')

    async def fetch_forecast_data(self):
        """Fetch forecast weather data for all locations."""
        if self.session is None:
            self.session = aiohttp.ClientSession()
        for location, coords in self.locations.items():
            base_params = {
                'lat': coords['lat'], 
                'lon': coords['lon'],
                'appid': self.api_key, 
                'units': self.units 
            }
            try:
                async with self.session.get(self.forecast_url,
                        params=base_params, proxy=self.proxy) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        logging.info(f'Queue forecast {location} {data}')
                        await self.queue.put((location, data))
                    else:
                        logging.error(f'OpenWeather forecast API error for '
                            f'{location}: Status:{resp.status}, '
                            f'Response:{await resp.text()}')
            except Exception as e:
                logging.error(f'OpenWeather forecast API error for {location}: '
                    f'Exception:{type(e).__name__}, Message:{str(e)}')

    async def poll(self):
        """Poll OpenWeather APIs every 10 minutes."""
        now = int(time())
        if now % 600 == 0:  # Every 10 minutes
            asyncio.create_task(self.fetch_current_data())
        if now % 3600 == 60:  # Every 3 hours, offset by 1 minute
            asyncio.create_task(self.fetch_forecast_data())

    async def start(self):
        """Start bus connection and API polling."""
        if self.busclient is not None:
            await self.busclient.start()
        self.handle = asyncio.create_task(self.handle_response())
        self.periodic = Periodic(self.poll, 1.0)
        await self.periodic.start()
