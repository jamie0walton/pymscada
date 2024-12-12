"""Test OpNotes."""
# import asyncio
from pathlib import Path
import pytest
# import pytest_asyncio
from pymscada.opnotes import OpNotes
from pymscada.tag import Tag


@pytest.fixture(scope='module')
def opnotes_db():
    """Create a fixture for DB access."""
    Path('tests/test_assets/db.sqlite').unlink(missing_ok=True)
    return OpNotes(bus_ip=None, bus_port=None,
                   db='tests/test_assets/db.sqlite')


@pytest.fixture(scope='module')
def opnotes_tag():
    """Create the RTA tag."""
    return Tag('__opnotes__', dict)


@pytest.fixture(scope='module')
def reply_tag():
    """Create the reply tag."""
    return Tag('__wwwserver__', dict)


def test_db_and_tag(opnotes_db, opnotes_tag):
    """Basic tests."""
    db = opnotes_db
    tag = opnotes_tag  # OpNotes sets the tag value for www clients.
    record = {
        'action': 'ADD',
        'id': 15,
        'site': 'Aniwhenua',
        'by': 'Jamie Walton',
        'date_ms': 1234567890123,
        'note': 'Note °±²³😖.'
    }
    db.rta_cb(record)
    assert tag.value['id'] == 1
    assert tag.value['note'] == 'Note °±²³😖.'
    record['id'] = tag.value['id']
    record['action'] = 'MODIFY'
    record['note'] = 'hi'
    db.rta_cb(record)
    assert tag.value['id'] == 1
    assert tag.value['note'] == 'hi'
    record['action'] = 'DELETE'
    db.rta_cb(record)
    assert tag.value == {'id': 1}


def test_history_queries(opnotes_db, opnotes_tag, reply_tag):
    """Bigger queries."""
    BUSID = 999
    db = opnotes_db
    o_tag: Tag = opnotes_tag
    o_values = []

    def o_cb(tag):
        o_values.append(tag.value)

    o_tag.add_callback(o_cb, BUSID)
    record = {'action': 'ADD',
              'date_ms': 12345,
              'site': 'Site',
              'by': 'Me',
              'note': 'hi'}
    for i in range(10):
        record['date_ms'] -= 1
        db.rta_cb(record)  # id 1-10
    assert o_values[9]['id'] == 10
    rq = {'__rta_id__': BUSID,
          'action': 'HISTORY',
          'date_ms': 12345 - 5.1,
          'reply_tag': '__wwwserver__'}
    db.rta_cb(rq)
    assert o_values[10]['date_ms'] == 12340
    for i in range(1, 11):  # sqlite3 id counts from 1
        rq = {'action': 'DELETE', 'id': i}
        db.rta_cb(rq)
    assert o_values[-1] == {'id': 10}
