"""Bus client."""
import asyncio
import struct
import json
import time
import logging
from pymscada.tag import Tag
import pymscada.protocol_constants as pc


class BusClient:
    """
    Connects to a Bus Server.

    await client.connect() to make the connection. If bus server connection
    fails, die.
    """

    def __init__(self, ip: str = '127.0.0.1', port: int = 1324, tag_info=None,
                 module: str = '_unset_'):
        """Create bus server."""
        self.ip = ip
        self.port = port
        self.read_task = None
        self.tag_info = tag_info
        self.module = module
        self.tag_by_id: dict[int, Tag] = {}
        self.tag_by_name: dict[str, Tag] = {}
        self.to_publish: dict[str, Tag] = {}
        self.rta_handlers: dict[str, object] = {}
        self.pending = {}

    def publish(self, tag: Tag):
        """
        Update bus server with tag value change.

        A tag is given bus_id id(self) when set from bus. Don't publish to
        source.
        """
        if tag.id is None:
            logging.warning(f'queued {tag.name} {tag.value}')
            self.to_publish[tag.name] = tag
            return
        if tag.type is float:
            data = struct.pack('!Bd', pc.TYPE_FLOAT, tag.value)
        elif tag.type is int:
            data = struct.pack('!Bq', pc.TYPE_INT, tag.value)
        elif tag.type is bytes:
            size = len(tag.value)
            try:
                data = struct.pack(f'!B{size}s', pc.TYPE_BYTES, tag.value)
            except struct.error as e:
                logging.error(f'bus_client {tag.name} {e}')
        elif tag.type is str:
            size = len(tag.value)
            data = struct.pack(f'!B{size}s', pc.TYPE_STR, tag.value.encode())
        elif tag.type in [list, dict]:
            jsonstr = json.dumps(tag.value).encode()
            size = len(jsonstr)
            data = struct.pack(f'!B{size}s', pc.TYPE_JSON, jsonstr)
        else:
            logging.warning(f'publish {tag.name} unhandled {tag.type}')
            return
        self.write(pc.CMD_SET, tag.id, tag.time_us, data)

    def add_callback_rta(self, tagname, handler):
        """Collect callback handlers."""
        if callable(handler):
            self.rta_handlers[tagname] = handler
        else:
            logging.error(f'invalid RTA handler for {tagname}')

    def rta(self, tagname: str, request: dict):
        """Send a Request Set message."""
        time_us = int(time.time() * 1e6)
        jsonstr = json.dumps(request).encode()
        size = len(jsonstr)
        data = struct.pack(f'>B{size}s', pc.TYPE_JSON, jsonstr)
        self.write(pc.CMD_RTA, self.tag_by_name[tagname].id, time_us, data)

    def write(self, command: pc.COMMANDS, tag_id: int, time_us: int,
              data: bytes):
        """Write a message."""
        if data is None:
            data = b''
        for i in range(0, len(data) + 1, pc.MAX_LEN):
            snip = data[i:i+pc.MAX_LEN]
            size = len(snip)
            msg = struct.pack(f">BBHHQ{size}s", 1, command, tag_id, size,
                              time_us, snip)
            try:
                self.writer.write(msg)
            except (asyncio.IncompleteReadError, ConnectionResetError):
                self.read_task.cancel()
            except AttributeError:
                logging.warning('Attribute Error, TO DO, fix in test')

    def add_tag(self, tag: Tag):
        """Add the new tag and get the tag's bus ID."""
        tag.add_callback(self.publish, id(self))
        self.tag_by_name[tag.name] = tag
        if tag.value is not None:
            self.to_publish[tag.name] = tag
        self.write(pc.CMD_ID, 0, 0, tag.name.encode())

    async def open_connection(self):
        """Establish connection and callbacks."""
        self.reader, self.writer = await asyncio.open_connection(
            self.ip, self.port)
        self.addr = self.writer.get_extra_info('sockname')
        self.write(pc.CMD_LOG, 0, 0, f'{self.module} connected'.encode())
        logging.info(f'connected {self.addr}')
        for tag in Tag.get_all_tags().values():
            self.add_tag(tag)
        Tag.set_notify(self.add_tag)

    async def close_connection(self):
        """Close connection and remove callbacks."""
        logging.warning(f'closed/ing connection {self.addr}')
        Tag.del_notify()
        for tag in self.tag_by_name.values():
            tag.del_callback(self.publish)
        self.writer.close()  # writer owns the socket
        await self.writer.wait_closed()

    async def read(self):
        """Read forever."""
        await self.open_connection()
        while True:
            try:
                head = await self.reader.readexactly(14)
                _, cmd, tag_id, size, time_us = struct.unpack('>BBHHQ', head)
            except (ConnectionResetError, asyncio.IncompleteReadError,
                    asyncio.CancelledError):
                break
            if size == 0:
                self.process(cmd, tag_id, time_us, None)
                continue
            try:
                payload = await self.reader.readexactly(size)
                data = struct.unpack(f'>{size}s', payload)[0]
            except (ConnectionResetError, asyncio.IncompleteReadError):
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
            self.process(cmd, tag_id, time_us, data)
        await self.close_connection()

    def process(self, cmd, tag_id, time_us, value):
        """Process bus message, updating the local tag value."""
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
            if tag.name in self.to_publish:
                self.publish(tag)
                del self.to_publish[tag.name]
            return
        tag = self.tag_by_id[tag_id]
        if cmd == pc.CMD_SET:
            if value is None:
                try:
                    if self.tag_info is None:
                        return
                    data = self.tag_info[tag.name]['init']
                    time_us = int(time.time() * 1e6)
                    bus_id = None  # needed to pub to connected webclients
                    tag.value = data, time_us, bus_id
                    logging.warning(f'{tag.name} init value {data}')
                except KeyError:
                    pass
                return
            data_type = struct.unpack_from('!B', value, offset=0)[0]
            if data_type == pc.TYPE_FLOAT:
                data = struct.unpack_from('!d', value, offset=1)[0]
            elif data_type == pc.TYPE_INT:
                data = struct.unpack_from('!q', value, offset=1)[0]
            elif data_type == pc.TYPE_BYTES:
                data = struct.unpack_from(f'!{len(value) - 1}s', value,
                                          offset=1)[0]
            elif data_type == pc.TYPE_STR:
                data = struct.unpack_from(f'!{len(value) - 1}s', value,
                                          offset=1)[0].decode()
            elif data_type == pc.TYPE_JSON:
                data = json.loads(struct.unpack_from(f'!{len(value) - 1}s',
                                                     value, offset=1
                                                     )[0].decode())
            else:
                logging.warning(f'process error {tag.name} {tag.type} {value}')
                return
            tag.value = data, time_us, id(self)
        elif cmd == pc.CMD_RTA:
            data = struct.unpack_from(f'!{len(value) - 1}s', value, offset=1
                                      )[0].decode()
            data = json.loads(data)
            try:
                self.rta_handlers[tag.name](data)
            except KeyError:
                logging.warning(f'unhandled RTA for {tag.name} {data}')
        else:
            raise SystemExit(f'Invalid message {cmd}')

    async def shutdown(self):
        """Shutdown starts with closing the writer."""
        self.writer.close()
        await self.writer.wait_closed()

    async def start(self):
        """Start async."""
        self.read_task = asyncio.create_task(self.read())
