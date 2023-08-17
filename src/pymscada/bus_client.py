"""Bus client."""
import asyncio
from struct import pack, unpack, unpack_from
import json
import logging
from .tag import Tag
from . import protocol_constants as pc


class BusClient:
    """
    Connects to a Bus Server.

    await client.connect() to make the connection. If bus server connection
    fails, die.
    """

    def __init__(self, ip: str = '127.0.0.1', port: int = 1324):
        """Create bus server."""
        self.ip = ip
        self.port = port
        self.tag_by_id: dict[int, Tag] = {}
        self.tag_by_name: dict[str, Tag] = {}
        self.addr = None
        self.pending = {}

    def publish(self, tag: Tag, bus_id):
        """Update bus server with tag value change."""
        if tag.from_bus == bus_id or tag.value is None:
            return
        if tag.type is float:
            data = pack('>Bf', pc.TYPE_FLOAT, tag.value)
        elif tag.type is int:
            data = pack('>Bq', pc.TYPE_INT, tag.value)
        elif tag.type is str:
            size = len(tag.value)
            data = pack(f'>B{size}s', pc.TYPE_STR, tag.value.encode())
        elif tag.type in [list, dict]:
            jsonstr = json.dumps(tag.value)
            size = len(jsonstr)
            data = pack(f'>B{size}s', pc.TYPE_JSON, jsonstr)
        else:
            logging.warning(f'publish {tag.name} unhandled {tag.type}')
            return
        self.write(pc.CMD_SET, tag.id, tag.time_us, data)

    def write(self, command: pc.COMMANDS, tag_id: int, time_us: int,
              data: bytes):
        """Write a message."""
        if data is None:
            data = b''
        for i in range(0, len(data) + 1, pc.MAX_LEN):
            snip = data[i:i+pc.MAX_LEN]
            size = len(snip)
            msg = pack(f">BBHHQ{size}s", 1, command, tag_id, size, time_us,
                       data)
            try:
                self.writer.write(msg)
            except (asyncio.IncompleteReadError, ConnectionResetError):
                self.read_task.cancel()

    def add_tag(self, tag: Tag):
        """Add the new tag and get the tag's bus ID."""
        self.tag_by_name[tag.name] = tag
        self.write(pc.CMD_ID, 0, 0, tag.name.encode())

    async def read(self):
        """Read forever."""
        bus_id = id(self)
        while True:
            # start with the command packet, _always_ 14 bytes
            try:
                head = await self.reader.readexactly(14)
                _, cmd, tag_id, size, time_us = unpack('>BBHHQ', head)
            except (ConnectionResetError, asyncio.IncompleteReadError,
                    asyncio.CancelledError):
                break
            # if the command packet indicates data, get that too
            if size == 0:
                self.process(bus_id, cmd, tag_id, time_us, None)
                continue
            try:
                payload = await self.reader.readexactly(size)
                data = unpack(f'>{size}s', payload)[0]
            except (ConnectionResetError, asyncio.IncompleteReadError,
                    asyncio.CancelledError):
                break
            # if MAX_LEN then a continuation packet is required
            if size == pc.MAX_LEN:
                try:
                    self.pending[tag_id] += data
                except KeyError:
                    self.pending[tag_id] = data
                continue
            # if not MAX_LEN then this is the final or only packet
            if tag_id in self.pending:
                data = self.pending[tag_id] + data
                del self.pending[tag_id]
            self.process(bus_id, cmd, tag_id, time_us, data)
        # on broken connection
        self.process(bus_id, None, 0, 0, None)

    def process(self, bus_id, cmd, tag_id, time_us, value):
        """Process bus message, updating the local tag value."""
        if cmd is None:
            logging.critical(f'lost connection to {self.addr}')
            return
        if cmd == pc.CMD_ERR:
            logging.warning(f'Bus server error {tag_id} {value}')
            return
        if cmd == pc.CMD_ID:
            tag = self.tag_by_name[value.decode()]
            tag.id = tag_id
            self.tag_by_id[tag_id] = tag
            self.write(pc.CMD_SUB, tag.id, 0, b'')
            if tag.name in self.tag_by_name:
                self.tag_by_id[tag.id] = tag
                del self.tag_by_name[tag.name]
            return
        tag = self.tag_by_id[tag_id]
        if cmd == pc.CMD_SET:
            if value is None:
                return
            data_type = unpack_from('>B', value, offset=0)[0]
            if data_type == pc.TYPE_FLOAT:
                data = unpack_from('>f', value, offset=1)[0]
            elif data_type == pc.TYPE_INT:
                data = unpack_from('>q', value, offset=1)[0]
            else:
                data = unpack_from(f'>{len(value) - 1}s', value, offset=1
                                   )[0].decode()
                if data_type is pc.TYPE_STR:
                    pass
                elif data_type == pc.TYPE_JSON:
                    data = json.loads(data)
            tag.value = data, time_us, bus_id
        elif cmd == pc.CMD_RQS:
            logging.warning('TODO')
        else:  # consider disconnecting
            logging.warn(f'invalid message {cmd}')

    async def connect(self):
        """Start bus read / write tasks and return."""
        self.reader, self.writer = await asyncio.open_connection(
            self.ip, self.port)
        self.addr = self.writer.get_extra_info('sockname')
        logging.info(f'connected {self.addr}')
        Tag.set_notify(self.add_tag)
        for tag in Tag.get_all_tags().values():
            self.tag_by_name[tag.name] = tag
            self.write(pc.CMD_ID, 0, 0, tag.name.encode())
        self.read_task = asyncio.create_task(self.read())

    async def shutdown(self):
        """Shutdown read task."""
        self.read_task.cancel()
