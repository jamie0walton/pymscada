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

    def __init__(self, address: str = '127.0.0.1', port: int = 1324):
        """Create bus server."""
        self.address = address
        self.port = port
        self.addr = None
        self.pending = {}
        self.tags: dict[str, Tag] = {}
        self.tag_by_id: dict[int, Tag] = {}

    async def write(self, command: pc.COMMANDS, tag_id: int,
                    time_us: int, data: bytes):
        """Write a message."""
        if data is None:
            data = b''
        for i in range(0, len(data) + 1, pc.MAX_LEN):
            snip = data[i:i+pc.MAX_LEN]
            size = len(snip)
            msg = pack(f">BBHHQ{size}s", 1, command, tag_id, size, time_us,
                       data)
            try:
                # async with asyncio.Timeout(1):  asyncio.TimeoutError,
                self.writer.write(msg)
                await self.writer.drain()
            except (asyncio.IncompleteReadError, ConnectionResetError):
                self.read_task.cancel()

    def add_tag(self, tag: Tag):
        """Add the new tag and get the tag's bus ID."""
        self.tags[tag.name] = tag
        asyncio.create_task(self.write(pc.CMD_ID, 0, 0, tag.name.encode()))

    async def read(self):
        """Read forever."""
        Tag.notify = self.add_tag
        for tag in Tag.get_all_tags().values():
            self.tags[tag.name] = tag
            await self.write(pc.CMD_ID, 0, 0, tag.name.encode())
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
                await self.read_callback((bus_id, cmd, tag_id, time_us, None))
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
            await self.read_callback((bus_id, cmd, tag_id, time_us, data))
        # on broken connection
        await self.read_callback((bus_id, None, 0, 0, None))

    async def publish(self, tag: Tag, bus_id):
        """Update bus server with tag value change."""
        if tag.from_bus == bus_id or tag.value is None:
            return
        if tag.type is float:
            data = pack('>sf', pc.TYPE_FLOAT, tag.value)
        elif tag.type is int:
            data = pack('>sq', pc.TYPE_INT, tag.value)
        elif tag.type is str:
            data = pack('>{size}s', pc.TYPE_STR, tag.value)
        elif tag.type in [list, dict]:
            jsonstr = json.dumps(tag.value)
            data = pack('>{size}s', pc.TYPE_JSON, jsonstr)
        else:
            logging.warning(f'publish {tag.name} unhandled {tag.type}')
            return
        await self.write(pc.CMD_SET, tag.id, tag.time_us, data)

    async def process(self, bus_id, cmd, tag_id, time_us, value):
        """Process bus message, updating the local tag value."""
        if cmd == pc.CMD_ERR:
            logging.warning(f'Bus server error {tag_id} {value}')
            return
        if cmd == pc.CMD_ID:
            tag = self.tags[value.decode()]
            tag.id = tag_id
            self.tag_by_id[tag_id] = tag
            await self.write(pc.CMD_SUB, tag.id, 0, b'')
            return
        tag = self.tag_by_id[tag_id]
        if cmd == pc.CMD_SET:
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

    async def read_callback(self, command):
        """Process read messages."""
        bus_id, cmd, tag_id, time_us, data = command
        if cmd is None:
            logging.critical(f'lost connection to {self.addr}')
            return
        await self.process(bus_id, cmd, tag_id, time_us, data)

    async def connect(self):
        """Start bus read / write tasks and return."""
        self.reader, self.writer = await asyncio.open_connection(
            self.address, self.port)
        self.addr = self.writer.get_extra_info('sockname')
        print(f'connected {self.addr}')
        self.read_task = asyncio.create_task(self.read())

    async def shutdown(self):
        """Shutdown read task."""
        self.read_task.cancel()
