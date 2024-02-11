"""Map between modbus table and Tag."""
import logging
from time import time
from pymscada.tag import Tag


# data types for PLCs
DTYPES = {
    'int32': [int, -2147483648, 2147483647],
    'float32': [float, -3.40282346639e+38, 3.40282346639e+38],
    'bool': [int, 0, 1]
}


def tag_split(plc_tag: str):
    separator = plc_tag.find(':')
    arr_start_loc = plc_tag.find('[')
    arr_end_loc = plc_tag.find(']')
    bit_loc = plc_tag.find('.')
    plc = plc_tag[:separator]
    if arr_start_loc == -1 and bit_loc == -1:
        var = plc_tag[separator + 1:]
        elm = None
        bit = None
    elif arr_start_loc == -1:
        var = plc_tag[separator + 1:bit_loc]
        elm = None
        bit = int(plc_tag[bit_loc + 1:])
    elif bit_loc == -1:
        var = plc_tag[separator + 1:arr_start_loc]
        elm = int(plc_tag[arr_start_loc + 1:arr_end_loc])
        bit = None
    else:
        var = plc_tag[separator + 1:arr_start_loc]
        elm = int(plc_tag[arr_start_loc + 1:arr_end_loc])
        bit = int(plc_tag[bit_loc + 1:])
    return plc, var, elm, bit


class LogixMap:
    """Do value updates for each tag."""

    def __init__(self, tagname: str, src_type: str, read_tag: str,
                 write_tag: str):
        """Initialise modbus map and Tag."""
        dtype, dmin, dmax = DTYPES[src_type][0:3]
        self.tag = Tag(tagname, dtype)
        self.map_bus = id(self)
        self.read_plc, self.read_var, self.read_elm, self.read_bit = \
            tag_split(read_tag)
        self.plc_read_tag = read_tag
        self.write_plc, self.write_var, self.write_elm, self.write_bit = \
            tag_split(write_tag)
        self.plc_write_tag = write_tag
        self.callback = None
        if dmin is not None:
            self.tag.value_min = dmin
        if dmax is not None:
            self.tag.value_max = dmax

    def set_callback(self, callback):
        """Add tag callback interface."""
        self.callback = callback
        self.tag.add_callback(self.tag_value_changed, bus_id=self.map_bus)

    def set_tag_value(self, value, time_us):
        """Pass update from IO driver to tag value."""
        if self.read_bit is not None:
            if value & 1 << self.read_bit:
                value = 1
            else:
                value = 0
        if self.tag.value != value:
            self.tag.value = value, time_us, self.map_bus

    def tag_value_changed(self, tag: Tag):
        """Pass update from tag value to IO driver."""
        if self.write_elm is None and self.write_bit is None:
            addr = self.write_var
        elif self.write_elm is None:
            addr = f'{self.write_var}.{self.write_bit}'
        elif self.write_bit is None:
            addr = f'{self.write_var}[{self.write_elm}]'
        else:
            addr = f'{self.write_var}[{self.write_elm}].{self.write_bit}'
        self.callback(addr, tag.value)


class LogixMaps:
    """Link tags with protocol connector."""

    def __init__(self, tags: dict):
        """Collect maps based on a tag dictionary."""
        # use the tagname to access the map.
        self.tag_map: dict[str, LogixMap] = {}
        # use the plc_name then variable name to access a list of maps.
        self.read_var_map: dict[str, dict[str, list[LogixMap]]] = {}
        for tagname, v in tags.items():
            if 'addr' in v:
                read_addr = v['addr']
                write_addr = v['addr']
            else:
                read_addr = v['read']
                write_addr = v['write']
            map = LogixMap(tagname, v['type'], read_addr, write_addr)
            if map.read_plc not in self.read_var_map:
                self.read_var_map[map.read_plc] = {}
            if map.read_var not in self.read_var_map[map.read_plc]:
                # make a list so multiple bits can map to a word
                self.read_var_map[map.read_plc][map.read_var] = []
            self.read_var_map[map.read_plc][map.read_var].append(map)
            self.tag_map[map.tag.name] = map

    def add_write_callback(self, plcname, writeok, callback):
        """Connection advises device links."""
        # Create a set of all possible valid addresses
        write_set = set()
        for w in writeok:
            if '[' in w['type']:
                for i in range(w['start'], w['end'] + 1):
                    write_set.add((w['addr'], i))
            else:
                write_set.add((w['addr'], None))
        # where the mapped tag uses a valid address, add callback to
        # the connection writer
        for map in self.tag_map.values():
            if map.write_plc == plcname and \
                    (map.write_var, map.write_elm) in write_set:
                map.set_callback(callback)

    def polled_data(self, plcname, polls):
        """Pass updates read from the PLC to the tags."""
        time_us = int(time() * 1e6)
        for poll in polls:
            if poll.error is not None:
                logging.error(poll.error)
            arr_start_loc = poll.tag.find('[')
            if arr_start_loc == -1:
                for map in self.read_var_map[plcname][poll.tag]:
                    map.set_tag_value(poll.value, time_us)
            else:
                var = poll.tag[:arr_start_loc]
                elm = int(poll.tag[arr_start_loc + 1: -1])
                for map in self.read_var_map[plcname][var]:
                    elm_offset = map.read_elm - elm
                    if elm_offset > 0 and elm_offset < len(poll.value):
                        map.set_tag_value(poll.value[elm_offset], time_us)
