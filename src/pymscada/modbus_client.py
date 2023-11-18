"""Modbus Client."""
import asyncio
from itertools import chain
import logging
from struct import pack, unpack_from
from pymscada.bus_client import BusClient
from pymscada.modbus_map import ModbusMaps
from pymscada.periodic import Periodic


class ModbusClientProtocol(asyncio.Protocol):
    """Modbus TCP and UDP client."""

    def __init__(self, process):
        """Modbus client protocol."""
        self.process = process
        self._mbap_tr = 0  # start at 0
        self.buffer = b""
        self.peername = None
        self.sockname = None

    def __del__(self):
        """Log deletion."""
        logging.info("__del__")

    def connection_lost(self, err):
        """Modbus connection lost."""
        logging.info(f'connection_lost {self.sockname} to {self.peername}')

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

    def data_received(self, recv):
        """Received TCP data, see if there is a full modbus packet."""
        # logging.info("data_received")
        # logging.info(f'tcp echo server received: {recv}')
        start = 0
        self.buffer += recv
        while True:
            buf_len = len(self.buffer)
            if buf_len < 6 + start:  # assumes possible mbap_len of 0
                self.buffer = self.buffer[start:]
                break
            (_mbap_tr, _mbap_pr, mbap_len) = unpack_from(
                ">3H", self.buffer, start
            )
            if buf_len < 6 + mbap_len:
                self.buffer = self.buffer[start:]
                break
            end = start + 6 + mbap_len
            # got a complete message, set start to end for buffer prune
            self.process(self.buffer[start:end])
            start = end

    def datagram_received(self, recv, _addr):
        """Received a UDP packet, see if it is a full modbus packet."""
        # logging.info("datagram_received")
        start = 0
        buffer = recv
        while True:
            buf_len = len(buffer)
            if buf_len < 6 + start:  # assumes possible mbap_len of 0
                buffer = buffer[start:]
                break
            (_mbap_tr, _mbap_pr, mbap_len) = unpack_from(">3H", buffer, start)
            if buf_len < 6 + mbap_len:
                buffer = buffer[start:]
                break
            end = start + 6 + mbap_len
            # got a complete message, set start to end for buffer prune
            self.process(self.buffer[start:end])
            start = end


class ModbusClientConnector:
    """Poll Modbus device, write on change in write range."""

    def __init__(self, name: str, ip: str, port: int, rate: int, tcp_udp: str,
                 read: list, writeok: list, mapping: ModbusMaps):
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
        self.read = read
        self.writeok = writeok
        self.periodic = Periodic(self.poll, rate)
        self.mapping = mapping
        self.sent = {}
        size = {}
        for file_range in chain(read, writeok):
            unit = file_range['unit']
            file = file_range['file']
            end = file_range['end']
            if unit not in size:
                size[unit] = {}
            if file not in size[unit]:
                size[unit][file] = 1
            size[unit][file] = max(size[unit][file], end)
        self.mapping.add_data_table(self.name, size)
        self._mbap_tr = 0

    def process(self, msg):
        """Process received message, match to transaction."""
        # logging.info(f"messages in sent {len(self.sent)}")
        mbap_tr, _mbap_pr, _mbap_len, mbap_unit, pdu_fc = unpack_from(
            ">3H2B", msg, 0)
        if pdu_fc == 3:
            data = msg[9:]
            self.mapping.set_data(name=self.name, data=data,
                                  **self.sent[mbap_tr])
            del self.sent[mbap_tr]
        elif pdu_fc > 128:
            errorcode, *_ = unpack_from('>B', msg, 8)
            logging.error(f"Received error on {pdu_fc - 128} {errorcode}")
            return
        else:  # Unsupported
            logging.info(f"Received function code {pdu_fc}")
            return
        pass

    async def start_connection(self):
        """Start the UDP or TCP connection."""
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

    def mbap_tr(self):
        """Global transaction number provider."""
        self._mbap_tr += 1
        if self._mbap_tr == 65536:
            self._mbap_tr = 0
        return self._mbap_tr

    def mb_read(self, unit, file, start, end):
        """Build read, save the transaction for matching responses."""
        mbap_tr = self.mbap_tr()
        mbap_pr = 0  # protocol always 0
        mbap_len = None
        mbap_unit = unit
        if file == '4x':
            pdu_fc = 3
            pdu_start = start
            pdu_count = end - start + 1
            pdu = pack(">B2H", pdu_fc, pdu_start, pdu_count)
            pdu_len = 5
        else:
            logging.warn(f"no support for {file}")
            return
        mbap_len = pdu_len + 1
        mbap = pack(">3H1B", mbap_tr, mbap_pr, mbap_len, mbap_unit)
        msg = mbap + pdu
        if self.tcp_udp == "udp":
            self.transport.sendto(msg)
        else:
            self.transport.write(msg)
        self.sent[mbap_tr] = {"unit": unit, "file": file, 
                              "start": start, "end": end}

    def mb_write(self, unit, file, start, end):
        """Build write, save transaction to match."""
        logging.debug(f"would write {unit} {file} {start} {end}")
        mbap_tr = self.mbap_tr()
        mbap_pr = 0  # protocol always 0
        mbap_len = None
        mbap_unit = unit
        count = end - start
        if file == '4x':
            pdu_fc = 16
            data = []
            for address in range(start, end):
                target = self.tags[mbap_unit][file]
                if target[address].value is None:
                    data.append(0)
                else:
                    data.append(target[address].value)
            pdu = pack(f">B2HB{count}H", pdu_fc, start, count, count * 2,
                       *data)
            pdu_len = 6 + count * 2
            # logging.info(f"{pdu_fc} {start} {count} "
            #          f"{count * 2} {data} {pdu.hex()}")
        else:
            logging.warn(f"no support for {file}")
            return
        mbap_len = pdu_len + 1
        mbap = pack(">3H1B", mbap_tr, mbap_pr, mbap_len, mbap_unit)
        msg = mbap + pdu
        if self.tcp_udp == "udp":
            logging.info(f"UDP write {unit} {file} {start} {end}")
            self.transport.sendto(msg)
        else:
            logging.info(f"TCP write {unit} {file} {start} {end}")
            self.transport.write(msg)

    async def poll(self):
        """Create Modbus polling connections."""
        if self.transport is not None and self.transport.is_closing() is True:
            logging.info('closing')
            self.protocol = None
            self.transport = None
        if self.transport is None:
            await self.start_connection()
        for poll in self.read:
            self.mb_read(**poll)

    async def start(self):
        """Start polling."""
        await self.periodic.start()


class ModbusClient:
    """Connect to bus on bus_ip:bus_post, serve on ip:port for modbus."""

    def __init__(self, bus_ip: str = '127.0.0.1', bus_port: int = 1324,
                 rtus: dict = {}, tags: dict = {}) -> None:
        """
        Connect to bus on bus_ip:bus_port, serve on ip:port for webclient.

        Serves the webclient files at /, as a relative path. The webclient uses
        a websocket connection to request and set tag values and subscribe to
        changes.

        Event loop must be running.
        """
        self.busclient = None
        if bus_ip is not None:
            self.busclient = BusClient(bus_ip, bus_port)
        self.mapping = ModbusMaps(tags)
        self.connections: list[ModbusClientConnector] = []
        self.data = {}
        for rtu in rtus:
            connection = ModbusClientConnector(**rtu, mapping=self.mapping)
            self.connections.append(connection)
        self.mapping.make_map()

    async def start(self):
        """Provide a web server."""
        if self.busclient is not None:
            await self.busclient.start()
        for connection in self.connections:
            await connection.start()
