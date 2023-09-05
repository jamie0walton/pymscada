"""Store and provide history."""
from struct import pack_into, unpack_from, error
from pathlib import Path
import logging
import atexit
from .bus_client import BusClient
from .tag import Tag, TYPES


ITEM_SIZE = 16  # Q + q, Q or d
ITEM_COUNT = 1024
CHUNK_SIZE = ITEM_COUNT * ITEM_SIZE
FILE_CHUNKS = 64


def tag_for_history(tagname: str, tag: dict):
    """Correct tag dictionary in place to be suitable for web client."""
    tag['name'] = tagname
    tag['id'] = None
    if 'desc' not in tag:
        tag['desc'] = tag.name
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
        """Create persistent tag store. Respond to RQS."""
        self.name = tagname
        if type(tagtype) is type:
            self.type = tagtype
        else:
            self.type = TYPES[tagtype]
        if tagtype is int:
            self.type = '!Qq'
        elif tagtype is float:
            self.type = '!Qd'
        else:
            raise TypeError(f'{tagtype} not supported')
        self.path = Path(path)
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

    def read(self, start_us: int = 0, end_us: int = -1):
        """Read in partial store on start-up, or read-in older data."""
        resp_time = []
        resp_values = []
        files_us: dict[int, Path] = {}
        for file in self.path.glob(f'{self.name}_*.dat'):
            i = file.stem.rindex('_') + 1
            files_us[int(file.stem[i:])] = file
        times = [x for x in sorted(files_us.keys())]
        while len(times) > 2:
            if times[0] < start_us and times[1] < start_us:
                times.pop(0)
            else:
                break
        if end_us != -1:
            while times[-1] > end_us:
                times.pop()
        for time_us in times:
            size = files_us[time_us].stat().st_size
            if size % ITEM_SIZE != 0:
                logging.warning(f'{files_us[time_us]} size is incorrect.')
                size -= size % ITEM_SIZE
            with open(files_us[time_us], 'rb') as fh:
                dat = fh.read()
                for i in range(0, size, ITEM_SIZE):
                    vtime_us, value = unpack_from(self.type, dat, offset=i)
                    if end_us != -1 and vtime_us >= end_us:
                        break
                    if vtime_us >= start_us:
                        resp_time.append(vtime_us)
                        resp_values.append(value)
                if end_us != -1 and vtime_us >= end_us:
                    break
        return resp_time, resp_values

    def read_bytes(self, start_us: int = 0, end_us: int = -1):
        """Read in partial store on start-up, or read-in older data."""
        resp: bytes = b''
        files_us: dict[int, Path] = {}
        for file in self.path.glob(f'{self.name}_*.dat'):
            i = file.stem.rindex('_') + 1
            files_us[int(file.stem[i:])] = file
        times = [x for x in sorted(files_us.keys())]
        while len(times) > 2:
            if times[0] < start_us and times[1] < start_us:
                times.pop(0)
            elif end_us != -1 and times[-1] > end_us:
                times.pop()
            else:
                break
        for idx, time_us in enumerate(times):
            start = 0
            end = files_us[time_us].stat().st_size
            if end % ITEM_SIZE != 0:
                logging.warning(f'{files_us[time_us]} size is incorrect.')
                end -= end % ITEM_SIZE
            with open(files_us[time_us], 'rb') as fh:
                dat = fh.read()
                if idx == 0:  # find start
                    for i in range(0, end, ITEM_SIZE):
                        vtime_us, value = unpack_from(self.type, dat, offset=i)
                        if vtime_us >= start_us:
                            start = i
                            break
                if end_us != -1 and idx == len(times) - 1:  # find end
                    for i in range(end - ITEM_SIZE, 0, -ITEM_SIZE):
                        vtime_us, value = unpack_from(self.type, dat, offset=i)
                        if vtime_us < end_us:
                            end = i + ITEM_SIZE
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
            pack_into(self.type, self.chunk, self.chunk_idx,
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


class History():
    """Connect to bus_ip:bus_port, store and provide a value history."""

    def __init__(self, bus_ip: str = '127.0.0.1', bus_port: int = 1324,
                 path: str = 'history', rqs: str = '__history__',
                 tag_info: dict = {}) -> None:
        """
        Connect to bus_ip:bus_port, store and provide a value history.

        History files are binary files named <tagname>_<time_us>.dat. On
        receipt of a request via RQS message, History will send the data
        via __history__.value which you can watch with a tag.add_callback.

        Event loop must be running.
        """
        self.busclient = BusClient(bus_ip, bus_port)
        self.path = path
        self.tags: dict[str, TagHistory] = {}
        for tagname, tag in tag_info.items():
            tag_for_history(tagname, tag)
            if tag['type'] not in [float, int]:
                continue
            self.tags[tagname] = TagHistory(tagname, tag['type'], path,
                                            min=tag['min'], max=tag['max'],
                                            deadband=tag['deadband'])
        self.rqs = Tag(rqs, dict)
        self.rqs.add_rqs(self.rqs_cb)
        self.rqs.value = {'type': 'OK', 'dat': None}

    def rqs_cb(self, tag):
        """Respond to bus requests for data to publish on rqs."""
        pass

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