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


def test_right_files(t0: TagHistory):
    """Check tag_0 and tag_0_10 return different files."""
    t0_files = get_tag_hist_files(Path('tests/test_assets'), 'hist_tag_0')
    t0_times = [x for x in sorted(t0_files.keys())]
    assert t0_times == [0, 15, 26]
    t0_10_files = get_tag_hist_files(Path('tests/test_assets'),
                                     'hist_tag_0_10')
    t0_10_times = [x for x in sorted(t0_10_files.keys())]
    assert t0_10_times == [2]


@pytest.mark.asyncio()
async def test_read_ranges(t0: TagHistory):
    """Basic tests."""
    rd = t0.read_bytes()
    rd_t = []
    rd_v = []
    for i in range(0, len(rd), ITEM_SIZE):
        t, v = unpack_from(t0.packstr, rd, offset=i)
        rd_t.append(t)
        rd_v.append(v)
    assert rd_t == TIMES
    assert rd_v == VALUES
    # Check every range
    for start in range(60):
        for end in range(start, 61):
            if end == 60:
                rd = t0.read_bytes(start, -1)
            else:
                rd = t0.read_bytes(start, end)
            rd_t = []
            rd_v = []
            for i in range(0, len(rd), ITEM_SIZE):
                t, v = unpack_from(t0.packstr, rd, offset=i)
                rd_t.append(t)
                rd_v.append(v)
            assert rd_t == TIMES[start:end]
            assert rd_v == VALUES[start:end]


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


READ_TESTS = [
    ({'__rta_id__': 12345, 'tagname': 'hist_tag_0', 'start_us': 55,
      'end_us': -1},
     {'rta_id': 12345, 'tagid': 2, 'packtype': 1, 'start': (55, 55),
      'end': (59, 59)}),
    ({'__rta_id__': 255, 'tagname': 'hist_tag_0', 'start_us': 55,
      'end_us': 80},
     {'rta_id': 255, 'tagid': 2, 'packtype': 1, 'start': (55, 55),
      'end': (59, 59)}),
    ({'__rta_id__': 303, 'tagname': 'hist_tag_0', 'start_us': 20,
      'end_us': 55},
     {'rta_id': 303, 'tagid': 2, 'packtype': 1, 'start': (20, 10),
      'end': (54, 54)}),
    ({'__rta_id__': 305, 'tagname': 'hist_tag_0', 'start_us': -1,
     'end_us': 30},
     {'rta_id': 305, 'tagid': 2, 'packtype': 1, 'start': (0, 255),
      'end': (29, 19)}),
]


def test_read_rta_cb(t0: TagHistory):
    """Test the RTA request data."""
    history = History(path='tests/test_assets',
                      tag_info={'hist_tag_0': {'type': 'int'}})
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
        rta_id, tagid, packtype = unpack_from('>HHH', results)
        result = {
            'rta_id': rta_id,
            'tagid': tagid,
            'packtype': packtype,
            'dat': []
        }
        for offset in range(6, size, 16):
            result['dat'].append(unpack_from('!Qq', results, offset=offset))
        return result

    history_tag.add_callback(history_cb, 999)  # fake non-local bus
    """Read in middle of range crossing two files."""
    for test, resp in READ_TESTS:
        history.rta_cb(test)
        decoded = decode(results.pop(0))
        assert decoded['rta_id'] == resp['rta_id']
        assert decoded['tagid'] == resp['tagid']  # as set above
        assert decoded['packtype'] == resp['packtype']  # is integer
        assert decoded['dat'][0] == resp['start']
        assert decoded['dat'][-1] == resp['end']
        assert results.pop(0) == b'\x00\x00\x00\x00\x00\x00'
