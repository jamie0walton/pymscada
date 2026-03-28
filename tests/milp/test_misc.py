"""Test misc functions."""
import pytest
import time
from pymscada.milp.misc import interp, as_list, bid_period, bid_time, find_nodes


def test_interp():
    """Confirm interpolation works outside the range."""
    assert interp(5, [1, 10], [100, 200]) == pytest.approx(144.444444444444)
    assert interp(-5, [1, 10], [100, 200]) == pytest.approx(33.3333333333333)
    assert interp(15, [1, 10], [100, 200]) == pytest.approx(255.5555555555555)


def test_as_list():
    """Test list of lists flattening to list."""
    assert as_list(1, 2, 3, 4) == [1, 2, 3, 4]
    assert as_list(1, 2, 'three', 4.0) == [1, 2, 'three', 4.0]
    assert as_list(1, [2, 'three'], 4.0) == [1, 2, 'three', 4.0]
    assert as_list([1], [2, 'three'], [4.0]) == [1, 2, 'three', 4.0]


def test_time_period():
    """Check we get a valid bid period, including awkward DST days."""
    t0 = time.strptime('1 Jan 2018 00:00:00', r'%d %b %Y %H:%M:%S')
    t1 = time.strptime("1 Jan 2019 00:00:00", r'%d %b %Y %H:%M:%S')
    s0 = int(time.mktime(t0))
    s1 = int(time.mktime(t1))
    count = [0 for x in range(0, 51)]
    timed = {
        0: 0,
        600: 0,
        1200: 0
    }
    # test the whole 2018 year
    for s in range(s0, s1, 600):  # 10 minute steps for a year
        p = bid_period(s)
        rtime = bid_time(s, p)
        if s - rtime in timed:
            timed[s - rtime] += 1
        count[p] += 1
    assert timed[0] == 17520
    assert timed[600] == 17520
    assert timed[1200] == 17520
    # 1095 == 3 each day for 365 days, should be for 2..46 as well
    assert count[1] == 1095
    assert count[47] == 1092  # DST short day
    assert count[48] == 1092
    assert count[49] == 3  # DST long day
    assert count[50] == 3

    t2 = time.strptime("5 Apr 2020 01:50:00", r'%d %b %Y %H:%M:%S')
    t3 = time.strptime("5 Apr 2020 03:10:00", r'%d %b %Y %H:%M:%S')
    s2 = int(time.mktime(t2))
    s3 = int(time.mktime(t3))
    assert s3 - s2 == 600 + 3600 + 3600 + 600  # replays the hour on 5 Apr
    assert bid_period(s2) == 4
    assert bid_period(s3) == 9


def test_find_nodes():
    """Check the node searching tool used for TDS, and sub / pub."""
    d = {
        'a': {
            'b': {
                'sub': 'here'
            },
            'sub': 'there'
        },
        'sub': 'and here'
    }
    i = 0
    for r in find_nodes('sub', d):
        i += 1
        assert 'sub' in r
    assert i == 3
