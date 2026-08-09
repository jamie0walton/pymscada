"""Tests for initvalues module."""

import logging
import pytest
from pymscada.bus_client import BusClient
from pymscada.init_values import InitValuesBus, InitValuesLogic, Tags


@pytest.fixture
def busclient():
    """Create a bus client in pytest mode so TagTyped can be instantiated."""
    client = BusClient(ip=None, port=None, module='test_initvalues')
    yield client
    # Ensure callback state is cleaned up between tests.
    from pymscada.bus_client_tag import TagTyped
    TagTyped.del_bus_callback()


def test_tags_apply_init_to_none(busclient, caplog):
    tag_info = {
        'iv_none_1': {'type': 'str', 'init': 'hello'},
    }
    tags = Tags(tag_info)
    logic = InitValuesLogic(tags)
    with caplog.at_level(logging.INFO):
        logic.apply_init_values()
    assert tags.tags['iv_none_1'].value == 'hello'
    assert 'iv_none_1 initialised' in caplog.text


def test_tags_preserve_valid_non_none(busclient, caplog):
    tag_info = {
        'iv_keep_1': {'type': 'str', 'init': 'fallback'},
    }
    tags = Tags(tag_info)
    tags.tags['iv_keep_1'].set_value('bus-value', 1, 0)
    logic = InitValuesLogic(tags)
    with caplog.at_level(logging.INFO):
        logic.apply_init_values()
    assert tags.tags['iv_keep_1'].value == 'bus-value'
    assert 'already bus-value' in caplog.text


def test_tags_skip_init_type_mismatch(busclient, caplog):
    tag_info = {
        'iv_fix_1': {'type': 'float', 'init': 'what'},
    }
    with caplog.at_level(logging.INFO):
        tags = Tags(tag_info)
    assert 'iv_fix_1' not in tags.tags
    assert 'iv_fix_1' not in tags.init
    assert 'iv_fix_1 init value type is' in caplog.text


@pytest.mark.asyncio
async def test_initvalues_start_runs_init(busclient, monkeypatch):
    async def no_sleep(_):
        return None

    monkeypatch.setattr('pymscada.init_values.asyncio.sleep', no_sleep)
    module = InitValuesBus(
        bus_ip=None,
        bus_port=1324,
        tag_info={'iv_start_1': {'type': 'int', 'init': 5}},
    )
    await module.start()
    assert module.tags.tags.tags['iv_start_1'].value == 5
