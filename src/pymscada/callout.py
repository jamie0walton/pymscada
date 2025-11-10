"""Callout handling."""
import logging
import socket
import time
from pymscada.bus_client import BusClient
from pymscada.periodic import Periodic
from pymscada.tag import Tag


"""
Callout monitors alarms and sends SMS notifications to configured callees.

Configuration:
- callees: list of recipients with SMS numbers, delays, and group filters
- alarms_tag: RTA tag receiving alarms from alarms.py
- ack_tag: tag for receiving acknowledgments
- rta_tag: tag for configuration updates and SMS requests

Operation:
1. Collect alarms from alarms_tag (kind=ALM)
2. For each callee, check if alarms match their group filter and delay
3. Send SMS via rta_tag when conditions are met
4. Track sent notifications in alarm['sent'] hash
5. Remove alarms when callee acknowledges (matches their group)
"""

ALM = 0

IDLE = 0
NEW_ALM = 1
CALLOUT = 2

SENT = 0
REMIND = 1


class CalloutCallee:
    """Track status of callee for callout."""

    def __init__(self, callee: dict):
        if not isinstance(callee, dict) or 'name' not in callee or \
                'sms' not in callee:
            logging.warning(f'Callee malformed {callee}')
            return
        self.name = callee['name']
        self.sms = callee['sms']
        self.role = callee.get('role', '')
        self.group = callee.get('group', '')
        self.delay_ms = 0

    def set_role(self, role: str, delay_ms: int):
        self.role = role
        self.delay_ms = delay_ms

    def set_group(self, group: str):
        self.group = group


class CalloutAlarm:
    """Track status of alarm for callout."""

    def __init__(self, alm_tag_value):
        if not isinstance(alm_tag_value, dict) or \
                'date_ms' not in alm_tag_value or \
                'alarm_string' not in alm_tag_value or \
                'desc' not in alm_tag_value or \
                'group' not in alm_tag_value or \
                'kind' not in alm_tag_value or \
                alm_tag_value['kind'] != ALM:
            logging.warning(f'alarms_cb malformed {alm_tag_value}')
            return
        self.date_ms = alm_tag_value['date_ms']
        self.alarm_string = alm_tag_value['alarm_string']
        self.desc = alm_tag_value['desc']
        self.group = alm_tag_value['group']
        self.sent: set[CalloutCallee] = set()
        self.remind: set[CalloutCallee] = set()

    def callee_in_group(self, callee: CalloutCallee, groups: dict):
        if callee.group == '':
            return True
        if callee.group not in groups:
            return False
        group = groups[callee.group]
        if 'tagnames' in group:
            for tagname in group['tagnames']:
                if self.alarm_string.startswith(tagname):
                    return True
        if 'groups' in group:
            for group in group['groups']:
                if self.group in group:
                    return True
        return False


class Callout:
    """Connect to bus_ip:bus_port, monitor alarms and manage callouts."""

    def __init__(
        self,
        bus_ip: str | None = '127.0.0.1',
        bus_port: int | None = 1324,
        rta_tag: str = '__callout__',
        alarms_tag: str | None = None,
        sms_send_tag: str | None = None,
        sms_recv_tag: str | None = None,
        ack_tag: str | None = None,
        status_tag: str | None = None,
        callees: list = [],
        groups: dict = {},
        escalation: dict = {}
    ) -> None:
        """
        Connect to bus_ip:bus_port, monitor alarms and manage callouts.

        Monitor alarms via alarms_tag and manage callout messages to callees
        based on configured delays and area filters.

        Event loop must be running.

        For testing only: bus_ip can be None to skip connection.
        """
        if bus_ip is None:
            logging.warning('Callout has bus_ip=None, only use for testing')
        else:
            try:
                socket.gethostbyname(bus_ip)
            except socket.gaierror as e:
                raise ValueError(f'Cannot resolve IP/hostname: {e}')
            if not isinstance(bus_port, int):
                raise TypeError('bus_port must be an integer')
            if not 1024 <= bus_port <= 65535:
                raise ValueError('bus_port must be between 1024 and 65535')
        if not isinstance(rta_tag, str) or not rta_tag:
            raise ValueError('rta_tag must be a non-empty string')
        if alarms_tag is None:
            raise ValueError('alarms_tag must be defined')
        if sms_send_tag is None:
            raise ValueError('sms_send_tag must be defined')
        if sms_recv_tag is None:
            raise ValueError('sms_recv_tag must be defined')

        logging.warning(f'Callout {bus_ip} {bus_port} {rta_tag} '
                        f'{sms_send_tag} {sms_recv_tag}')
        self.callees: list[CalloutCallee] = []
        for callee in callees:
            self.callees.append(CalloutCallee(callee))
        self.groups = groups
        self.escalation = escalation
        self.alarms: list[CalloutAlarm] = []
        self.alarms_tag = Tag(alarms_tag, dict)
        self.alarms_tag.add_callback(self.alarms_cb)
        self.sms_recv_tag = Tag(sms_recv_tag, dict)
        self.sms_recv_tag.add_callback(self.sms_recv_cb)
        self.sms_send_tag = Tag(sms_send_tag, dict)
        if ack_tag is not None:
            self.ack_tag = Tag(ack_tag, int)
            self.ack_tag.add_callback(self.ack_cb)
        if status_tag is not None:
            self.status = Tag(status_tag, int)
        else:
            self.status = None
        self.busclient = BusClient(bus_ip, bus_port, module='Callout')
        self.rta = Tag(rta_tag, dict)
        self.set_rta_value(rta_id=0)
        self.busclient.add_callback_rta(rta_tag, self.rta_cb)
        self.periodic = Periodic(self.periodic_cb, 1.0)

    def set_rta_value(self, rta_id: int):
        """Publish the current configuration to the RTA tag."""
        callees = [{'name': callee.name, 'sms': callee.sms, 'role': callee.role,
                    'group': callee.group, 'delay_ms': callee.delay_ms}
                    for callee in self.callees]
        self.rta.value = {'__rta_id__': rta_id,
                          'callees': callees,
                          'groups': self.groups,
                          'escalation': list(self.escalation.keys())}

    def alarms_cb(self, alm_tag):
        """Handle alarm messages from alarms.py."""
        alarm = CalloutAlarm(alm_tag.value)
        self.alarms.append(alarm)
        logging.info(f'Added alarm to list: {alarm}')
        if self.status is not None and self.status.value == IDLE:
            self.status.value = NEW_ALM

    def ack_cb(self, ack_tag):
        """Handle ACK requests for alarm acknowledgment."""
        if ack_tag.value == 1:
            self.alarms = []
            if self.status is not None:
                self.status.value = IDLE
            logging.info('ACK: all alarms cleared')

    def sms_recv_cb(self, sms_recv_tag: Tag):
        """Handle SMS messages from the modem."""
        logging.info(f'sms_recv_cb {sms_recv_tag.value}')
        if not isinstance(sms_recv_tag.value, dict) or \
                'number' not in sms_recv_tag.value or \
                'message' not in sms_recv_tag.value:
            logging.warning(f'sms_recv_cb invalid {sms_recv_tag.value}')
            return
        _number = sms_recv_tag.value['number']
        message = sms_recv_tag.value['message'][:2].upper()
        if message in ['OK', 'AC', 'TH']:
            self.alarms = []
            if self.status is not None:
                self.status.value = IDLE
            logging.info('ACK: all alarms cleared')

    def rta_cb(self, request):
        """Handle RTA requests for callout configuration."""
        logging.info(f'rta_cb {request}')
        if 'action' not in request:
            logging.warning(f'rta_cb malformed {request}')
            return
        if request['action'] == 'GET CONFIG':
            self.set_rta_value(rta_id=request['__rta_id__'])
        elif request['action'] == 'MODIFY':
            for callee in self.callees:
                if callee.name == request['name']:
                    if not 'role' in request and not 'group' in request:
                        logging.warning(f'rta_cb invalid request: {request}')
                        return
                    role = request['role']
                    group = request['group']
                    valid_role = role == '' or role in self.escalation
                    valid_group = group == '' or group in self.groups
                    if not valid_role or not valid_group:
                        logging.warning(f'rta_cb MODIFY invalid: {request}')
                        return
                    callee.set_role(role, self.escalation.get(role, 0))
                    callee.set_group(group)
            self.set_rta_value(rta_id=0)

    def check_callee_messages(self, callee, time_ms):
        if callee.role == '':
            return ''
        callee_alarms = set()
        for alarm in self.alarms:
            if alarm.callee_in_group(callee, self.groups):
                callee_alarms.add(alarm)
        notify_message = ''
        remind_message = ''
        notify_ms = time_ms - callee.delay_ms
        remind_ms = notify_ms - 60000
        notify = []
        remind = []
        for alarm in callee_alarms:
            if not callee in alarm.sent and notify_ms > alarm.date_ms:
                notify_message += f'{alarm.desc}\n'
                alarm.sent.add(callee)
            else:
                notify.append(alarm)
            if not callee in alarm.remind and remind_ms > alarm.date_ms:
                remind_message += f'{alarm.desc}\n'
                alarm.remind.add(callee)
            else:
                remind.append(alarm)
        message = ''
        if notify_message != '':
            message += f'ALARMS\n{notify_message}'
            for alarm in notify:
                message += f'{alarm.desc}\n'
                alarm.sent.add(callee)
        if remind_message != '':
            message += f'REMINDERS\n{remind_message}'
            for alarm in remind:
                message += f'{alarm.desc}\n'
                alarm.remind.add(callee)
        return message

    def check_alarms(self):
        """Check alarms for each callee."""
        time_ms = int(time.time() * 1000)
        for callee in self.callees:
            message = self.check_callee_messages(callee, time_ms)
            if message == '':
                continue
            self.sms_send_tag.value = {
                'number': callee.sms,
                'message': message
            }
            if self.status is not None:
                self.status.value = CALLOUT

    async def periodic_cb(self):
        """Periodic callback to check alarms and send callouts."""
        self.check_alarms()

    async def start(self):
        """Async startup."""
        await self.busclient.start()
        await self.periodic.start()
