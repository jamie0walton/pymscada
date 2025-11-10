'''Tests for callout components.'''
import time
from pymscada.callout import ALM, Callout, CalloutAlarm, CalloutCallee
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

ESCALATION = [
    {'On Call': 60000},
    {'Backup': 180000}
]

ALARMS = [
    {
        'date_ms': 5000,
        'alarm_string': 'MtT1Fa == 1 for 3',
        'desc': 'Tower 1 Fault',
        'group': 'SI',
        'kind': ALM
    },
    {
        'date_ms': 5000,
        'alarm_string': 'MtT2Fa == 1 for 3',
        'desc': 'Tower 2 Fault',
        'group': '',
        'kind': ALM
    },
    {
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
    callee.set_role('On Call', 60000)
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
    assert alarms[0].callee_in_group(callees[0], GROUPS)
    assert alarms[0].callee_in_group(callees[1], GROUPS)
    assert not alarms[0].callee_in_group(callees[2], GROUPS)


def test_callout():
    '''Callout sends SMS for assigned alarms.'''
    BUSID = 999
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

    sms_send_tag.add_callback(cb, BUSID)
    callout = Callout(
        bus_ip=None,
        alarms_tag=alarms_tag.name,
        sms_send_tag=sms_send_tag.name,
        sms_recv_tag=sms_recv_tag.name,
        callees=CALLEES,
        groups=GROUPS,
        escalation=ESCALATION
    )
    callout.callees[0].set_role('On Call', 60000)
    callout.callees[1].set_role('Backup', 180000)
    for alarm in ALARMS:
        alarms_tag.value = alarm, 10000, BUSID
    callout.check_alarms()
    assert len(sms_sent) == 2  # +102 never gets an alarm
    assert sms_sent[0]['number'] == '+100'
    for message in ['Lake Onslow Dam Phase Fail', 'Tower 1 Fault',
                    'Tower 2 Fault']:
        assert message in sms_sent[0]['alarms']
        assert message in sms_sent[0]['reminders']
    assert sms_sent[1]['number'] == '+101'
    for message in ['Tower 1 Fault']:
        assert message in sms_sent[1]['alarms']
        assert message in sms_sent[1]['reminders']
