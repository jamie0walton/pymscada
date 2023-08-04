"""Bus client."""
import asyncio
from struct import pack, unpack_from
from collections import deque
import json
import logging
from .tag import Tag
from . import protocol_constants as pc


class BusClientProtocol(asyncio.Protocol):
    """
    Implements bus client protocol.

    State machine of calls:
    * -> connection_made()
    * load existing tags
    * listen for new tags
    * get ID and subscribe to all tags
    * -> data_received()*
    * on new tag, get ID and subscribe
    * -> eof_received()?
    * -> connection_lost(), process must die
    """

    def __init__(self):
        """Initialise with the tags to watch and set."""
        self.pause = False
        self.buffer = b''
        self.commands = deque()
        self.pending = {}
        self.bus_id = id(self)
        self.tags: dict[str, 'Tag'] = {}
        self.tag_by_id: dict[int, 'Tag'] = {}

    def __del__(self):
        """Perhaps do something here."""
        logging.info("deleted BusClientProtocol instance")
        # took a bit to make this work as the tag callback hooks held it live

    def connection_made(self, transport):
        """When Bus connection is made, register to listen to subtags."""
        logging.info(f"connection made {transport.get_extra_info('peername')}")
        self.transport = transport
        Tag.notify = self.add_tag
        for tag in Tag.get_all_tags():
            self.add_tag(tag)

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
        logging.warn(f"got eof {self.transport.get_extra_info('peername')}")
        self.transport.abort()

    def connection_lost(self, exc):
        """If we lose bus connection, kill the program."""
        logging.critical(f"Lost bus connection, reason: {exc}")
        raise SystemExit('Exiting on lost bus')

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

    def add_tag(self, tag: Tag):
        """Add the new tag and get the tag's bus ID."""
        self.tags[tag.name] = tag
        self.message(pc.CMD_ID, 0, 0, tag.name.encode())

    def publish(self, tag: Tag):
        """
        If published tag value changes, send to bus.

        Don't send to bus if it came from the bus.
        Convert type to bytes and send.
        """
        if tag.from_bus == self.bus_id or tag.value is None:
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
            logging.warning(f'{tag.name} unhandled {tag.type}')
            return
        self.message(pc.CMD_SET, tag.id, tag.time_us, data)

    def process(self):
        """Process bus message, updating the local tag value."""
        command, tag_id, time_us, value = self.commands.popleft()
        if command == pc.CMD_ERR:
            logging.warning(f'Bus server error {tag_id} {value}')
            return
        if command == pc.CMD_ID:
            tag = self.tags[value.decode()]
            tag.id = tag_id
            self.tag_by_id[tag_id] = tag
            self.message(pc.CMD_SUB, tag.id, 0, b'')
            return
        tag = self.tag_by_id[tag_id]
        if command == pc.CMD_SET:
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
            tag.value = data, time_us, self.bus_id
        elif command == pc.CMD_RQS:
            logging.warning('TODO')
        else:  # consider disconnecting
            logging.warn(f'invalid message {command}')

    def parse(self):
        """Parse commands from stream."""
        i = 0
        while len(self.buffer) >= i + 14:
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


class BusClient:
    """
    Connects to a Bus Server.

    Monitors UniqueTag.notify for tag creation. If bus server connection
    fails, die.
    """

    def __init__(self, address: str = '127.0.0.1', port: int = 1324):
        """Create a new Bus client."""
        self.address = address
        self.port = port

    async def start(self):
        """Create the connection and register the protocol. Run once."""
        return await asyncio.get_running_loop().create_connection(
            lambda: BusClientProtocol(), self.address, self.port)
