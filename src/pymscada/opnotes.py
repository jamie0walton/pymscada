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

        TODO
        Write something.

        Event loop must be running.
        """
        if db is None:
            raise SystemExit('OpNotes db must be defined')
        logging.warning(f'OpNotes {bus_ip} {bus_port} {db} {rta_tag}')
        self.connection = sqlite3.connect(db)
        self.table = table
        self.cursor = self.connection.cursor()
        query = (
            'CREATE TABLE IF NOT EXISTS ' + self.table +
            '(id INTEGER PRIMARY KEY ASC, '
            'date_ms INTEGER, '
            'site TEXT, '
            'by TEXT, '
            'note TEXT)'
        )
        self.cursor.execute(query)
        self.busclient = BusClient(bus_ip, bus_port, module='OpNotes')
        self.rta = Tag(rta_tag, dict)
        self.rta.value = {}
        self.busclient.add_callback_rta(rta_tag, self.rta_cb)

    def rta_cb(self, request):
        """Respond to Request to Author and publish on rta_tag as needed."""
        if 'action' not in request:
            logging.warning(f'rta_cb malformed {request}')
        elif request['action'] == 'ADD':
            try:
                logging.info(f'add {request}')
                with self.connection:
                    self.cursor.execute(
                        f'INSERT INTO {self.table} (date_ms, site, by, note) '
                        'VALUES(:date_ms, :site, :by, :note) RETURNING *;',
                        request)
                    res = self.cursor.fetchone()
                    self.rta.value = {
                        'id': res[0],
                        'date_ms': res[1],
                        'site': res[2],
                        'by': res[3],
                        'note': res[4]
                    }
            except sqlite3.IntegrityError as error:
                logging.warning(f'OpNotes rta_cb {error}')
        elif request['action'] == 'MODIFY':
            try:
                logging.info(f'modify {request}')
                with self.connection:
                    self.cursor.execute(
                        f'REPLACE INTO {self.table} VALUES(:id, :date_ms, '
                        ':site, :by, :note) RETURNING *;', request)
                    res = self.cursor.fetchone()
                    self.rta.value = {
                        'id': res[0],
                        'date_ms': res[1],
                        'site': res[2],
                        'by': res[3],
                        'note': res[4]
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
                            'note': res[4]
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
