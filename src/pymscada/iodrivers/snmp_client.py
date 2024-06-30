"""Poll SNMP OIDs from devices."""
import logging
from pymscada.bus_client import BusClient
from pymscada.periodic import Periodic
from pymscada.iodrivers.snmp_map import SnmpMaps
try:
    import pysnmp.hlapi.asyncio as snmp
except ModuleNotFoundError:
    logging.error('snmp_client not available.')


class SnmpClientConnector:
    """Poll snmp devices, write and traps are not implemented."""

    def __init__(self, name: str, ip: str, rate: float, poll: list,
                 community: str, mapping: SnmpMaps):
        """Set up polling client."""
        self.snmp_name = name
        self.ip = ip
        self.community = community
        self.read_oids = [snmp.ObjectType(snmp.ObjectIdentity(x))
                          for x in poll]
        self.mapping = mapping
        self.periodic = Periodic(self.poll, rate)
        self.snmp_engine = snmp.SnmpEngine()

    async def poll(self):
        """Poll data."""
        r = await snmp.getCmd(
            self.snmp_engine,
            snmp.CommunityData(self.community),
            snmp.UdpTransportTarget((self.ip, 161)),
            snmp.ContextData(),
            *self.read_oids
        )
        errorIndication, errorStatus, errorIndex, varBinds = r
        if errorIndication:
            logging.error(errorIndication)
        elif errorStatus:
            logging.error('%s at %s' % (
                errorStatus.prettyPrint(),
                errorIndex and varBinds[int(errorIndex) - 1][0] or '?'))
        else:
            self.mapping.polled_data(self.snmp_name, varBinds)

    async def start(self):
        """Start polling."""
        await self.periodic.start()


class SnmpClient:
    """SNMP client."""

    def __init__(self, bus_ip: str = '127.0.0.1', bus_port: int = 1324,
                 rtus: dict = {}, tags: dict = {}) -> None:
        """
        Connect to bus on bus_ip:bus_port, connect to snmp devices.

        Event loop must be running.
        """
        self.busclient = None
        if bus_ip is not None:
            self.busclient = BusClient(bus_ip, bus_port, module='SNMP Client')
        self.mapping = SnmpMaps(tags)
        self.connections: list[SnmpClientConnector] = []
        for rtu in rtus:
            connection = SnmpClientConnector(**rtu, mapping=self.mapping)
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
