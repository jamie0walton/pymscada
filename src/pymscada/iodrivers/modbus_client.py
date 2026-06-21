"""Modbus Client."""
import asyncio
import logging
from itertools import chain
from struct import pack, unpack, pack_into, unpack_from
from time import time
from pymscada.bus_client import BusClient
from pymscada.bus_client_tag import TagInt, TagFloat
from pymscada.tag import Tag
from pymscada.periodic import Periodic


# Modbus
#
# Transaction ID    2 bytes     incrementing
# Protocol          2 bytes     always 0
# Length            2 bytes     number of following bytes
# Unit address      1 byte      PLC address
# Message           N bytes     max size, 253 bytes
#                               max overall 260 bytes
# Function code     1 byte      3 Read registers
# First address     2 bytes     0 == 40001
# Register count    2 bytes     125 is the largest


# data types for PLCs
DTYPES = {
    'int16': [int, -32768, 32767, 1],
    'int32': [int, -2147483648, 2147483647, 2],
    'int64': [int, -2**63, 2**63 - 1, 4],
    'uint16': [int, 0, 65535, 1],
    'uint32': [int, 0, 4294967295, 2],
    'uint64': [int, 0, 2**64 - 1, 4],
    'float32': [float, None, None, 2],
    'float64': [float, None, None, 4],
    'bool': [int, 0, 1, 1]
}

START_UP = 0
OFFLINE = 1
CONNECT = 2
READ_WRITES = 3
WRITES_READ = 4
READ_AND_WRITE = 5


class Map:
    """namespace map."""

    def __init__(self, tagname: str, src_type: str, addr: str):
        self.tagname = tagname
        self.src_type = src_type
        dtype, dmin, dmax, dsize = DTYPES[src_type]
        if dtype is int:
            self.tag = TagInt(tagname)
        elif dtype is float:
            self.tag = TagFloat(tagname)
        else:
            raise ValueError(f'unsupported Modbus tag type {src_type}')
        if dmin is not None:
            self.tag.value_min = dmin
        if dmax is not None:
            self.tag.value_max = dmax
        self.size = dsize
        rtu, unit, file, word = addr.split(':')
        bit_loc = word.find('.')
        if bit_loc == -1:
            self.bit = None
            self.word = int(word)
        else:
            self.bit = int(word[bit_loc + 1:])
            self.word = int(word[:bit_loc])
        self.rtu = rtu
        self.unit = int(unit)
        self.file = file
        self.byte = (self.word - 1) * 2
        self.swap = bytearray(4)


class Tags:
    """update tags."""

    def __init__(self, tags: dict):
        """add the tags"""
        self.reads = {}
        self.read_map = {}
        self.writes = {}
        for tagname in tags:
            read = tags[tagname].get('read', None)
            write = tags[tagname].get('write', None)
            src_type = tags[tagname]['type']
            if read is not None:
                self.reads[tagname] = Map(tagname, src_type, read)
            elif read is None and write is not None:
                self.writes[tagname] = Map(tagname, src_type, write)
            else:
                raise ValueError(f'{tagname} set either read or write')
        for tagname, read in self.reads.items():
            for i in range(read.size):
                addr = f"{read.rtu}:{read.unit}:{read.file}:{read.word + i}"
                if addr not in self.read_map:
                    self.read_map[addr] = []
                self.read_map[addr].append(tagname)


class ModbusClientProtocol(asyncio.Protocol):
    """Modbus TCP and UDP client."""

    def __init__(self, process):
        """Modbus client protocol."""
        self.process = process
        self.buffer = b""
        self.peername = None
        self.sockname = None
        self.transport = None

    def connection_lost(self, exc):
        """Modbus connection lost."""
        logging.info(f'connection_lost {self.sockname} {self.peername} {exc}')
        self.transport = None

    def connection_made(self, transport: asyncio.BaseTransport):
        """Modbus connection made."""
        self.peername = transport.get_extra_info('peername')
        self.sockname = transport.get_extra_info('sockname')
        logging.info(f'connection_made {self.sockname} to {self.peername}')
        # transport.set_write_buffer_limits(high=0)  # type: ignore
        self.transport = transport

    def unpack_mb(self):
        """Return complete modbus packets and trim the buffer."""
        start = 0
        end = 0
        while True:
            buf_len = len(self.buffer)
            if buf_len < 6 + start:  # enough to unpack length
                break
            _mbap_tr, _mbap_pr, mbap_len = unpack_from(">3H", self.buffer, start)
            if buf_len < start + 6 + mbap_len:  # there is a complete message
                break
            end = start + 6 + mbap_len
            yield self.buffer[start:end]
            start = end
        self.buffer = self.buffer[end:]

    def data_received(self, data):
        """Received TCP data, see if there is a full modbus packet."""
        self.buffer += data
        for msg in self.unpack_mb():
            self.process(msg)


class ModbusClientConnector:
    """Poll Modbus device, write on change in write range."""

    def __init__(self, name: str, ip: str, port: int, rate: int,
                 reads: list, writes: list, tags: Tags):
        """
        Set up polling client.

        TODO fix BROKEN! tag alignment with units on differing rtus.
        """
        self.name = name
        self.ip = ip
        self.port = port
        self.connected = START_UP
        self.connected_wait = 0
        self.transport = None
        self.protocol = None
        self.reads = reads
        self.writes = writes
        self.tags = tags
        for write in self.tags.writes.values():
            write.tag.add_callback(self.update_write_table)
        self.data: dict[str, bytearray] = {}
        self.make_data()
        self.periodic = Periodic(self.poll, rate)
        self.sent = {}
        self._mbap_tr = 0

    async def start_connection(self):
        """Start the connection."""
        try:
            logging.debug(f'TCP to {self.ip}:{self.port}')
            self.transport, self.protocol = \
                await asyncio.get_running_loop().create_connection(
                    lambda: ModbusClientProtocol(self.process),
                    self.ip, self.port)
        except Exception as e:
            logging.warning(f'start_connection {e}')

    def update_tag_value(self, data_file: str, tagname: str, time_us: int):
        read = self.tags.reads[tagname]
        data = self.data[data_file]
        if read.src_type == 'bool':
            word_value = unpack_from('>H', data, read.byte)[0]
            bit_num = read.bit
            value = (word_value >> bit_num) & 1
        elif read.src_type == 'int16':
            value = unpack_from('>h', data, read.byte)[0]
        elif read.src_type == 'uint16':
            value = unpack_from('>H', data, read.byte)[0]
        elif read.src_type == 'int32':
            read.swap[0:2] = data[read.byte + 2 : read.byte + 4]
            read.swap[2:4] = data[read.byte : read.byte + 2]
            value = unpack('>i', read.swap)[0]
        elif read.src_type == 'uint32':
            read.swap[0:2] = data[read.byte + 2 : read.byte + 4]
            read.swap[2:4] = data[read.byte : read.byte + 2]
            value = unpack('>I', read.swap)[0]
        elif read.src_type == 'int64':
            logging.error(f'{read.src_type} likely needs word swap')
            value = unpack_from('>q', data, read.byte)[0]
        elif read.src_type == 'uint64':
            logging.error(f'{read.src_type} likely needs word swap')
            value = unpack_from('>Q', data, read.byte)[0]
        elif read.src_type == 'float32':
            read.swap[0:2] = data[read.byte + 2 : read.byte + 4]
            read.swap[2:4] = data[read.byte : read.byte + 2]
            value = unpack('>f', read.swap)[0]
        elif read.src_type == 'float64':
            logging.error(f'{read.src_type} likely needs word swap')
            value = unpack_from('>d', data, read.byte)[0]
        else:
            return
        # if value != read.tag.value:
        logging.warning(f"update_tag_value {read.tag.name} from {data_file} "
                        f"{read.word} {read.bit} {value}")
        read.tag.set_value(value, time_us)

    def update_tag_values(self, data_file: str, start: int, end: int):
        logging.warning(f'update_tag_value {data_file} {start} {end}')
        time_us = int(time() * 1e6)
        update = set()
        for word in range(start // 2, end // 2):
            addr = f"{data_file}:{word + 1}"
            if addr in self.tags.read_map:
                for tagname in self.tags.read_map[addr]:
                    update.add(tagname)
        for tagname in update:
            self.update_tag_value(data_file, tagname, time_us)

    def update_write_table(self, tag: TagInt | TagFloat):
        write = self.tags.writes[tag.name]
        data_file = f"{write.rtu}:{write.unit}:{write.file}"
        data = self.data[data_file]
        logging.warning(f"update_write_table {data_file} {write.word} "
                        f"{write.bit} from {tag.name} {tag.value}")
        if write.src_type == 'bool':
            word_value = unpack_from('>H', data, write.byte)[0]
            bit_num = write.bit
            if tag.value == 1:
                word_value |= 1 << bit_num
            else:
                word_value &= ~(1 << bit_num)
            data[write.byte : write.byte + 2] = pack('>h', word_value)
        elif write.src_type == 'int16':
            data[write.byte : write.byte + 2] = pack('>h', tag.value)
        elif write.src_type == 'uint16':
            data[write.byte : write.byte + 2] = pack('>H', tag.value)
        elif write.src_type == 'int32':
            data[write.byte : write.byte + 4] = pack('>i', tag.value)
        elif write.src_type == 'uint32':
            data[write.byte : write.byte + 4] = pack('>I', tag.value)
        elif write.src_type == 'int64':
            data[write.byte : write.byte + 8] = pack('>q', tag.value)
        elif write.src_type == 'uint64':
            data[write.byte : write.byte + 8] = pack('>Q', tag.value)
        elif write.src_type == 'float32':
            swap = pack('>f', tag.value)
            data[write.byte : write.byte + 4] = swap[2:4] + swap[0:2]
        elif write.src_type == 'float64':
            data[write.byte : write.byte + 8] = pack('>d', tag.value)


    def set_data(self, mbap_tr: int, data: bytearray):
        tr = self.sent[mbap_tr]
        time_us = int(time() * 1e6)
        start = tr['pdu_start'] * 2
        end = start + tr['pdu_count'] * 2
        data_file = f'{self.name}:{tr['unit']}:{tr['file']}'
        logging.warning(f"set_data {data_file} {start} {end} "
                        f"{len(data)} {mbap_tr}")
        self.data[data_file][start:end] = data
        self.update_tag_values(data_file, start, end)

    def get_data(self, mbap_tr: int, unit: int, file: str, pdu_start: int,
                 pdu_count: int):
        data_file = f'{self.name}:{unit}:{file}'
        start = pdu_start * 2
        end = start + pdu_count * 2
        data = self.data[data_file][start:end]
        logging.warning(f"get_data {data_file} {start} {end} "
                        f"{len(data)} {mbap_tr}")
        return data

    def process(self, msg):
        """Process received message, match to transaction."""
        mbap_tr, _mbap_pr, _mbap_len, mbap_unit, pdu_fc = unpack_from(
            ">3H2B", msg, 0)
        if pdu_fc == 3:
            data = msg[9:]
            self.set_data(mbap_tr, data)
            try:
                del self.sent[mbap_tr]
            except KeyError:
                logging.warning(f"mbap_tr {mbap_tr} not found in sent")
        elif pdu_fc == 16:
            pdu_start, pdu_count = unpack_from(">2H", msg, 8)
            pass
        elif pdu_fc > 128:
            errorcode, *_ = unpack_from('>B', msg, 8)
            logging.error(f"process error {pdu_fc - 128} {errorcode}")
        else:
            logging.error(f"process unsupported {pdu_fc}")

    def mbap_tr(self):
        """Global transaction number provider."""
        self._mbap_tr += 1
        if self._mbap_tr == 65536:
            self._mbap_tr = 0
        return self._mbap_tr

    def mb_read(self, unit: int, file: str, start: int, end: int):
        """Build read, save the transaction for matching responses."""
        mbap_tr = self.mbap_tr()
        mbap_pr = 0  # protocol always 0
        mbap_len = None
        mbap_unit = unit
        if file == '4x':
            pdu_fc = 3
            pdu_start = start - 1
            pdu_count = end - start + 1
            pdu = pack(">B2H", pdu_fc, pdu_start, pdu_count)
            pdu_len = 5
        else:
            logging.warning(f"no support for {file}")
            return
        mbap_len = pdu_len + 1
        mbap = pack(">3H1B", mbap_tr, mbap_pr, mbap_len, mbap_unit)
        msg = mbap + pdu
        # logging.info(f"TCP read {mbap_unit} {file} {pdu_start} "
        #                 f"{pdu_count} {msg}")
        self.transport.write(msg)  # type: ignore
        self.sent[mbap_tr] = {"unit": mbap_unit, "file": file,
                              "pdu_start": pdu_start, "pdu_count": pdu_count}

    def mb_write(self, unit: int, file: str, start: int, end: int):
        """Build write, save transaction to match."""
        mbap_tr = self.mbap_tr()
        mbap_pr = 0  # protocol always 0
        mbap_len = None
        mbap_unit = unit
        if file == '4x':
            pdu_fc = 16
            pdu_start = start - 1
            pdu_count = end - start + 1
            data = self.get_data(mbap_tr, unit, file, pdu_start, pdu_count)
            pdu = pack('>B2HB', pdu_fc, pdu_start, pdu_count, pdu_count * 2
                       ) + data
            pdu_len = 6 + pdu_count * 2
        else:
            logging.warning(f"no support for {file}")
            return
        mbap_len = pdu_len + 1
        mbap = pack(">3H1B", mbap_tr, mbap_pr, mbap_len, mbap_unit)
        msg = mbap + pdu
        # logging.info(f"TCP write {mbap_unit} {file} {start} {end}")
        self.transport.write(msg)  # type: ignore

    def make_data(self):
        """Create words for exchange with RTU."""
        tables = {}
        for file_range in chain(self.reads, self.writes):
            unit = file_range['unit']
            file = file_range['file']
            table = f'{self.name}:{unit}:{file}'
            end = file_range['end'] + 1
            if table not in tables:
                tables[table] = 1
            tables[table] = max(tables[table], end)
        for table in tables:
            self.data[table] = bytearray(2 * tables[table])

    async def poll(self):
        """Create Modbus polling connections."""
        self.connected_wait = max(0, self.connected_wait - 1)
        if self.connected_wait > 0:
            return
        offline = self.transport is None or self.transport.is_closing()
        if self.connected == START_UP:
            if offline:
                await self.start_connection()
                logging.warning(f"{self.name} connecting")
            else:
                self.connected = READ_WRITES
                logging.warning(f"{self.name} connected")
        elif self.connected == OFFLINE:
            if offline:
                self.sent = {}
                self.connected_wait = 5
                await self.start_connection()
            else:
                self.connected = READ_WRITES
        if offline:
            self.connected_wait = 5
            self.connected = OFFLINE
            return
            logging.warning(f"{self.name} offline")
        if self.connected == READ_WRITES:
            for read in self.writes:
                self.mb_read(**read)
            self.connected = WRITES_READ
            self.connected_wait = 2
            logging.warning(f"{self.name} read writes")
        elif self.connected == WRITES_READ:
            if len(self.sent) == 0:
                self.connected = READ_AND_WRITE
                logging.warning(f"{self.name} writes read")
            else:
                # self.transport.close()  # type: ignore
                self.connected_wait = 5
        elif self.connected == READ_AND_WRITE:
            for read in self.reads:
                self.mb_read(**read)
            for write in self.writes:
                self.mb_write(**write)
            logging.warning(f"{self.name} read/write")

    async def start(self):
        """Start polling."""
        await self.periodic.start()
        while self.connected != READ_AND_WRITE:
            logging.info('waiting for connection')
            await asyncio.sleep(1.0)


class ModbusClient:
    """Connect to bus on bus_ip:bus_port, serve on ip:port for modbus."""

    def __init__(self, bus_ip: str = '127.0.0.1', bus_port: int = 1324,
                 rtus: dict = {}, tags: dict = {}) -> None:
        """
        Connect to bus on bus_ip:bus_port.

        Makes connections to Modbus PLCs to read and write data.
        Event loop must be running.
        """
        self.busclient = None
        if bus_ip is not None:
            self.busclient = BusClient(bus_ip, bus_port,
                                       module='Modbus Client')
        self.connections: list[ModbusClientConnector] = []
        for rtu in rtus:
            connection = ModbusClientConnector(**rtu, tags=Tags(tags))
            self.connections.append(connection)

    async def start(self):
        """Provide a modbus client."""
        if self.busclient is not None:
            await self.busclient.start()
        for connection in self.connections:
            await connection.start()
