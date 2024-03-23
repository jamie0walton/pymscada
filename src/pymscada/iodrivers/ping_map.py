"""Map between snmp MIB and Tag."""
from time import time
from pymscada.tag import Tag


class PingMap:
    """Do value updates for each tag."""

    def __init__(self, tagname: str, addr: str):
        """Initialise MIB map and Tag."""
        self.last_value = None
        self.tag = Tag(tagname, float)
        self.addr = addr
        self.map_bus = id(self)

    def set_tag_value(self, value, time_us):
        """Pass update from IO driver to tag value."""
        if self.last_value is None:
            self.last_value = value
            return
        if self.last_value != value:
            self.tag.value = value, time_us, self.map_bus


class PingMaps:
    """Link tags with protocol connector."""

    def __init__(self, tags: dict):
        """Collect maps based on a tag dictionary."""
        # use the tagname to access the map.
        self.tag_map: dict[str, PingMap] = {}
        # use the plc_name then variable name to access a list of maps.
        self.var_map: dict[str, PingMap] = {}
        for tagname, v in tags.items():
            addr = v['addr']
            map = PingMap(tagname, addr)
            self.var_map[addr] = map
            self.tag_map[tagname] = map

    def polled_data(self, address, latency):
        """Pass updates read from the PLC to the tags."""
        time_us = int(time() * 1e6)
        self.var_map[address].set_tag_value(latency, time_us)
