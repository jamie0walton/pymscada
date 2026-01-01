'''Tests for callout components.'''
import time
from pymscada.callout import ALM, Callout, CalloutAlarm, CalloutCallee, callee_in_group
from pymscada.tag import Tag

CALLEES = [
    {'name': 'The Dude', 'sms': '+100'},
    {'name': 'Freddy', 'sms': '+101', 'group': 'Wind'},
    {'name': 'Jack', 'sms': '+102', 'group': 'Inv'}
]

GROUPS = {
    'Wind': {
        'groups': ['SI']
    },
    'Invercargill': {
        'tagnames': ['Fh']
    }
}

ESCALATION = {
    'On Call': 60000,
    'Backup': 180000
}

ALARMS = [
    {
        '__rta_id__': 0,    
        'date_ms': 5000,
        'alarm_string': 'MtT1Fa == 1 for 3',
        'desc': 'Tower 1 Fault',
        'group': 'SI',
        'kind': ALM
    },
    {
        '__rta_id__': 0,    
        'date_ms': 5000,
        'alarm_string': 'MtT2Fa == 1 for 3',
        'desc': 'Tower 2 Fault',
        'group': '',
        'kind': ALM
    },
    {
        '__rta_id__': 0,    
        'date_ms': 5000,
        'alarm_string': 'OnDmDIPhFa == 1',
        'desc': 'Lake Onslow Dam Phase Fail',
        'group': '',
        'kind': ALM
    },
]

def test_callout_callee():
    '''CalloutCallee stores identity and configuration.'''
    callee = CalloutCallee(CALLEES[0])
    callee.role = 'On Call'
    callee.delay_ms = 60000
    assert callee.name == 'The Dude'
    assert callee.delay_ms == 60000
    assert callee.group == ''


def test_callout_alarm():
    '''CalloutAlarm tracks alarm metadata and grouping.'''
    alarms = []
    for alarm in ALARMS:
        alarms.append(CalloutAlarm(alarm))
    callees = []
    for callee in CALLEES:
        callees.append(CalloutCallee(callee))
    assert callee_in_group(alarms[0], callees[0], GROUPS)
    assert callee_in_group(alarms[0], callees[1], GROUPS)
    assert not callee_in_group(alarms[0], callees[2], GROUPS)


def test_callee_in_group():
    '''Check callee messages for notify and remind.'''
    dude = CalloutCallee(CALLEES[0])
    freddy = CalloutCallee(CALLEES[1])
    south_0 = CalloutAlarm(ALARMS[0])
    empty_1 = CalloutAlarm(ALARMS[1])
    empty_2 = CalloutAlarm(ALARMS[2])
    assert callee_in_group(south_0, dude, GROUPS)
    assert callee_in_group(empty_1, dude, GROUPS)
    assert callee_in_group(empty_2, dude, GROUPS)
    assert callee_in_group(south_0, freddy, GROUPS)
    assert not callee_in_group(empty_1, freddy, GROUPS)
    assert not callee_in_group(empty_2, freddy, GROUPS)

def test_callout():
    '''Callout sends SMS for assigned alarms.'''
    BUS_ID = 999
    alarms_tag = Tag('alarm_tag', dict)
    sms_send_tag = Tag('send_tag', dict)
    sms_recv_tag = Tag('recv_tag', dict)
    alarms_tag.value = {}
    sms_send_tag.value = {}
    sms_recv_tag.value = {}
    sms_sent = []

    def cb(tag: Tag):
        if not isinstance(tag.value, dict) or \
                'message' not in tag.value or \
                'number' not in tag.value:
            return
        lines = tag.value['message'].split('\n')
        alarms = []
        reminders = []
        section = None
        for line in lines:
            if not line:
                continue
            if line.startswith('ALARMS'):
                section = alarms
                continue
            if line.startswith('REMINDERS'):
                section = reminders
                continue
            if section is not None:
                section.append(line)
        sms_sent.append({'number': tag.value['number'],
                         'alarms': alarms,
                         'reminders': reminders})

    sms_send_tag.add_callback(cb, BUS_ID)
    callout = Callout(
        bus_ip=None,
        alarms_tag=alarms_tag.name,
        sms_send_tag=sms_send_tag.name,
        sms_recv_tag=sms_recv_tag.name,
        callees=CALLEES,
        groups=GROUPS,
        escalation=ESCALATION
    )
    callout.callees[0].role = 'On Call'
    callout.callees[0].delay_ms = 60000
    callout.callees[1].role = 'Backup'
    callout.callees[1].delay_ms = 180000
    for alarm in ALARMS:
        alarms_tag.value = alarm, 10000, BUS_ID
    callout.check_alarms()
    assert len(sms_sent) == 2  # +102 never gets an alarm
    assert sms_sent[0]['number'] == '+100'
    for message in ['Lake Onslow Dam Phase Fail', 'Tower 1 Fault',
                    'Tower 2 Fault']:
        assert message in sms_sent[0]['alarms']
    assert sms_sent[1]['number'] == '+101'
    for message in ['Tower 1 Fault']:
        assert message in sms_sent[1]['alarms']
