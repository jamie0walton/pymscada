"""Check the history tags."""
# import asyncio
import math
from pathlib import Path
import pytest
from struct import unpack_from
from pymscada.history import get_tag_hist_files, TagHistory, History, ITEM_SIZE
from pymscada.tag import Tag


TIMES = list(range(60))
VALUES = [
    255, 65535, 4_294_967_295, 2**63-1, -2**63,  # 0, 1, 2, 3, 4
    0, 0, 0, 0, 0,                               # 5, 6, 7, 8, 9
    0, 1, 2, 3, 4, 5, 6, 7, 8, 9,                # 10-19
    10, 11, 12, 13, 14, 15, 16, 17, 18, 19,      # 20-29
    20, 21, 22, 23, 24, 25, 26, 27, 28, 29,      # 30-39
    30, 31, 32, 33, 34, 35, 36, 37, 38, 39,      # 40-49
    50, 51, 52, 53, 54, 55, 56, 57, 58, 59,      # 50-59
]


@pytest.fixture(scope='session')
def t0():
    """Make test files in the test_assets folder."""
    for df in Path('tests/test_assets').glob('hist_tag_0_*'):
        df.unlink()
    tag_0 = TagHistory('hist_tag_0', int, 'tests/test_assets')
    for time_us, value in zip(TIMES, VALUES):
        tag_0.append(time_us, value)
        if time_us in [14, 25, 49]:
            tag_0.flush()
    Path('tests/test_assets/hist_tag_0_10_2.dat').touch()
    return tag_0


def test_right_files(t0):
    """Check tag_0 and tag_0_10 return different files."""
    t0_files = get_tag_hist_files(Path('tests/test_assets'), 'hist_tag_0')
    t0_times = [x for x in sorted(t0_files.keys())]
    assert t0_times == [0, 15, 26]
    t0_10_files = get_tag_hist_files(Path('tests/test_assets'),
                                     'hist_tag_0_10')
    t0_10_times = [x for x in sorted(t0_10_files.keys())]
    assert t0_10_times == [2]


@pytest.mark.asyncio()
async def test_read_ranges(t0):
    """Basic tests."""
    rd = t0.read()
    assert rd[0] == TIMES
    assert rd[1] == VALUES
    rd = t0.read_bytes()
    rd_t = []
    rd_v = []
    for i in range(0, len(rd), ITEM_SIZE):
        t, v = unpack_from(t0.packstr, rd, offset=i)
        rd_t.append(t)
        rd_v.append(v)
    assert rd_t == TIMES
    assert rd_v == VALUES
    rd = t0.read(1, 20)
    assert rd[0] == TIMES[1:20]
    assert rd[1] == VALUES[1:20]
    rd = t0.read_bytes(1, 20)
    rd_t = []
    rd_v = []
    for i in range(0, len(rd), ITEM_SIZE):
        t, v = unpack_from(t0.packstr, rd, offset=i)
        rd_t.append(t)
        rd_v.append(v)
    assert rd_t == TIMES[1:20]
    assert rd_v == VALUES[1:20]
    rd = t0.read(20, 40)
    assert rd[0] == TIMES[20:40]
    assert rd[1] == VALUES[20:40]
    rd = t0.read_bytes(20, 40)
    rd_t = []
    rd_v = []
    for i in range(0, len(rd), ITEM_SIZE):
        t, v = unpack_from(t0.packstr, rd, offset=i)
        rd_t.append(t)
        rd_v.append(v)
    assert rd_t == TIMES[20:40]
    assert rd_v == VALUES[20:40]
    rd = t0.read(20)
    assert rd[0] == TIMES[20:]
    assert rd[1] == VALUES[20:]
    rd = t0.read_bytes(20)
    rd_t = []
    rd_v = []
    for i in range(0, len(rd), ITEM_SIZE):
        t, v = unpack_from(t0.packstr, rd, offset=i)
        rd_t.append(t)
        rd_v.append(v)
    assert rd_t == TIMES[20:]
    assert rd_v == VALUES[20:]


@pytest.mark.asyncio()
async def test_write_history():
    """Check the file rolls at 1MB and on flush."""
    t1 = TagHistory('tag_1', float, 'tests/test_assets')
    ts = 1000000
    for i in range(65 * 1024):
        if i == 65656:
            t1.flush()
        t1.append(ts + i, math.sin(2 * math.pi * i / 50))
    t1.flush()
    for file, size in [
        ['tests/test_assets/tag_1_1000000.dat', 1048576],
        ['tests/test_assets/tag_1_1065536.dat', 1920],
        ['tests/test_assets/tag_1_1065656.dat', 14464]
    ]:
        p = Path(file)
        assert p.stat().st_size == size
        p.unlink()


@pytest.mark.asyncio()
async def test_deadband_write_history():
    """Check that small changes are filtered with deadband."""
    t1 = TagHistory('tag_1', float, 'tests/test_assets', min=-0.99, max=0.99,
                    deadband=0.5)
    ts = 1000000
    for i in range(65 * 1024):
        if i == 65656:
            t1.flush()
        t1.append(ts + i, math.sin(2 * math.pi * i / 50))
    t1.flush()
    for file, size in [
        ['tests/test_assets/tag_1_1000000.dat', 210096],
        ['tests/test_assets/tag_1_1065656.dat', 2896]
    ]:
        p = Path(file)
        assert p.stat().st_size == size
        p.unlink()


def test_read_rqs_cb(t0):
    """Test the RQS request data."""
    history = History(path='tests/test_assets', tag_info={'hist_tag_0': {
        'desc': 'Test tag',
        'type': 'int'
    }})
    history_tag = Tag('__history__', bytes)
    hist_tag_0 = Tag('hist_tag_0', int)
    for time_us, value in zip(TIMES[50:], VALUES[50:]):
        hist_tag_0.value = value, time_us, 999
    history_tag.id = 1  # no bus running in test so force this
    hist_tag_0.id = 2
    assert history_tag.value == b'\x00\x00\x00\x00\x00\x00'
    results = []

    def history_cb(tag: Tag):
        nonlocal results
        results.append(tag.value)

    def decode(results):
        size = len(results)
        rqs_id, tagid, packtype = unpack_from('>HHH', results)
        result = {
            'rqs_id': rqs_id,
            'tagid': tagid,
            'packtype': packtype,
            'dat': []
        }
        for offset in range(6, size, 16):
            result['dat'].append(unpack_from('!Qq', results, offset=offset))
        return result

    history_tag.add_callback(history_cb, 999)  # fake non-local bus
    """Read in middle of range crossing two files."""
    history.rqs_cb({
        '__rqs_id__': 12345,
        'tagname': 'hist_tag_0',
        'start_us': 55,
        'end_us': -1
    })
    decoded = decode(results.pop(0))
    assert decoded['rqs_id'] == 12345
    assert decoded['tagid'] == 2  # as set above
    assert decoded['packtype'] == 1  # is integer
    assert decoded['dat'][0] == (55, 55)
    assert decoded['dat'][-1] == (59, 59)
    assert results.pop(0) == b'\x00\x00\x00\x00\x00\x00'
    """Read from memory data."""
    history.rqs_cb({
        '__rqs_id__': 255,
        'tagname': 'hist_tag_0',
        'start_us': 55,
        'end_us': 80
    })
    decoded = decode(results.pop(0))
    assert decoded['dat'][0] == (55, 55)
    assert decoded['dat'][-1] == (59, 59)
    assert results.pop(0) == b'\x00\x00\x00\x00\x00\x00'
    """Data that is not available."""
    history.rqs_cb({
        '__rqs_id__': 303,
        'tagname': 'hist_tag_0',
        'start_us': 20,
        'end_us': 55
    })
    decoded = decode(results.pop(0))
    assert decoded['dat'][0] == (20, 10)
    assert decoded['dat'][-1] == (54, 54)
    assert results.pop(0) == b'\x00\x00\x00\x00\x00\x00'
    """Data that is not available."""
    history.rqs_cb({
        '__rqs_id__': 303,
        'tagname': 'hist_tag_0',
        'start_us': -1,
        'end_us': 30
    })
    decoded = decode(results.pop(0))
    assert decoded['dat'][0] == (0, 255)
    assert decoded['dat'][-1] == (29, 19)
    assert results.pop(0) == b'\x00\x00\x00\x00\x00\x00'
