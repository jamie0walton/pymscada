"""Alarms handling."""
import logging
import sqlite3  # note that sqlite3 has blocking calls
import socket
import time
import atexit
from pymscada.bus_client import BusClient
from pymscada.tag import Tag, TYPES

ALM = 0
RTN = 1
ACT = 2
INF = 3

NORMAL = 0
ALARM = 1


def standardise_tag_info(tagname: str, tag: dict):
    """Correct tag dictionary in place to be suitable for modules."""
    tag['name'] = tagname
    tag['id'] = None
    if 'desc' not in tag:
        logging.warning(f"Tag {tagname} has no description, using name")
        tag['desc'] = tag['name']
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


class Alarm:
    """Manages multiple alarm conditions for a single tag."""
    def __init__(self, tag: Tag, conditions: str | list[str]):
        """Initialize alarm with tag and condition(s)."""
        if tag.type not in (int, float):
            raise ValueError(f"Alarms only supported for numeric types, not {tag.type}")
            
        self.tag = tag
        self.tests: list[tuple[str, callable, float]] = []
        
        # Handle both string and list conditions
        if isinstance(conditions, str):
            conditions = [conditions]
            
        for condition in conditions:
            operator_str, value = condition.split(' ')
            self.tests.append((
                condition,
                {
                    '==': (lambda x, y: x == y),
                    '<': (lambda x, y: x < y),
                    '>': (lambda x, y: x > y),
                    '<=': (lambda x, y: x <= y),
                    '>=': (lambda x, y: x >= y)
                }[operator_str],
                float(value)
            ))
            
    def check_conditions(self, in_alarm: set[str]) -> list[tuple[str, bool, float, int]]:
        """Check all conditions and return list of changes.
        Returns list of (alarm_ref, is_in_alarm, value, timestamp) for changed states."""
        changes = []
        for condition_str, test, value in self.tests:
            alarm_ref = f"{self.tag.name} {condition_str}"
            is_in_alarm = test(self.tag.value, value)
            
            if is_in_alarm and alarm_ref not in in_alarm:
                changes.append((alarm_ref, True, self.tag.value, self.tag.time_us))
                
            elif not is_in_alarm and alarm_ref in in_alarm:
                changes.append((alarm_ref, False, self.tag.value, self.tag.time_us))
                
        return changes


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
        self.connection = sqlite3.connect(db)
        self.tags: dict[str, Tag] = {}
        self.alarms: dict[str, Alarm] = {}
        self.in_alarm: dict[str, int] = {}
        for tagname, tag in tag_info.items():
            standardise_tag_info(tagname, tag)
            if 'alarm' not in tag or tag['type'] not in (int, float):
                continue
            self.tags[tagname] = Tag(tagname, tag['type'])
            self.tags[tagname].desc = tag['desc']
            self.tags[tagname].dp = tag['dp']
            self.tags[tagname].units = tag['units']
            self.tags[tagname].add_callback(self.alarm_cb)
            self.alarms[tagname] = Alarm(self.tags[tagname], tag['alarm'])
        self.table = table
        self.cursor = self.connection.cursor()
        self.busclient = BusClient(bus_ip, bus_port, module='Alarms')
        self.rta = Tag(rta_tag, dict)
        self.rta.value = {}
        self.busclient.add_callback_rta(rta_tag, self.rta_cb)
        atexit.register(self.close)

    def alarm_cb(self, tag: Tag):
        """Callback for alarm tags."""
        if tag.name not in self.alarms:
            return
        changes = self.alarms[tag.name].check_conditions(self.in_alarm)
        for alarm_ref, is_in_alarm, value, time_us in changes:
            self._handle_alarm_change(
                alarm_ref, 
                is_in_alarm, 
                tag, 
                value, 
                time_us
            )

    def _handle_alarm_change(self, alarm_ref: str, is_in_alarm: bool, 
                           tag: Tag, value: float, time_us: int):
        """Handle alarm state changes and database updates."""
        if is_in_alarm:
            logging.warning(f'Alarm {alarm_ref} {value}')
            kind = ALM
            state = ALARM
            alarm_record = {
                'action': 'ADD',
                'date_ms': int(time_us / 1000),
                'tag_alm': alarm_ref,
                'kind': kind,
                'desc': f'{tag.desc} {value:.{tag.dp}f} {tag.units}',
                'in_alm': state
            }
            self.rta_cb(alarm_record)
            self.in_alarm[alarm_ref] = self.rta.value['id']
        else:
            logging.info(f'No alarm {alarm_ref} {value}')
            if alarm_ref in self.in_alarm:
                # First update the existing alarm record to NORMAL
                update_record = {
                    'action': 'UPDATE',
                    'id': self.in_alarm[alarm_ref],
                    'in_alm': NORMAL
                }
                self.rta_cb(update_record)
                
                # Then add the RTN record
                rtn_record = {
                    'action': 'ADD',
                    'date_ms': int(time_us / 1000),
                    'tag_alm': alarm_ref,
                    'kind': RTN,
                    'desc': f'{tag.desc} {value:.{tag.dp}f} {tag.units}',
                    'in_alm': NORMAL
                }
                self.rta_cb(rtn_record)
                del self.in_alarm[alarm_ref]

    def _init_table(self):
        """Initialize the database table schema."""
        query = (
            'CREATE TABLE IF NOT EXISTS ' + self.table +
            '(id INTEGER PRIMARY KEY ASC, '
            'date_ms INTEGER, '
            'tag_alm TEXT, '
            'kind INTEGER, '
            'desc TEXT, '
            'in_alm INTEGER)'
        )
        self.cursor.execute(query)
        
        # Clear any existing ALARM states
        try:
            with self.connection:
                # Update all alarm records to NORMAL
                self.cursor.execute(
                    f'SELECT id, tag_alm FROM {self.table} WHERE in_alm = ?',
                    (ALARM,))
                alarm_records = self.cursor.fetchall()
                for record_id, tag_alm in alarm_records:
                    update_record = {
                        'action': 'UPDATE',
                        'id': record_id,
                        'in_alm': NORMAL
                    }
                    self.rta_cb(update_record)
        except sqlite3.Error as e:
            logging.error(f'Error clearing alarm states during startup: {e}')
        
        # Add startup record using existing ADD functionality
        startup_record = {
            'action': 'ADD',
            'date_ms': int(time.time() * 1000),
            'tag_alm': self.rta.name,
            'kind': INF,
            'desc': 'Alarm logging started',
            'in_alm': NORMAL
        }
        self.rta_cb(startup_record)

    def rta_cb(self, request):
        """Respond to Request to Author and publish on rta_tag as needed."""
        if 'action' not in request:
            logging.warning(f'rta_cb malformed {request}')
        elif request['action'] == 'ADD':
            try:
                logging.info(f'add {request}')
                with self.connection:
                    self.cursor.execute(
                        f'INSERT INTO {self.table} '
                        '(date_ms, tag_alm, kind, desc, in_alm) '
                        'VALUES(:date_ms, :tag_alm, :kind, :desc, :in_alm) '
                        'RETURNING *;',
                        request)
                    res = self.cursor.fetchone()
                    self.rta.value = {
                        'id': res[0],
                        'date_ms': res[1],
                        'tag_alm': res[2],
                        'kind': res[3],
                        'desc': res[4],
                        'in_alm': res[5]
                    }
            except sqlite3.IntegrityError as error:
                logging.warning(f'Alarms rta_cb {error}')
        elif request['action'] == 'UPDATE':
            try:
                logging.info(f'update {request}')
                with self.connection:
                    self.cursor.execute(
                        f'UPDATE {self.table} SET in_alm = :in_alm '
                        'WHERE id = :id RETURNING *;',
                        request)
                    res = self.cursor.fetchone()
                    if res:
                        self.rta.value = {
                            'id': res[0],
                            'date_ms': res[1],
                            'tag_alm': res[2],
                            'kind': res[3],
                            'desc': res[4],
                            'in_alm': res[5]
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
                            'tag_alm': res[2],
                            'kind': res[3],
                            'desc': res[4],
                            'in_alm': res[5]
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

    async def start(self):
        """Async startup."""
        await self.busclient.start()
        self._init_table()

    def close(self):
        """Clean shutdown of alarms logging."""
        for alarm_ref, record_id in self.in_alarm.items():
            update_record = {
                'action': 'UPDATE',
                'id': record_id,
                'in_alm': NORMAL
            }
            try:
                self.rta_cb(update_record)
            except sqlite3.Error as e:
                logging.error(f'Error clearing alarm {alarm_ref}: {e}')
        
        shutdown_record = {
            'action': 'ADD',
            'date_ms': int(time.time() * 1000),
            'tag_alm': self.rta.name,
            'kind': INF,
            'desc': 'Alarm logging stopped',
            'in_alm': NORMAL
        }
        try:
            self.rta_cb(shutdown_record)
        except sqlite3.Error as e:
            logging.error(f'Error during alarm shutdown: {e}')
