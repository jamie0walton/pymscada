"""Serve files through an RQS tag."""
from pathlib import Path
from pymscada.bus_client import BusClient
from pymscada.tag import Tag


class Files():
    """Connect to bus_ip:bus_port, store and provide a value history."""

    def __init__(self, bus_ip: str = '127.0.0.1', bus_port: int = 1324,
                 files: list = None) -> None:
        """
        Connect to bus_ip:bus_port, serve and update files.

        TODO
        Write something.

        Event loop must be running.
        """
        self.busclient = BusClient(bus_ip, bus_port)
        self.files = files
        self.rqs = Tag('__files__', dict)
        self.busclient.add_callback_rqs('__files__', self.rqs_cb)
        self.paths = {}
        self.info = {}
        self.scan_files()
        pass

    def scan_files(self):
        """Scan folders for files."""
        for scan in self.files:
            if 'path' not in scan:
                continue
            desc = ''
            if 'desc' in scan:
                desc = scan['desc']
            mode = 'ro'
            if 'mode' in scan:
                mode = 'rw'
            path = Path(scan['path'])
            for fn in Path(path.parent).glob(path.name):
                file_id = id(fn)
                self.paths[file_id] = {'path': fn, 'mode': mode}
                self.info[file_id] = {'parent': str(fn.parent),
                                      'name': fn.name,
                                      'desc': desc,
                                      'mode': mode}
        self.rqs.value = {'__rqs_id__': 0, 'dat': self.info}

    def rqs_cb(self, tag):
        """Respond to bus requests for data to publish on rqs."""
        pass

    async def start(self):
        """Async startup."""
        await self.busclient.start()
