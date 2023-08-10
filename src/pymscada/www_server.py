"""WWW Server."""
import asyncio
from aiohttp import web, WSMsgType
from struct import pack
from pathlib import Path
import logging
from .tag import Tag
from .config import get_file
from .bus_client import BusClient

INT_TYPE = 1
FLOAT_TYPE = 2
STRING_TYPE = 3
INT_ARRAY_TYPE = 4
FLOAT_ARRAY_TYPE = 5




class WwwCommon:
    """Single place for common connection requirements."""

    def __init__(self, tags: dict, pages: dict) -> None:
        self.tags = tags
        self.pages = pages
        self.tag_by_name: list[str, Tag] = {}
        self.tag_by_id: list[int, Tag] = {}


# a new instance is created for each connection
class WSHandler():
    """
    Websocket handler pushes displays, tags and values to client.

    Maintains a client state insofar as tag updates are concerned.
    """

    def __init__(self, ws: web.WebSocketResponse, common: WwwCommon):
        """Create callbacks to monitor tag values."""
        self.ws = ws
        self.common = common
        self.queue = asyncio.Queue()

    def _cleanup(self):
        """Remove callbacks to avoid memory leak."""
        pass
        # for tag in self.app.tags.values():
        #     tag.del_callback(self.publish)

    async def send_queue(self):
        """Run forever, write from queue."""
        while True:
            as_bytes, message = await self.queue.get()
            try:
                if as_bytes:
                    await self.ws.send_bytes(message)
                else:
                    await self.ws.send_json(message)
            except asyncio.CancelledError:
                logging.warn(f"send queue error, close {self.ws.exception()}")
                return

    def publish(self, tag: Tag):
        """Prepare message for web client."""
        if tag.type == int:
            self.queue.put_nowait(True, pack(
                '!HHIIi',            # Network big-endian
                tag.id,               # Uint16
                INT_TYPE,            # Uint16
                tag.time_us // 1000000,  # Uint32
                tag.time_us % 1000000,   # Uint32
                tag.value                # Int32
            ))
        elif tag.type == float:
            self.queue.put_nowait(True, pack(
                '!HHIIf',            # Network big-endian
                tag.id,               # Uint16
                FLOAT_TYPE,          # Uint16
                tag.time_us // 1000000,  # Uint32
                tag.time_us % 1000000,   # Uint32
                tag.value                # Float32
            ))
        elif tag.type == str:
            asbytes = tag.value.encode()
            self.queue.put_nowait(True, pack(
                f'!HHII{len(asbytes)}s',  # Network big-endian
                tag.id,               # Uint16
                STRING_TYPE,         # Uint16
                tag.time_us // 1000000,  # Uint32
                tag.time_us % 1000000,   # Uint32
                asbytes              # Char as needed
            ))
        elif tag.type in [dict, list]:
            self.queue.put_nowait(False, {
                'type': 'tag',
                'payload': {
                    'tagid': tag.id,
                    'time_us': tag.time_us,
                    'value': tag.value
                }
            })

    async def connection_active(self):
        """Run while the connection is active and don't return."""
        asyncio.create_task(self.send_queue())
        async for msg in self.ws:
            if msg.type == WSMsgType.TEXT:
                logging.info(f"{msg.json()}")
                command = msg.json()
                if command['type'] == 'set':  # pc.CMD_SET
                    pass
                elif command['type'] == 'rqs':  # pc.CMD_RQS
                    pass
                elif command['type'] == 'get':  # pc.CMD_GET
                    pass
                elif command['type'] == 'sub':  # pc.CMD_SUB
                    self.queue.put_nowait(self.publish(command['tag_id']))
                elif command['type'] == 'unsub':  # pc.CMD_UNSUB
                    pass
                elif command['type'] == 'init':
                    self.queue.put_nowait((
                        False, {'type': 'pages', 'payload': self.common.pages}
                    ))
            elif msg.type == WSMsgType.BINARY:
                logging.info(f'{msg.data}')
            elif msg.type == WSMsgType.ERROR:
                logging.warn(f"ws closing error {self.ws.exception()}")
        self._cleanup()


class WwwServer:
    """WWW Server."""

    def __init__(self, bus_ip: str = '127.0.0.1', bus_port: int = 1324,
                 ip: str = '127.0.0.1', port: int = 8324, get_path: str = None,
                 tags: dict = {}, pages: dict = {}) -> None:
        """WWW Server."""
        self.busclient = BusClient(bus_ip, bus_port)
        self.ip = ip
        self.port = port
        self.get_path = get_path
        self.common = WwwCommon(tags, pages)

    async def redirect_handler(self, _request: web.Request):
        """Point an empty request to the index."""
        if self.get_path is None:
            file = get_file('index.html')
        else:
            file = Path(self.get_path, 'index.html')
        return web.FileResponse(file)

    async def web_handler(self, request: web.Request):
        """Point an empty request to the index."""
        if self.get_path is None:
            file = get_file(request.match_info['file'])
        else:
            file = Path(self.get_path, request.match_info['file'])
        return web.FileResponse(file)

    async def websocket_handler(self, request: web.Request):
        """Wait for connections. Create a new one each time."""
        peer = request.transport.get_extra_info('peername')
        logging.info(f"WS from {peer}")
        ws = web.WebSocketResponse(max_msg_size=0)  # disables max message size
        await ws.prepare(request)
        await WSHandler(ws, self.common).connection_active()
        await ws.close()
        logging.info(f"WS closed {peer}")
        return ws

    async def on_prepare(self, request, response):
        """Set the cache headers. Angular builds apps with a hash."""
        if request.path == '/index.html':
            response.headers['Cache-Control'] = 'no-cache'
        else:
            response.headers['Cache-Control'] =\
                'public,max-age=31536000,immutable'

    async def start(self):
        """Provide a web server."""
        self.webapp = web.Application()
        routes = [web.get('/', self.redirect_handler),
                  web.get('/ws', self.websocket_handler),
                  web.get('/{file}', self.web_handler)]
        self.webapp.add_routes(routes)
        self.webapp.on_response_prepare.append(self.on_prepare)
        self.runner = web.AppRunner(self.webapp, access_log=None)
        await self.runner.setup()
        self.site = web.TCPSite(self.runner, self.ip, self.port)
        await self.site.start()

    async def run_forever(self):
        """Run forever."""
        await self.start()
        await asyncio.get_event_loop().create_future()
