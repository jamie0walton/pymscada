"""Modbus Server."""
import asyncio
import logging
from struct import pack, unpack_from
from time import time
from pymscada.bus_client import BusClient
from pymscada.tag import Tag


class ModbusServerProtocol:
    """Class."""

    def __init__(self, get_data, set_data):
        """Init."""
        self.get_data = get_data
        self.set_data = set_data
        self.msg = b""
        self.buffer = b""

    def __del__(self):
        """Del."""
        logging.info("deleted, good!")
        # care or the tag callback hooks hold this live

    def connection_made(self, transport):
        """Made."""
        peername = transport.get_extra_info('peername')
        sockname = transport.get_extra_info('sockname')
        logging.info(f'connection_made {sockname} to {peername}')
        transport.set_write_buffer_limits(high=0)
        self.transport = transport

    def connection_lost(self, err):
        """Lost."""
        self.transport.abort()

    def process(self):
        """Process."""
        mbap_tr, mbap_pr, _mbap_len, mbap_unit, pdu_fc = unpack_from(
            ">3H2B", self.msg, 0)
        print(mbap_tr)
        if pdu_fc == 3:  # Read Holding Registers
            # Return 0 for missing addresses
            pdu_start, pdu_count = unpack_from(">2H", self.msg, 8)
            word = pdu_start * 2
            end = word + pdu_count * 2
            data = self.get_data(mbap_unit, '4x', word, end)
            data_len = len(data)
            msg_len = 3 + data_len
            self.msg = pack('>3H3B', mbap_tr, mbap_pr, msg_len, mbap_unit,
                            pdu_fc, data_len) + data
        elif pdu_fc == 6:  # Set Single Register    4x
            pdu_start = unpack_from(">H", self.msg, 8)[0]
            data = bytearray(self.msg[10:12])
            start = pdu_start * 2
            end = start + 2
            self.set_data(mbap_unit, '4x', start, end, data)
            msg_len = 6
            self.msg = pack(">3H2BH", mbap_tr, mbap_pr, msg_len, mbap_unit,
                            pdu_fc, pdu_start) + data
        elif pdu_fc == 16:  # Set Multiple Registers 4x
            pdu_start, pdu_count, pdu_bytes = unpack_from(">2HB", self.msg, 8)
            data = bytearray(self.msg[13:13 + pdu_bytes])
            start = pdu_start * 2
            end = start + pdu_bytes
            self.set_data(mbap_unit, '4x', start, end, data)
            msg_len = 6
            self.msg = pack(">3H2B2H", mbap_tr, mbap_pr, msg_len, mbap_unit,
                            pdu_fc, pdu_start, pdu_count)
        else:
            # Unsupported, send the standard Modbus exception
            logging.warn(
                f"{self.transport.get_extra_info('peername')}"
                f" attempted FC {pdu_fc}"
            )
            msg_len = 3
            self.msg = pack(">3H2BB", mbap_tr, mbap_pr, msg_len, mbap_unit,
                            pdu_fc + 128, 1)

    def data_received(self, recv):
        """Received."""
        # logging.info(f'received: {recv}')
        start = 0
        self.buffer += recv
        while True:
            buf_len = len(self.buffer)
            if buf_len < 6 + start:  # enough to unpack length
                self.buffer = self.buffer[start:]
                break
            (_mbap_tr, _mbap_pr, mbap_len) = unpack_from(
                ">3H", self.buffer, start
            )
            if buf_len < 6 + mbap_len:  # there is a complete message
                self.buffer = self.buffer[start:]
                break
            end = start + 6 + mbap_len
            self.msg = self.buffer[start:end]
            start = end
            self.process()
            if self.msg is not None:
                self.transport.write(self.msg)
            self.msg = b""

    def datagram_received(self, recv, addr):
        """Received."""
        start = 0
        buffer = recv
        while True:
            buf_len = len(buffer)
            if buf_len < 6 + start:  # enough to unpack length
                buffer = buffer[start:]
                break
            (_mbap_tr, _mbap_pr, mbap_len) = unpack_from(">3H", buffer, start)
            if buf_len < 6 + mbap_len:  # there is a complete message
                buffer = buffer[start:]
                break
            end = start + 6 + mbap_len
            self.msg = buffer[start:end]
            start = end
            self.process()
            if self.msg is not None:
                self.transport.sendto(self.msg, addr)
            self.msg = b""

    def eof_received(self):
        """EOF."""
        logging.info("got eof")


# data types for PLCs
DTYPES = {
    'int16': [int, -32768, 32767],
    'int32': [int, -2147483648, 2147483647],
    'int64': [int, -2**63, 2**63 - 1],
    'uint16': [int, 0, 65535],
    'uint32': [int, 0, 4294967295],
    'uint64': [int, 0, 2**64 - 1],
    'float32': [float, None, None],
    'float64': [float, None, None]
}


class ModbusMap:
    """Map the data table to a Tag."""

    def __init__(self, tagname: str, src_type: str, word: int):
        """Initialise modbus map and Tag."""
        self.src_type = src_type
        dtype, dmin, dmax = DTYPES[src_type]
        self.tag = Tag(tagname, dtype)
        if dmin is not None:
            self.tag.value_min = dmin
        if dmax is not None:
            self.tag.value_max = dmax
        self.word = word
        self.byte = (word - 1) * 2

    def update_tag(self, data, time_us):
        """Unpack from modbus registers to tag value."""
        if self.src_type == 'int16':
            value = unpack_from('>h', data, self.byte)[0]
        elif self.src_type == 'uint16':
            value = unpack_from('>H', data, self.byte)[0]
        elif self.src_type == 'int32':
            value = unpack_from('>i', data, self.byte)[0]
        elif self.src_type == 'uint32':
            value = unpack_from('>I', data, self.byte)[0]
        elif self.src_type == 'int64':
            value = unpack_from('>q', data, self.byte)[0]
        elif self.src_type == 'uint64':
            value = unpack_from('>Q', data, self.byte)[0]
        elif self.src_type == 'float32':
            value = unpack_from('>f', data, self.byte)[0]
        elif self.src_type == 'float64':
            value = unpack_from('>d', data, self.byte)[0]
        if value != self.tag.value:
            self.tag.value = value, time_us


class ModbusServer:
    """Connect to bus on bus_ip:bus_post, serve on ip:port for modbus."""

    def __init__(self, bus_ip: str = '127.0.0.1', bus_port: int = 1324,
                 ip: str = '127.0.0.1', port: int = 502, protocol: str = 'tcp',
                 rtus: dict = {}, tags: dict = {}) -> None:
        """
        Connect to bus on bus_ip:bus_port, serve on ip:port for webclient.

        Serves the webclient files at /, as a relative path. The webclient uses
        a websocket connection to request and set tag values and subscribe to
        changes.

        Event loop must be running.
        """
        if bus_ip is not None:
            self.busclient = BusClient(bus_ip, bus_port)
        self.ip = ip
        self.port = port
        self.protocol = protocol
        self.tags = {}
        self.maps = {}
        for tagname, v in tags.items():
            dtype = v['type']
            addr = v['addr']
            unit, file, word = addr.split(':')
            map = ModbusMap(tagname, dtype, int(word))
            words = int(dtype[-2:]) // 16
            for i in range(0, words):
                addr = ':'.join([unit, file, str(int(word) + i)])
                self.maps[addr] = map
        self.data = {}
        for rtu in rtus:
            self.data[rtu['unit']] = {}
            for file in rtu['files']:
                self.data[rtu['unit']][file['name']] = bytearray(
                    2 * file['size'])
        pass

    def get_data(self, unit: int, file: str, start: int, end: int
                 ) -> bytearray:
        """Update the values and then the tags."""
        logging.info(f'read {unit} {file} {start}-{end}')
        return self.data[unit][file][start:end]

    def set_data(self, unit: int, file: str, start: int, end: int,
                 data: bytearray):
        """Update the values and then the tags."""
        time_us = int(time() * 1e6)
        self.data[unit][file][start:end] = data
        # print(self.data[unit][file].hex())
        maps = set()
        for byte in range(start, end, 2):
            word = byte // 2 + 1
            maps.add(self.maps[f'{unit}:{file}:{word}'])
        logging.info(f'write {unit} {file} {start // 2}-{word}')
        for map in maps:
            map.update_tag(self.data[unit][file], time_us)

    async def start(self):
        """Start the server and return."""
        if self.protocol == 'udp':
            await asyncio.get_running_loop().create_datagram_endpoint(
                lambda: ModbusServerProtocol(self.get_data, self.set_data),
                local_addr=(self.ip, self.port))
        else:
            await asyncio.get_running_loop().create_server(
                lambda: ModbusServerProtocol(self.get_data, self.set_data),
                self.ip, self.port)
