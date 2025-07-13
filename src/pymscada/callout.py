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


def normalise_callees(callees: list | None):
    """Normalise callees to include delay_ms and remove delay."""
    if callees is None:
        return []
    for callee in callees:
        if 'sms' not in callee:
            raise ValueError(f'Callee {callee["name"]} has no sms number')
        if 'delay' in callee:
            callee['delay_ms'] = callee['delay'] * 1000
            del callee['delay']
        else:
            callee['delay_ms'] = 0
        if 'group' not in callee:
            callee['group'] = []
    callees.sort(key=lambda x: x['delay_ms'])
    return callees


def alarm_in_callee_group(alarm_group: list, callee_group: list):
    """Check if alarm_group is in callee_group."""
    if not callee_group:
        if not alarm_group:
            return ''
        return alarm_group[0]
    if not alarm_group:
        return None
    for group in alarm_group:
        if group in callee_group:
            return group
    return None


class Callout:
    """Connect to bus_ip:bus_port, monitor alarms and manage callouts."""

    def __init__(
        self,
        bus_ip: str | None = '127.0.0.1',
        bus_port: int | None = 1324,
        rta_tag: str = '__callout__',
        alarms_tag: str | None = None,
        ack_tag: str | None = None,
        status_tag: str | None = None,
        callees: list | None = None,
        groups: list | None = None
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

        logging.warning(f'Callout {bus_ip} {bus_port} {rta_tag}')
        self.alarms = []
        self.callees = normalise_callees(callees)
        self.groups = []
        if groups is not None:
            self.groups = groups
        self.status = None
        if status_tag is not None:
            self.status = Tag(status_tag, int)
            self.status.value = IDLE
        self.busclient = BusClient(bus_ip, bus_port, module='Callout')
        self.busclient.add_callback_rta(alarms_tag, self.alarms_cb)
        self.busclient.add_callback_rta(ack_tag, self.ack_cb)
        self.rta = Tag(rta_tag, dict)
        self.rta.value = {}
        self.busclient.add_callback_rta(rta_tag, self.rta_cb)
        self.periodic = Periodic(self.periodic_cb, 1.0)

    def alarms_cb(self, request):
        """Handle alarm messages from alarms.py."""
        if request['kind'] != ALM:
            return
        alarm = {
            'date_ms': request['date_ms'],
            'alarm_string': request['alarm_string'],
            'desc': request['desc'],
            'group': request['group'],
            'sent': {}
        }
        self.alarms.append(alarm)
        logging.info(f'Added alarm to list: {alarm}')

    def ack_cb(self, ack: str):
        """Handle ACK requests for alarm acknowledgment."""
        if ack == '__all':
            self.alarms = []
            return
        callee = None
        for c in self.callees:
            if ack == c['sms']:
                callee = c
                break
            if ack == c['name']:
                callee = c
                break
        if callee is None:
            logging.warning(f'ACK rejected: {ack}')
            return
        logging.info(f'ACK accepted: {ack}')
        group = callee['group']
        remaining_alarms = []
        for alarm in self.alarms:
            alarm_group = alarm_in_callee_group(alarm['group'], group)
            if alarm_group is None:
                remaining_alarms.append(alarm)
        self.alarms = remaining_alarms

    def rta_cb(self, request):
        """Handle RTA requests for callout configuration."""
        if 'action' not in request:
            logging.warning(f'rta_cb malformed {request}')
        elif request['action'] == 'MODIFY':
            for callee in self.callees:
                if callee['name'] == request['name']:
                    if 'delay' in request:
                        callee['delay_ms'] = request['delay'] * 1000
                    if 'group' in request:
                        callee['group'] = request['group']
                    logging.info(f'Modified callee with {request}')

    def check_callouts(self):
        """Check alarms and send callouts. Can be called independently for testing."""
        time_ms = int(time.time() * 1000)
        for callee in self.callees:
            message = ''
            count = 0
            group = callee['group']
            notify_ms = time_ms - callee['delay_ms']
            for alarm in self.alarms:
                if alarm['date_ms'] < notify_ms:
                    alarm_group = alarm_in_callee_group(alarm['group'], group)
                    if alarm_group is not None and callee['name'] not in alarm['sent']:
                        count += 1
                        message += f"{alarm['alarm_string']}\n"
                        alarm['sent'][callee['name']] = time_ms
            if count > 0:
                send_message = f"{alarm_group} {count} unack alarms\n{message}"
                logging.warning(f'Callout to {callee["name"]}: {send_message}')
                self.rta.value = {'action': 'SMS', 'sms': callee['sms'],
                                  'message': send_message}
                if self.status is not None:
                    self.status.value = CALLOUT

    async def periodic_cb(self):
        """Periodic callback to check alarms and send callouts."""
        self.check_callouts()

    async def start(self):
        """Async startup."""
        await self.busclient.start()
        await self.periodic.start()
