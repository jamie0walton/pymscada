"""Serve files through an RTA tag."""
import logging
from pathlib import Path
from pymscada.bus_client import BusClient
from pymscada.periodic import Periodic
from pymscada.tag import Tag


RATE = 10


class Files():
    """Connect to bus_ip:bus_port, store and provide a value history."""

    def __init__(self, bus_ip: str = '127.0.0.1', bus_port: int = 1324,
                 path: str = '', files: list = None,
                 rta_tag: str = '__files__') -> None:
        """
        Connect to bus_ip:bus_port, serve and update files.

        TODO
        Write something.

        Event loop must be running.
        """
        self.busclient = BusClient(bus_ip, bus_port, module='Files')
        self.path = Path(path)
        self.files = files
        for file in self.files:
            if 'desc' not in file:
                file['desc'] = ''
            if 'mode' not in file:
                file['mode'] = 'ro'
            file['_path'] = self.path.joinpath(file['path'])
            file['st_mtime_ns'] = 0
        self.rta = Tag(rta_tag, dict)
        self.busclient.add_callback_rta(rta_tag, self.rta_cb)
        self.scan_files()

    def scan_files(self):
        """Scan folders for files."""
        update = False
        for file in self.files:
            stat = file['_path'].parent.stat()
            if stat.st_mtime_ns <= file['st_mtime_ns']:
                continue
            update = True
            file['st_mtime_ns'] = stat.st_mtime_ns
        if not update:
            return
        info = []
        for file in self.files:
            path = file['_path']
            for fn in sorted(Path(path.parent).glob(path.name)):
                logging.info(fn)
                info.append({'path': file['path'].split('/')[0],
                             'name': fn.name,
                             'desc': file['desc'],
                             'mode': file['mode']})
        self.rta.value = {'__rta_id__': 0, 'dat': info}

    def rta_cb(self, tag):
        """Respond to bus requests for data to publish on rta."""
        logging.info(f'files rta_cb {tag.name} {tag.value}')
        pass

    async def check_files(self):
        """Check to see if any files have changed."""
        self.scan_files()

    async def start(self):
        """Async startup."""
        await self.busclient.start()
        self.periodic = Periodic(self.check_files, RATE)
        await self.periodic.start()
