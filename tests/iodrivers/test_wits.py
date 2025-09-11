import asyncio
import os
import pytest
import time
from pymscada.iodrivers.witsapi import WitsAPIClient
from pymscada.tag import Tag


@pytest.mark.asyncio
async def test_wits_api():
    """Test reading pricing data from WITS API."""
    client_id = os.getenv('MSCADA_WITS_CLIENT_ID')
    client_secret = os.getenv('MSCADA_WITS_CLIENT_SECRET')
    if not client_id:
        pytest.skip("MSCADA_WITS_CLIENT_ID environment variable not set")
    if not client_secret:
        pytest.skip("MSCADA_WITS_CLIENT_SECRET environment variable not set")
    api_config = {
        'url': 'https://api.electricityinfo.co.nz',
        'client_id': client_id,
        'client_secret': client_secret,
        'gxp_list': ['MAT1101'],
        'back': 1,
        'forward': 10
    }
    tags = ['MAT1101_RTD']
    values = []

    def callback(tag: Tag):
        values.append((tag.value, tag.time_us, tag.from_bus))

    tag = Tag('MAT1101_RTD', float)
    tag.add_callback(callback)
    client = WitsAPIClient(bus_ip=None, api=api_config, tags=tags)
    try:
        handle_task = asyncio.create_task(client.handle_response())
        t0 = int(time.time()* 1000000)
        await client.fetch_data()
        await asyncio.sleep(2)
        assert len(values) > 10, "No values received"
        assert isinstance(values[0][0], float), "First value is not a float"
        assert isinstance(values[0][1], int), "First value has no timestamp"
        assert isinstance(values[0][2], int), "First value has no from_bus"
        assert values[0][2] == client.map_bus, "First value has wrong from_bus"
        future_count = 0
        past_count = 0
        for _, time_us, _ in values:
            if time_us > t0:
                future_count += 1
            else:
                past_count += 1
        assert past_count > 4, "Not enough past values received"
        assert future_count > 4, "Not enough future values received"
    finally:
        handle_task.cancel()
        if client.session:
            await client.session.close()
