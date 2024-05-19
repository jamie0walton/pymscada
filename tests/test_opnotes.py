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
        'oid': 15,
        'site': 'Aniwhenua',
        'operator': 'Jamie Walton',
        'datetime': 1234567890123,
        'note': 'Note °±²³😖.'
    }
    db.rta_cb(record)
    assert tag.value['oid'] == 1
    assert tag.value['note'] == 'Note °±²³😖.'
    record['oid'] = tag.value['oid']
    record['action'] = 'MODIFY'
    record['note'] = 'hi'
    db.rta_cb(record)
    assert tag.value['oid'] == 1
    assert tag.value['note'] == 'hi'
    record['action'] = 'DELETE'
    db.rta_cb(record)
    assert tag.value == {'oid': 1}


def test_history_queries(opnotes_db, opnotes_tag, reply_tag):
    """Bigger queries."""
    db = opnotes_db
    o_tag: Tag = opnotes_tag
    r_tag: Tag = reply_tag
    o_values = []
    r_values = []

    def o_cb(tag):
        o_values.append(tag.value)

    def r_cb(tag):
        r_values.append(tag.value)

    o_tag.add_callback(o_cb, 999)
    r_tag.add_callback(r_cb, 999)
    record = {'action': 'ADD',
              'datetime': 12345,
              'site': 'Site',
              'operator': 'Me',
              'note': 'hi'}
    for i in range(10):
        record['datetime'] -= 1
        db.rta_cb(record)  # oid 1-10
    assert o_values[9]['oid'] == 10
    rq = {'action': 'HISTORY',
          'datetime': 12345 - 3,
          'reply_tag': '__wwwserver__'}
    db.rta_cb(rq)
    assert r_values[1]['datetime'] == 12340
    for i in range(1, 11):  # sqlite3 oid counts from 1
        rq = {'action': 'DELETE', 'oid': i}
        db.rta_cb(rq)
    o_values[19] == {'oid': 10}
