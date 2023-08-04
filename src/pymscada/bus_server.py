"""Bus protocol pack and unpack."""
import asyncio
from struct import pack, unpack_from
from collections import deque
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
        self.from_bus: 'BusServerProtocol' = None
        self.pub = []

    def add_callback(self, callback):
        """Add a callback to update the value when a change is seen."""
        if callback not in self.pub:
            self.pub.append(callback)

    def del_callback(self, callback):
        """Remove the callback."""
        if callback in self.pub:
            self.pub.remove(callback)

    def update(self, value: bytes, time_us: int, from_bus:
               'BusServerProtocol'):
        """Assign value and update subscribers."""
        self.value = value
        self.time_us = time_us
        self.from_bus = from_bus
        for callback in self.pub:
            callback(self)


class BusServerProtocol(asyncio.Protocol):
    """
    Implements bus client protocol.

    State machine of calls:
    * -> connection_made()
    * -> data_received()*
    * on ID assign new tag and return ID to client
    * -> eof_received()?
    * -> connection_lost(), process must die
    """

    def __init__(self):
        """Initialise with tags so these are (potentially) visible."""
        self.pause = False
        self.buffer = b''
        self.commands = deque()
        self.pending = {}
        self.bus_id = id(self)

    def __del__(self):
        """Perhaps do something here."""
        logging.info("deleted BusServerProtocol instance")
        # took a bit to make this work as the tag callback hooks held it live

    def connection_made(self, transport):
        """Save the transport. Initialise working vars."""
        logging.info(f"connection made {transport.get_extra_info('peername')}")
        self.transport = transport

    def pause_writing(self, err):
        """High water level pause, abandon at the moment."""
        logging.warn('pausing '
                     f"{self.transport.get_extra_info('peername')}")
        self.pause = True

    def resume_writing(self, resc):
        """Not implemented."""
        logging.warn('resuming '
                     f"{self.transport.get_extra_info('peername')}")
        self.pause = False

    def eof_received(self):
        """data_received will never be called again, abort."""
        logging.warn(f"EOF from {self.transport.get_extra_info('peername')}")
        self.transport.abort()

    def connection_lost(self, err):
        """Just drop the connection when lost."""
        logging.warn('connection lost '
                     f"{self.transport.get_extra_info('peername')}")
        for tag in BusTags._tag_by_id.values():
            tag.del_callback(self.publish)
        self.transport.abort()

    def message(self, command: pc.COMMANDS, tag_id: int,
                time_us: int, value: bytes):
        """Send a message."""
        if value is None:
            value = b''
        for i in range(0, len(value) + 1, pc.MAX_LEN):
            snip = value[i:i+pc.MAX_LEN]
            size = len(snip)
            msg = pack(f">BBHHQ{size}s", 1, command, tag_id, size, time_us,
                       value)
            try:
                self.transport.write(msg)
            except Exception as e:
                logging.warn(f'error in bus server message {e}')

    def publish(self, tag: BusTag):
        """
        If published tag value changes, send to bus.

        Don't send to bus if it came from the bus.
        Always bytes type in bus, just send.
        """
        if tag.from_bus == self.bus_id or tag.value is None:
            return
        self.message(pc.CMD_SET, tag.id, tag.time_us, tag.value)

    def process(self):
        """Process bus message, updating the local tag value."""
        command, tag_id, time_us, value = self.commands.popleft()
        if command == pc.CMD_SET:
            try:
                tag = BusTags._tag_by_id[tag_id]
                tag.update(value, time_us, self.bus_id)
            except KeyError:
                self.message(pc.CMD_ERR, tag_id, time_us,
                             f"SET KeyError {tag_id}".encode())
        elif command == pc.CMD_RQS:
            try:
                tag = BusTags._tag_by_id[tag_id]
            except KeyError:
                self.message(pc.CMD_ERR, tag_id, time_us,
                             f"RQS KeyError {tag_id}".encode())
            """Reply comes from another BusClient, not the Server."""
            try:
                tag.from_bus._message(command, tag_id, time_us, value)
            except Exception as e:
                self.message(pc.CMD_ERR, tag_id, time_us,
                             f"RQS {tag_id} {e}".encode())
        elif command == pc.CMD_SUB:
            try:
                tag = BusTags._tag_by_id[tag_id]
            except KeyError:
                self.message(pc.CMD_ERR, tag_id, time_us,
                             f"SUBscribe KeyError {tag_id}".encode())
            if tag.time_us != 0:
                self.message(pc.CMD_SET, tag_id, tag.time_us,
                             tag.value)
            tag.add_callback(self.publish)
        elif command == pc.CMD_ID:
            try:
                tag = BusTags._tag_by_name[value]
            except KeyError:
                self.message(pc.CMD_ERR, tag_id, time_us,
                             f"ID {value} undefined".encode())
                tag = BusTag(value)
            self.message(pc.CMD_ID, tag.id, tag.time_us, tag.name)
        elif command == pc.CMD_GET:
            try:
                tag = BusTags._tag_by_id[tag_id]
            except KeyError:
                self.message(pc.CMD_ERR, tag_id, time_us,
                             f"GET KeyError for {tag_id}".encode())
            self.message(pc.CMD_SET, tag.id, tag.time_us,
                         tag.value)
        elif command == pc.CMD_UNSUB:
            try:
                tag = BusTags._tag_by_id[tag_id]
            except KeyError:
                self.message(pc.CMD_ERR, tag_id, time_us,
                             f"UNSubscribe KeyError for {tag_id}".encode())
            tag.del_callback(self.pub_update)
        elif command == pc.CMD_LIST:
            tagname_list = []
            if len(value) == 0:
                for _x, tag in BusTags._tag_by_id.items():
                    if tag.time_us > time_us:
                        tagname_list.append(tag.name)
            elif value.startswith(b'^'):
                start = value[1:]
                for _x, tag in BusTags._tag_by_id.items():
                    if tag.name.startswith(start):
                        tagname_list.append(tag.name)
            elif value.endswith(b'$'):
                end = value[:-1]
                for _x, tag in BusTags._tag_by_id.items():
                    if tag.name.endswith(end):
                        tagname_list.append(tag.name)
            else:
                for _x, tag in BusTags._tag_by_id.items():
                    if value in tag.name:
                        tagname_list.append(tag.name)
            self.message(pc.CMD_LIST, 0, time_us, b' '.join(tagname_list))
        else:  # consider disconnecting
            logging.warn(f'invalid message {command}')

    def parse(self):
        """Parse commands from stream."""
        i = 0
        while True:
            if len(self.buffer) < i + 14:
                break  # let buffer grow
            _version, command, tag_id, size, time_us = unpack_from(
                '>BBHHQ', self.buffer, offset=i)
            if len(self.buffer) < i + 14 + size:
                break  # let buffer grow
            if size == 0:
                value = b''
            elif size > 0:
                value = unpack_from(f">{size}s", self.buffer, offset=i + 14)[0]
            i += 14 + size  # index to next message
            if size == pc.MAX_LEN:  # continuation required
                if tag_id in self.pending:
                    self.pending[tag_id] += value
                else:
                    self.pending[tag_id] = value
            else:
                if tag_id in self.pending:
                    self.pending[tag_id] += value
                    value = self.pending[tag_id]
                    del self.pending[tag_id]
                self.commands.append([command, tag_id, time_us, value])
        if i == len(self.buffer):
            self.buffer = b''
        else:
            self.buffer = self.buffer[i:]

    def data_received(self, recv):
        """Parse for commands then process the commands."""
        if len(self.buffer) == 0:
            self.buffer = recv
        else:
            self.buffer += recv
        self.parse()
        while len(self.commands):
            self.process()


class BusServer:
    """
    Create a Bus Server that will handle changing connections.

    Creates tags on ID message. If process stops pymscada must completely
    restart.
    """

    def __init__(self, address: str = '127.0.0.1', port: int = 1324):
        """Set binding address and port for BusServer."""
        self.address = address
        self.port = port

    async def start(self) -> asyncio.Server:
        """Start the server."""
        return await asyncio.get_running_loop().create_server(
            lambda: BusServerProtocol(), self.address, self.port)
