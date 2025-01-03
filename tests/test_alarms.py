"""Test Alarms."""
from pathlib import Path
import pytest
from pymscada.alarms import Alarms, ALM, RTN, ACT, INF
from pymscada.tag import Tag


@pytest.fixture(scope='module')
def alarms_db():
    """Create a fixture for DB access."""
    tag_info = {
        'localhost_ping': {
            'desc': 'Ping time to localhost',
            'units': 'ms',
            'alarm': '> 2',
            'type': float
        }
    }
    Path('tests/test_assets/alarms.sqlite').unlink(missing_ok=True)
    return Alarms(bus_ip=None, bus_port=None,
                 db='tests/test_assets/alarms.sqlite',
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
    
    # Verify startup record was created
    assert tag.value['transition'] == 3  # INF
    assert 'Alarm logging started' in tag.value['description']
    
    # Test adding an alarm
    record = {
        'action': 'ADD',
        'tagname': 'TEST_TAG',
        'date_ms': 1234567890123,
        'transition': ALM,
        'description': 'Test alarm condition'
    }
    db.rta_cb(record)
    assert tag.value['id'] == 2  # Second record after startup
    assert tag.value['transition'] == 0
    assert tag.value['description'] == 'Test alarm condition'


def test_history_queries(alarms_db, alarms_tag, reply_tag):
    """Test history queries."""
    BUSID = 999
    db = alarms_db
    a_tag: Tag = alarms_tag
    a_values = []

    def a_cb(tag):
        a_values.append(tag.value)

    a_tag.add_callback(a_cb, BUSID)
    
    # Add some test records
    record = {
        'action': 'ADD',
        'tagname': 'TEST_TAG',
        'date_ms': 12345,
        'transition': ALM,
        'description': 'Test alarm'
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
    assert a_values[-1]['description'] == 'Alarm logging started'

    db.close()
    assert a_values[-1]['transition'] == INF
    assert a_values[-1]['description'] == 'Alarm logging stopped'


def test_alarm_tag(alarms_db, alarms_tag):
    """Test alarm tag callback."""
    BUSID = 999
    db = alarms_db
    a_tag = alarms_tag
    a_values = []

    def a_cb(tag):
        a_values.append(tag.value)

    a_tag.add_callback(a_cb, BUSID)

    ping_tag = db.tags['localhost_ping']
    ping_tag.value = (3.0, 12345000, BUSID)
    rq = {
        '__rta_id__': BUSID,
        'action': 'HISTORY',
        'date_ms': 10000,
        'reply_tag': '__wwwserver__'
    }
    db.rta_cb(rq)
    for record in a_values:
        if record['tagname'] == 'localhost_ping':
            assert record['transition'] == ALM
            assert record['description'] == 'Ping time to localhost 3.0'
