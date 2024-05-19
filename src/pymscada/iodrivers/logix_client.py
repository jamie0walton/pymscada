"""Read and write to Logix PLC processor."""
import logging
from pycomm3 import LogixDriver
from pymscada.bus_client import BusClient
from pymscada.periodic import Periodic
from pymscada.iodrivers.logix_map import LogixMaps


class LogixClientConnector:
    """Manage interface to device."""

    def __init__(self, name: str, ip: str, rate: float, poll: list,
                 mapping: LogixMaps):
        """Set up polling client."""
        self.plc_name = name
        self.ip = ip
        self.read_tags = []
        for r in poll:
            tag = r['addr']
            if r['type'].endswith('[]'):
                count = r['end'] - r['start'] + 1
                tag = f"{r['addr']}[{r['start']}]{{{count}}}"
            self.read_tags.append(tag)
        self.mapping = mapping
        self.mapping.add_write_callback(name, self.write_tag_update)
        self.periodic = Periodic(self.poll, rate)
        self.plc = LogixDriver(ip)

    def write_tag_update(self, addr: str, value):  # : int|float
        """Write out any tag updates."""
        if not self.plc.connected and not self.plc.open():
            logging.warning(f'write failed {self.plc_name} {addr} to {value}')
            return
        logging.info(f'writing {addr} {value}')
        result = self.plc.write((addr, value))
        logging.info(result)

    async def poll(self):
        """Poll data, reopen connection if dead."""
        if not self.plc.connected and not self.plc.open():
            return
        # polled_tags = None
        polled_tags = self.plc.read(*self.read_tags)
        self.mapping.polled_data(self.plc_name, polled_tags)

    async def start(self):
        """Start polling."""
        await self.periodic.start()


class LogixClient:
    """Manage interface between bus and individual devices."""

    def __init__(self, bus_ip: str = '127.0.0.1', bus_port: int = 1324,
                 rtus: dict = {}, tags: dict = {}) -> None:
        """
        Connect to bus on bus_ip:bus_port, connect to Logix PLCs.

        Event loop must be running.
        """
        self.busclient = None
        if bus_ip is not None:
            self.busclient = BusClient(bus_ip, bus_port, module='Logix Client')
        self.mapping = LogixMaps(tags)
        self.connections: list[LogixClientConnector] = []
        for rtu in rtus:
            connection = LogixClientConnector(**rtu, mapping=self.mapping)
            self.connections.append(connection)

    async def _poll(self):
        """For testing."""
        for connection in self.connections:
            await connection.poll()

    async def start(self):
        """Start bus connection and PLC polling."""
        if self.busclient is not None:
            await self.busclient.start()
        for connection in self.connections:
            await connection.start()
