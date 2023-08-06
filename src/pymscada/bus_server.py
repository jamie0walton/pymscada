"""Bus protocol pack and unpack."""
import asyncio
from struct import pack, unpack
import logging
from . import protocol_constants as pc


class BusTags(type):
    """Enforce unique name and ID."""

    _tag_by_name: dict[bytes, 'BusTag'] = {}
    _tag_by_id: dict[int, 'BusTag'] = {}
    _next_id = 0

    def __call__(cls, tagname: bytes):
        """Return existing tag if tagname already exists."""
        if tagname in cls._tag_by_name:
            return cls._tag_by_name[tagname]
        tag: 'BusTag' = cls.__new__(cls, tagname)
        tag.__init__(tagname)
        tag.id = cls._next_id
        cls._next_id += 1
        cls._tag_by_name[tagname] = tag
        cls._tag_by_id[tag.id] = tag
        return tag


class BusTag(metaclass=BusTags):
    """Bus tag does not use types, depends on app for unique name and id."""

    __slots__ = ('name', 'id', 'value', 'time_us', 'from_bus', 'pub')

    def __init__(self, name: bytes):
        """Name and id must be unique."""
        self.name = name
        self.id = None
        self.time_us: int = 0
        self.value: bytes = b''
        self.from_bus: 'BusConnection' = None
        self.pub = []

    def add_callback(self, callback, bus_id):
        """Add a callback to update the value when a change is seen."""
        if (callback, bus_id) not in self.pub:
            self.pub.append((callback, bus_id))

    def del_callback(self, callback, bus_id):
        """Remove the callback."""
        if (callback, bus_id) in self.pub:
            self.pub.remove((callback, bus_id))

    async def update(self, data: bytes, time_us: int, from_bus:
                     'BusConnection'):
        """Assign value and update subscribers."""
        self.value = data
        self.time_us = time_us
        self.from_bus = from_bus
        for callback, bus_id in self.pub:
            await callback(self, bus_id)


class BusConnection():
    """Client bus connection."""

    __slots__ = ('read_callback', 'reader', 'writer', 'read_task', 'addr',
                 'pending')

    def __init__(self, read_callback, reader: asyncio.StreamReader,
                 writer: asyncio.StreamWriter):
        """Initialise with stream reader and writer."""
        self.read_callback = read_callback
        self.reader = reader
        self.writer = writer
        self.read_task = asyncio.create_task(self.read())
        self.addr = writer.get_extra_info('peername')
        self.pending = {}
        logging.warning(f'{self.addr} connected.')

    def delete(self):
        """Something in here is necessary, just delete all."""
        del self.read_callback
        del self.reader
        del self.writer
        del self.read_task
        del self.addr
        del self.pending

    async def write(self, command: pc.COMMANDS, tag_id: int,
                    time_us: int, data: bytes):
        """Write a message."""
        if data is None:
            data = b''
        for i in range(0, len(data) + 1, pc.MAX_LEN):
            snip = data[i:i+pc.MAX_LEN]
            size = len(snip)
            msg = pack(f">BBHHQ{size}s", 1, command, tag_id, size, time_us,
                       snip)
            try:
                # async with asyncio.Timeout(10):  asyncio.TimeoutError,
                self.writer.write(msg)
                await self.writer.drain()
            except (asyncio.IncompleteReadError, ConnectionResetError):
                self.read_task.cancel()

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


class BusServer:
    """
    Create a Bus Server that will handle changing connections.

    Creates tags on ID message. If process stops pymscada must completely
    restart.
    """

    __slots__ = ('address', 'port', 'server', 'connections')

    def __init__(self, address: str = '127.0.0.1', port: int = 1324):
        """Set binding address and port for BusServer."""
        self.address = address
        self.port = port
        self.server = None
        self.connections: dict[int, BusConnection] = {}

    async def publish(self, tag: BusTag, bus_id):
        """Update subcribers with tag value change."""
        if tag.from_bus == bus_id or tag.value is None:
            return
        try:
            await self.connections[bus_id].write(
                pc.CMD_SET, tag.id, tag.time_us, tag.value
            )
        except KeyError:
            tag.del_callback(self.publish, bus_id)

    async def process(self, bus_id, cmd, tag_id, time_us, data):
        """Process bus message, updating the local tag value."""
        if cmd == pc.CMD_SET:
            try:
                tag = BusTags._tag_by_id[tag_id]
                await tag.update(data, time_us, bus_id)
            except KeyError:
                await self.connections[bus_id].write(
                    pc.CMD_ERR, tag_id, time_us,
                    f"SET KeyError {tag_id}".encode()
                )
        elif cmd == pc.CMD_RQS:
            try:
                tag = BusTags._tag_by_id[tag_id]
            except KeyError:
                await self.connections[bus_id].write(
                    pc.CMD_ERR, tag_id, time_us,
                    f"RQS KeyError {tag_id}".encode()
                )
            """Reply comes from another BusClient, not the Server."""
            try:
                tag.from_bus._message(cmd, tag_id, time_us, data)
            except Exception as e:
                await self.connections[bus_id].write(
                    pc.CMD_ERR, tag_id, time_us,
                    f"RQS {tag_id} {e}".encode()
                )
        elif cmd == pc.CMD_SUB:
            try:
                tag = BusTags._tag_by_id[tag_id]
            except KeyError:
                await self.connections[bus_id].write(
                    pc.CMD_ERR, tag_id, time_us,
                    f"SUBscribe KeyError {tag_id}".encode()
                )
            if tag.time_us != 0:
                await self.connections[bus_id].write(
                    pc.CMD_SET, tag_id, tag.time_us, tag.value
                )
            tag.add_callback(self.publish, bus_id)
        elif cmd == pc.CMD_ID:
            try:
                tag = BusTags._tag_by_name[data]
            except KeyError:
                await self.connections[bus_id].write(
                    pc.CMD_ERR, tag_id, time_us,
                    f"ID {data} undefined".encode()
                )
                tag = BusTag(data)
            await self.connections[bus_id].write(
                pc.CMD_ID, tag.id, tag.time_us, tag.name
            )
        elif cmd == pc.CMD_GET:
            try:
                tag = BusTags._tag_by_id[tag_id]
            except KeyError:
                await self.connections[bus_id].write(
                    pc.CMD_ERR, tag_id, time_us,
                    f"GET KeyError for {tag_id}".encode()
                )
            await self.connections[bus_id].write(
                pc.CMD_SET, tag.id, tag.time_us, tag.value
            )
        elif cmd == pc.CMD_UNSUB:
            try:
                tag = BusTags._tag_by_id[tag_id]
            except KeyError:
                await self.connections[bus_id].write(
                    pc.CMD_ERR, tag_id, time_us,
                    f"UNSubscribe KeyError for {tag_id}".encode()
                )
            tag.del_callback(self.publish, bus_id)
        elif cmd == pc.CMD_LIST:
            tagname_list = []
            if len(data) == 0:
                for _, tag in BusTags._tag_by_id.items():
                    if tag.time_us > time_us:
                        tagname_list.append(tag.name)
            elif data.startswith(b'^'):
                start = data[1:]
                for _, tag in BusTags._tag_by_id.items():
                    if tag.name.startswith(start):
                        tagname_list.append(tag.name)
            elif data.endswith(b'$'):
                end = data[:-1]
                for _x, tag in BusTags._tag_by_id.items():
                    if tag.name.endswith(end):
                        tagname_list.append(tag.name)
            else:
                for _, tag in BusTags._tag_by_id.items():
                    if data in tag.name:
                        tagname_list.append(tag.name)
            await self.connections[bus_id].write(
                pc.CMD_LIST, 0, time_us, b' '.join(tagname_list)
            )
        else:  # consider disconnecting
            logging.warn(f'invalid message {cmd}')

    async def read_callback(self, command):
        """Process read messages, delete broken connections."""
        bus_id, cmd, tag_id, time_us, data = command
        if cmd is None:
            self.connections[bus_id].delete()
            del self.connections[bus_id]
            return
        await self.process(bus_id, cmd, tag_id, time_us, data)

    async def new_connection(self, reader: asyncio.StreamReader,
                             writer: asyncio.StreamWriter):
        """Accept new connections."""
        busconnection = BusConnection(self.read_callback, reader, writer)
        self.connections[id(busconnection)] = busconnection

    async def start(self):
        """Provide a bus server."""
        self.server = await asyncio.start_server(self.new_connection,
                                                 self.address, self.port)
        addrs = [str(sock.getsockname()) for sock in self.server.sockets]
        print(f'Serving on {", ".join(addrs)}')
        asyncio.create_task(self.server.serve_forever())
        return self.server
