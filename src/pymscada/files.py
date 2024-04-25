"""Serve files through an RQS tag."""
import logging
from pathlib import Path
from pymscada.bus_client import BusClient
from pymscada.tag import Tag


class Files():
    """Connect to bus_ip:bus_port, store and provide a value history."""

    def __init__(self, bus_ip: str = '127.0.0.1', bus_port: int = 1324,
                 path: str = '', files: list = None) -> None:
        """
        Connect to bus_ip:bus_port, serve and update files.

        TODO
        Write something.

        Event loop must be running.
        """
        self.busclient = BusClient(bus_ip, bus_port)
        self.path = Path(path)
        self.files = files
        self.rqs = Tag('__files__', dict)
        self.busclient.add_callback_rqs('__files__', self.rqs_cb)
        self.info = []
        self.scan_files()
        pass

    def scan_files(self):
        """Scan folders for files."""
        for file in self.files:
            if 'path' not in file:
                continue
            desc = ''
            if 'desc' in file:
                desc = file['desc']
            mode = 'ro'
            if 'mode' in file:
                mode = 'rw'
            path = self.path.joinpath(file['path'])
            for fn in sorted(Path(path.parent).glob(path.name)):
                logging.info(fn)
                self.info.append({'path': file['path'].split('/')[0],
                                  'name': fn.name,
                                  'desc': desc,
                                  'mode': mode})
        self.rqs.value = {'__rqs_id__': 0, 'dat': self.info}

    def rqs_cb(self, tag):
        """Respond to bus requests for data to publish on rqs."""
        pass

    async def start(self):
        """Async startup."""
        await self.busclient.start()
