"""Check the history tags."""
import pytest
# import asyncio
from struct import unpack_from
from pathlib import Path
import math
from pymscada.history import TagHistory, ITEM_SIZE


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
    t0 = TagHistory('tag_0', int, 'tests/test_assets')
    for time_us, value in zip(TIMES, VALUES):
        t0.append(time_us, value)
        if time_us in [14, 25, 49]:
            t0.flush()
    t0.flush()


@pytest.mark.asyncio()
async def test_read_ranges():
    """Basic tests."""
    # make_test_files()
    t0 = TagHistory('tag_0', int, 'tests/test_assets')
    rd = t0.read()
    assert rd[0] == TIMES
    assert rd[1] == VALUES
    rd = t0.read_bytes()
    rd_t = []
    rd_v = []
    for i in range(0, len(rd), ITEM_SIZE):
        t, v = unpack_from(t0.type, rd, offset=i)
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
        t, v = unpack_from(t0.type, rd, offset=i)
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
        t, v = unpack_from(t0.type, rd, offset=i)
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
        t, v = unpack_from(t0.type, rd, offset=i)
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
