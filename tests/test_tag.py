"""
Check the bus tags.

Note, having a BusClient in another test that has not been properly closed
will cause these tests to fail.
"""
import pytest
import asyncio
from pymscada import Tag


def test_create_tags():
    """Check some very basics."""
    try:
        tag_0 = Tag('tag_0')
        pytest.fail("TypeError type not declared.")
    except TypeError:
        assert True
    tag_0 = Tag('tag_0', str)
    assert tag_0.value is None and tag_0.time_us == 0
    try:
        tag_0.value = None
        pytest.fail("Setting to None not permitted.")
    except TypeError:
        assert True
    tag_1 = Tag('tag_1', float)
    tag_2 = Tag('tag_1')  # returns same object
    assert tag_0.desc == ''
    assert tag_0.type == str
    assert tag_2.type == float
    tag_1.value = 12345.
    assert tag_2.value == 12345.  # tag_2 _is_ tag_1


def test_list_dict_types():
    """Lists and dictionaries."""
    tag_3 = Tag('tag_3', list)
    tag_4 = Tag('tag_4', dict)
    try:
        tag_3.value = 7
        pytest.fail("TypeError type mismatch.")
    except TypeError:
        assert True
    tag_3.value = [1, 2, 3, 4.999]
    try:
        tag_4.value = [3]
        pytest.fail("TypeError type mismatch.")
    except TypeError:
        assert True
    tag_4.value = {'this': 'should work'}


def test_multi():
    """Special case for integer value."""
    tag_10 = Tag('tag_10', int)
    tag_10.multi = ['zero', 'one', 'two', 'three']
    assert tag_10.value is None
    tag_10.value = 2
    assert tag_10.value == 2
    tag_10.value = 10
    assert tag_10.value == 3  # list sets min/max values


def test_bytes_type():
    """Raw type."""
    tag_11 = Tag('tag_11', bytes)
    tag_11.value = b'1234567890'
    assert tag_11.value == b'1234567890'


def test_value_limits():
    """Hi."""
    tag_5 = Tag('tag_5', "float")
    tag_5.value_min = -5
    tag_5.value_max = 5
    tag_5.value = 100
    assert tag_5.value == 5
    tag_5.value = -100
    assert tag_5.value == -5


def test_int_with_float():
    """Hi."""
    tag_6 = Tag('tag_6', int)
    tag_6.value = 1.235
    tag_7 = Tag('tag_7', float)
    tag_7.value = 1
    assert tag_6.value == 1
    assert type(tag_7.value) is float


def test_dict_callback():
    """Dict test with callback."""
    r1 = None

    def dict_cb(dtag):
        nonlocal r1
        r1 = dtag.value['a']

    t1 = {'a': 1}
    t2 = {'a': 3, 'b': 4}
    v1 = Tag('note1', dict)
    v1.value = t1
    assert v1.value['a'] == 1
    v1.add_callback(dict_cb, 1)  # a non-zero bus_id required
    v1.value = t2
    assert r1 is not None
    assert r1 == 3
    """
    CAREFUL with this, normal immutability trap.
    """
    v1.value['a'] = 5
    assert r1 != 5
    v1.value.update(a=12)
    assert r1 != 12
    v1.value = dict(v1.value, a=22)
    assert r1 == 22
    v1.value = {**v1.value, 'a': 55}
    assert r1 == 55


def test_watch_tags():
    """Hi."""
    new_tags = []

    def callback(tag: Tag):
        new_tags.append(tag)

    Tag.set_notify(callback)
    v1 = Tag('n1', str)
    v2 = Tag('n1', str)
    v3 = Tag('n2', str)
    v1.value = 'A'
    v3.value = 'B'
    assert v2.value == 'A'
    assert new_tags == [v2, v3]
    Tag.del_notify()


def test_from_bus():
    """Confirm we can set and see if the bus is the source of the tag value."""
    b1_res = None
    b2_res = None

    def b1_cb(tag: Tag):
        nonlocal b1_res
        b1_res = f'b1 {tag.name} {tag.value} bus{tag.from_bus}'

    def b2_cb(tag: Tag):
        nonlocal b2_res
        b2_res = f'b2 {tag.name} {tag.value} bus{tag.from_bus}'

    t1 = Tag('tag', str)
    t2 = Tag('tag', str)
    t1.add_callback(b1_cb, 1)
    t2.add_callback(b2_cb, 2)

    t1.value = ("val_0", 2)  # from bus 0
    assert b1_res == 'b1 tag val_0 bus0'
    assert b2_res == 'b2 tag val_0 bus0'
    b1_res = None
    b2_res = None
    t1.value = ("val_1", 3, 1)  # from bus 1
    assert b1_res is None
    assert b2_res == 'b2 tag val_1 bus1'
    b1_res = None
    b2_res = None
    t1.value = ("val_2", 4, 2)  # from bus 2
    assert b1_res == 'b1 tag val_2 bus2'
    assert b2_res is None


@pytest.fixture(scope='module')
def event_loop():
    """Override default scope from function to module."""
    policy = asyncio.get_event_loop_policy()
    loop = policy.new_event_loop()
    yield loop
    loop.close()


def test_callbacks():
    """
    Check callbacks.

    v1 updates because v1 is not publishing to the callback
    v2 does not because v2 is publishing to the callback
    """
    v1 = Tag('tag_F', float)
    v1.value = 1.111

    def callback(tag):
        nonlocal v1
        v1.value = v1.value * 3
        tag.value = tag.value * 3

    v2 = Tag('tag_G', float)
    v2.add_callback(callback, 1)
    v2.value = 1.0
    assert v1.value == 3.333
    assert v2.value == 1.0


def test_deadband():
    """Test deadband operation."""
    d1 = Tag('db1', float)
    d1.value = 10.0
    d1.value_min = 0.0
    d1.value_max = 100.0
    d1.deadband = 0.1
    assert d1.value == 10.0
    d1.value = 9.95  # Don't update, within deadband
    assert d1.value == 10.0
    d1.value = 0.05
    assert d1.value == 0.05
    d1.value = 0.0  # Do update, within deadband at limit
    assert d1.value == 0.0


def test_history():
    """Internal tag history."""
    h1 = Tag('h1', float)
    h1.age_us = 1000
    h1.value = 0
    for v in range(1, 100):
        h1.value = v
        if v == 50:
            get_us = h1.time_us
    a_value = h1.get(get_us)
    assert a_value in [50, 51]  # Sometimes time is too fast
    assert len(h1.values) == 100
