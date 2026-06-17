"""Modbus tests. TODO make these more than just a quick hack."""
import asyncio
import pytest
from pymscada import ModbusClient, ModbusServer, Tag

CLIENT = {
    'bus_ip': "127.0.0.1",
    'bus_port': 1325,
    'rtus': [
        {
            'name': 'RTU',
            'ip': '192.168.92.62',
            'port': 502,
            'tcp_udp': 'tcp',
            'rate': 0.1,
            'sleep': 0.2,
            'poll': [
                {'unit': 1, 'file': '4x', 'start': 1, 'end': 50},
                # {'unit': 1, 'file': '4x', 'start': 51, 'end': 100},
                # {'unit': 1, 'file': '4x', 'start': 101, 'end': 150},
                # {'unit': 1, 'file': '4x', 'start': 151, 'end': 200}
            ]
        }
    ],
    'tags': {
        '4x_001': {
            'type': 'int16',
            'read': 'RTU:1:4x:1'
        },
        '4x_002': {
            'type': 'int16',
            'read': 'RTU:1:4x:2'
        },
        '4x_003': {
            'type': 'int16',
            'read': 'RTU:1:4x:3'
        },
        '4x_004': {
            'type': 'int16',
            'read': 'RTU:1:4x:4'
        },
        '4x_005': {
            'type': 'int16',
            'read': 'RTU:1:4x:5'
        },
        '4x_202': {
            'type': 'int16',
            'write': 'RTU:1:4x:202'
        },
        '4x_203': {
            'type': 'int16',
            'write': 'RTU:1:4x:203'
        },
        '4x_204': {
            'type': 'int16',
            'write': 'RTU:1:4x:204'
        },
        '4x_205': {
            'type': 'int16',
            'write': 'RTU:1:4x:205'
        },
    }
}
write_queue = asyncio.Queue()
write_qhist = []
read_queue = asyncio.Queue()
read_qhist = []
count_queue = asyncio.Queue()
count_qhist = []


def write_callback(tag: Tag):
    """Pipe all async messages through here."""
    global write_queue
    global write_qhist
    write_qhist.append((tag.name, tag.value))
    write_queue.put_nowait(tag)


def read_callback(tag: Tag):
    """Pipe all async messages through here."""
    global read_queue
    global read_qhist
    read_qhist.append((tag.name, tag.value))
    read_queue.put_nowait(tag)


def count_callback(tag: Tag):
    """Pipe all async messages through here."""
    global count_queue
    global count_qhist
    count_qhist.append((tag.name, tag.value))
    count_queue.put_nowait(tag)


BUS_ID = 9999
WRITE_TAGS = ['4x_202', '4x_203', '4x_204', '4x_205']
READ_TAGS = ['4x_002', '4x_003', '4x_004', '4x_005']
COUNT_TAG = '4x_001'

@pytest.mark.asyncio
async def test_modbus_tcp():
    """Test modbus."""
    return
    global count_qhist
    global read_qhist
    global write_qhist
    mc = ModbusClient(**CLIENT)
    tags = {}
    tags[COUNT_TAG] = Tag(COUNT_TAG, int)
    tags[COUNT_TAG].add_callback(count_callback, BUS_ID)
    for tagname in READ_TAGS:
        tags[tagname] = Tag(tagname, int)
        tags[tagname].add_callback(read_callback, BUS_ID)
    for tagname in WRITE_TAGS:
        tags[tagname] = Tag(tagname, int)
        tags[tagname].add_callback(write_callback, BUS_ID)

    await mc.start()
    for tagname in WRITE_TAGS:
        tags[tagname].value = 0
    await asyncio.sleep(0.5)
    count_qhist = []
    read_qhist = []
    write_qhist = []
    for i in range(10):
        for j in range(len(WRITE_TAGS)):
            tagname = WRITE_TAGS[j]
            tags[tagname].value = i * 10 + j
        await asyncio.sleep(0.5)
    await asyncio.sleep(0.2)
    x_001 = [x[1] for x in count_qhist]
    x_002 = [x[1] for x in read_qhist if x[0] == '4x_002']
    x_003 = [x[1] for x in read_qhist if x[0] == '4x_003']
    x_004 = [x[1] for x in read_qhist if x[0] == '4x_004']
    x_005 = [x[1] for x in read_qhist if x[0] == '4x_005']
    x_202 = [x[1] for x in write_qhist if x[0] == '4x_202']
    x_203 = [x[1] for x in write_qhist if x[0] == '4x_203']
    x_204 = [x[1] for x in write_qhist if x[0] == '4x_204']
    x_205 = [x[1] for x in write_qhist if x[0] == '4x_205']
    assert x_002 == x_202
    assert x_003 == x_203
    assert x_004 == x_204
    assert x_005 == x_205
    diff = []
    for i in range(len(x_001) - 1):
        diff.append(x_001[i + 1] - x_001[i])
    lowdiff = [x for x in diff if x < 200 and x > 0]
    highdiff = [x for x in diff if x < -9800]
    assert len(lowdiff) + len(highdiff) == len(diff)
    assert len(highdiff) <= 1
    pass
