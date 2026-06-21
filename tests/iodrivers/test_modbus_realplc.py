"""Modbus tests. TODO make these more than just a quick hack."""
import asyncio
import pytest
from itertools import chain
import time
from pymscada import ModbusClient, TagInt, TagFloat

BUS_ID = 9999
CLIENT = {
    'bus_ip': "127.0.0.1",
    'bus_port': 1325,
    'rtus': [
        {
            'name': 'RTU',
            'ip': '192.168.92.62',
            'port': 502,
            'rate': 0.5,
            'reads': [
                {'unit': 1, 'file': '4x', 'start': 1, 'end': 100},
                {'unit': 1, 'file': '4x', 'start': 51, 'end': 100},
                {'unit': 1, 'file': '4x', 'start': 101, 'end': 150},
                {'unit': 1, 'file': '4x', 'start': 151, 'end': 200}
            ],
            'writes': [
                {'unit': 1, 'file': '4x', 'start': 201, 'end': 250}
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
        '4x_006_0': {
            'type': 'bool',
            'read': 'RTU:1:4x:6.0'
        },
        '4x_006_1': {
            'type': 'bool',
            'read': 'RTU:1:4x:6.1'
        },
        '4x_006_2': {
            'type': 'bool',
            'read': 'RTU:1:4x:6.2'
        },
        '4x_006_3': {
            'type': 'bool',
            'read': 'RTU:1:4x:6.3'
        },
        '4x_007': {
            'type': 'float32',
            'read': 'RTU:1:4x:7'
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
        '4x_206_0': {
            'type': 'bool',
            'write': 'RTU:1:4x:206.0'
        },
        '4x_206_1': {
            'type': 'bool',
            'write': 'RTU:1:4x:206.1'
        },
        '4x_206_2': {
            'type': 'bool',
            'write': 'RTU:1:4x:206.2'
        },
        '4x_206_3': {
            'type': 'bool',
            'write': 'RTU:1:4x:206.3'
        },
        '4x_207': {
            'type': 'float32',
            'write': 'RTU:1:4x:207'
        },
    }
}


queue_count = asyncio.Queue()
hist_count = {}


def callback_count(tag: TagInt):
    """Pipe all async messages through here."""
    global queue_count
    global hist_count
    if tag.name not in hist_count:
        hist_count[tag.name] = []
    hist_count[tag.name].append(tag.value)
    queue_count.put_nowait(1)


queue_int = asyncio.Queue()
hist_int = {}


def callback_int(tag: TagInt):
    """Pipe all async messages through here."""
    global queue_int
    global hist_int
    if tag.name not in hist_int:
        hist_int[tag.name] = []
    hist_int[tag.name].append(tag.value)
    queue_int.put_nowait(1)


queue_bool = asyncio.Queue()
hist_bool = {}


def callback_bool(tag: TagInt):
    """Pipe all async messages through here."""
    global queue_bool
    global hist_bool
    if tag.name not in hist_bool:
        hist_bool[tag.name] = []
    hist_bool[tag.name].append(tag.value)
    queue_bool.put_nowait(1)


queue_float = asyncio.Queue()
hist_float = {}


def callback_float(tag: TagFloat):
    """Pipe all async messages through here."""
    global queue_float
    global hist_float
    if tag.name not in hist_float:
        hist_float[tag.name] = []
    hist_float[tag.name].append(tag.value)
    queue_float.put_nowait(1)


def flush(queue: asyncio.Queue):
    while True:
        try:
            queue.get_nowait()
            queue.task_done()
        except asyncio.QueueEmpty:
            break


@pytest.mark.asyncio
async def test_modbus_tcp():
    """Test modbus."""
    global queue_count
    global hist_count
    global queue_int
    global hist_int
    global queue_bool
    global hist_bool
    global queue_float
    global hist_float
    mc = ModbusClient(**CLIENT)
    tag_x001 = TagInt('4x_001')
    tag_x001.add_callback(callback_count, BUS_ID)
    tag_x002 = TagInt('4x_002')
    tag_x002.add_callback(callback_int, BUS_ID)
    tag_x003 = TagInt('4x_003')
    tag_x003.add_callback(callback_int, BUS_ID)
    tag_x004 = TagInt('4x_004')
    tag_x004.add_callback(callback_int, BUS_ID)
    tag_x005 = TagInt('4x_005')
    tag_x005.add_callback(callback_int, BUS_ID)
    tag_x006_0 = TagInt('4x_006_0')
    tag_x006_0.add_callback(callback_bool, BUS_ID)
    tag_x006_1 = TagInt('4x_006_1')
    tag_x006_1.add_callback(callback_bool, BUS_ID)
    tag_x006_2 = TagInt('4x_006_2')
    tag_x006_2.add_callback(callback_bool, BUS_ID)
    tag_x006_3 = TagInt('4x_006_3')
    tag_x006_3.add_callback(callback_bool, BUS_ID)
    tag_x007 = TagFloat('4x_007')
    tag_x007.add_callback(callback_float, BUS_ID)
    tag_x202 = TagInt('4x_202')
    tag_x203 = TagInt('4x_203')
    tag_x204 = TagInt('4x_204')
    tag_x205 = TagInt('4x_205')
    tag_x206_0 = TagInt('4x_206_0')
    tag_x206_1 = TagInt('4x_206_1')
    tag_x206_2 = TagInt('4x_206_2')
    tag_x206_3 = TagInt('4x_206_3')
    tag_x207 = TagFloat('4x_207')
    await mc.start()
    flush(queue_count)
    i = 0
    last_count = 10000
    while True:
        i += 1
        await queue_count.get()
        count = hist_count['4x_001'][-1]
        if count > last_count:
            break
        elif i > 5:
            assert False, "Count not changing"
        last_count = count
    flush(queue_int)
    for j in range(5):
        time_us = int(time.time() * 1e6)
        tag_x202.set_value(10 + j, time_us, BUS_ID)
        tag_x203.set_value(20 + j, time_us, BUS_ID)
        tag_x204.set_value(30 + j, time_us, BUS_ID)
        tag_x205.set_value(40 + j, time_us, BUS_ID)
        i = 0
        while True:
            i += 1
            await queue_int.get()
            res = [hist_int[x][-1] for x in
                   ['4x_002', '4x_003', '4x_004', '4x_005']]
            if res == [10 + j, 20 + j, 30 + j, 40 + j]:
                break
            elif i > 20:  # * 4 as 4 int tags
                assert False, "Int not changing"
    flush(queue_bool)
    v = [[0, 1, 1, 0], [1, 1, 1, 1], [1, 0, 0, 1], [0, 0, 0, 0], [0, 0, 0, 1]]
    for j in range(5):
        time_us = int(time.time() * 1e6)
        tag_x206_0.set_value(v[j][0], time_us, BUS_ID)
        tag_x206_1.set_value(v[j][1], time_us, BUS_ID)
        tag_x206_2.set_value(v[j][2], time_us, BUS_ID)
        tag_x206_3.set_value(v[j][3], time_us, BUS_ID)
        i = 0
        while True:
            i += 1
            await queue_bool.get()
            res = [hist_bool[x][-1] for x in
                   ['4x_006_0', '4x_006_1', '4x_006_2', '4x_006_3']]
            if res == v[j]:
                break
            elif i > 20:  # * 4 as 4 bool tags
                assert False, "Bool not changing"
    flush(queue_float)
    for value in [-1.2345e6, -50, -1, -0.5, 0, 0.5, 1, 50, 1.2345e6]:
        time_us = int(time.time() * 1e6)
        tag_x207.set_value(value, time_us, BUS_ID)
        i = 0
        while True:
            i += 1
            await queue_float.get()
            if hist_float['4x_007'][-1] == value:
                break
            elif i > 5:
                assert False, 'float not changing'
    pass
