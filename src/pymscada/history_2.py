import atexit
import asyncio
import logging
from pathlib import Path
from struct import pack, unpack_from
import zstandard as zstd
from pymscada.bus_client import BusClient
from pymscada.bus_client_tag import TagTyped, TagInt, TagFloat, TagDict
from pymscada.periodic import Periodic


ITEM_SIZE = 16  # Q + q, Q or d
# None of the following sizes is exact
HOLD = 100
WRITE = 1000
MEM_WRITE = 1100 * ITEM_SIZE  # avoid this many in memory
MEM_HOLD = 100 * ITEM_SIZE  # keep this many in memory
FILE_SIZE = 100000 * ITEM_SIZE  # new file when above this
REPLY_SIZE = 100000 * ITEM_SIZE  # max size for chunks to send back for RTA


class TagData:
    """
    Handles time series data for an individual tag. Includes in memory and on
    file data. Presents an interface to other classes that allows data to be
    seen as if it is all in memory.

    Searches for old format files. Checks timestamps and name for order, if
    inconsistent show error message and exit. If consistent provide a generator
    to yield data to the calling class so that it can stream in the values as
    if being received to generate new format files.

    New file names are:
    <tagname>_<time_us>.dat.zst

    Old file names are:
    <tagname>_<time_us>.dat

    Old file names once new files are written with their data are:
    zzz_old/<tagname>_<time_us>.dat
    """

    def __init__(self, tagname, tagtype, path):
        self.name = tagname
        self.path = Path(path)
        self.packstr = {int: '!Qq', float: '!Qd'}[tagtype]
        self.data = bytearray()
        self.time_us = 0
        atexit.register(self.flush)

    def append(self, time_us, value):
        if time_us > self.time_us:
            self.data.extend(pack(self.packstr, time_us, value))
            self.time_us = time_us
            if len(self.data) < MEM_WRITE:
                return  # most common fast path
            
        
        self.buffer.append([time_us, value])
        if self.searching or self.reading:
            return
        for time_us, value in self.buffer:
            
        
            time_us, value = self.buffer.
        
        



        record = 
        if self.state == SEARCHING:
            
        elif self.state == IDLE:



        for offset in range(0, len(self.chunk), ITEM_SIZE):
            timestamp, _ = unpack_from(self.packstr, self.chunk, offset)
            if timestamp >= time_us:
                del self.chunk[offset:]
                break
        self.chunk.extend(record)

    def raw_chunks(self, chunk_size, start_us=0, end_us=-1):
        files = []
        for file in self.path.glob(f'{self.name}_*.dat.zst'):
            name, _, timestamp = file.name[:-8].rpartition('_')
            if name == self.name and timestamp.isdigit():
                files.append((int(timestamp), file))
        files.sort()
        first = 0
        for index, (timestamp, _) in enumerate(files):
            if timestamp > start_us:
                break
            first = index
        for timestamp, file in files[first:]:
            if end_us != -1 and timestamp >= end_us:
                break
            with file.open('rb') as source:
                with zstd.ZstdDecompressor().stream_reader(source) as reader:
                    data = bytearray()
                    while block := reader.read(chunk_size - len(data)):
                        data.extend(block)
                        if len(data) == chunk_size:
                            yield bytes(data)
                            data.clear()
                    if len(data) % ITEM_SIZE:
                        raise ValueError(f'Incomplete record in {file}')
                    if data:
                        yield bytes(data)
        for offset in range(0, len(self.chunk), chunk_size):
            yield bytes(self.chunk[offset:offset + chunk_size])

    def position(self, data, time_us):
        lower = 0
        upper = len(data) // ITEM_SIZE
        while lower < upper:
            middle = (lower + upper) // 2
            timestamp, = unpack_from('!Q', data, middle * ITEM_SIZE)
            if timestamp < time_us:
                lower = middle + 1
            else:
                upper = middle
        return lower * ITEM_SIZE

    def get_data(self, start_us=0, end_us=-1):
        pass


    def write(self):
        # write self.data out to file keeping MEM_HOLD


    def flush(self):
        # write self.data out to file
        pass


class TagHistory:
    """
    Handle tag specific RTA and updates. Filter by deadband. Hold the TagData
    instance for the tag. If TagData reports old data, process in a way
    identical to that for received data from the bus.
    """


class Tags:
    """Hold tags needed for the operation of HistoryBus as properties"""

    def __init__(self) -> None:
        self.rta = TagDict('__history_2_rta__')
        self.tags: list[TagTyped] = list(vars(self).values())

    async def all_ready(self):
        """return when everything has a value"""
        while True:
            await asyncio.sleep(0.2)
            done = True
            for tag in self.tags:
                if tag.is_none:
                    logging.info(f"{tag.name} value is None")
                    done = False
            if done:
                return


class History:
    """Interface with the BusClient to the BusServer."""

    def __init__(self, bus_ip: str | None = '127.0.0.1'):
        self.busclient = BusClient(bus_ip, module='History')