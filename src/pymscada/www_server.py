"""WWW Server."""
import asyncio
from aiohttp import web, WSMsgType
import logging
from pathlib import Path
from struct import pack, unpack_from
import time
from pymscada.bus_client import BusClient
import pymscada.protocol_constants as pc
from pymscada.tag import Tag, tag_for_web, TYPES
from pymscada_html import get_html_file


class Interface():
    """Provide an interface between web client rta and the action."""

    def __init__(self, tagname: str) -> None:
        """Return path tagname for rta requests."""
        self.tag = Tag(tagname, dict)

    def ask(self, message):
        """Process the message."""
        logging.warning(message)


class WSHandler():
    """
    Websocket handler pushes displays, tags and values to client.

    Maintains a client state insofar as tag updates are concerned.
    This are transitory, lasting for a given web browser client.
    """

    ids = set(range(1, 100))

    def __init__(self, ws: web.WebSocketResponse, pages: dict,
                 tag_info: dict[str, Tag], do_rta, interface: Interface):
        """Create callbacks to monitor tag values."""
        self.ws = ws
        self.pages = pages
        self.tag_info = tag_info
        self.tag_by_id: dict[int, Tag] = {}
        self.tag_by_name: dict[str, Tag] = {}
        self.queue = asyncio.Queue()
        self.do_rta = do_rta
        self.rta_id = self.ids.pop()
        logging.info(f'websocket id {self.rta_id}')
        self.interface = interface

    def __del__(self):
        """Depends on garbage collector. Is OK."""
        self.ids.add(self.rta_id)

    async def send_queue(self):
        """Run forever, write from queue."""
        try:
            while True:
                as_bytes, message = await self.queue.get()
                if as_bytes:
                    await self.ws.send_bytes(message)
                else:
                    await self.ws.send_json(message)
        except asyncio.CancelledError:
            logging.warn(f'{self.rta_id}: send queue error, close '
                         f'{self.ws.exception()}')
            return

    def publish(self, tag: Tag):
        """
        Prepare message for web client.

        javascript number is IEEE754 64-bit float.
        52-bits fraction where leading 1 is implicit. 2**53 - 1
        This is also the integer, so +/- 9,007,199,254,740,991
        mscada uses microsec, today is   1,692,472,361,000,000
        Today is 20 Aug 2023, 07:12:46.

        Use q, Q and d for time, int and float.
        i.e. Uint64, Int64, Float64.
        """
        if tag.type == int:
            self.queue.put_nowait((True, pack(
                '!HHQq',            # Network big-endian
                tag.id,             # Uint16
                pc.TYPE_INT,        # Uint16
                tag.time_us,        # Uint64
                tag.value           # Int64
            )))
        elif tag.type == float:
            self.queue.put_nowait((True, pack(
                '!HHQd',            # Network big-endian
                tag.id,             # Uint16
                pc.TYPE_FLOAT,      # Uint16
                tag.time_us,        # Uint64
                tag.value           # Float64
            )))
        elif tag.type == str:
            asbytes = tag.value.encode()
            self.queue.put_nowait((True, pack(
                f'!HHQ{len(asbytes)}s',  # Network big-endian
                tag.id,             # Uint16
                pc.TYPE_STR,        # Uint16
                tag.time_us,        # Uint64
                asbytes             # Char as needed
            )))
        elif tag.type == bytes:
            rta_id = unpack_from('>H', tag.value)[0]
            if rta_id in [0, self.rta_id]:
                self.queue.put_nowait((True, pack(
                    f'!HHQ{len(tag.value)}s',  # Network big-endian
                    tag.id,             # Uint16
                    pc.TYPE_BYTES,      # Uint16
                    tag.time_us,        # Uint64
                    tag.value           # Char as needed
                )))
            else:
                logging.info(f'{self.rta_id}: {tag.name} bytes mismatch id')
        elif tag.type in [dict, list]:
            self.queue.put_nowait((False, {
                'type': 'tag',
                'payload': {
                    'tagid': tag.id,
                    'time_us': tag.time_us,
                    'value': tag.value
                }
            }))

    def notify_id(self, tag: Tag):
        """Must be done here."""
        logging.info(f'{self.rta_id}: send id to webclient for {tag.name}')
        self.tag_info[tag.name]['id'] = tag.id
        self.tag_by_id[tag.id] = tag
        self.tag_by_name[tag.name] = tag
        self.queue.put_nowait(
            (False, {'type': 'tag_info', 'payload': self.tag_info[tag.name]}))
        tag.add_callback(self.publish)
        tag.del_callback_id(self.notify_id)

    def do_sub(self, tagname: str):
        """Subscribe to tag value."""
        try:
            tag = self.tag_by_name[tagname]
        except KeyError:
            if tagname not in self.tag_info:
                logging.warning(f'{self.rta_id}: no {tagname} in tag_info')
                return
            tag = Tag(tagname, TYPES[self.tag_info[tagname]['type']])
        if tag.id is None:
            tag.add_callback_id(self.notify_id)
        else:
            self.notify_id(tag)
            if tag.value is not None:
                self.publish(tag)

    async def connection_active(self):
        """Run while the connection is active and don't return."""
        send_queue = asyncio.create_task(self.send_queue())
        self.queue.put_nowait(
            (False, {'type': 'pages', 'payload': self.pages}))
        async for msg in self.ws:
            if msg.type == WSMsgType.TEXT:
                logging.info(f'{self.rta_id}: websocket recv {msg.json()}')
                command = msg.json()
                action = command['type']
                tagname = command['tagname']
                value = command['value']
                time_us = int(time.time() * 1e6)
                bus = None
                if action == 'set':  # pc.CMD_SET
                    self.tag_by_name[tagname].value = value, time_us, bus
                elif action == 'rta':  # pc.CMD_RTA
                    if 'File' in value:
                        file = await anext(self.ws)
                        value['_file_data'] = file.data
                    value['__rta_id__'] = self.rta_id
                    self.do_rta(tagname, value)
                elif action == 'request_to_author':
                    self.interface.ask(command)
                elif action == 'sub':  # pc.CMD_SUB
                    self.do_sub(tagname)
                elif action == 'get':  # pc.CMD_GET
                    logging.warning(f'{self.rta_id}: CMD_GET not implemented.')
                elif action == 'unsub':  # pc.CMD_UNSUB
                    logging.warning(f'{self.rta_id}: CMD_UNSUB not '
                                    'implemented.')
            elif msg.type == WSMsgType.BINARY:
                logging.info(f'{msg.data}')
            elif msg.type == WSMsgType.ERROR:
                logging.warn(f'{self.rta_id}: ws closing error '
                             f'{self.ws.exception()}')
        send_queue.cancel()
        for tag in self.tag_by_id.values():
            tag.del_callback_id(self.notify_id)
            tag.del_callback(self.publish)


class WwwServer:
    """Connect to bus on bus_ip:bus_port, serve on ip:port for webclient."""

    def __init__(self, bus_ip: str = '127.0.0.1', bus_port: int = 1324,
                 ip: str = '127.0.0.1', port: int = 8324, get_path: str = None,
                 tag_info: dict = {}, pages: dict = {}, serve_path: str = None,
                 www_tag: str = '__wwwserver__'
                 ) -> None:
        """
        Connect to bus on bus_ip:bus_port, serve on ip:port for webclient.

        Serves the webclient files at /, as a relative path. The webclient uses
        a websocket connection to request and set tag values and subscribe to
        changes.

        Event loop must be running.
        """
        self.busclient = BusClient(bus_ip, bus_port, tag_info,
                                   module='WWW Server')
        self.ip = ip
        self.port = port
        self.get_path = get_path
        self.serve_path = Path(serve_path)
        for tagname, tag in tag_info.items():
            tag_for_web(tagname, tag)
        self.tag_info = tag_info
        self.pages = pages
        self.interface = Interface(www_tag)

    async def redirect_handler(self, _request: web.Request):
        """Point an empty request to the index."""
        if self.get_path is None:
            file = get_html_file('index.html')
        else:
            file = Path(self.get_path, 'index.html')
        return web.FileResponse(file)

    async def web_handler(self, request: web.Request):
        """Point an empty request to the index."""
        logging.info(f"read {request.match_info['file']}")
        if self.get_path is None:
            file = get_html_file(request.match_info['file'])
        else:
            file = Path(self.get_path, request.match_info['file'])
        return web.FileResponse(file)

    async def path_handler(self, request: web.Request):
        """Plain files."""
        logging.info(f"path {request.match_info['path']}")
        path = self.serve_path.joinpath(request.match_info['path'])
        if path.is_dir():
            return web.HTTPForbidden(reason='folder not permitted')
        if not path.exists():
            return web.HTTPNotFound(reason='no such file in path')
        return web.FileResponse(path)
        logging.warning(f"path not configured {request.match_info['path']}")
        return web.HTTPForbidden(reason='path not permitted')

    async def websocket_handler(self, request: web.Request):
        """Wait for connections. Create a new one each time."""
        peer = request.transport.get_extra_info('peername')
        logging.info(f"WS from {peer}")
        ws = web.WebSocketResponse(max_msg_size=0)  # disables max message size
        await ws.prepare(request)
        await WSHandler(ws, self.pages, self.tag_info, self.busclient.rta,
                        self.interface).connection_active()
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
        await self.busclient.start()
        self.webapp = web.Application()
        routes = [web.get('/', self.redirect_handler),
                  web.get('/ws', self.websocket_handler),
                  web.get('/{file}', self.web_handler),
                  web.get('/{path:.*}', self.path_handler)]
        self.webapp.add_routes(routes)
        self.webapp.on_response_prepare.append(self.on_prepare)
        self.runner = web.AppRunner(self.webapp, access_log=None)
        await self.runner.setup()
        self.site = web.TCPSite(self.runner, self.ip, self.port)
        await self.site.start()
