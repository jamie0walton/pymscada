"""Check the history tags."""
# import asyncio
import math
from pathlib import Path
import pytest
from struct import unpack_from
from pymscada.history import TagHistory, History, ITEM_SIZE
from pymscada.tag import Tag


TIMES = list(range(60))
VALUES = [
    255, 65535, 4_294_967_295, 2**63-1, -2**63,
    0, 0, 0, 0, 0,
    0, 1, 2, 3, 4, 5, 6, 7, 8, 9,
    10, 11, 12, 13, 14, 15, 16, 17, 18, 19,
    20, 21, 22, 23, 24, 25, 26, 27, 28, 29,
    30, 31, 32, 33, 34, 35, 36, 37, 38, 39,
    50, 51, 52, 53, 54, 55, 56, 57, 58, 59,
]


def make_test_files():
    """Make test files in the test_assets folder."""
    for df in Path('tests/test_assets').glob('hist_tag_0_*'):
        df.unlink()
    t0 = TagHistory('hist_tag_0', int, 'tests/test_assets')
    for time_us, value in zip(TIMES, VALUES):
        t0.append(time_us, value)
        if time_us in [14, 25, 49]:
            t0.flush()
    # t0.flush()  # test in memory values too


@pytest.mark.asyncio()
async def test_read_ranges():
    """Basic tests."""
    for df in Path('tests/test_assets').glob('hist_tag_0_*'):
        df.unlink()
    t0 = TagHistory('hist_tag_0', int, 'tests/test_assets')
    for time_us, value in zip(TIMES, VALUES):
        t0.append(time_us, value)
        if time_us in [14, 25, 49]:
            t0.flush()
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


def test_read_rqs_cb():
    """Test the RQS request data."""
    history = History(path='tests/test_assets', tag_info={'hist_tag_0': {
        'desc': 'Test tag',
        'type': 'int'
    }})
    history_tag = Tag('__history__', bytes)
    hist_tag_0 = Tag('hist_tag_0', int)
    history_tag.id = 1  # no bus running in test so force this
    hist_tag_0.id = 2
    assert history_tag.value == b'\x00\x00\x00\x00\x00\x00'
    results = []

    def history_cb(tag: Tag):
        nonlocal results
        results.append(tag.value)

    history_tag.add_callback(history_cb, 999)  # fake non-local bus
    history.rqs_cb({
        '__rqs_id__': 12345,
        'tagname': 'hist_tag_0',
        'start_us': 5,
        'end_us': 30
    })
    decoded = []
    size = len(results[0])
    rqs_id, tagid, packtype = unpack_from('>HHH', results[0])
    assert rqs_id == 12345
    assert tagid == 2  # as set above
    assert packtype == 1  # is integer
    for offset in range(6, size, 16):
        decoded.append(unpack_from('!Qq', results[0], offset=offset))
    assert decoded[0][0] == 5
    assert decoded[21][0] == 26
    assert results[1] == b'\x00\x00\x00\x00\x00\x00'
