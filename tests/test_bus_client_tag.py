"""
Check the bus client tags.

Note, having a BusClient in another test that has not been properly closed
will cause these tests to fail.
"""
import pytest
import struct
import time
from pymscada.bus_client import BusClient
from pymscada.bus_client_tag import TagTyped, TagInt, TagFloat, TagStr, \
                                    TagBytes, TagList, TagDict
import pymscada.protocol_constants as pc


@pytest.fixture(scope='function')
def bus_client():
    """Create BusClient and set callback, but never start it."""
    client = BusClient(None, None)
    yield client
    TagTyped.del_bus_callback()


def test_missing_bus(bus_client):
    """Check that a missing bus raises an error."""
    TagTyped.del_bus_callback()  # required when other tests set the callback.
    try:
        tag_int = TagInt('failme')
        pytest.fail("SystemExit should be raised with not bus client.")
    except SystemExit:
        assert True


def test_callback_errors(bus_client):
    """Check that recursion raises an error and callback exceptions are raised."""
    tag_int = TagInt('tag_recursive')
    tag_int.value = 10

    def recursive_callback(tag):
        try:
            tag.value = 20
            pytest.fail("SystemError should be raised for recursive change.")
        except SystemError:
            assert True

    tag_int.add_callback(recursive_callback, 1)
    tag_int.value = 15
    # recursive_callback runs before value assignment of 15 finishes
    
    tag_float = TagFloat('tag_callback_error')
    tag_float.value = 1.0
    
    def error_callback(tag):
        raise RuntimeError('callback error')
    
    tag_float.add_callback(error_callback, 1)
    try:
        tag_float.set_value(2.0, int(time.time() * 1e6), 0)
        pytest.fail("SystemError should be raised for callback exception.")
    except SystemError as e:
        assert 'publish' in str(e)
    
    tag_int_id = TagInt('tag_id_recursive')
    tag_int_id.id = 10
    
    def id_callback(tag):
        try:
            tag.id = 20
            pytest.fail("SystemError should be raised for recursive id change.")
        except SystemError:
            assert True
    
    tag_int_id.add_callback_id(id_callback)
    tag_int_id.id = 15


def test_create_tags(bus_client):
    """Check creation for all types, singleton behavior, and None handling."""
    # Test that tags can be created for all types
    tag_int = TagInt('tag_int_0')
    tag_float = TagFloat('tag_float_0')
    tag_str = TagStr('tag_str_0')
    tag_bytes = TagBytes('tag_bytes_0')
    tag_list = TagList('tag_list_0')
    tag_dict = TagDict('tag_dict_0')
    
    # Test that accessing value before initialization raises SystemExit
    try:
        _ = tag_int.value
        pytest.fail("SystemExit should be raised when value is None.")
    except SystemExit:
        assert True
    
    # Test is_none property
    assert tag_int.is_none is True
    assert tag_float.is_none is True
    assert tag_str.is_none is True
    
    # Test singleton behavior - same name returns same object
    tag_int_1 = TagInt('tag_int_0')
    assert tag_int is tag_int_1
    
    # Test that different types with same name raises SystemExit
    try:
        TagFloat('tag_int_0')
        pytest.fail("SystemExit should be raised for type conflict.")
    except SystemExit:
        assert True
    
    # Test basic properties
    assert tag_int.desc == ''
    assert tag_int.time_us == 0
    
    # Test that setting value initializes it
    tag_int.set_value(42, int(time.time() * 1e6), 0)
    assert tag_int.value == 42
    assert tag_int.is_none is False


def test_deadband(bus_client):
    """Test deadband operation for int and float."""
    # Test float deadband
    tag_float = TagFloat('tag_float_deadband')
    tag_float.set_value(8.0, int(time.time() * 1e6), 0)
    tag_float.value_min = 0.0
    assert tag_float.value_min == 0.0
    tag_float.value_max = 10.0
    assert tag_float.value_max == 10.0
    tag_float.deadband = 2.5
    assert tag_float.deadband == 2.5
    assert tag_float.value == 8.0
    tag_float.value = 7.0
    assert tag_float.value == 8.0
    tag_float.value = 10.1
    assert tag_float.value == 10.0
    tag_float.value = 0.9
    assert tag_float.value == 0.9
    tag_float.value = -0.1
    assert tag_float.value == 0.0
    
    # Test int deadband
    tag_int = TagInt('tag_int_deadband')
    tag_int.set_value(8, int(time.time() * 1e6), 0)
    tag_int.value_min = 0
    assert tag_int.value_min == 0
    tag_int.value_max = 10
    assert tag_int.value_max == 10
    tag_int.deadband = 4
    assert tag_int.deadband == 4
    assert tag_int.value == 8
    tag_int.value = 7
    assert tag_int.value == 8
    tag_int.value = 11
    assert tag_int.value == 10
    tag_int.value = 1
    assert tag_int.value == 1
    tag_int.value = -1
    assert tag_int.value == 0


def test_history(bus_client):
    """Test history for int and float."""
    time_us = int(time.time() * 1e6) # ensure timestamps change with offset
    # Test float history
    tag_float = TagFloat('tag_float_history')
    assert tag_float.age_us is None
    tag_float.set_value(0, time_us, 0)
    assert tag_float.get(time_us) == 0.0  # default to value when no history
    tag_float.age_us = 1000
    assert tag_float.age_us == 1000
    get_us = 0
    for v in range(1, 100):
        tag_float.set_value(float(v), time_us + v, 0)
        if v == 50:
            get_us = tag_float.time_us
    a_value = tag_float.get(get_us)
    assert a_value == 50.0  # get back the right value for the time
    assert len(tag_float.values) == 100  # nothing is pruned
    tag_float.set_value(200.0, time_us + 1050, 0)
    assert len(tag_float.values) == 51  # half are pruned
    tag_float.set_value(300.0, time_us + 2051, 0)  # was 1151
    assert len(tag_float.values) == 1  # all is pruned
    assert tag_float.get(time_us - 1) == tag_float.values[0]
    
    # Test int history
    tag_int = TagInt('tag_int_history')
    assert tag_int.age_us is None
    tag_int.set_value(0, time_us, 0)
    assert tag_int.get(time_us) == 0
    tag_int.age_us = 1000
    assert tag_int.age_us == 1000
    get_us = 0
    for v in range(1, 100):
        tag_int.set_value(v, time_us + v, 0)
        if v == 50:
            get_us = tag_int.time_us
    a_value = tag_int.get(get_us)
    assert a_value == 50.0
    assert len(tag_int.values) == 100
    tag_int.set_value(200, time_us + 1050, 0)
    assert len(tag_int.values) == 51
    tag_int.set_value(300, time_us + 2051, 0)
    assert len(tag_int.values) == 1
    assert tag_int.get(time_us - 1) == tag_int.values[0]


def test_callbacks(bus_client):
    """Test callbacks for all types."""
    # Test float callback
    time_us = int(time.time() * 1e6)
    tag_float_1 = TagFloat('tag_float_cb1')
    tag_float_1.set_value(1.111, time_us, 0)
    
    result = None
    
    def callback(tag):
        nonlocal result
        result = tag.value * 2
        if tag.value == 123.0:
            raise ValueError('for testing')
    
    tag_float_2 = TagFloat('tag_float_cb2')
    tag_float_2.add_callback(callback, 1)
    tag_float_2.set_value(1.0, time_us + 1, None)
    assert result == 2.0
    try:
        tag_float_2.set_value(123.0, time_us + 2, 1)
        pytest.fail('should raise error')
    except:
        assert True
    
    # Test int callback
    tag_int = TagInt('tag_int_cb')
    result_int = None
    
    def callback_int(tag):
        nonlocal result_int
        result_int = tag.value * 3
    
    tag_int.add_callback(callback_int, 1)
    tag_int.set_value(5, int(time.time() * 1e6), 0)
    assert result_int == 15
    
    # Test str callback
    tag_str = TagStr('tag_str_cb')
    result_str = None
    
    def callback_str(tag):
        nonlocal result_str
        result_str = tag.value.upper()
    
    tag_str.add_callback(callback_str, 1)
    tag_str.set_value('hello', int(time.time() * 1e6), 0)
    assert result_str == 'HELLO'


def test_from_bus(bus_client):
    """Test bus_id filtering for all types."""
    b1_res = None
    b2_res = None
    
    def b1_cb(tag):
        nonlocal b1_res
        b1_res = f'b1 {tag.name} {tag.value} bus{tag.from_bus}'
    
    def b2_cb(tag):
        nonlocal b2_res
        b2_res = f'b2 {tag.name} {tag.value} bus{tag.from_bus}'
    
    # Test with str
    t1 = TagStr('tag_bus_str')
    t2 = TagStr('tag_bus_str')
    t1.add_callback(b1_cb, 1)
    t2.add_callback(b2_cb, 2)
    
    t1.set_value("val_0", int(time.time() * 1e6), 0)  # from bus 0
    assert b1_res == 'b1 tag_bus_str val_0 bus0'
    assert b2_res == 'b2 tag_bus_str val_0 bus0'
    b1_res = None
    b2_res = None
    
    t1.set_value("val_1", int(time.time() * 1e6), 1)  # from bus 1
    assert b1_res is None
    assert b2_res == 'b2 tag_bus_str val_1 bus1'
    b1_res = None
    b2_res = None
    
    t1.set_value("val_2", int(time.time() * 1e6), 2)  # from bus 2
    assert b1_res == 'b1 tag_bus_str val_2 bus2'
    assert b2_res is None
    
    # Test with int
    b1_res = None
    b2_res = None
    t3 = TagInt('tag_bus_int')
    t4 = TagInt('tag_bus_int')
    t3.add_callback(b1_cb, 1)
    t4.add_callback(b2_cb, 2)
    
    t3.set_value(42, int(time.time() * 1e6), 0)
    assert b1_res == 'b1 tag_bus_int 42 bus0'
    assert b2_res == 'b2 tag_bus_int 42 bus0'


def test_int_specific(bus_client):
    """Test int-specific features: multi, value_min, value_max."""
    tag_int = TagInt('tag_int_multi')
    tag_int.multi = ['zero', 'one', 'two', 'three']
    assert tag_int.multi == ['zero', 'one', 'two', 'three']
    assert tag_int.is_none is True
    tag_int.set_value(2, int(time.time() * 1e6), 0)
    assert tag_int.value == 2
    tag_int.set_value(10, int(time.time() * 1e6), 0)  # list sets min/max values
    assert tag_int.value == 3  # max is len(multi) - 1
    
    # Test that multi sets min/max
    assert tag_int.value_min == 0
    assert tag_int.value_max == 3
    
    # Test value_min and value_max setters
    tag_int_2 = TagInt('tag_int_limits2')
    tag_int_2.value_min = 10
    tag_int_2.value_max = 20
    tag_int_2.set_value(5, int(time.time() * 1e6), 0)
    assert tag_int_2.value == 10
    tag_int_2.set_value(25, int(time.time() * 1e6), 0)
    assert tag_int_2.value == 20


def test_float_specific(bus_client):
    """Test float-specific features: value_min, value_max."""
    tag_float = TagFloat('tag_float_limits2')
    tag_float.value_min = 10.5
    tag_float.value_max = 20.5
    tag_float.set_value(5.0, int(time.time() * 1e6), 0)
    assert tag_float.value == 10.5
    tag_float.set_value(25.0, int(time.time() * 1e6), 0)
    assert tag_float.value == 20.5


def test_list_dict_types(bus_client):
    """Test list and dict specific behaviors."""
    tag_list = TagList('tag_list_1')
    tag_dict = TagDict('tag_dict_1')
    
    # Test list assignment
    tag_list.set_value([1, 2, 3, 4.999], int(time.time() * 1e6), 0)
    assert tag_list.value == [1, 2, 3, 4.999]
    
    # Test dict assignment
    tag_dict.set_value({'this': 'should work'}, int(time.time() * 1e6), 0)
    assert tag_dict.value == {'this': 'should work'}
    
    # Test dict callback
    r1 = None
    
    def dict_cb(dtag):
        nonlocal r1
        r1 = dtag.value['a']
    
    t1 = {'a': 1}
    t2 = {'a': 3, 'b': 4}
    v1 = TagDict('tag_dict_cb')
    v1.set_value(t1, int(time.time() * 1e6), 0)
    assert v1.value['a'] == 1
    v1.add_callback(dict_cb, 1)  # a non-zero bus_id required
    v1.set_value(t2, int(time.time() * 1e6), 0)
    assert r1 is not None
    assert r1 == 3
    """
    CAREFUL with this, normal immutability trap.
    """
    v1.value['a'] = 5
    assert r1 != 5
    v1.value.update(a=12)
    assert r1 != 12
    v1.set_value(dict(v1.value, a=22), int(time.time() * 1e6), 0)
    assert r1 == 22
    v1.set_value({**v1.value, 'a': 55}, int(time.time() * 1e6), 0)
    assert r1 == 55


def test_bytes_type(bus_client):
    """Test bytes specific behavior."""
    tag_bytes = TagBytes('tag_bytes_1')
    tag_bytes.set_value(b'1234567890', int(time.time() * 1e6), 0)
    assert tag_bytes.value == b'1234567890'


def test_str_type(bus_client):
    """Test str specific behavior."""
    tag_str = TagStr('tag_str_1')
    tag_str.set_value('test string', int(time.time() * 1e6), 0)
    assert tag_str.value == 'test string'


def test_callback_id(bus_client):
    """Test id callback functionality."""
    tag_int = TagInt('tag_id_cb')
    result = None
    
    def id_callback(tag):
        nonlocal result
        result = tag.id
    
    tag_int.add_callback_id(id_callback)
    tag_int.id = 42
    assert result == 42
    
    tag_int.del_callback_id(id_callback)
    result = None
    tag_int.id = 43
    assert result is None


def test_check_none_value(bus_client):
    """Test check_none_value class method."""
    tag_int = TagInt('tag_check_none_1')
    tag_float = TagFloat('tag_check_none_2')
    tag_str = TagStr('tag_check_none_3')
    
    # All should be None initially
    none_list = TagTyped.check_none_values(['tag_check_none_1', 'tag_check_none_2', 'tag_check_none_3'])
    assert set(none_list) == {'tag_check_none_1', 'tag_check_none_2', 'tag_check_none_3'}
    
    # Set one value
    tag_int.set_value(42, int(time.time() * 1e6), 0)
    none_list = TagTyped.check_none_values(['tag_check_none_1', 'tag_check_none_2', 'tag_check_none_3'])
    assert set(none_list) == {'tag_check_none_2', 'tag_check_none_3'}


def test_packed_value(bus_client):
    """Test packed_value and set_packed_value for all tag types."""
    time_us = int(time.time() * 1e6)
    
    # TagInt
    ti = TagInt('tag_packed_int')
    ti.set_value(42, time_us, 0)
    pv = ti.packed_value
    assert pv == struct.pack('!Bq', pc.TYPE.INT, 42)
    pv_mod = pv[:1] + struct.pack('!q', 99)
    ti.set_packed_value(pv_mod, time_us, 0)
    assert ti.value == 99
    try:
        ti.set_packed_value(struct.pack('!Bq', pc.TYPE.FLOAT, 99), time_us, 0)
        pytest.fail("TypeError should be raised for wrong type.")
    except TypeError:
        assert True
    
    # TagFloat
    tf = TagFloat('tag_packed_float')
    tf.set_value(3.14, time_us, 0)
    pv = tf.packed_value
    assert pv == struct.pack('!Bd', pc.TYPE.FLOAT, 3.14)
    pv_mod = pv[:1] + struct.pack('!d', 2.71)
    tf.set_packed_value(pv_mod, time_us, 0)
    assert tf.value == 2.71
    try:
        tf.set_packed_value(struct.pack('!Bd', pc.TYPE.INT, 2.71), time_us, 0)
        pytest.fail("TypeError should be raised for wrong type.")
    except TypeError:
        assert True
    
    # TagStr
    ts = TagStr('tag_packed_str')
    ts.set_value('hello', time_us, 0)
    pv = ts.packed_value
    assert pv == struct.pack(f'!B{len("hello")}s', pc.TYPE.STR, b'hello')
    pv_mod = pv[:1] + b'world'
    ts.set_packed_value(pv_mod, time_us, 0)
    assert ts.value == 'world'
    try:
        ts.set_packed_value(struct.pack(f'!B{len(b"test")}s', pc.TYPE.INT, b'test'), time_us, 0)
        pytest.fail("TypeError should be raised for wrong type.")
    except TypeError:
        assert True
    
    # TagBytes
    tb = TagBytes('tag_packed_bytes')
    tb.set_value(b'abc', time_us, 0)
    pv = tb.packed_value
    assert pv == struct.pack(f'!B{len(b"abc")}s', pc.TYPE.BYTES, b'abc')
    pv_mod = pv[:1] + b'xyz'
    tb.set_packed_value(pv_mod, time_us, 0)
    assert tb.value == b'xyz'
    try:
        tb.set_packed_value(struct.pack(f'!B{len(b"test")}s', pc.TYPE.STR, b'test'), time_us, 0)
        pytest.fail("TypeError should be raised for wrong type.")
    except TypeError:
        assert True
    
    # TagList
    tl = TagList('tag_packed_list')
    tl.set_value([1, 2], time_us, 0)
    pv = tl.packed_value
    json_bytes = b'[1, 2]'
    assert pv == struct.pack(f'!B{len(json_bytes)}s', pc.TYPE.JSON, json_bytes)
    pv_mod = pv[:1] + b'[3, 4]'
    tl.set_packed_value(pv_mod, time_us, 0)
    assert tl.value == [3, 4]
    try:
        tl.set_packed_value(struct.pack(f'!B{len(b"test")}s', pc.TYPE.INT, b'test'), time_us, 0)
        pytest.fail("TypeError should be raised for wrong type.")
    except TypeError:
        assert True
    
    # TagDict
    td = TagDict('tag_packed_dict')
    td.set_value({'a': 1}, time_us, 0)
    pv = td.packed_value
    json_bytes = b'{"a": 1}'
    assert pv == struct.pack(f'!B{len(json_bytes)}s', pc.TYPE.JSON, json_bytes)
    pv_mod = pv[:1] + b'{"b": 2}'
    td.set_packed_value(pv_mod, time_us, 0)
    assert td.value == {'b': 2}
    try:
        td.set_packed_value(struct.pack(f'!B{len(b"test")}s', pc.TYPE.STR, b'test'), time_us, 0)
        pytest.fail("TypeError should be raised for wrong type.")
    except TypeError:
        assert True


def test_none_value(bus_client):
    """Test value getters and setters when value is None."""
    tf = TagFloat('tag_none_float')
    try:
        _ = tf.value
        pytest.fail("SystemExit should be raised when value is None.")
    except SystemExit:
        assert True
    tf.value = 1.5
    assert tf.value == 1.5
    
    ts = TagStr('tag_none_str')
    try:
        _ = ts.value
        pytest.fail("SystemExit should be raised when value is None.")
    except SystemExit:
        assert True
    ts.value = 'test'
    assert ts.value == 'test'
    
    tb = TagBytes('tag_none_bytes')
    try:
        _ = tb.value
        pytest.fail("SystemExit should be raised when value is None.")
    except SystemExit:
        assert True
    tb.value = b'data'
    assert tb.value == b'data'
    
    tl = TagList('tag_none_list')
    try:
        _ = tl.value
        pytest.fail("SystemExit should be raised when value is None.")
    except SystemExit:
        assert True
    tl.value = [1, 2, 3]
    assert tl.value == [1, 2, 3]
    
    td = TagDict('tag_none_dict')
    try:
        _ = td.value
        pytest.fail("SystemExit should be raised when value is None.")
    except SystemExit:
        assert True
    td.value = {'key': 'val'}
    assert td.value == {'key': 'val'}

