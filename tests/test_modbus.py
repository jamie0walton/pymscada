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
            'port': 1502,
            'tcp_udp': 'tcp',
            'serve': [{'unit': 1, 'file': '4x', 'start': 1, 'end': 20}]
        }
    ],
    'tags': {
        's_int16Tag': {'type': 'int16', 'addr': 'RTU:1:4x:1'},
        's_int32Tag': {'type': 'int32', 'addr': 'RTU:1:4x:2'},
        's_uint64Tag': {'type': 'uint64', 'addr': 'RTU:1:4x:4'},
        's_float32Tag': {'type': 'float32', 'addr': 'RTU:1:4x:9'},
        's_float64Tag': {'type': 'float64', 'addr': 'RTU:1:4x:11'}
    }
}
CLIENT = {
    'bus_ip': None,
    'bus_port': None,
    'rtus': [
        {
            'name': 'RTU',
            'ip': '127.0.0.1',
            'port': 1502,
            'tcp_udp': 'tcp',
            'rate': 1.0,
            'read': [{'unit': 1, 'file': '4x', 'start': 1, 'end': 20}],
            'writeok': [{'unit': 1, 'file': '4x', 'start': 1, 'end': 20}]
        }
    ],
    'tags': {
        'c_int16Tag': {'type': 'int16', 'addr': 'RTU:1:4x:1'},
        'c_int32Tag': {'type': 'int32', 'addr': 'RTU:1:4x:2'},
        'c_uint64Tag': {'type': 'uint64', 'addr': 'RTU:1:4x:4'},
        'c_float32Tag': {'type': 'float32', 'addr': 'RTU:1:4x:9'},
        'c_float64Tag': {'type': 'float64', 'addr': 'RTU:1:4x:11'}
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


@pytest.mark.asyncio
async def test_modbus_server():
    """Test modbus."""
    ms = ModbusServer(**SERVER)
    await ms.start()
    mc = ModbusClient(**CLIENT)
    await mc.start()
    await asyncio.sleep(0.1)
    c_int16Tag = Tag('c_int16Tag', int)
    s_int16Tag = Tag('s_int16Tag', int)
    s_int16Tag.add_callback(tag_callback)
    c_int16Tag.value = 12345
    await asyncio.sleep(0.1)
    assert s_int16Tag.value == 12345
    pass
