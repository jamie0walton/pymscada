"""Serve files through an RQS tag."""
from pathlib import Path
import logging
from .bus_client import BusClient
from .tag import Tag


class Files():
    """Connect to bus_ip:bus_port, store and provide a value history."""

    def __init__(self, bus_ip: str = '127.0.0.1', bus_port: int = 1324,
                 folders: list = None, files: list = None,
                 rqs: str = '__files__') -> None:
        """
        Connect to bus_ip:bus_port, serve and update files.

        Folders is a list of {path: , handler: , mode: } where the handler
        is one of pdf or file and mode is either read or readwrite.

        Files is a list of {path: , desc: } where the paths must be present
        in Folders to find a valid handler.

        Updates are via __files__.value.

        Event loop must be running.
        """
        self.busclient = BusClient(bus_ip, bus_port)
        self.folders = folders
        self.files = files
        self.rqs = Tag(rqs, dict)
        self.rqs.add_rqs(self.rqs_cb)
        self.integrity()
        pass

    def integrity(self):
        """Scan folders for files."""
        self.db = {}
        for folder in [x for x in self.folders if Path(x['path']).is_dir()]:
            for file in Path(folder['path']).iterdir():
                if not file.is_file():
                    continue
                try:
                    v = next(x for x in self.files if
                             file.samefile(x['path']))
                except StopIteration:
                    v = {'path': str(file).replace('\\', '/'),
                         'desc': str(file).replace('\\', '/')}
                v['mode'] = folder['mode']
                v['group'] = folder['handler']
                v['id'] = id(v)
                self.db[v['id']] = v
        self.rqs.value = {'type': 'INTEGRITY',
                          'dat': [x for x in self.db.values()]}

    def rqs_cb(self, tag):
        """Respond to bus requests for data to publish on rqs."""
        pass

    async def start(self):
        """Async startup."""
        await self.busclient.start()
