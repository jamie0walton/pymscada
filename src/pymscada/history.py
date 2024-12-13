"""Store and provide history.

History File Structure
---------------------
History files are binary files stored as <tagname>_<time_us>.dat where time_us
is the microsecond timestamp of the first entry in that file.

Each file contains a series of fixed-size records (16 bytes each):
- For integer tags: 8 bytes timestamp (uint64) + 8 bytes value (int64)
- For float tags: 8 bytes timestamp (uint64) + 8 bytes value (double)

Files are organized in chunks:
- Each chunk is 1024 records (16KB)
- Each file contains up to 64 chunks (1MB)
- New files are created when:
  1. Current file reaches max size (64 chunks)
  2. Manual flush() is called
  3. Application shutdown

Timestamps are stored as microseconds since epoch in network byte order (big-endian).
Values are also stored in network byte order.
"""
import atexit
import logging
from pathlib import Path
from struct import pack, pack_into, unpack_from, error
import time
from typing import TypedDict, Optional
from pymscada.bus_client import BusClient
from pymscada.tag import Tag, TagInfo, TYPES


ITEM_SIZE = 16  # Q + q, Q or d
ITEM_COUNT = 1024
CHUNK_SIZE = ITEM_COUNT * ITEM_SIZE
FILE_CHUNKS = 64


class Request(TypedDict, total=False):
    """Type definition for request dictionary."""
    tagname: str 
    start_ms: Optional[int]  # Allow web client to use native ms
    start_us: Optional[int]  # Native for pymscada server
    end_ms: Optional[int]
    end_us: Optional[int]
    __rta_id__: Optional[int]  # Empty for a change that must be broadcast


def tag_for_history(tagname: str, tag: dict):
    """Correct tag dictionary in place to be suitable for web client."""
    tag['name'] = tagname
    tag['id'] = None
    if 'desc' not in tag:
        tag['desc'] = tag['name']
    if 'multi' in tag:
        tag['type'] = int
    else:
        if 'type' not in tag:
            tag['type'] = float
        else:
            if tag['type'] not in TYPES:
                tag['type'] = str
            else:
                tag['type'] = TYPES[tag['type']]
    if 'min' not in tag:
        tag['min'] = None
    if 'max' not in tag:
        tag['max'] = None
    if 'deadband' not in tag:
        tag['deadband'] = None


def get_tag_hist_files(path: Path, tagname: str) -> dict[int, Path]:
    """Parse path for history files matching tagname."""
    files_us = {}
    for file in path.glob(f'{tagname}_*.dat'):
        parts = file.stem.split('_')
        parts_tag = '_'.join(parts[:-1])
        if parts_tag != tagname or not parts[-1].isdigit():
            continue
        files_us[int(parts[-1])] = file
    return files_us


class TagHistory():
    """Efficiently store and serve history for a given tagname."""

    _tags: dict[str, 'TagHistory'] = {}

    def __new__(cls, tagname: str, tagtype, path: str, **kwds):
        """Return existing taghistory if defined."""
        if tagname not in cls._tags:
            tag = super().__new__(cls)
            tag.__init__(tagname, tagtype, path, **kwds)
            cls._tags[tagname] = tag
        return cls._tags[tagname]

    def __init__(self, tagname: str, tagtype, path: str,
                 min=None, max=None, deadband=None):
        """Create persistent tag store. Respond to RTA."""
        self.name = tagname
        if type(tagtype) is type:
            self.type = tagtype
        else:
            self.type = TYPES[tagtype]
        if tagtype is int:
            self.packstr = '!Qq'
        elif tagtype is float:
            self.packstr = '!Qd'
        else:
            raise TypeError(f'{tagtype} not supported')
        self.path = Path(path)
        if not self.path.exists():
            raise FileNotFoundError(f'{self.path.absolute()} not found')
        if min is None:
            self.min = None
        else:
            self.min = tagtype(min)
        if max is None:
            self.max = None
        else:
            self.max = tagtype(max)
        if deadband is None:
            self.deadband = None
        else:
            self.deadband = tagtype(deadband)
        self.value = None
        self.files = {}
        self.chunk: bytearray = bytearray(CHUNK_SIZE)
        self.chunk_idx: int = 0
        self.chunks: int = 0
        self.file: Path = None

    def read_bytes(self, start_us: int = 0, end_us: int = -1):
        """Read in partial store on start-up, or read-in older data."""
        resp: bytes = b''
        # find the chunks that cover the time span requested
        srcs = get_tag_hist_files(self.path, self.name)
        if self.chunk_idx > 0:
            time_us, _ = unpack_from(self.packstr, self.chunk)
            srcs[time_us] = None
        times_us = [x for x in sorted(srcs.keys())]
        while len(times_us) > 1:
            if times_us[1] <= start_us:
                times_us.pop(0)
            else:
                break
        if end_us != -1:
            while len(times_us) > 1:
                if times_us[-1] > end_us:
                    times_us.pop()
                else:
                    break
        # collect the chunks into a single response
        for time_us in times_us:
            if srcs[time_us] is None:
                dat = self.chunk
                end = self.chunk_idx
            else:
                with open(srcs[time_us], 'rb') as fh:
                    dat = fh.read()
                    end = len(dat)
            for start in range(0, end, ITEM_SIZE):
                first_us, _ = unpack_from(self.packstr, dat, offset=start)
                if first_us >= start_us:
                    break
            for end in range(end - ITEM_SIZE, start - ITEM_SIZE, -ITEM_SIZE):
                last_us, _ = unpack_from(self.packstr, dat,
                                         offset=end)
                if last_us < end_us or end_us == -1:
                    end += ITEM_SIZE
                    break
            resp += dat[start:end]
        return resp

    def flush(self):
        """Flush to file, resets chunk pointer to zero."""
        if self.chunk_idx == 0:
            return
        with open(self.file, 'a+b') as fh:
            fh.write(self.chunk[:self.chunk_idx])
        self.chunk_idx = 0
        self.chunks = 0

    def append(self, time_us: int, value):
        """Append a timestamp(us) and value."""
        deadband = self.deadband
        if self.min is not None and value <= self.min:
            value = self.min
            deadband = 0  # sitting at 0 is better than 0 + deadband
        elif self.max is not None and value >= self.max:
            value = self.max
            deadband = 0  # same for sitting at 100%
        if deadband is not None and self.value is not None and abs(
                value - self.value) < deadband:
            return
        self.value = value
        try:
            pack_into(self.packstr, self.chunk, self.chunk_idx,
                      time_us, value)
            self.chunk_idx += ITEM_SIZE
        except error:
            raise SystemExit(f'pack_into failed {self.name} {value}')
        if self.chunk_idx == CHUNK_SIZE:
            with open(self.file, 'a+b') as fh:
                fh.write(self.chunk)
            # don't bother filling chunk with zeros, just take care.
            self.chunk_idx = 0
            self.chunks += 1
            if self.chunks == FILE_CHUNKS:
                self.chunks = 0
        if self.chunks == 0 and self.chunk_idx == ITEM_SIZE:
            self.file = self.path.joinpath(f'{self.name}_{time_us}.dat')

    def callback(self, tag: Tag):
        """Append directly from Tag."""
        self.append(tag.time_us, tag.value)


class History():
    """Connect to bus_ip:bus_port, store and provide a value history."""

    def __init__(self, bus_ip: str = '127.0.0.1', bus_port: int = 1324,
                 path: str = 'history', tag_info: TagInfo = {},
                 rta_tag: str = '__history__') -> None:
        """
        Connect to bus_ip:bus_port, store and provide a value history.

        History files are binary files named <tagname>_<time_us>.dat. On
        receipt of a request via RTA message, History will send the data
        via rta_tag.value which you can watch with a tag.add_callback.

        Event loop must be running.
        """
        self.busclient = BusClient(bus_ip, bus_port, module='History')
        self.path = path
        self.tags: dict[str, Tag] = {}
        self.hist_tags: dict[str, TagHistory] = {}
        for tagname, tag in tag_info.items():
            tag_for_history(tagname, tag)
            if tag['type'] not in [float, int]:
                continue
            self.hist_tags[tagname] = TagHistory(
                tagname, tag['type'], path, min=tag['min'], max=tag['max'],
                deadband=tag['deadband'])
            self.tags[tagname] = Tag(tagname, tag['type'])
            self.tags[tagname].add_callback(self.hist_tags[tagname].callback)
        self.rta = Tag(rta_tag, bytes)
        self.rta.value = b'\x00\x00\x00\x00\x00\x00'
        self.busclient.add_callback_rta(rta_tag, self.rta_cb)

    def rta_cb(self, request: Request):
        """Respond to bus requests for data to publish on rta."""
        if 'start_ms' in request:
            request['start_us'] = request['start_ms'] * 1000
            request['end_us'] = request['end_ms'] * 1000
        rta_id = 0
        if '__rta_id__' in request:
            rta_id = request['__rta_id__']
        tagname = request['tagname']
        start_time = time.asctime(time.localtime(
            request['start_us'] / 1000000))
        end_time = time.asctime(time.localtime(
            request['end_us'] / 1000000))
        logging.info(f"RTA {tagname} {start_time} {end_time}")
        try:
            data = self.hist_tags[request['tagname']].read_bytes(
                request['start_us'], request['end_us'])
            tagid = self.tags[request['tagname']].id
            tagtype = self.tags[request['tagname']].type
            packtype = 0
            if tagtype == int:
                packtype = 1
            elif tagtype == float:
                packtype = 2
            self.rta.value = pack('>HHH', rta_id, tagid, packtype) + data
            logging.info(f'sent {len(data)} bytes for {request["tagname"]}')
            self.rta.value = b'\x00\x00\x00\x00\x00\x00'
        except Exception as e:
            logging.error(f'history rta_cb {e}')

    async def start(self):
        """Async startup."""
        await self.busclient.start()


@atexit.register
def flush_all_tags():
    """Try to save all in memory history on shutdown."""
    try:
        for tag in TagHistory._tags.values():
            tag.flush()
    except Exception:
        logging.error(f'could not flush {tag.name}')
