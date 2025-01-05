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
        self.alarm_test: dict[str, dict] = {}
        self.in_alarm: set[str] = set()
        for tagname, tag in tag_info.items():
            standardise_tag_info(tagname, tag)
            if 'alarm' not in tag:
                continue
            self.tags[tagname] = Tag(tagname, tag['type'])
            self.tags[tagname].desc = tag['desc']
            self.tags[tagname].dp = tag['dp']
            self.tags[tagname].units = tag['units']
            self.tags[tagname].add_callback(self.alarm_cb)
            operator, value = tag['alarm'].split(' ')
            self.alarm_test[tagname] = [
                {
                    '==': (lambda x, y: x == y),
                    '<': (lambda x, y: x < y),
                    '>': (lambda x, y: x > y),
                    '<=': (lambda x, y: x <= y),
                    '>=': (lambda x, y: x >= y)
                }[operator],
                float(value)
            ]
        self.table = table
        self.cursor = self.connection.cursor()
        self.busclient = BusClient(bus_ip, bus_port, module='Alarms')
        self.rta = Tag(rta_tag, dict)
        self.rta.value = {}
        self.busclient.add_callback_rta(rta_tag, self.rta_cb)
        atexit.register(self.close)

    def alarm_cb(self, tag):
        """Callback for alarm tags."""
        operator, value = self.alarm_test[tag.name]
        if operator(tag.value, value) and tag.name not in self.in_alarm:
            logging.warning(f'Alarm {tag.name} {tag.value}')
            alarm_record = {
                'action': 'ADD',
                'date_ms': int(tag.time_us / 1000),
                'tagname': tag.name,
                'kind': ALM,
                'desc': f'{tag.desc} {tag.value:.{tag.dp}f} {tag.units}'
            }
            self.rta_cb(alarm_record)
            self.in_alarm.add(tag.name)
        elif not operator(tag.value, value) and tag.name in self.in_alarm:
            logging.info(f'No alarm {tag.name} {tag.value}')
            alarm_record = {
                'action': 'ADD',
                'date_ms': int(tag.time_us / 1000),
                'tagname': tag.name,
                'kind': RTN,
                'desc': f'{tag.desc} {tag.value:.{tag.dp}f} {tag.units}'
            }
            self.rta_cb(alarm_record)
            self.in_alarm.remove(tag.name)

    def _init_table(self):
        """Initialize the database table schema."""
        query = (
            'CREATE TABLE IF NOT EXISTS ' + self.table +
            '(id INTEGER PRIMARY KEY ASC, '
            'date_ms INTEGER, '
            'tagname TEXT, '
            'kind INTEGER, '
            'desc TEXT)'
        )
        self.cursor.execute(query)
        
        # Add startup record using existing ADD functionality
        startup_record = {
            'action': 'ADD',
            'date_ms': int(time.time() * 1000),
            'tagname': self.rta.name,
            'kind': INF,
            'desc': 'Alarm logging started'
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
                        '(date_ms, tagname, kind, desc) '
                        'VALUES(:date_ms, :tagname, :kind, :desc) '
                        'RETURNING *;',
                        request)
                    res = self.cursor.fetchone()
                    self.rta.value = {
                        'id': res[0],
                        'date_ms': res[1],
                        'tagname': res[2],
                        'kind': res[3],
                        'desc': res[4]
                    }
            except sqlite3.IntegrityError as error:
                logging.warning(f'Alarms rta_cb {error}')
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
                            'tagname': res[2],
                            'kind': res[3],
                            'desc': res[4]
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
        shutdown_record = {
            'action': 'ADD',
            'date_ms': int(time.time() * 1000),
            'tagname': self.rta.name,
            'kind': INF,
            'desc': 'Alarm logging stopped'
        }
        try:
            self.rta_cb(shutdown_record)
        except sqlite3.Error as e:
            logging.error(f'Error during alarm shutdown: {e}')
