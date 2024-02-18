"""Modbus tests. TODO make these more than just a quick hack."""
import asyncio
import pytest
from pymscada import ModbusClient, ModbusServer, Tag

SERVER = {
    'bus_ip': None,
    'bus_port': None,
    'rtus': [
        {
            'name': 'RTU',
            'ip': '127.0.0.1',
            'port': 1512,
            'tcp_udp': 'tcp',
            'serve': [{'unit': 1, 'file': '4x', 'start': 1, 'end': 30}]
        },
        {
            'name': 'RTU_UDP',
            'ip': '127.0.0.1',
            'port': 1513,
            'tcp_udp': 'udp',
            'serve': [{'unit': 1, 'file': '4x', 'start': 1, 'end': 30}]
        }
    ],
    'tags': {
        's_int16Tag': {'type': 'int16', 'addr': 'RTU:1:4x:1'},
        's_uint16Tag': {'type': 'uint16', 'addr': 'RTU:1:4x:2'},
        's_int32Tag': {'type': 'int32', 'addr': 'RTU:1:4x:3'},
        's_uint32Tag': {'type': 'uint32', 'addr': 'RTU:1:4x:5'},
        's_int64Tag': {'type': 'int64', 'addr': 'RTU:1:4x:7'},
        's_uint64Tag': {'type': 'uint64', 'addr': 'RTU:1:4x:11'},
        's_float32Tag': {'type': 'float32', 'addr': 'RTU:1:4x:15'},
        's_float64Tag': {'type': 'float64', 'addr': 'RTU:1:4x:17'},
        's_udp_int16Tag': {'type': 'int16', 'addr': 'RTU_UDP:1:4x:1'},
    }
}
CLIENT = {
    'bus_ip': None,
    'bus_port': None,
    'rtus': [
        {
            'name': 'RTU',
            'ip': '127.0.0.1',
            'port': 1512,
            'tcp_udp': 'tcp',
            'rate': 0.1,
            'read': [{'unit': 1, 'file': '4x', 'start': 1, 'end': 30}],
            'writeok': [{'unit': 1, 'file': '4x', 'start': 1, 'end': 30}]
        },
        {
            'name': 'RTU_UDP',
            'ip': '127.0.0.1',
            'port': 1513,
            'tcp_udp': 'udp',
            'rate': 0.1,
            'read': [{'unit': 1, 'file': '4x', 'start': 1, 'end': 30}],
            'writeok': [{'unit': 1, 'file': '4x', 'start': 1, 'end': 30}]
        }
    ],
    'tags': {
        'c_int16Tag': {'type': 'int16', 'addr': 'RTU:1:4x:1'},
        'c_uint16Tag': {'type': 'uint16', 'addr': 'RTU:1:4x:2'},
        'c_int32Tag': {'type': 'int32', 'addr': 'RTU:1:4x:3'},
        'c_uint32Tag': {'type': 'uint32', 'addr': 'RTU:1:4x:5'},
        'c_int64Tag': {'type': 'int64', 'addr': 'RTU:1:4x:7'},
        'c_uint64Tag': {'type': 'uint64', 'addr': 'RTU:1:4x:11'},
        'c_float32Tag': {'type': 'float32', 'addr': 'RTU:1:4x:15'},
        'c_float64Tag': {'type': 'float64', 'addr': 'RTU:1:4x:17'},
        'c_udp_int16Tag': {'type': 'int16', 'addr': 'RTU_UDP:1:4x:1'}
    }
}
queue = asyncio.Queue()
qhist = []


def tag_callback(tag: Tag):
    """Pipe all async messages through here."""
    global queue
    global qhist
    qhist.append(tag)
    queue.put_nowait(tag)


def msg_callback(msg):
    """Pipe all async messages through here."""
    global queue
    global qhist
    qhist.append(msg)
    queue.put_nowait(msg)


MODBUS_TEST = [
    (int, 'c_int16Tag', 's_int16Tag', -77, -55),
    (int, 'c_uint16Tag', 's_uint16Tag', 123, 456),
    (int, 'c_int32Tag', 's_int32Tag', -90, -99),
    (int, 'c_uint32Tag', 's_uint32Tag', 1000000, 2000000),
    (int, 'c_int64Tag', 's_int64Tag', -123, -12),
    (int, 'c_uint64Tag', 's_uint64Tag', 12345678901234, 22345678901234),
    (float, 'c_float32Tag', 's_float32Tag', 1.23, 4.56),
    (float, 'c_float64Tag', 's_float64Tag', 1.23e200, -5.67e-200),
    (int, 'c_udp_int16Tag', 's_udp_int16Tag', 12345, -12345),
]


@pytest.mark.asyncio
async def test_modbus_tcp():
    """Test modbus."""
    ms = ModbusServer(**SERVER)
    await ms.start()
    mc = ModbusClient(**CLIENT)
    await mc.start()
    tags: dict[str, Tag] = {}
    i = 0
    while mc.connections[0].transport is None:
        await asyncio.sleep(0.01)
        i += 1
        if i > 10:
            pytest.fail('Modbus connection unsuccessful')
    for tagtype, tag1, tag2, set, _ in MODBUS_TEST:
        tags[tag1] = Tag(tag1, tagtype)
        tags[tag2] = Tag(tag2, tagtype)
        tags[tag1].value = set
    await asyncio.sleep(0.01)
    for tagtype, _, tag2, set, _ in MODBUS_TEST:
        if tagtype is int:
            assert tags[tag2].value == set
        else:
            assert tags[tag2].value == pytest.approx(set)
    for _, tag1, tag2, _, get in MODBUS_TEST:
        tags[tag2].value = get
    await asyncio.sleep(0.2)
    for tagtype, tag1, _, _, get in MODBUS_TEST:
        if tagtype is int:
            assert tags[tag1].value == get
        else:
            assert tags[tag1].value == pytest.approx(get)
