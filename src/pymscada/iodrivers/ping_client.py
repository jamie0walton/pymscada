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


class Ping:
    def __init__(self, addresses, rate = 60, retry=3):
        self.addresses = addresses
        self.rate = rate
        self.retry = retry
        self.periodic = Periodic(self.poll, rate)
        self.ping_id = 0
        self.dns = {}
        self.match = {}
        self.results = {}

    def send_ping(self, dest):
        """Wait for the ping socket process."""
        self.ping_id = (self.ping_id + 1) & 0xffff
        header = struct.pack("!BbHHh", ICMP_REQUEST, 0, 0, self.ping_id, 1)
        data = struct.pack("!d", time.perf_counter()) + (60 * b'\0')
        checksum = checksum_chat(header + data)
        msg = struct.pack("!BbHHh", ICMP_REQUEST, 0, checksum, self.ping_id,
                          1) + data
        self.match[self.ping_id] = dest[0]
        if not dest[0] in self.results:
            self.results[dest[0]] = []
        self.sock.sendto(msg, dest)
        asyncio.get_event_loop().remove_writer(self.sock)

    async def pinger(self):
        """Send pings, one at a time."""
        for address in self.addresses:
            dest = (await asyncio.get_event_loop().getaddrinfo(
                address, None, proto=socket.IPPROTO_ICMP))[0][4]
            self.dns[dest[0]] = address
            asyncio.get_event_loop().add_writer(self.sock, self.send_ping,
                                                dest)

    def ping_response(self):
        try:
            msg = self.sock.recv(1024)
            msgtype, _, _, ping_id, _ = struct.unpack('!BBHHH', msg[20:28])
            if msgtype != ICMP_REPLY:
                return
            latency = time.perf_counter() - struct.unpack('!d', msg[28:36])[0]
            # print(ping_id, latency)
            self.results[self.match[ping_id]].append(latency)
        except socket.timeout:
            pass

    async def handler(self):
        asyncio.get_event_loop().add_reader(self.sock, self.ping_response)
        await asyncio.sleep(9.1)


    async def poll(self):
        """Ping."""
        self.match = {}
        self.results = {}
        result = {}
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_RAW,
                                  socket.IPPROTO_ICMP)
        self.sock.settimeout(3.0)
        handler = asyncio.create_task(self.handler())
        for _i in range(3):
            await self.pinger()
            await asyncio.sleep(1.0)
        await asyncio.gather(handler)
        for k, v in self.results.items():
            if len(v) > 0:
                lv = len(v)
                if lv % 2 == 0:
                    m = sorted(v)[len(v) // 2 - 1]
                else:
                    m = sorted(v)[len(v) // 2]
                result[self.dns[k]] = m
                # print(self.dns[k], m, v)
        print(result)

    async def start(self):
        await self.periodic.start()


class PingClient:
    """Ping client."""

    def __init__(self, bus_ip: str = '127.0.0.1', bus_port: int = 1324,
                 ping: dict = {}, tags: dict = {}) -> None:
        """
        Connect to bus on bus_ip:bus_port, ping a list.

        Event loop must be running.
        """
        self.busclient = None
        if bus_ip is not None:
            self.busclient = BusClient(bus_ip, bus_port)
        self.mapping = PingMaps(tags)
        self.pinger = Ping(self.mapping.var_map.keys(), **ping)

    async def _poll(self):
        """For testing."""
        for connection in self.connections:
            await connection.poll()

    async def start(self):
        """Start bus connection and PLC polling."""
        if self.busclient is not None:
            await self.busclient.start()
        await self.pinger.start()
