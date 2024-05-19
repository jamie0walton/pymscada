"""Bus protocol pack and unpack."""
import asyncio
from struct import pack, unpack
import time
import logging
import pymscada.protocol_constants as pc


class BusTags(type):
    """Enforce unique name and ID."""

    _tag_by_name: dict[bytes, 'BusTag'] = {}
    _tag_by_id: dict[int, 'BusTag'] = {}
    _next_id = 1  # start at 1 so 0 is not a valid ID

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

    def update(self, data: bytes, time_us: int, from_bus: 'BusConnection'):
        """Assign value and update subscribers."""
        self.value = data
        self.time_us = time_us
        self.from_bus = from_bus
        for callback, bus_id in self.pub:
            callback(self, bus_id)


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

    def write(self, command: pc.COMMANDS, tag_id: int, time_us: int,
              data: bytes):
        """Write a message."""
        if data is None:
            data = b''
        logging.info(f'write {pc.CMD_TEXT[command]} {tag_id}')
        for i in range(0, len(data) + 1, pc.MAX_LEN):
            snip = data[i:i+pc.MAX_LEN]
            size = len(snip)
            msg = pack(f"!BBHHQ{size}s", 1, command, tag_id, size, time_us,
                       snip)
            try:
                self.writer.write(msg)
            except (asyncio.IncompleteReadError, ConnectionResetError):
                self.read_task.cancel()

    async def read(self):
        """Read forever."""
        bus_id = id(self)
        while True:
            # start with the command packet, _always_ 14 bytes
            try:
                head = await self.reader.readexactly(14)
                _, cmd, tag_id, size, time_us = unpack('!BBHHQ', head)
            except (ConnectionResetError, asyncio.IncompleteReadError,
                    asyncio.CancelledError):
                break
            # if the command packet indicates data, get that too
            if size == 0:
                self.read_callback((bus_id, cmd, tag_id, time_us, None))
                continue
            try:
                payload = await self.reader.readexactly(size)
                data = unpack(f'!{size}s', payload)[0]
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
            self.read_callback((bus_id, cmd, tag_id, time_us, data))
        # on broken connection
        self.read_callback((bus_id, None, 0, 0, None))


class BusServer:
    """Serve Tags on ip:port, echoing changes to any subscribers."""

    __slots__ = ('ip', 'port', 'server', 'connections', 'bus_tag')

    def __init__(self, ip: str = '127.0.0.1', port: int = 1324,
                 bus_tag: str = '__bus__'):
        """
        Serve Tags on ip:port, echoing changes to any subscribers.

        Each connection can publish and subscribe to tags. Any tag set is
        broadcast to any listeners excepting the connection that sets the
        tag value.

        Event loop must be running.
        """
        self.ip = ip
        self.port = port
        self.server = None
        self.connections: dict[int, BusConnection] = {}
        self.bus_tag = BusTag(bus_tag.encode())
        self.bus_tag.value = b'\x03started'  # \x03 is string type
        self.bus_tag.time_us = int(time.time() * 1e6)
        self.bus_tag.from_bus = 0

    def publish(self, tag: BusTag, bus_id):
        """Update subcribers with tag value change."""
        if tag.from_bus == bus_id:
            return
        try:
            self.connections[bus_id].write(pc.CMD_SET, tag.id, tag.time_us,
                                           tag.value)
        except KeyError:
            tag.del_callback(self.publish, bus_id)

    def process(self, bus_id, cmd, tag_id, time_us, data):
        """Process bus message, updating the local tag value."""
        logging.info(f'write {pc.CMD_TEXT[cmd]} {tag_id} '
                     f'{"None" if data is None else data[:20]}')
        if cmd == pc.CMD_SET:
            try:
                tag = BusTags._tag_by_id[tag_id]
                tag.update(data, time_us, bus_id)
            except KeyError:
                self.connections[bus_id].write(
                    pc.CMD_ERR, tag_id, time_us,
                    f"SET KeyError {tag_id}".encode())
        elif cmd == pc.CMD_RTA:
            try:
                tag = BusTags._tag_by_id[tag_id]
            except KeyError:
                self.connections[bus_id].write(
                    pc.CMD_ERR, tag_id, time_us,
                    f"RTA KeyError {tag_id}".encode())
            try:
                self.connections[tag.from_bus].write(
                    pc.CMD_RTA, tag_id, tag.time_us, data)
            except KeyError:
                logging.warning(f'likely busclient for {tag.name} is gone')
            except Exception as e:
                self.connections[bus_id].write(
                    pc.CMD_ERR, tag_id, time_us,
                    f"RTA {tag_id} {e}".encode())
            """Reply comes from another BusClient, not the Server."""
        elif cmd == pc.CMD_SUB:
            try:
                tag = BusTags._tag_by_id[tag_id]
            except KeyError:
                self.connections[bus_id].write(
                    pc.CMD_ERR, tag_id, time_us,
                    f"SUBscribe KeyError {tag_id}".encode())
            self.connections[bus_id].write(pc.CMD_SET, tag_id, tag.time_us,
                                           tag.value)
            tag.add_callback(self.publish, bus_id)
        elif cmd == pc.CMD_ID:
            try:
                tag = BusTags._tag_by_name[data]
            except KeyError:
                self.connections[bus_id].write(
                    pc.CMD_ERR, tag_id, time_us,
                    f"ID {data} undefined".encode())
                tag = BusTag(data)
            self.connections[bus_id].write(pc.CMD_ID, tag.id, tag.time_us,
                                           tag.name)
        elif cmd == pc.CMD_GET:
            try:
                tag = BusTags._tag_by_id[tag_id]
            except KeyError:
                self.connections[bus_id].write(
                    pc.CMD_ERR, tag_id, time_us,
                    f"GET KeyError for {tag_id}".encode())
            self.connections[bus_id].write(pc.CMD_SET, tag.id, tag.time_us,
                                           tag.value)
        elif cmd == pc.CMD_UNSUB:
            try:
                tag = BusTags._tag_by_id[tag_id]
            except KeyError:
                self.connections[bus_id].write(
                    pc.CMD_ERR, tag_id, time_us,
                    f"UNSubscribe KeyError for {tag_id}".encode())
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
            self.connections[bus_id].write(
                pc.CMD_LIST, 0, time_us, b' '.join(tagname_list))
        elif cmd == pc.CMD_LOG:
            if len(data) > 300:
                logging.warning(f'process: log message too long from {bus_id}')
            else:
                logging.warning(data.decode())
        else:  # consider disconnecting
            logging.warn(f'invalid message {cmd}')

    def read_callback(self, command):
        """Process read messages, delete broken connections."""
        bus_id, cmd, tag_id, time_us, data = command
        if cmd is None:
            self.connections[bus_id].delete()
            del self.connections[bus_id]
            return
        self.process(bus_id, cmd, tag_id, time_us, data)

    def new_connection(self, reader: asyncio.StreamReader,
                       writer: asyncio.StreamWriter):
        """Accept new connections."""
        busconnection = BusConnection(self.read_callback, reader, writer)
        self.connections[id(busconnection)] = busconnection

    async def start(self):
        """Provide a bus server."""
        self.server = await asyncio.start_server(self.new_connection,
                                                 self.ip, self.port)
        addrs = [str(sock.getsockname()) for sock in self.server.sockets]
        logging.info(f'Serving on {", ".join(addrs)}')
        asyncio.create_task(self.server.serve_forever())
        return self.server
