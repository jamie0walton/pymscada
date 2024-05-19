"""Network monitoring / scanning."""
import asyncio
import logging
import socket
import struct
import time
from pymscada.bus_client import BusClient
from pymscada.periodic import Periodic
from pymscada.iodrivers.ping_map import PingMaps


ICMP_REQUEST = 8
ICMP_REPLY = 0
RATE = 60


def checksum_chat(data):
    """Calculate ICMP Checksum."""
    if len(data) & 1:  # If the packet length is odd
        data += b'\0'
    res = 0
    # Process two bytes at a time
    for i in range(0, len(data), 2):
        res += (data[i] << 8) + data[i + 1]
    res = (res >> 16) + (res & 0xffff)
    res += res >> 16
    return (~res) & 0xffff  # Return ones' complement of the result


class PingClientConnector:
    """Ping a list of addresses."""

    def __init__(self, mapping: PingMaps):
        """Accept list of addresses, ip or name."""
        self.mapping = mapping
        self.dns = {}
        self.addr_info = {}
        self.socket = None
        self.ping_id = 0
        self.ping_dict = {}

    async def poll(self):
        """Do pings."""
        self.reply_dict = {}
        if self.socket is None:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_RAW,
                                        socket.IPPROTO_ICMP)
            asyncio.get_event_loop().add_reader(self.socket,
                                                self.read_response)
        for ping_id, address in list(self.ping_dict.items()):
            logging.info(f'failed {self.dns[address]} {ping_id}')
            self.mapping.polled_data(self.dns[address], float('NAN'))
            del self.ping_dict[ping_id]
        self.send_ping()

    def send_ping(self):
        """Build and send ping messages."""
        for address in self.dns.keys():
            self.ping_id = (self.ping_id + 1) & 0xffff
            self.ping_dict[self.ping_id] = address
            logging.info(f'ping {address} id {self.ping_id}')
            header = struct.pack("!BbHHh", ICMP_REQUEST, 0, 0, self.ping_id, 1)
            data = struct.pack("!d", time.perf_counter()) + (60 * b'\0')
            checksum = checksum_chat(header + data)
            packet = struct.pack("!BbHHh", ICMP_REQUEST, 0, checksum,
                                 self.ping_id, 1) + data
            self.socket.sendto(packet, (address, 0))

    def read_response(self):
        """Match ping response."""
        data, address = self.socket.recvfrom(1024)
        msgtype, _, _, ping_id, _ = struct.unpack('!BBHHH', data[20:28])
        if msgtype != ICMP_REPLY:
            return
        if ping_id in self.ping_dict:
            latency = 1000 * (time.perf_counter() -
                              struct.unpack('!d', data[28:36])[0])
            name = self.dns[address[0]]
            logging.info(f'success {name} {ping_id} {latency}ms')
            self.mapping.polled_data(name, latency)
            del self.ping_dict[ping_id]

    async def start(self):
        """Start pinging."""
        loop = asyncio.get_event_loop()
        for address in self.mapping.var_map.keys():
            info = await loop.getaddrinfo(address, None, family=socket.AF_INET,
                                          type=socket.SOCK_STREAM)
            ip = info[0][4][0]
            self.dns[ip] = address
        self.periodic = Periodic(self.poll, RATE)
        await self.periodic.start()


class PingClient:
    """Ping client."""

    def __init__(self, bus_ip: str = '127.0.0.1', bus_port: int = 1324,
                 tags: dict = {}) -> None:
        """
        Connect to bus on bus_ip:bus_port, ping a list.

        Event loop must be running.
        """
        self.busclient = None
        if bus_ip is not None:
            self.busclient = BusClient(bus_ip, bus_port, module='Ping Client')
        self.mapping = PingMaps(tags)
        self.pinger = PingClientConnector(mapping=self.mapping)

    async def _poll(self):
        """For testing."""
        for connection in self.connections:
            await connection.poll()

    async def start(self):
        """Start bus connection and PLC polling."""
        if self.busclient is not None:
            await self.busclient.start()
        await self.pinger.start()
