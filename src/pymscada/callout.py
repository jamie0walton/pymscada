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


def normalise_callees(callees: list | None, escalation: dict):
    """Normalise callees to include delay_ms and remove role."""
    if callees is None:
        return []
    for callee in callees:
        if 'sms' not in callee:
            raise ValueError(f'Callee {callee["name"]} has no sms number')
        if 'role' in callee:
            if callee['role'] not in escalation:
                raise ValueError(f'Invalid role: {callee["role"]}. Must be'
                                 f' one of: {list(escalation.keys())}')
            callee['delay_ms'] = escalation[callee['role']]
        else:
            callee['delay_ms'] = 0
            callee['role'] = ''
        if 'group' not in callee:
            callee['group'] = ''
    callees.sort(key=lambda x: x['delay_ms'])
    return callees


def alarm_in_group(alarm, callee_group, groups):
    """Check if alarm_group matches callee_group."""
    if callee_group == '':
        return True
    if callee_group not in groups:
        return False
    group = groups[callee_group]
    if 'tagnames' in group:
        for tagname in group['tagnames']:
            if alarm['alarm_string'].startswith(tagname):
                return True
    if 'groups' in group:
        for group in group['groups']:
            if group in alarm['group']:
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
        callees: list | None = None,
        groups: dict = {},
        escalation: list | None = None
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

        self.escalation = [list(d.keys())[0] for d in escalation]
        self.delay_ms = {list(d.keys())[0]: list(d.values())[0]
                         for d in escalation}
        logging.warning(f'Callout {bus_ip} {bus_port} {rta_tag} '
                        f'{sms_send_tag} {sms_recv_tag}')
        self.alarms = []
        self.callees = normalise_callees(callees, self.delay_ms)
        self.groups = groups
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
        self.busclient = BusClient(bus_ip, bus_port, module='Callout')
        self.rta = Tag(rta_tag, dict)
        self.rta.value = {'__rta_id__': 0,
                          'callees': self.callees,
                          'groups': self.groups,
                          'escalation': self.escalation}
        self.busclient.add_callback_rta(rta_tag, self.rta_cb)
        self.periodic = Periodic(self.periodic_cb, 1.0)

    def alarms_cb(self, alm_tag):
        """Handle alarm messages from alarms.py."""
        alarm = alm_tag.value
        if 'kind' not in alarm or alarm['kind'] != ALM:
            return
        alarm = {
            'date_ms': alarm['date_ms'],
            'alarm_string': alarm['alarm_string'],
            'desc': alarm['desc'],
            'group': alarm['group'],
            'sent': {}
        }
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

    def sms_recv_cb(self, sms_recv_tag: dict):
        """Handle SMS messages from the modem."""
        logging.info(f'sms_recv_cb {sms_recv_tag.value}')
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
            self.rta.value = {'__rta_id__': request['__rta_id__'],
                              'callees': self.callees,
                              'groups': self.groups,
                              'escalation': self.escalation}
        elif request['action'] == 'MODIFY':
            send_update = False
            for callee in self.callees:
                if callee['name'] == request['name']:
                    if 'role' in request:
                        callee['role'] = request['role']
                        callee['delay_ms'] = self.delay_ms.get(
                            request['role'], 30000)
                    if 'group' in request:
                        callee['group'] = request['group']
                    logging.info(f'Modified callee with {request}')
                    send_update = True
            if send_update:
                self.rta.value = {'__rta_id__': 0,
                                  'callees': self.callees,
                                  'groups': self.groups,
                                  'escalation': self.escalation}

    def check_callouts(self):
        """Check alarms and send callouts."""
        time_ms = int(time.time() * 1000)
        for callee in self.callees:
            if not callee['role']:
                continue
            count = 0
            message = ''
            notify_ms = time_ms - callee['delay_ms']
            remind_ms = notify_ms - 60000
            for alarm in self.alarms:
                if not alarm_in_group(alarm, callee['group'], self.groups):
                    continue
                if notify_ms < alarm['date_ms']:
                    continue
                if callee['name'] not in alarm['sent']:
                    message += f"{alarm['desc']}\n"
                    alarm['sent'][callee['name']] = SENT
                    count += 1
                    continue
                if remind_ms < alarm['date_ms']:
                    continue
                if alarm['sent'][callee['name']] != REMIND:
                    message += f"REMIND {alarm['desc']}\n"
                    alarm['sent'][callee['name']] = REMIND
                    count += 1
            if count > 0:
                if len(message) > 200:
                    message = message[:200] + '\n...'
                send_message = f"{count} Alarms\n{message}"
                self.sms_send_tag.value = {
                    'number': callee['sms'],
                    'message': send_message
                }
                if self.status is not None:
                    self.status.value = CALLOUT

    async def periodic_cb(self):
        """Periodic callback to check alarms and send callouts."""
        self.check_callouts()

    async def start(self):
        """Async startup."""
        await self.busclient.start()
        await self.periodic.start()
