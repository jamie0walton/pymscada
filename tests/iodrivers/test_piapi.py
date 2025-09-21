import asyncio
import pytest
import time
from pymscada.iodrivers.piapi import PIWebAPIClient
from pymscada.tag import Tag


@pytest.mark.asyncio
async def test_pi_webapi():
    """Test reading tag data from PI WebAPI."""
    BUSID = 999
    api_config = {
        'url': 'https://192.168.15.1/',
        'webid': 'F1Em9DA80Xftdkec1gdWFtX7NAm1eiSAyV8BG1mAAMKQIjRQUEdQSVxQSU9ORUVSXFdFQkFQSVxNT0JJTEVTQ0FEQQ',
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
        tag.add_callback(callback, BUSID)
    
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
