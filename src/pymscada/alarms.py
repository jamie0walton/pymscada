"""Alarms handling."""
import logging
import sqlite3  # note that sqlite3 has blocking calls
import socket
import time
from pymscada.bus_client import BusClient
from pymscada.periodic import Periodic
from pymscada.tag import Tag, TYPES

ALM = 0
RTN = 1
ACT = 2
INF = 3
TIMING = 4
KIND = {
    ALM: 'ALM',
    RTN: 'RTN',
    ACT: 'ACT',
    INF: 'INF'
}

NORMAL = 0
ALARM = 1

"""
Database schema:

alarms contains an event log of changes as they occur, this
includes information on actions taken by the alarm system.

CREATE TABLE IF NOT EXISTS alarms (
    id INTEGER PRIMARY KEY ASC,
    date_ms INTEGER,
    alarm_string TEXT,
    kind INTEGER,     # one of ALM, RTN, ACT, INF
    desc TEXT,
    group TEXT
)
"""


def standardise_tag_info(tagname: str, tag: dict):
    """Correct tag dictionary in place to be suitable for modules."""
    tag['name'] = tagname
    tag['id'] = None
    if 'desc' not in tag:
        logging.warning(f"Tag {tagname} has no description, using name")
        tag['desc'] = tag['name']
    if 'group' not in tag:
        tag['group'] = ''
    if 'multi' in tag:
        tag['type'] = int
    else:
        if 'type' not in tag:
            tag['type'] = float
        else:
            if tag['type'] not in TYPES:
                tag['type'] = str
            else:
                tag['type'] = TYPES[tag['type']]
    if 'dp' not in tag:
        if tag['type'] == int:
            tag['dp'] = 0
        else:
            tag['dp'] = 2
    if 'units' not in tag:
        tag['units'] = ''
    if 'alarm' in tag:
        if isinstance(tag['alarm'], str):
            tag['alarm'] = [tag['alarm']]
        if not isinstance(tag['alarm'], list):
            logging.warning(f"Tag {tagname} has invalid alarm {tag['alarm']}")
            del tag['alarm']


def split_operator(alarm: str) -> dict:
    """Split alarm string into operator and value."""
    tokens = alarm.split(' ')
    if len(tokens) not in (2, 4):
        raise ValueError(f"Invalid alarm {alarm}")
    if tokens[0] not in ['>', '<', '==', '>=', '<=']:
        raise ValueError(f"Invalid alarm {alarm}")
    alm_dict = {'for': 0, 'operator': tokens[0], 'value': None}
    try:
        alm_dict['value'] = float(tokens[1])
    except ValueError:
        raise ValueError(f"Invalid alarm {alarm}")
    if len(tokens) == 4:
        if tokens[2] != 'for':
            raise ValueError(f"Invalid alarm {alarm}")
        try:
            alm_dict['for'] = int(tokens[3])
        except ValueError:
            raise ValueError(f"Invalid alarm {alarm}")
    return alm_dict


class Alarm():
    """
    Single alarm class.

    Alarms are defined by a tag and a condition. Tags may have multiple
    conditions, each combination of tag and condition is a separate Alarm.

    Monitors tag value through the Tag callback. Tracks in alarm state.
    Notifies Alarms of state changes via state callback.
    """

    def __init__(self, tagname: str, tag: dict, alarm: str, group: str,
                 state_cb) -> None:
        """Initialize alarm with tag and condition(s)."""
        self.alarm_id = f'{tagname} {alarm}'
        self.tag = Tag(tagname, tag['type'])
        self.tag.desc = tag['desc']
        self.tag.dp = tag['dp']
        self.tag.units = tag['units']
        self.tag.add_callback(self.callback)
        self.group = group
        self.state_cb = state_cb
        self.alarm = split_operator(alarm)
        self.in_alarm = False
        self.disabled_until = 0

    def callback(self, tag: Tag):
        """Handle tag value changes and generate ALM/RTN messages."""
        if tag.value is None or tag.time_us < self.disabled_until:
            return
        value = float(tag.value)
        new_in_alarm = False
        op = self.alarm['operator']
        if op == '>':
            new_in_alarm = value > self.alarm['value']
        elif op == '<':
            new_in_alarm = value < self.alarm['value']
        elif op == '==':
            new_in_alarm = value == self.alarm['value']
        elif op == '>=':
            new_in_alarm = value >= self.alarm['value']
        elif op == '<=':
            new_in_alarm = value <= self.alarm['value']
        if new_in_alarm == self.in_alarm:
            return
        if new_in_alarm:
            if self.alarm['for'] > 0:
                self.state_cb(self, TIMING)
            else:
                self.state_cb(self, ALM)
        else:
            self.state_cb(self, RTN)
        self.in_alarm = new_in_alarm

    def check_duration(self, current_time_us: int):
        """Check if alarm condition has been met for required duration."""
        if current_time_us - self.tag.time_us >= self.alarm['for'] * 1000000:
            self.state_cb(self, ALM)


class Alarms:
    """Connect to bus_ip:bus_port, store and provide Alarms."""

    def __init__(
        self,
        bus_ip: str | None = '127.0.0.1',
        bus_port: int | None = 1324,
        db: str | None = None,
        table: str = 'alarms',
        tag_info: dict[str, dict] = {},
        rta_tag: str = '__alarms__'
    ) -> None:
        """
        Connect to bus_ip:bus_port, serve and update alarms database.

        Open an Alarms table, creating if necessary. Provide additions
        and history requests via the rta_tag.

        Event loop must be running.

        For testing only: bus_ip can be None to skip connection.
        """
        if db is None:
            raise SystemExit('Alarms db must be defined')
        if bus_ip is None:
            logging.warning('Alarms has bus_ip=None, only use for testing')
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
        if not isinstance(table, str) or not table:
            raise ValueError('table must be a non-empty string')

        logging.warning(f'Alarms {bus_ip} {bus_port} {db} {rta_tag}')
        self.alarms: list[Alarm] = []
        self.checking_alarms: list[Alarm] = []
        self.in_alarm: list[Alarm] = []
        for tagname, tag in tag_info.items():
            standardise_tag_info(tagname, tag)
            if 'alarm' not in tag or tag['type'] not in (int, float):
                continue
            group = tag['group']
            for alarm in tag['alarm']:
                new_alarm = Alarm(tagname, tag, alarm, group, self.state_cb)
                self.alarms.append(new_alarm)
        self.busclient = BusClient(bus_ip, bus_port, module='Alarms')
        self.rta = Tag(rta_tag, dict)
        self.rta.value = {'__rta_id__': 0}
        self.busclient.add_callback_rta(rta_tag, self.rta_cb)
        self.busclient.add_tag(self.rta)
        self._init_db(db, table)
        self.periodic = Periodic(self.periodic_cb, 1.0)

    def _init_db(self, db, table):
        """Initialize the database table schema."""
        self.connection = sqlite3.connect(db)
        self.table = table
        self.cursor = self.connection.cursor()
        
        # Check SQLite version for RETURNING clause support (requires >= 3.35.0)
        sqlite_version = sqlite3.sqlite_version_info
        self.has_returning = sqlite_version >= (3, 35, 0)
        if not self.has_returning:
            logging.warning(
                f'SQLite version {sqlite3.sqlite_version} is older than 3.35.0. '
                f'RETURNING clause not supported, using fallback method. '
                f'Consider upgrading SQLite for better performance.'
            )
        
        query = (
            'CREATE TABLE IF NOT EXISTS ' + self.table + ' '
            '(id INTEGER PRIMARY KEY ASC, '
            'date_ms INTEGER, '
            'alarm_string TEXT, '
            'kind INTEGER, '
            'desc TEXT, '
            '"group" TEXT)'
        )
        self.cursor.execute(query)
        self.connection.commit()
        
        startup_record = {
            'action': 'ADD',
            'date_ms': int(time.time() * 1000),
            'alarm_string': self.rta.name,
            'kind': INF,
            'desc': 'Alarm logging started',
            'group': '__system__'
        }
        self.rta_cb(startup_record)

    async def periodic_cb(self):
        """Periodic callback to check alarms."""
        current_time_us = int(time.time() * 1000000)
        for alarm in self.checking_alarms[:]:
            alarm.check_duration(current_time_us)

    def state_cb(self, alarm: Alarm, state: int):
        """Handle alarm state changes."""
        if state == TIMING:
            self.checking_alarms.append(alarm)
        elif state == ALM:
            if alarm in self.checking_alarms:
                self.checking_alarms.remove(alarm)
            self.in_alarm.append(alarm)
            self.generate_alarm(alarm, ALM)
        elif state == RTN:
            if alarm in self.checking_alarms:
                self.checking_alarms.remove(alarm)
            if alarm in self.in_alarm:
                self.in_alarm.remove(alarm)
            self.generate_alarm(alarm, RTN)

    def generate_alarm(self, alarm: Alarm, kind: int):
        """Generate alarm message."""
        value = alarm.tag.value
        time_us = alarm.tag.time_us
        logging.warning(f'Alarm {alarm.alarm_id} {value} {KIND[kind]}')
        self.rta_cb({
            'action': 'ADD',
            'date_ms': int(time_us / 1000),
            'alarm_string': alarm.alarm_id,
            'kind': kind,
            'desc': f'{alarm.tag.desc} {value:.{alarm.tag.dp}f}'
                    f' {alarm.tag.units}',
            'group': alarm.group
        })

    def rta_cb(self, request):
        """Respond to Request to Author and publish on rta_tag as needed."""
        if 'action' not in request:
            logging.warning(f'rta_cb malformed {request}')
        elif request['action'] == 'ADD':
            try:
                logging.info(f'add {request}')
                with self.connection:
                    if self.has_returning:
                        self.cursor.execute(
                            f'INSERT INTO {self.table} '
                            '(date_ms, alarm_string, kind, desc, "group") '
                            'VALUES(:date_ms, :alarm_string, :kind, :desc, :group) '
                            'RETURNING *;',
                            request)
                        res = self.cursor.fetchone()
                    else:
                        self.cursor.execute(
                            f'INSERT INTO {self.table} '
                            '(date_ms, alarm_string, kind, desc, "group") '
                            'VALUES(:date_ms, :alarm_string, :kind, :desc, :group);',
                            request)
                        row_id = self.cursor.lastrowid
                        self.cursor.execute(
                            f'SELECT * FROM {self.table} WHERE id = ?;',
                            (row_id,))
                        res = self.cursor.fetchone()
                    self.rta.value = {
                        '__rta_id__': 0,
                        'id': res[0],
                        'date_ms': res[1],
                        'alarm_string': res[2],
                        'kind': res[3],
                        'desc': res[4],
                        'group': res[5]
                    }
            except sqlite3.IntegrityError as error:
                logging.warning(f'Alarms rta_cb {error}')
        elif request['action'] == 'UPDATE':
            try:
                logging.info(f'update {request}')
                with self.connection:
                    if self.has_returning:
                        self.cursor.execute(
                            f'UPDATE {self.table} SET in_alm = :in_alm '
                            'WHERE id = :id RETURNING *;',
                            request)
                        res = self.cursor.fetchone()
                        if res:
                            self.rta.value = {
                                '__rta_id__': 0,
                                'id': res[0],
                                'date_ms': res[1],
                                'alarm_string': res[2],
                                'kind': res[3],
                                'desc': res[4],
                                'group': res[5]
                            }
                    else:
                        self.cursor.execute(
                            f'UPDATE {self.table} SET in_alm = :in_alm '
                            'WHERE id = :id;',
                            request)
                        if self.cursor.rowcount > 0:
                            self.cursor.execute(
                                f'SELECT * FROM {self.table} WHERE id = :id;',
                                request)
                            res = self.cursor.fetchone()
                            if res:
                                self.rta.value = {
                                    '__rta_id__': 0,
                                    'id': res[0],
                                    'date_ms': res[1],
                                    'alarm_string': res[2],
                                    'kind': res[3],
                                    'desc': res[4],
                                    'group': res[5]
                                }
            except sqlite3.IntegrityError as error:
                logging.warning(f'Alarms rta_cb update {error}')
        elif request['action'] == 'HISTORY':
            try:
                logging.info(f'history {request}')
                with self.connection:
                    self.cursor.execute(
                        f'SELECT * FROM {self.table} WHERE date_ms > :date_ms '
                        'ORDER BY (date_ms - :date_ms);', request)
                    for res in self.cursor.fetchall():
                        self.rta.value = {
                            '__rta_id__': request['__rta_id__'],
                            'id': res[0],
                            'date_ms': res[1],
                            'alarm_string': res[2],
                            'kind': res[3],
                            'desc': res[4],
                            'group': res[5]
                        }
            except sqlite3.IntegrityError as error:
                logging.warning(f'Alarms rta_cb {error}')
        elif request['action'] == 'BULK HISTORY':
            try:
                logging.info(f'bulk history {request}')
                with self.connection:
                    self.cursor.execute(
                        f'SELECT * FROM {self.table} WHERE date_ms > :date_ms '
                        'ORDER BY -date_ms;', request)
                    results = list(self.cursor.fetchall())
                    self.rta.value = {'__rta_id__': request['__rta_id__'],
                                      'data': results}
            except sqlite3.IntegrityError as error:
                logging.warning(f'Alarms rta_cb {error}')
        elif request['action'] == 'IN ALARM':
            self.rta.value = {'__rta_id__': request['__rta_id__'],
                              'data': {'in_alarm': list(self.in_alarm)}}
        elif request['action'] == 'ENABLE':
            time_us = int(time.time() * 1000000)
            local_time = time.localtime(time_us / 1000000)
            for alarm in self.alarms:
                if alarm.alarm_id == request['alarm id']:
                    enable = request['enable']
                    if enable == 'Enable':
                        disabled_until_us = 0
                    else:
                        if enable == 'Disable until 8am':
                            target_hour = 8
                            target_day_offset = 0
                            next_offset = 1
                        elif enable == 'Disable until 4pm':
                            target_hour = 16
                            target_day_offset = 0
                            next_offset = 1
                        elif enable == 'Disable until Monday 8am':
                            target_hour = 8
                            target_day_offset = (0 - local_time.tm_wday) % 7
                            next_offset = 7
                        else:
                            disabled_until_us = 0
                            break
                        target_s = time.mktime((
                            local_time.tm_year, local_time.tm_mon,
                            local_time.tm_mday + target_day_offset,
                            target_hour, 0, 0, 0, 0, -1
                        ))
                        if target_s * 1000000 <= time_us:
                            target_s = time.mktime((
                                local_time.tm_year, local_time.tm_mon,
                                local_time.tm_mday + next_offset, 
                                target_hour, 0, 0, 0, 0, -1
                            ))
                        disabled_until_us = int(target_s * 1000000)
                    alarm.disabled_until = disabled_until_us
                    ts = time.strftime(
                        "%Y-%m-%d %H:%M:%S",
                        time.localtime(disabled_until_us / 1000000)
                    )
                    if disabled_until_us == 0:
                        desc = 'Enable'
                    else:
                        desc = f'Disable until {ts}'
                    self.rta_cb({
                        'action': 'ADD',
                        'date_ms': int(time_us / 1000),
                        'alarm_string': alarm.alarm_id,
                        'kind': ACT,
                        'desc': desc,
                        'group': alarm.group
                    })
                    break
 

    async def start(self):
        """Async startup."""
        await self.busclient.start()
        await self.periodic.start()
