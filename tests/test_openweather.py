import asyncio
import os
import pytest
from pymscada.iodrivers.openweather import OpenWeatherClient


@pytest.mark.asyncio
async def test_openweather_temperature():
    """Test reading current temperature from OpenWeather API."""
    api_key = os.getenv('OPENWEATHER_API_KEY')
    if not api_key:
        pytest.skip("OPENWEATHER_API_KEY environment variable not set")
    api_config = {
        'api_key': api_key,
        'locations': {'London': {'lat': 51.5074,'lon': -0.1278}},
        'units': 'metric',
        'parameters': ['Temp'],
        'times': [1, 2, 3]
    }
    tags = ['London_Temp', 'London_Temp_01', 'London_Temp_02',
            'London_Temp_03']
    client = OpenWeatherClient(bus_ip=None, bus_port=None, api=api_config,
                               tags=tags)
    try:
        handle_task = asyncio.create_task(client.handle_response())
        await client.fetch_current_data()
        await client.fetch_forecast_data()
        await asyncio.sleep(2)
        current_temp = client.tags['London_Temp'].value
        forecast1_temp = client.tags['London_Temp_01'].value
        forecast2_temp = client.tags['London_Temp_02'].value
        forecast3_temp = client.tags['London_Temp_03'].value
        floats = 0
        nones = 0
        for temp in [current_temp, forecast1_temp, forecast2_temp, forecast3_temp]:
            if isinstance(temp, float):
                floats += 1
            else:
                nones += 1
        assert floats == 2, "Two temperatures should be floats"
        assert nones == 2, "Two temperatures should be None"
        assert -50 <= current_temp <= 50, f'Current temp {current_temp}°C' \
            ' should be in a reasonable range'
    finally:
        handle_task.cancel()
        if client.session:
            await client.session.close()
