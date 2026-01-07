import asyncio
import os
import pytest
import time
from pymscada.iodrivers.piapi import PIWebAPI
from pymscada.bus_client import BusClient
from pymscada.bus_client_tag import TagFloat

BUS_ID = 999


@pytest.fixture(scope='module')
def bus_client():
    """Create BusClient and set callback, but never start it."""
    client = BusClient(None, None)
    yield client


@pytest.mark.asyncio
async def test_pi_point_get_set():
    """Test getting tag web IDs from PI WebAPI."""
    url = os.getenv('MSCADA_PI_URL')
    webid = os.getenv('MSCADA_PI_WEBID')
    points_id = os.getenv('MSCADA_PI_POINTS_ID')
    if not url:
        pytest.skip("MSCADA_PI_URL environment variable not set")
    if not webid:
        pytest.skip("MSCADA_PI_WEBID environment variable not set")
    if not points_id:
        pytest.skip("MSCADA_PI_POINTS_ID environment variable not set")
    api_config = {
        'url': url,
        'webid': webid,
        'averaging': 300,
        'points_id': points_id
    }
    client = PIWebAPI(bus_ip=None, api=api_config)
    await client.get_pi_points_ids(contains="OtOs")
    assert len(client.points) >= 1
    await client.get_pi_points_attributes()
    assert client.points['OtOs.Test'].engunits == 'MW'
    result = await client.get_pi_value("OtOs.Test")
    OtOs_value = result.get('Value')
    assert 0 < OtOs_value < 100
    OtOs_value += 1.1
    if OtOs_value > 100:
        OtOs_value = 0.1
    await client.write_pi_data("OtOs.Test", OtOs_value, None)
    result = await client.get_pi_value("OtOs.Test")
    assert pytest.approx(result.get('Value')) == OtOs_value
    await client.get_pi_points_count(int(time.time()))
    count = client.points['OtOs.Test'].count
    assert count is not None and count > 0


@pytest.mark.asyncio
async def test_pi_collection_get(bus_client):
    """Test reading tag data from PI WebAPI."""
    url = os.getenv('MSCADA_PI_URL')
    webid = os.getenv('MSCADA_PI_WEBID')
    if not url:
        pytest.skip("MSCADA_PI_URL environment variable not set")
    if not webid:
        pytest.skip("MSCADA_PI_WEBID environment variable not set")
    api_config = {
        'url': url,
        'webid': webid,
        'averaging': 300
    }
    tags = {
        'I_An_G1_MW': {'pitag': 'AnG1.AIMw'},
        'I_An_G2_MW': {'pitag': 'AnG2.AIMw'},
        'I_Ko_Gn_MW': {'pitag': 'KoGn.AIkW', 'scale': 1000}
    }
    values = []

    def callback(tag: TagFloat):
        values.append((tag.name, tag.value, tag.time_us, tag.from_bus))

    # Add callbacks to test tags
    for tagname in tags.keys():
        tag = TagFloat(tagname)
        tag.add_callback(callback, BUS_ID)
    
    client = PIWebAPI(bus_ip=None, api=api_config, tags=tags)
    handle_task = None
    try:
        handle_task = asyncio.create_task(client.handle_response())
        t0 = int(time.time() * 1000000)
        await client.fetch_data(int(time.time()))
        await asyncio.sleep(2)
        assert len(values) == 36, "There should be 36 values"
    finally:
        if isinstance(handle_task, asyncio.Task):
            handle_task.cancel()
        if client.session:
            await client.session.close()



