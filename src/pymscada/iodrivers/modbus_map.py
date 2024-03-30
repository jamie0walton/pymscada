"""Map between modbus table and Tag."""
import logging
from struct import unpack_from, pack_into, pack
from time import time
from pymscada.tag import Tag


# Modbus
#
# Transaction ID    2 bytes     incrementing
# Protocol          2 bytes     always 0
# Length            2 bytes     number of following bytes
# Unit address      1 byte      PLC address
# Message           N bytes     max size, 253 bytes
#                               max overall 260 bytes
# Function code     1 byte      3 Read registers
# First address     2 bytes     0 == 40001
# Register count    2 bytes     125 is the largest


# data types for PLCs
DTYPES = {
    'int16': [int, -32768, 32767, 1],
    'int32': [int, -2147483648, 2147483647, 2],
    'int64': [int, -2**63, 2**63 - 1, 4],
    'uint16': [int, 0, 65535, 1],
    'uint32': [int, 0, 4294967295, 2],
    'uint64': [int, 0, 2**64 - 1, 4],
    'float32': [float, None, None, 2],
    'float64': [float, None, None, 4]
}


class ModbusMap:
    """Map the data table to a Tag."""

    def __init__(self, tagname: str, src_type: str, addr: str, data: dict,
                 value_chg: dict):
        """Initialise modbus map and Tag."""
        name, unit, file, word = addr.split(':')
        self.data_file = f'{name}:{unit}:{file}'
        self.data = data[self.data_file]
        self.value_chg = value_chg[self.data_file]
        self.src_type = src_type
        dtype, dmin, dmax = DTYPES[src_type][0:3]
        self.tag = Tag(tagname, dtype)
        self.map_bus = id(self)
        if self.value_chg is None:
            self.tag.add_callback(self.tag_value_changed, self.map_bus)
        else:
            self.tag.add_callback(self.tag_value_ext, self.map_bus)
        if dmin is not None:
            self.tag.value_min = dmin
        if dmax is not None:
            self.tag.value_max = dmax
        self.byte = (int(word) - 1) * 2

    def update_tag(self, time_us):
        """Unpack from modbus registers to tag value if different."""
        if self.src_type == 'int16':
            value = unpack_from('>h', self.data, self.byte)[0]
        elif self.src_type == 'uint16':
            value = unpack_from('>H', self.data, self.byte)[0]
        elif self.src_type == 'int32':
            value = unpack_from('>i', self.data, self.byte)[0]
        elif self.src_type == 'uint32':
            value = unpack_from('>I', self.data, self.byte)[0]
        elif self.src_type == 'int64':
            value = unpack_from('>q', self.data, self.byte)[0]
        elif self.src_type == 'uint64':
            value = unpack_from('>Q', self.data, self.byte)[0]
        elif self.src_type == 'float32':
            value = unpack_from('>f', self.data, self.byte)[0]
        elif self.src_type == 'float64':
            value = unpack_from('>d', self.data, self.byte)[0]
        if value != self.tag.value:
            logging.info(f'updating {self.tag.name} from {self.tag.value}'
                         f' to {value}')
            self.tag.value = value, time_us, self.map_bus

    def tag_value_changed(self, tag: Tag):
        """Tag value changed (or not), update the table."""
        logging.info(f'tag_value_changed {tag.name} {tag.value}')
        if self.src_type == 'int16':
            pack_into('>h', self.data, self.byte, tag.value)
        elif self.src_type == 'uint16':
            pack_into('>H', self.data, self.byte, tag.value)
        elif self.src_type == 'int32':
            pack_into('>i', self.data, self.byte, tag.value)
        elif self.src_type == 'uint32':
            pack_into('>I', self.data, self.byte, tag.value)
        elif self.src_type == 'int64':
            pack_into('>q', self.data, self.byte, tag.value)
        elif self.src_type == 'uint64':
            pack_into('>Q', self.data, self.byte, tag.value)
        elif self.src_type == 'float32':
            pack_into('>f', self.data, self.byte, tag.value)
        elif self.src_type == 'float64':
            pack_into('>d', self.data, self.byte, tag.value)

    def tag_value_ext(self, tag: Tag):
        """Call external tag value update to write remote table."""
        logging.info(f'tag_value_changed {tag.name} {tag.value}')
        if self.src_type == 'int16':
            self.value_chg(self.data_file, self.byte, pack('>h', tag.value))
        elif self.src_type == 'uint16':
            self.value_chg(self.data_file, self.byte, pack('>H', tag.value))
        elif self.src_type == 'int32':
            self.value_chg(self.data_file, self.byte, pack('>i', tag.value))
        elif self.src_type == 'uint32':
            self.value_chg(self.data_file, self.byte, pack('>I', tag.value))
        elif self.src_type == 'int64':
            self.value_chg(self.data_file, self.byte, pack('>q', tag.value))
        elif self.src_type == 'uint64':
            self.value_chg(self.data_file, self.byte, pack('>Q', tag.value))
        elif self.src_type == 'float32':
            self.value_chg(self.data_file, self.byte, pack('>f', tag.value))
        elif self.src_type == 'float64':
            self.value_chg(self.data_file, self.byte, pack('>d', tag.value))


class ModbusMaps():
    """Shared modbus mapping."""

    def __init__(self, tags):
        """Singular please."""
        self.tags = tags
        self.data = {}
        self.value_chg = {}
        self.maps = {}

    def add_data_table(self, tables, value_chg=None):
        """Add a bytes data table."""
        for table in tables:
            self.data[table] = bytearray(2 * (tables[table] - 1))
            self.value_chg[table] = value_chg

    def make_map(self):
        """Make the maps."""
        for tagname, v in self.tags.items():
            dtype = v['type']
            try:
                addr = v['read']
            except KeyError:
                addr = v['addr']
            map = ModbusMap(tagname, dtype, addr, self.data, self.value_chg)
            size = DTYPES[dtype][3]
            name, unit, file, word = addr.split(':')
            for i in range(0, size):
                addr = f'{name}:{unit}:{file}:{int(word) + i}'
                self.maps[addr] = map

    def get_data(self, name: str, unit: int, file: str, pdu_start: int,
                 pdu_count: int) -> bytearray:
        """Update the values and then the tags."""
        start = pdu_start * 2
        end = start + pdu_count * 2
        data_file = f'{name}:{unit}:{file}'
        logging.info(f'read {data_file} {start}-{end}')
        return self.data[data_file][start:end]

    def set_data(self, name: str, unit: int, file: str, pdu_start: int,
                 pdu_count: int, data: bytearray):
        """Set data, start and end in byte count."""
        time_us = int(time() * 1e6)
        start = pdu_start * 2
        end = start + pdu_count * 2
        data_file = f'{name}:{unit}:{file}'
        self.data[data_file][start:end] = data
        maps: set[ModbusMap] = set()
        for word_count in range(1, pdu_count + 1):
            word = word_count + pdu_start
            try:
                maps.add(self.maps[f'{name}:{unit}:{file}:{word}'])
            except KeyError:
                pass
        logging.debug(f'set_data {name} {unit} {file} {start} {end}')
        for map in maps:
            map.update_tag(time_us)
        pass
