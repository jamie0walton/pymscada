"""Modbus Server."""
import asyncio
import logging
from struct import pack, unpack_from
from pymscada.bus_client import BusClient
from pymscada.iodrivers.modbus_map import ModbusMaps


class ModbusServerProtocol:
    """Class."""

    def __init__(self, name: str, mapping: ModbusMaps):
        """Init."""
        self.name = name
        self.mapping = mapping
        self.msg = b""
        self.buffer = b""

    def __del__(self):
        """Del."""
        logging.info("deleted, good!")
        # care or the tag callback hooks hold this live

    def connection_lost(self, err):
        """Lost."""
        self.transport.abort()

    def eof_received(self):
        """EOF."""
        logging.info("eof_received")

    def connection_made(self, transport: asyncio.Transport):
        """Made."""
        peername = transport.get_extra_info('peername')
        sockname = transport.get_extra_info('sockname')
        logging.info(f'connection_made {sockname} to {peername}')
        transport.set_write_buffer_limits(high=0)
        self.transport = transport

    def unpack_mb(self):
        """Return complete modbus packets and trim the buffer."""
        start = 0
        while True:
            buf_len = len(self.buffer)
            if buf_len < 6 + start:  # enough to unpack length
                break
            mbap_tr, mbap_pr, mbap_len = unpack_from(">3H", self.buffer, start)
            if buf_len < start + 6 + mbap_len:  # there is a complete message
                break
            end = start + 6 + mbap_len
            yield self.buffer[start:end]
            start = end
        self.buffer = self.buffer[end:]

    def data_received(self, recv):
        """Received."""
        # logging.info(f'received: {recv}')
        self.buffer += recv
        for msg in self.unpack_mb():
            reply = self.process(msg)
            self.transport.write(reply)

    def datagram_received(self, recv, addr):
        """Received."""
        self.buffer = recv
        for msg in self.unpack_mb():
            reply = self.process(msg)
            self.transport.sendto(reply, addr)

    def process(self, msg):
        """Process."""
        mbap_tr, mbap_pr, _mbap_len, mbap_unit, pdu_fc = unpack_from(
            ">3H2B", msg, 0)
        if pdu_fc == 3:  # Read Holding Registers
            # Return 0 for missing addresses
            pdu_start, pdu_count = unpack_from(">2H", msg, 8)
            data = self.mapping.get_data(self.name, mbap_unit, '4x', pdu_start,
                                         pdu_count)
            data_len = len(data)
            msg_len = 3 + data_len
            reply = pack('>3H3B', mbap_tr, mbap_pr, msg_len, mbap_unit,
                         pdu_fc, data_len) + data
        elif pdu_fc == 6:  # Set Single Register    4x
            pdu_start = unpack_from(">H", msg, 8)[0]
            data = bytearray(msg[10:12])
            self.mapping.set_data(self.name, mbap_unit, '4x', pdu_start,
                                  1, data)
            msg_len = 6
            reply = pack(">3H2BH", mbap_tr, mbap_pr, msg_len, mbap_unit,
                         pdu_fc, pdu_start) + data
        elif pdu_fc == 16:  # Set Multiple Registers 4x
            pdu_start, pdu_count, pdu_bytes = unpack_from(">2HB", msg, 8)
            data = bytearray(msg[13:13 + pdu_bytes])
            self.mapping.set_data(self.name, mbap_unit, '4x', pdu_start,
                                  pdu_count, data)
            msg_len = 6
            reply = pack(">3H2B2H", mbap_tr, mbap_pr, msg_len, mbap_unit,
                         pdu_fc, pdu_start, pdu_count)
        else:
            # Unsupported, send the standard Modbus exception
            logging.warn(
                f"{self.transport.get_extra_info('peername')}"
                f" attempted FC {pdu_fc}"
            )
            msg_len = 3
            reply = pack(">3H2BB", mbap_tr, mbap_pr, msg_len, mbap_unit,
                         pdu_fc + 128, 1)
        return reply


class ModbusServerConnector:
    """Modbus Server Connector for one or more bound ports."""

    def __init__(self, name: str, ip: str, port: int, tcp_udp: str,
                 serve: list, mapping: ModbusMaps):
        """Set up server."""
        self.name = name
        self.ip = ip
        self.port = port
        self.tcp_udp = tcp_udp
        self.serve = serve
        self.mapping = mapping
        tables = {}
        for file_range in serve:
            unit = file_range['unit']
            file = file_range['file']
            table = f'{name}:{unit}:{file}'
            end = file_range['end']
            if table not in tables:
                tables[table] = 1
            tables[table] = max(tables[table], end)
        mapping.add_data_table(tables)

    async def start(self):
        """Start the UDP or TCP binding."""
        if self.tcp_udp == 'udp':
            logging.debug(f'UDP to {self.ip}:{self.port}')
            await asyncio.get_running_loop().create_datagram_endpoint(
                lambda: ModbusServerProtocol(self.name, self.mapping),
                local_addr=(self.ip, self.port))
        else:
            logging.debug(f'TCP to {self.ip}:{self.port}')
            await asyncio.get_running_loop().create_server(
                lambda: ModbusServerProtocol(self.name, self.mapping),
                self.ip, self.port)


class ModbusServer:
    """Modbus Server application module."""

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
            self.busclient = BusClient(bus_ip, bus_port,
                                       module='Modbus Server')
        self.mapping = ModbusMaps(tags)
        self.connections: list[ModbusServerConnector] = []
        for rtu in rtus:
            connection = ModbusServerConnector(**rtu, mapping=self.mapping)
            self.connections.append(connection)
        self.mapping.make_map()

    async def start(self):
        """Start the server and return."""
        if self.busclient is not None:
            await self.busclient.start()
        for connection in self.connections:
            await connection.start()
