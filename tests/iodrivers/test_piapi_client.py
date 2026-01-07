import asyncio
import pytest
import pytest_asyncio
import os
import time
from pymscada.iodrivers.piapi_client import PIWebAPIClient
from pymscada.bus_client_tag import TagFloat

BUS_ID = 999


@pytest_asyncio.fixture
async def piapi_client():
    """Create PIWebAPIClient instance."""
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
    tags_config = {
        'I_An_G1_MW': {
            'read': 'AnG1.AIMw'
        },
        'I_Ko_Gn_MW': {
            'read': 'KoGn.AIkW',
            'scale': 1000
        },
        'I_OtOs_Test': {
            'read': 'OtOs.Test',
            'write': 'OtOs.Test'
        }
    }
    client = PIWebAPIClient(bus_ip=None, bus_port=None, api=api_config,
                            tag_config=tags_config)
    return client


@pytest.mark.asyncio
async def test_piapi_client_create(piapi_client):
    """Test creating PIWebAPIClient instance."""
    assert piapi_client is not None
    test_tag = TagFloat('I_OtOs_Test')
    await piapi_client.connector.get_attributes()
    assert len(piapi_client.mapping.pi_tags) == 3
    await piapi_client.connector.get_pi_data(int(time.time()))
    assert piapi_client.mapping.pi_tags['AnG1.AIMw'].read_tag.value is not None
    assert piapi_client.mapping.pi_tags['KoGn.AIkW'].read_tag.value is not None
    assert piapi_client.mapping.pi_tags['OtOs.Test'].read_tag.value is not None
    test_value = piapi_client.mapping.pi_tags['OtOs.Test'].read_tag.value + 1.1
    if test_value > 100:
        test_value = 0.1
    test_tag.set_value(test_value, int(time.time() * 1e6), BUS_ID)
    assert test_tag.value == test_value
    await asyncio.sleep(1)
