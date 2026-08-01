"""Tests for initvalues module."""

import logging
import pytest
from pymscada.bus_client import BusClient
from pymscada.init_values import InitValuesBus, Tags


@pytest.fixture
def typed_busclient():
    """Create a bus client in pytest mode so TagTyped can be instantiated."""
    client = BusClient(ip=None, port=None, module='test_initvalues')
    yield client
    # Ensure callback state is cleaned up between tests.
    from pymscada.bus_client_tag import TagTyped
    TagTyped.del_bus_callback()


def test_tags_apply_init_to_none(typed_busclient, caplog):
    tag_info = {
        'iv_none_1': {'type': 'str', 'init': 'hello'},
    }
    tags = Tags(tag_info)
    with caplog.at_level(logging.INFO):
        initialised, corrected = tags.apply_initial_values()
    assert initialised == 1
    assert corrected == 0
    assert tags.init_specs['iv_none_1']['tag'].value == 'hello'
    assert 'initialised iv_none_1' in caplog.text


def test_tags_preserve_valid_non_none(typed_busclient, caplog):
    tag_info = {
        'iv_keep_1': {'type': 'str', 'init': 'fallback'},
    }
    tags = Tags(tag_info)
    tags.init_specs['iv_keep_1']['tag'].set_value('bus-value', 1, 0)
    with caplog.at_level(logging.INFO):
        initialised, corrected = tags.apply_initial_values()
    assert initialised == 0
    assert corrected == 0
    assert tags.init_specs['iv_keep_1']['tag'].value == 'bus-value'
    assert 'iv_keep_1' not in caplog.text


def test_tags_correct_type_mismatch(typed_busclient, caplog):
    tag_info = {
        'iv_fix_1': {'type': 'float', 'init': 1.25},
    }
    tags = Tags(tag_info)
    # TagFloat accepts int in set_value path, making this a mismatch candidate.
    tags.init_specs['iv_fix_1']['tag'].set_value(1, 1, 0)
    with caplog.at_level(logging.INFO):
        initialised, corrected = tags.apply_initial_values()
    assert initialised == 0
    assert corrected == 1
    assert tags.init_specs['iv_fix_1']['tag'].value == 1.25
    assert 'type mismatch' in caplog.text
    assert 'initialised iv_fix_1' in caplog.text


@pytest.mark.asyncio
async def test_initvalues_start_runs_init_after_wait(typed_busclient):
    module = InitValues(
        bus_ip=None,
        bus_port=1324,
        wait_s=0.0,
        tag_info={'iv_start_1': {'type': 'int', 'init': 5}},
    )
    await module.start()
    assert module.tags.init_specs['iv_start_1']['tag'].value == 5
