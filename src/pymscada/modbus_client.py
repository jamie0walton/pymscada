"""Modbus Client."""
import logging
from pymscada.bus_client import BusClient


class ModbusClient:
    """Connect to bus on bus_ip:bus_post, serve on ip:port for modbus."""

    def __init__(self, bus_ip: str = '127.0.0.1', bus_port: int = 1324,
                 ip: str = '127.0.0.1', port: int = 502, protocol: str = 'tcp',
                 rtus: dict = {}, tags: dict = {}, tag_info: dict = {}
                 ) -> None:
        """
        Connect to bus on bus_ip:bus_port, serve on ip:port for webclient.

        Serves the webclient files at /, as a relative path. The webclient uses
        a websocket connection to request and set tag values and subscribe to
        changes.

        Event loop must be running.
        """
        self.busclient = BusClient(bus_ip, bus_port, tag_info)
        self.ip = ip
        self.port = port
        for tagname, tag in tag_info.items():
            pass
            # tag_for_web(tagname, tag)
        self.tag_info = tag_info

    async def start(self):
        """Provide a web server."""
        await self.busclient.start()
