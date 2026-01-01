import asyncio
import os
import pytest
import time
from pymscada.iodrivers.piapi import PIWebAPIClient
from pymscada.tag import Tag

BUS_ID = 999


@pytest.mark.asyncio
async def test_pi_webapi():
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

    def callback(tag: Tag):
        values.append((tag.name, tag.value, tag.time_us, tag.from_bus))

    # Add callbacks to test tags
    for tagname in tags.keys():
        tag = Tag(tagname, float)
        tag.add_callback(callback, BUS_ID)
    
    client = PIWebAPIClient(bus_ip=None, api=api_config, tags=tags)
    try:
        handle_task = asyncio.create_task(client.handle_response())
        t0 = int(time.time() * 1000000)
        await client.fetch_data(int(time.time()))
        await asyncio.sleep(2)
        assert len(values) == 36, "There should be 36 values"
    finally:
        handle_task.cancel()
        if client.session:
            await client.session.close()


@pytest.mark.asyncio
async def test_pi_get_tag_web_ids():
    """Test getting tag web IDs from PI WebAPI."""
    pytest.skip("This is often too slow for testing (>60 seconds)")
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
    client = PIWebAPIClient(bus_ip=None, api=api_config)
    await client.get_pi_points_ids()
    assert True
    t0 = int(time.time())
    now = t0 - (t0 % 86400) - 86400 * 7
    await client.get_pi_points_count(now)
    pass
