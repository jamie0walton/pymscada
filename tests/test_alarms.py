"""Test Alarms."""
from pathlib import Path
import pytest
from pymscada.alarms import Alarms, ALM, INF, split_operator, \
    standardise_tag_info
from pymscada.tag import Tag


def test_split_operator():
    assert split_operator('> 2') == {
        'operator': '>',
        'value': 2.0,
        'for': 0
    }
    assert split_operator('>= 2.0') == {
        'operator': '>=',
        'value': 2.0,
        'for': 0
    }
    assert split_operator('> 500 for 30') == {
        'operator': '>',
        'value': 500.0,
        'for': 30
    }
    try:
        split_operator('>100for60')
    except ValueError:
        assert True
    else:
        assert False


def test_standardise_tag_info():
    tag = {'name': 'TEST_TAG', 'units': 'ms', 'alarm': '> 2'}
    standardise_tag_info('TEST_TAG', tag)
    assert tag['name'] == 'TEST_TAG'
    assert tag['desc'] == 'TEST_TAG'
    assert tag['units'] == 'ms'
    assert tag['alarm'] == ['> 2']
    assert tag['type'] == float
    assert tag['dp'] == 2
    assert tag['id'] is None


@pytest.fixture(scope='module')
def alarms_db():
    """Create a fixture for DB access."""
    tag_info = {
        'localhost_ping': {
            'desc': 'Ping time to localhost',
            'units': 'ms',
            'dp': 1,
            'alarm': '> 2',
            'type': 'float',
        }
    }
    db_path = Path('tests/test_assets/alarms.sqlite')
    db_path.parent.mkdir(parents=True, exist_ok=True)
    db_path.unlink(missing_ok=True)
    return Alarms(bus_ip=None, bus_port=None,
                 db=str(db_path),
                 tag_info=tag_info)


@pytest.fixture(scope='module')
def alarms_tag():
    """Create the RTA tag."""
    return Tag('__alarms__', dict)


@pytest.fixture(scope='module')
def reply_tag():
    """Create the reply tag."""
    return Tag('__wwwserver__', dict)


def test_db_and_tag(alarms_db, alarms_tag):
    """Basic tests."""
    db = alarms_db
    tag = alarms_tag  # Alarms sets the tag value for www clients.
    assert tag.value['kind'] == INF  # INF
    assert 'Alarm logging started' in tag.value['desc']
    record = {
        'action': 'ADD',
        'alarm_string': 'TEST_TAG > 2',
        'date_ms': 1234567890123,
        'kind': ALM,
        'desc': 'Test alarm condition',
        'group': 'TEST'
    }
    db.rta_cb(record)
    assert tag.value['id'] == 2  # Second record after startup
    assert tag.value['kind'] == ALM
    assert tag.value['desc'] == 'Test alarm condition'


def test_history_queries(alarms_db, alarms_tag, reply_tag):
    """Test history queries."""
    BUSID = 999
    db = alarms_db
    a_tag: Tag = alarms_tag
    a_values = []

    def a_cb(tag):
        a_values.append(tag.value)

    a_tag.add_callback(a_cb, BUSID)
    record = {
        'action': 'ADD',
        'alarm_string': 'Alarm string',
        'date_ms': 12345,
        'kind': ALM,
        'desc': 'Test alarm',
        'group': 'TEST'
    }
    for i in range(10):
        record['date_ms'] -= 1
        record['transition'] = i % 4  # Cycle through transitions
        db.rta_cb(record)
    rq = {
        '__rta_id__': BUSID,
        'action': 'HISTORY',
        'date_ms': 12345 - 5.1,
        'reply_tag': '__wwwserver__'
    }
    db.rta_cb(rq)
    assert a_values[10]['date_ms'] == 12340
    assert a_values[-1]['desc'] == 'Alarm logging started'


def test_alarm_tag(alarms_db, alarms_tag):
    """Test alarm tag callback."""
    BUSID = 999
    db = alarms_db
    a_tag = alarms_tag
    a_values = []

    def a_cb(tag):
        a_values.append(tag.value)

    a_tag.add_callback(a_cb, BUSID)
    tag_name = 'localhost_ping'
    ping_tag = Tag(tag_name, float)
    ping_tag.value = (3.0, 12345000, BUSID)
    rq = {
        '__rta_id__': BUSID,
        'action': 'HISTORY',
        'date_ms': 10000,
        'reply_tag': '__wwwserver__'
    }
    db.rta_cb(rq)
    for record in a_values:
        if record['alarm_string'] == 'localhost_ping > 2':
            assert record['kind'] == ALM
            assert record['desc'] == 'Ping time to localhost 3.0 ms'
