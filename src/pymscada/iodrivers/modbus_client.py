"""Modbus Client."""
import asyncio
import logging
from struct import pack, unpack_from, unpack
from time import time
from pymscada.bus_client import BusClient
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


def tag_split(modbus_tag: str):
    """Split the address into rtu, variable, element and bit."""
    name, unit, file, word = modbus_tag.split(':')
    bit_loc = word.find('.')
    if bit_loc == -1:
        bit = None
        word = word
    else:
        bit = word[bit_loc + 1:]
        word = word[:bit_loc]
    return name, unit, file, word, bit


class ModbusClientMap:
    """Map the data table to a Tag."""

    def __init__(self, tagname: str, src_type: str, addr: str, data: dict,
                 value_chg: dict):
        """Initialise modbus map and Tag."""
        name, unit, file, word, bit = tag_split(addr)
        self.data_file = f'{name}:{unit}:{file}'
        self.data = data[self.data_file]
        self.value_chg = value_chg[self.data_file]
        self.src_type = src_type
        self.bit = bit
        dtype, dmin, dmax = DTYPES[src_type][0:3]
        self.tag = Tag(tagname, dtype)
        self.map_bus = id(self)
        self.tag.add_callback(self.tag_value_ext, self.map_bus)
        if dmin is not None:
            self.tag.value_min = dmin
        if dmax is not None:
            self.tag.value_max = dmax
        self.byte = (int(word) - 1) * 2
        self.swap = bytearray(4)

    def update_tag(self, time_us):
        """Unpack from modbus registers to tag value if different."""
        if self.bit is not None:
            word_value = unpack_from('>H', self.data, self.byte)[0]
            bit_num = int(self.bit)
            value = (word_value >> bit_num) & 1
        elif self.src_type == 'int16':
            value = unpack_from('>h', self.data, self.byte)[0]
        elif self.src_type == 'uint16':
            value = unpack_from('>H', self.data, self.byte)[0]
        elif self.src_type == 'int32':
            self.swap[0:2] = self.data[self.byte+2:self.byte+4]
            self.swap[2:4] = self.data[self.byte:self.byte+2]
            value = unpack('>i', self.swap)[0]
        elif self.src_type == 'uint32':
            self.swap[0:2] = self.data[self.byte+2:self.byte+4]
            self.swap[2:4] = self.data[self.byte:self.byte+2]
            value = unpack('>I', self.swap)[0]
        elif self.src_type == 'int64':
            logging.error(f'{self.src_type} likely needs word swap')
            value = unpack_from('>q', self.data, self.byte)[0]
        elif self.src_type == 'uint64':
            logging.error(f'{self.src_type} likely needs word swap')
            value = unpack_from('>Q', self.data, self.byte)[0]
        elif self.src_type == 'float32':
            self.swap[0:2] = self.data[self.byte+2:self.byte+4]
            self.swap[2:4] = self.data[self.byte:self.byte+2]
            value = unpack('>f', self.swap)[0]
        elif self.src_type == 'float64':
            logging.error(f'{self.src_type} likely needs word swap')
            value = unpack_from('>d', self.data, self.byte)[0]
        else:
            return
        if value != self.tag.value:
            logging.info(f'updating {self.tag.name} from {self.tag.value}'
                         f' to {value}')
            self.tag.value = value, time_us, self.map_bus

    def tag_value_ext(self, tag: Tag):
        """Call external tag value update to write remote table."""
        logging.info(f'tag_value_changed {tag.name} {tag.value}')
        if self.src_type == 'int16':
            self.value_chg(self.data_file, self.byte, pack('>h', tag.value))
        elif self.src_type == 'uint16':
            self.value_chg(self.data_file, self.byte, pack('>H', tag.value))
        elif self.src_type == 'int32':
            self.value_chg(self.data_file, self.byte, pack('>i', tag.value))
        elif self.src_type == 'uint32':
            self.value_chg(self.data_file, self.byte, pack('>I', tag.value))
        elif self.src_type == 'int64':
            self.value_chg(self.data_file, self.byte, pack('>q', tag.value))
        elif self.src_type == 'uint64':
            self.value_chg(self.data_file, self.byte, pack('>Q', tag.value))
        elif self.src_type == 'float32':
            swap = pack('>f', tag.value)
            self.value_chg(self.data_file, self.byte, swap[2:4] + swap[0:2])
        elif self.src_type == 'float64':
            self.value_chg(self.data_file, self.byte, pack('>d', tag.value))


class ModbusClientMaps():
    """Shared modbus mapping."""

    def __init__(self, tags):
        """Singular please."""
        self.tags = tags
        self.data = {}
        self.value_chg = {}
        self.maps = {}

    def add_data_table(self, tables, value_chg):
        """Add a bytes data table."""
        for table in tables:
            self.data[table] = bytearray(2 * (tables[table] - 1))
            self.value_chg[table] = value_chg

    def make_map(self):
        """Make the maps."""
        for tagname, v in self.tags.items():
            dtype = v['type']
            if 'read' in v:
                addr = v['read']
            elif 'write' in v:
                addr = v['write']
            else:
                logging.error(f'{tagname} has no read or write address')
                continue
            map = ModbusClientMap(tagname, dtype, addr, self.data, self.value_chg)
            size = DTYPES[dtype][3]
            name, unit, file, word, _bit = tag_split(addr)
            for i in range(0, size):
                word_addr = f'{name}:{unit}:{file}:{int(word) + i}'
                if word_addr not in self.maps:
                    self.maps[word_addr] = []
                self.maps[word_addr].append(map)

    def set_data(self, name: str, unit: int, file: str, pdu_start: int,
                 pdu_count: int, data: bytearray):
        """Set data, start and end in byte count."""
        time_us = int(time() * 1e6)
        start = pdu_start * 2
        end = start + pdu_count * 2
        data_file = f'{name}:{unit}:{file}'
        self.data[data_file][start:end] = data
        maps: set[ModbusClientMap] = set()
        for word_count in range(1, pdu_count + 1):
            word = word_count + pdu_start
            word_addr = f'{name}:{unit}:{file}:{word}'
            try:
                word_maps = self.maps[word_addr]
                maps.update(word_maps)
            except KeyError:
                pass
        logging.debug(f'set_data {name} {unit} {file} {start} {end}')
        for map in maps:
            map.update_tag(time_us)
        pass


class ModbusClientProtocol(asyncio.Protocol):
    """Modbus TCP and UDP client."""

    def __init__(self, process):
        """Modbus client protocol."""
        self.process = process
        self.buffer = b""
        self.peername = None
        self.sockname = None

    def __del__(self):
        """Log deletion."""
        logging.info("__del__")

    def connection_lost(self, exc):
        """Modbus connection lost."""
        logging.info(f'connection_lost {self.sockname} {self.peername} {exc}')

    def eof_received(self):
        """EOF."""
        logging.info("eof_received")

    def error_received(self, exc):
        """Whatever."""
        logging.info("error_received {exc}")

    def connection_made(self, transport: asyncio.Transport):
        """Modbus connection made."""
        self.peername = transport.get_extra_info('peername')
        self.sockname = transport.get_extra_info('sockname')
        logging.info(f'connection_made {self.sockname} to {self.peername}')
        transport.set_write_buffer_limits(high=0)
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

    def datagram_received(self, data, _addr):
        """Received a UDP packet, discard any partial packets."""
        # logging.info("datagram_received")
        self.buffer = data
        for msg in self.unpack_mb():
            self.process(msg)


class ModbusClientConnector:
    """Poll Modbus device, write on change in write range."""

    def __init__(self, name: str, ip: str, port: int, rate: int, tcp_udp: str,
                 sleep: float, poll: list, mapping: ModbusClientMaps):
        """
        Set up polling client.

        TODO fix BROKEN! tag alignment with units on differing rtus.
        """
        self.name = name
        self.ip = ip
        self.port = port
        self.tcp_udp = tcp_udp
        self.transport = None
        self.protocol = None
        self.read = poll
        self.periodic = Periodic(self.poll, rate)
        self.sleep = sleep  # some devices require time between polls
        self.mapping = mapping
        self.sent = {}
        tables = {}
        for file_range in poll:  # chain(read, writeok):
            unit = file_range['unit']
            file = file_range['file']
            table = f'{name}:{unit}:{file}'
            end = file_range['end']
            if table not in tables:
                tables[table] = 1
            tables[table] = max(tables[table], end)
        self.mapping.add_data_table(tables, self.write_tag_update)
        self._mbap_tr = 0
        self.age_count = 0

    def process(self, msg):
        """Process received message, match to transaction."""
        # logging.info(f"messages in sent {len(self.sent)}")
        mbap_tr, _mbap_pr, _mbap_len, mbap_unit, pdu_fc = unpack_from(
            ">3H2B", msg, 0)
        logging.warning(f"process {mbap_tr}")
        if self.age_count > 0:
            self.age_count -= 1
        if pdu_fc == 3:
            data = msg[9:]
            self.mapping.set_data(name=self.name, data=data,
                                  **self.sent[mbap_tr])
            try:
                del self.sent[mbap_tr]
            except KeyError:
                logging.warning(f"mbap_tr {mbap_tr} not found in sent")
        elif pdu_fc == 16:  # provision for future
            pdu_start, pdu_count = unpack_from(">2H", msg, 8)
            pass
        elif pdu_fc > 128:
            errorcode, *_ = unpack_from('>B', msg, 8)
            logging.error(f"Received error on {pdu_fc - 128} {errorcode}")
            return
        else:  # Unsupported
            logging.info(f"Received function code {pdu_fc}")
            return

    async def start_connection(self):
        """Start the UDP or TCP connection."""
        try:
            if self.tcp_udp == 'udp':
                logging.debug(f'UDP to {self.ip}:{self.port}')
                self.transport, self.protocol = \
                    await asyncio.get_running_loop().create_datagram_endpoint(
                        lambda: ModbusClientProtocol(self.process),
                        remote_addr=(self.ip, self.port))
            else:
                logging.debug(f'TCP to {self.ip}:{self.port}')
                self.transport, self.protocol = \
                    await asyncio.get_running_loop().create_connection(
                        lambda: ModbusClientProtocol(self.process),
                        self.ip, self.port)
        except Exception as e:
            logging.warning(f'start_connection {e}')

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
        if self.tcp_udp == "udp":
            logging.info(f"UDP read {mbap_unit} {file} {pdu_start} "
                         f"{pdu_count}")
            self.transport.sendto(msg)  # type: ignore
        else:
            logging.info(f"TCP read {mbap_unit} {file} {pdu_start} "
                         f"{pdu_count}")
            self.transport.write(msg)  # type: ignore
        self.sent[mbap_tr] = {"unit": mbap_unit, "file": file,
                              "pdu_start": pdu_start, "pdu_count": pdu_count}

    def mb_write(self, unit: int, file: str, start: int, end: int,
                 data: bytes):
        """Build write, save transaction to match."""
        logging.debug(f"would write {unit} {file} {start} {end}")
        mbap_tr = self.mbap_tr()
        mbap_pr = 0  # protocol always 0
        mbap_len = None
        mbap_unit = unit
        count = end - start
        if file == '4x':
            pdu_fc = 16
            pdu = pack('>B2HB', pdu_fc, start, count, count * 2) + data
            pdu_len = 6 + count * 2
            # logging.info(f"{pdu_fc} {start} {count} "
            #          f"{count * 2} {data} {pdu.hex()}")
        else:
            logging.warning(f"no support for {file}")
            return
        mbap_len = pdu_len + 1
        mbap = pack(">3H1B", mbap_tr, mbap_pr, mbap_len, mbap_unit)
        msg = mbap + pdu
        if self.tcp_udp == "udp":
            logging.info(f"UDP write {mbap_unit} {file} {start} {end}")
            self.transport.sendto(msg)  # type: ignore
        else:
            logging.info(f"TCP write {mbap_unit} {file} {start} {end}")
            self.transport.write(msg)  # type: ignore

    def write_tag_update(self, addr: str, byte: int, data: bytes):
        """Write out any tag updates."""
        if self.transport is None:
            return
        _, unit, file = addr.split(':')
        mbap_unit = int(unit)
        start = byte // 2
        end = start + len(data) // 2
        self.mb_write(mbap_unit, file, start, end, data)
        pass

    async def poll(self):
        """Create Modbus polling connections."""
        self.age_count += 1
        if self.transport is not None and self.age_count > 15:
            logging.warning('modbusclient age reconnect')
            self.transport.close()
        if self.transport is not None and self.transport.is_closing() is True:
            logging.warning('closing')
            self.protocol = None
            self.transport = None
            self.sent = {}
            self.age_count = 0
        if self.transport is None:
            await self.start_connection()
        if self.transport is None:
            return
        for poll in self.read:
            self.mb_read(**poll)
            if self.sleep > 0:
                await asyncio.sleep(self.sleep)

    async def start(self):
        """Start polling."""
        await self.periodic.start()


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
        self.mapping = ModbusClientMaps(tags)
        self.connections: list[ModbusClientConnector] = []
        for rtu in rtus:
            connection = ModbusClientConnector(**rtu, mapping=self.mapping)
            self.connections.append(connection)
        self.mapping.make_map()

    async def start(self):
        """Provide a modbus client."""
        if self.busclient is not None:
            await self.busclient.start()
        for connection in self.connections:
            await connection.start()
