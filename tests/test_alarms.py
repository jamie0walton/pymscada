"""Test Alarms."""
from pathlib import Path
import pytest
import time
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
        },
        'Murupara_Temp': {
            'desc': 'Murupara Temp',
            'units': 'C',
            'dp': 1,
            'alarm': '> 2 for 30',
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
    """Basic test of the __alarms__ tag, start and first value."""
    db = alarms_db
    tag = alarms_tag  # Alarms sets the tag value for www clients.
    assert tag.value['id'] == 1  # Start record
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
    assert tag.value['id'] == 2  # First value, second record
    assert tag.value['kind'] == ALM
    assert tag.value['desc'] == 'Test alarm condition'


def test_history_queries(alarms_db, alarms_tag, reply_tag):
    """Write 10 alarms and read back the most recent."""
    BUSID = 999
    db = alarms_db
    tag: Tag = alarms_tag
    values = []

    def cb(tag):
        values.append(tag.value)

    tag.add_callback(cb, BUSID)
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
        db.rta_cb(record)
    rq = {
        '__rta_id__': BUSID,
        'action': 'HISTORY',
        'date_ms': 12345 - 5.1, # very old time.
        'reply_tag': '__wwwserver__'
    }
    db.rta_cb(rq)
    assert values[10]['date_ms'] == 12340
    # start is current time, much newer than 12340.
    assert values[-1]['desc'] == 'Alarm logging started'


def test_alarm_tag(alarms_db, alarms_tag):
    """Test request to author of alarm history."""
    BUSID = 999
    db = alarms_db
    tag = alarms_tag
    values = []

    def cb(tag):
        values.append(tag.value)

    tag.add_callback(cb, BUSID)
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
    assert '__rta_id__' not in values[0]
    assert values[0]['alarm_string'] == 'localhost_ping > 2'
    assert values[0]['desc'] == 'Ping time to localhost 3.0 ms'
    assert values[0]['date_ms'] == 12345
    assert values[1]['__rta_id__'] == BUSID
    assert values[1]['alarm_string'] == 'localhost_ping > 2'
    assert values[1]['desc'] == 'Ping time to localhost 3.0 ms'
    assert values[1]['date_ms'] == 12345
    assert values[2]['alarm_string'] == '__alarms__'
    assert values[2]['desc'] == 'Alarm logging started'


def test_delay_alarm(alarms_db, alarms_tag):
    """Test only alarms when alarm has been present for required duration."""
    BUSID = 999
    db = alarms_db
    tag = alarms_tag
    values = []

    def cb(tag):
        values.append(tag.value)

    tag.add_callback(cb, BUSID)
    tag_name = 'Murupara_Temp'
    time_us = int(time.time() * 1000000)
    temp_tag = Tag(tag_name, float)
    temp_tag.value = (50.0, time_us - 60000000, BUSID)
    temp_tag.value = (0.0, time_us - 1000000, BUSID)
    temp_tag.value = (200.0, time_us, BUSID)
    rq = {
        '__rta_id__': BUSID,
        'action': 'HISTORY',
        'date_ms': 10000,
        'reply_tag': '__wwwserver__'
    }
    db.rta_cb(rq)
    assert len(values) == 2
    assert values[0]['desc'] == 'Alarm logging started'
    assert values[1]['desc'] == 'Murupara Temp 50.0 C'
