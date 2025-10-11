"""Test Callout."""
import pytest
from pymscada.callout import Callout, alarm_in_callee_group, ALM


BUS_ID = 123
CALLEES = [
    {
        'name': 'Name Lazy',
        'sms': 'Lazy number',
        'role': 'Off',
        'group': ['NoZone']
    },
    {
        'name': 'Name System',
        'sms': 'System number',
        'role': 'OnCall',
        'group': ['System']
    },
    {
        'name': 'Name All',
        'sms': 'All number',
        'role': 'Standby',
        'group': []
    }
]
GROUPS = [
    {
        'name': 'My Group',
        'group': 'System'
    }
]

@pytest.fixture(scope='function')
def callout():
    """Create a fixture for Callout."""
    return Callout(bus_ip=None, callees=CALLEES, groups=GROUPS)


def test_alarm_in_callee_group(callout):
    """Test group in group."""
    # obvious match
    assert alarm_in_callee_group(['Test'], ['Test']) == 'Test'
    # empty callee_group should match all, otherwise match explicit
    assert alarm_in_callee_group([], []) == ''
    assert alarm_in_callee_group(['Test'], []) == 'Test'
    assert alarm_in_callee_group([], ['Test']) == None
    # return the first matching group from alarms if there is a match
    assert alarm_in_callee_group(['Test', '2'], ['Test', '2']) == 'Test'
    # return None is there is no match
    assert alarm_in_callee_group(['Other'], ['Test']) is None


def test_callout(callout):
    """Basic tests."""
    co = callout
    # test callees and groups setup from config variables
    # find the specific callee by name since sorting may change order
    lazy_callee = next(c for c in co.callees if c['name'] == 'Name Lazy')
    assert lazy_callee['delay_ms'] == 0  # Off role
    assert lazy_callee['group'] == ['NoZone']
    system_callee = next(c for c in co.callees if c['name'] == 'Name System')
    assert system_callee['delay_ms'] == 60000  # OnCall role
    all_callee = next(c for c in co.callees if c['name'] == 'Name All')
    assert all_callee['delay_ms'] == 180000  # Standby role
    assert co.groups[0]['name'] == 'My Group'
    assert co.groups[0]['group'] == 'System'
    # test update in the callee group
    callee_update = {
        'action': 'MODIFY',
        'name': 'Name Lazy',
        'group': ['Still No Zone']
    }
    co.rta_cb(callee_update)
    lazy_callee = next(c for c in co.callees if c['name'] == 'Name Lazy')
    assert lazy_callee['delay_ms'] == 0  # Off role
    assert lazy_callee['group'] == ['Still No Zone']


def test_new_alarm(callout):
    """Test new alarm."""
    values = []

    def rta_cb(tag):
        # the SMS modem module should monitor this tag to send SMSs
        values.append(tag.value)

    co = callout
    co.rta.add_callback(rta_cb, BUS_ID)
    # alarm should go to All and System
    alarm = {
        'date_ms': 12345,
        'alarm_string': 'sys alarm',
        'kind': ALM,
        'desc': 'System Alarm',
        'group': ['System']
    }
    co.alarms_cb(alarm)
    co.check_callouts()
    # doesn't have to be in the order in CALLEES, but it is so ...
    assert values[0]['action'] == 'SMS'
    assert values[0]['sms'] == 'System number'
    assert values[1]['action'] == 'SMS'
    assert values[1]['sms'] == 'All number'
    assert 'Name Lazy' not in co.alarms[0]['sent']
    assert 'Name System' in co.alarms[0]['sent']
    assert 'Name All' in co.alarms[0]['sent']
    # Alarm should go to All
    alarm = {
        'date_ms': 12345,
        'alarm_string': 'all alarm',
        'kind': ALM,
        'desc': 'Broadcast Alarm',
        'group': []
    }
    co.alarms_cb(alarm)
    co.check_callouts()
    assert values[2]['action'] == 'SMS'
    assert values[2]['sms'] == 'All number'
    assert 'Name Lazy' not in co.alarms[1]['sent']
    assert 'Name All' in co.alarms[1]['sent']
    assert 'Name System' not in co.alarms[1]['sent']


def test_ack_functionality(callout):
    """Test ACK functionality with sent hash."""
    co = callout
    alarm = {
        'date_ms': 12345,
        'alarm_string': 'sys alarm',
        'kind': ALM,
        'desc': 'System Alarm',
        'group': ['System']
    }
    co.alarms_cb(alarm)
    co.check_callouts()
    assert 'Name Lazy' not in co.alarms[0]['sent']
    assert 'Name System' in co.alarms[0]['sent']
    assert 'Name All' in co.alarms[0]['sent']
    co.ack_cb('__all')
    assert len(co.alarms) == 0
    co.alarms_cb(alarm)
    co.check_callouts()
    co.ack_cb('Lazy number')
    assert len(co.alarms) == 1
    co.ack_cb('System number')
    assert len(co.alarms) == 0
    co.alarms_cb(alarm)
    co.check_callouts()
    co.ack_cb('All number')
    assert len(co.alarms) == 0
