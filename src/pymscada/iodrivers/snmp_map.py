"""Map between snmp MIB and Tag."""
import logging
from time import time
from pymscada.tag import Tag


# data types for MIBs
DTYPES = {
    'int_roc': [int]
}


class SnmpMap:
    """Do value updates for each tag."""

    def __init__(self, tagname: str, src_type: str, plc_tag: str):
        """initialise MIB map and Tag."""
        dtype = DTYPES[src_type][0]
        self.last_value = None
        self.tag = Tag(tagname, dtype)
        self.map_bus = id(self)
        separator = plc_tag.find(':')
        self.plc = plc_tag[:separator]
        self.var = plc_tag[separator + 1:]

    def set_tag_value(self, value, time_us):
        """Pass update from IO driver to tag value."""
        vtype = type(value).__name__
        if vtype == 'Counter64':
            v = int(value)
            if self.last_value is None:
                self.last_value = v
                return
            d = v - self.last_value
            self.last_value = v
            if d < 0:
                d += 2**64
            if self.tag.value != d:
                self.tag.value = d, time_us, self.map_bus    
        else:
            logging.warning(
                f'SnmpMap: {self.tag.name} {vtype} not implemented')


class SnmpMaps:
    """Link tags with protocol connector."""

    def __init__(self, tags: dict):
        """Collect maps based on a tag dictionary."""
        # use the tagname to access the map.
        self.tag_map: dict[str, SnmpMap] = {}
        # use the plc_name then variable name to access a list of maps.
        self.var_map: dict[str, dict[str, list[SnmpMap]]] = {}
        for tagname, v in tags.items():
            addr = v['read']
            map = SnmpMap(tagname, v['type'], addr)
            if map.plc not in self.var_map:
                self.var_map[map.plc] = {}
            if map.var not in self.var_map[map.plc]:
                # make a list so multiple bits can map to a word
                self.var_map[map.plc][map.var] = []
            self.var_map[map.plc][map.var].append(map)
            self.tag_map[map.tag.name] = map

    def polled_data(self, plcname, polls):
        """Pass updates read from the PLC to the tags."""
        time_us = int(time() * 1e6)
        for poll in polls:
            oid, value = poll
            for map in self.var_map[plcname][str(oid)]:
                map.set_tag_value(value, time_us)
