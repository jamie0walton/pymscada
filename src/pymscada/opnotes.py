"""Operator Notes."""
import logging
import sqlite3  # note that sqlite3 has blocking calls
from pymscada.bus_client import BusClient
from pymscada.tag import Tag


class OpNotes:
    """Connect to bus_ip:bus_port, store and provide Operator Notes."""

    def __init__(self, bus_ip: str = '127.0.0.1', bus_port: int = 1324,
                 db: str = None, rta_tag: str = '__opnotes__',
                 table: str = 'opnotes') -> None:
        """
        Connect to bus_ip:bus_port, serve and update operator notes database.

        Open an Operator notes table, creating if necessary. Provide additions,
        updates, deletions and history requests via the rta_tag.

        Event loop must be running.
        """
        if db is None:
            raise SystemExit('OpNotes db must be defined')
        logging.warning(f'OpNotes {bus_ip} {bus_port} {db} {rta_tag}')
        self.connection = sqlite3.connect(db)
        self.table = table
        self.cursor = self.connection.cursor()
        self._init_table()
        self.busclient = BusClient(bus_ip, bus_port, module='OpNotes')
        self.rta = Tag(rta_tag, dict)
        self.rta.value = {}
        self.busclient.add_callback_rta(rta_tag, self.rta_cb)

    def _init_table(self):
        """Initialize or upgrade the database table schema."""
        query = (
            'CREATE TABLE IF NOT EXISTS ' + self.table +
            '(id INTEGER PRIMARY KEY ASC, '
            'date_ms INTEGER, '
            'site TEXT, '
            'by TEXT, '
            'note TEXT, '
            'abnormal INTEGER)'
        )
        self.cursor.execute(query)
        self.cursor.execute(f"PRAGMA table_info({self.table})")
        columns = {col[1]: col[2] for col in self.cursor.fetchall()}
        if 'abnormal' not in columns:
            # Add abnormal as INTEGER from original schema
            logging.warning(f'Upgrading {self.table} schema to include '
                          'abnormal INTEGER, CANNOT revert automatically!')
            self.cursor.execute(
                f'ALTER TABLE {self.table} ADD COLUMN abnormal INTEGER')
        elif columns['abnormal'].upper() == 'BOOLEAN':
            # Change abnormal from BOOLEAN to INTEGER
            logging.warning(f'Upgrading {self.table} abnormal from BOOLEAN to '
                          'INTEGER, CANNOT revert automatically!')
            self.cursor.execute(
                f'CREATE TABLE {self.table}_new '
                '(id INTEGER PRIMARY KEY ASC, '
                'date_ms INTEGER, '
                'site TEXT, '
                'by TEXT, '
                'note TEXT, '
                'abnormal INTEGER)'
            )
            self.cursor.execute(
                f'INSERT INTO {self.table}_new '
                f'SELECT id, date_ms, site, by, note, '
                f'CASE WHEN abnormal THEN 1 ELSE 0 END '
                f'FROM {self.table}'
            )
            self.cursor.execute(f'DROP TABLE {self.table}')
            self.cursor.execute(
                f'ALTER TABLE {self.table}_new RENAME TO {self.table}'
            )

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
                        '(date_ms, site, by, note, abnormal) '
                        'VALUES(:date_ms, :site, :by, :note, :abnormal) '
                        'RETURNING *;',
                        request)
                    res = self.cursor.fetchone()
                    self.rta.value = {
                        'id': res[0],
                        'date_ms': res[1],
                        'site': res[2],
                        'by': res[3],
                        'note': res[4],
                        'abnormal': res[5]
                    }
            except sqlite3.IntegrityError as error:
                logging.warning(f'OpNotes rta_cb {error}')
        elif request['action'] == 'MODIFY':
            try:
                logging.info(f'modify {request}')
                with self.connection:
                    self.cursor.execute(
                        f'REPLACE INTO {self.table} VALUES(:id, :date_ms, '
                        ':site, :by, :note, :abnormal) RETURNING *;', request)
                    res = self.cursor.fetchone()
                    self.rta.value = {
                        'id': res[0],
                        'date_ms': res[1],
                        'site': res[2],
                        'by': res[3],
                        'note': res[4],
                        'abnormal': res[5]
                    }
            except sqlite3.IntegrityError as error:
                logging.warning(f'OpNotes rta_cb {error}')
        elif request['action'] == 'DELETE':
            try:
                logging.info(f'delete {request}')
                with self.connection:
                    self.cursor.execute(
                        f'DELETE FROM {self.table} WHERE id = :id;', request)
                    self.rta.value = {'id': request['id']}
            except sqlite3.IntegrityError as error:
                logging.warning(f'OpNotes rta_cb {error}')
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
                            'site': res[2],
                            'by': res[3],
                            'note': res[4],
                            'abnormal': res[5]
                        }
            except sqlite3.IntegrityError as error:
                logging.warning(f'OpNotes rta_cb {error}')
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
                logging.warning(f'OpNotes rta_cb {error}')

    async def start(self):
        """Async startup."""
        await self.busclient.start()
