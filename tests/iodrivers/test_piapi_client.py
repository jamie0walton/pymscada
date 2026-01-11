import asyncio
import pytest
import pytest_asyncio
import os
import time
from pymscada.iodrivers.piapi_client import PIWebAPIClient
from pymscada.bus_client_tag import TagTyped, TagFloat

BUS_ID = 999


@pytest_asyncio.fixture
async def piapi_client():
    """Create PIWebAPIClient instance."""
    url = os.getenv('MSCADA_PI_URL')
    webid_5min = os.getenv('MSCADA_PI_WEBID_5MIN')
    webid_real_time = os.getenv('MSCADA_PI_WEBID_REALTIME')
    if not url:
        pytest.skip("MSCADA_PI_URL environment variable not set")
    if not webid_5min:
        pytest.skip("MSCADA_PI_WEBID_5MIN environment variable not set")
    if not webid_real_time:
        pytest.skip("MSCADA_PI_WEBID_REALTIME environment variable not set")
    api_config = {
        'url': url,
        'webids': [
            {'name': '5M', 'webid': webid_5min, 'averaging': 300},
            {'name': 'RT', 'webid': webid_real_time, 'averaging': 0}
        ]
    }
    tags_config = {
        'I_An_G1_MW': {
            'pi_point': 'AnG1.AIMw',
            'webid_name': '5M',
            'mode': 'r'
        },
        'I_Ko_Gn_MW': {
            'pi_point': 'KoGn.AIkW',
            'webid_name': '5M',
            'mode': 'r',
            'scale': 1000
        },
        'I_OtOs_Test': {
            'pi_point': 'OtOs.Test',
            'webid_name': 'RT',
            'mode': 'rw'
        }
    }
    client = PIWebAPIClient(bus_ip=None, bus_port=None, api=api_config,
                            tags=tags_config)
    await client.start()
    while True:
        await asyncio.sleep(0.1)
        if not any(client.connector.first.values()):
            break
    await asyncio.sleep(0.2)
    return client


@pytest.mark.asyncio
async def test_piapi_client_create(piapi_client):
    """Test creating PIWebAPIClient instance."""
    assert piapi_client is not None
    received_tags = {}
    for pi_link in piapi_client.mapping.pi_links.values():
        if pi_link.read_tag is not None:
            received_tags[pi_link.read_tag.name] = pi_link.read_tag
    assert type(received_tags['I_An_G1_MW'].value) == float
    assert type(received_tags['I_Ko_Gn_MW'].value) == float
    assert type(received_tags['I_OtOs_Test'].value) == float 

@pytest.mark.asyncio
async def test_piapi_client_tag(piapi_client):
    """Test writing to PIWebAPIClient instance."""
    tag = TagFloat('I_OtOs_Test')
    assert type(tag.value) == float
    old_value = tag.value
    new_value = old_value + 15.1
    if new_value > 100:
        new_value = 0.1
    set_time_us = int(time.time() * 1e6)
    tag.set_value(new_value, set_time_us, BUS_ID)
    await asyncio.sleep(1.0)  # allow time for PI to update tag value
    await piapi_client.connector.get_pi_value('OtOs.Test')
    while tag.time_us <= set_time_us:
        await asyncio.sleep(0.1)
    assert pytest.approx(tag.value) == new_value
