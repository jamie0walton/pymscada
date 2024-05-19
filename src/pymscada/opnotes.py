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
            '(oid INTEGER PRIMARY KEY ASC, '
            'datetime INTEGER, '
            'site TEXT, '
            'operator TEXT, '
            'note TEXT)'
        )
        self.cursor.execute(query)
        self.busclient = BusClient(bus_ip, bus_port, module='OpNotes')
        self.rta = Tag(rta_tag, dict)
        self.busclient.add_callback_rta(rta_tag, self.rta_cb)

    def rta_cb(self, request):
        """Respond to Request to Author and publish on rta_tag as needed."""
        if 'action' not in request:
            logging.warning(f'rta_cb malformed {request}')
        elif request['action'] == 'ADD':
            try:
                with self.connection:
                    self.cursor.execute(
                        f'INSERT INTO {self.table} (datetime, site, operator, '
                        'note) VALUES(:datetime, :site, :operator, :note) '
                        'RETURNING *;',
                        request)
                    res = self.cursor.fetchone()
                    self.rta.value = {
                        'oid': res[0],
                        'datetime': res[1],
                        'site': res[2],
                        'operator': res[3],
                        'note': res[4]
                    }
            except sqlite3.IntegrityError as error:
                logging.warning(f'OpNotes rta_cb {error}')
        elif request['action'] == 'MODIFY':
            try:
                with self.connection:
                    self.cursor.execute(
                        f'REPLACE INTO {self.table} VALUES(:oid, :datetime, '
                        ':site, :operator, :note) RETURNING *;', request)
                    res = self.cursor.fetchone()
                    self.rta.value = {
                        'oid': res[0],
                        'datetime': res[1],
                        'site': res[2],
                        'operator': res[3],
                        'note': res[4]
                    }
            except sqlite3.IntegrityError as error:
                logging.warning(f'OpNotes rta_cb {error}')
        elif request['action'] == 'DELETE':
            try:
                with self.connection:
                    self.cursor.execute(
                        f'DELETE FROM {self.table} WHERE oid = :oid;', request)
                    self.rta.value = {'oid': request['oid']}
            except sqlite3.IntegrityError as error:
                logging.warning(f'OpNotes rta_cb {error}')
        elif request['action'] == 'HISTORY':
            tag = Tag(request['reply_tag'], dict)
            try:
                with self.connection:
                    self.cursor.execute(
                        f'SELECT * FROM {self.table} WHERE datetime < '
                        ':datetime ORDER BY ABS(datetime - :datetime) '
                        'LIMIT 2;', request)
                    for res in self.cursor.fetchall():
                        tag.value = {
                            'oid': res[0],
                            'datetime': res[1],
                            'site': res[2],
                            'operator': res[3],
                            'note': res[4]
                        }
            except sqlite3.IntegrityError as error:
                logging.warning(f'OpNotes rta_cb {error}')

    async def start(self):
        """Async startup."""
        await self.busclient.start()
