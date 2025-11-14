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


def callee_in_group(alarm: 'CalloutAlarm', callee: 'CalloutCallee', groups: dict):
    if callee.group == '':
        return True
    if callee.group not in groups:
        return False
    group = groups[callee.group]
    if 'tagnames' in group:
        for tagname in group['tagnames']:
            if alarm.alarm_string.startswith(tagname):
                return True
    if 'groups' in group:
        for subgroup in group['groups']:
            if alarm.group == subgroup:
                return True
    return False


class CalloutCallee:
    """Track status of callee for callout."""

    def __init__(self, callee: dict):
        if not isinstance(callee, dict) or 'name' not in callee or \
                'sms' not in callee:
            raise ValueError(f'Callee malformed {callee}')
        self.name = callee['name']
        self.sms = callee['sms']
        self.role = callee.get('role', '')
        self.group = callee.get('group', '')
        self.delay_ms = 0


class CalloutAlarm:
    """Track status of alarm for callout."""

    def __init__(self, alm_tag_value):
        if not isinstance(alm_tag_value, dict) or \
                'date_ms' not in alm_tag_value or \
                'alarm_string' not in alm_tag_value or \
                'desc' not in alm_tag_value or \
                'group' not in alm_tag_value or \
                'kind' not in alm_tag_value:
            raise ValueError(f'alarms_cb malformed {alm_tag_value}')
        self.date_ms = alm_tag_value['date_ms']
        self.alarm_string = alm_tag_value['alarm_string']
        self.desc = alm_tag_value['desc']
        self.group = alm_tag_value['group']
        self.sent: list[str] = []
        self.remind: list[str] = []


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
        self.busclient = BusClient(bus_ip, bus_port, module='Callout')
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
        self.rta = Tag(rta_tag, dict)
        self.set_rta_value(rta_id=0)
        self.busclient.add_callback_rta(rta_tag, self.rta_cb)
        self.periodic = Periodic(self.periodic_cb, 1.0)

    def set_rta_value(self, rta_id: int):
        """Publish the current configuration to the RTA tag."""
        callees = [{'name': callee.name, 'sms': callee.sms,
                    'role': callee.role, 'group': callee.group}
                    for callee in self.callees]
        escalation = list(self.escalation.keys())
        value = {'__rta_id__': rta_id, 'callees': callees,
                 'groups': self.groups, 'escalation': escalation}
        logging.info(f'set_rta_value {rta_id} {value}')
        self.rta.value = value

    def alarms_cb(self, alm_tag):
        """Handle alarm messages from alarms.py."""
        if alm_tag.value['__rta_id__'] != 0:
            logging.info(f'alarms_cb ignoring RTA!=0 for {alm_tag.name}')
            return
        logging.info(f'alarms_cb {alm_tag.value}')
        if alm_tag.value['kind'] != ALM:
            return
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
        number = sms_recv_tag.value['number']
        name = [callee.name for callee in self.callees
                if callee.sms == number][0]
        message = sms_recv_tag.value['message'][:2].upper()
        if message in ['OK', 'AC', 'TH', 'YE']:
            new_alarms = []
            for alarm in self.alarms:
                if name in alarm.sent:
                    continue
                new_alarms.append(alarm)
            self.alarms = new_alarms
            if self.status is not None:
                self.status.value = IDLE
            logging.info(f'ACK: by {name} remaining alarms {len(new_alarms)}')

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
                    callee.role = role
                    callee.delay_ms = self.escalation.get(role, 0)
                    callee.group = group
            self.set_rta_value(rta_id=0)

    def check_callee_messages(self, callee: CalloutCallee, time_ms):
        if callee.role == '':
            return ''
        callee_alarms: list[CalloutAlarm] = []
        for alarm in self.alarms:
            if callee_in_group(alarm, callee, self.groups):
                callee_alarms.append(alarm)
        notify = False
        notify_ms = time_ms - callee.delay_ms
        remind = False
        remind_ms = notify_ms - 120000
        for alarm in callee_alarms:
            if callee.name not in alarm.sent:
                if notify_ms > alarm.date_ms:
                    notify = True
            if callee.name not in alarm.remind:
                if remind_ms > alarm.date_ms:
                    remind = True
        message = ''
        if notify:
            message += f'ALARMS {callee.role}'
            for alarm in callee_alarms:
                if callee.name in alarm.sent:
                    continue
                message += f'\n{alarm.desc}'
                alarm.sent.append(callee.name)
        elif remind:
            message += f'REMINDERS {callee.role}'
            for alarm in callee_alarms:
                if callee.name in alarm.remind:
                    continue
                message += f'\n{alarm.desc}'
                alarm.remind.append(callee.name)
        return message

    def check_alarms(self):
        """Check alarms for each callee."""
        time_ms = int(time.time() * 1000)
        for callee in self.callees:
            message = self.check_callee_messages(callee, time_ms)
            if message == '':
                continue
            logging.info(f'Sending message to {callee.name}: {message}')
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
