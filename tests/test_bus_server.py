"""Test the bus server."""
import pytest
import pytest_asyncio
from time import process_time_ns
import asyncio
from struct import pack, unpack_from
from pymscada import protocol_constants as pc
from pymscada.bus_server import BusTags, BusTag, BusServer
from pymscada.tag import Tag
from pymscada.bus_client import BusClient

server_port = None


@pytest.mark.asyncio
async def test_bustag():
    """Basic BusTags and BusTag checks."""
    tag_0 = BusTag(b'tag_0')
    tag_1 = BusTag(b'tag_1')
    tag_2 = BusTag(b'tag_0')
    assert tag_0.id == 0  # must be first test run to be 0th tag_id
    assert tag_1.id == 1
    assert tag_2.id == 0
    assert BusTags._tag_by_id[1].name == b'tag_1'
    assert BusTags._tag_by_name[b'tag_1'].id == 1
    cb0 = None

    def cb(tag: BusTag, bus_id):
        nonlocal cb0
        cb0 = tag.name + b' ' + str(tag.id).encode() + b' ' + tag.value

    tag_0.add_callback(cb, None)
    tag_0.update(b'new', 1000, 55)
    assert cb0 == b'tag_0 0 new'
    tag_2.update(b'newer', 0, 22)
    assert cb0 == b'tag_0 0 newer'
    tag_2.del_callback(cb, None)  # deletes callback on tag_0 as same tag
    tag_0.update(b'new again', 1000, 55)
    assert cb0 == b'tag_0 0 newer'


@pytest.fixture(scope='module')
def event_loop():
    """Override default scope from function to module."""
    policy = asyncio.get_event_loop_policy()
    loop = policy.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope='module')
async def bus_server():
    """Run a live server on an unused port."""
    global server_port
    busserver = BusServer(bus_port=0)
    server = await busserver.start()
    server_port = server.sockets[0].getsockname()[1]


PROTOCOL_TESTS = [
    {'desc': 'create a new bus tag with ID request',
     'send': (pc.CMD_ID, 170, 18_446_744_073_709_551_615, b't_0'),
     'recv': [(pc.CMD_ERR, None, None, b"ID b't_0' undefined"),
              (pc.CMD_ID, 'ID', None, b'')]},
    {'desc': 'SET the value of an existing tag',
     'send': (pc.CMD_SET, 'ID', 6_744_073_709_551_615, b'VAL'),
     'recv': [None]},
    {'desc': 'GET the value just SET',
     'send': (pc.CMD_GET, 'ID', 0, b''),
     'recv': [(pc.CMD_SET, 'ID', 6_744_073_709_551_615, b'VAL')]},
    {'desc': 'SUB to the created tag',
     'send': (pc.CMD_SUB, 'ID', 0, b''),
     'recv': [(pc.CMD_SET, 'ID', 6_744_073_709_551_615, b'VAL')]},
    {'desc': 'SET the subscribed tag',
     'send': (pc.CMD_SET, 'ID', 615, b'New value'),
     'recv': [None]},  # SUB does not return as this is sending bus
    {'desc': 'LIST bus tags',
     'send': (pc.CMD_LIST, 0, 0, b'^t_0'),
     'recv': [(pc.CMD_LIST, 0, None, b't_0')]},
]


@pytest.mark.asyncio
async def test_protocol_message(bus_server):
    """Connect to the server and test the protocol."""
    global server_port
    t_id = None
    data = b''
    reader, writer = await asyncio.open_connection('127.0.0.1', server_port)
    for test in PROTOCOL_TESTS:
        s_cmd, s_tag_id, s_time_us, s_value = test['send']
        if s_tag_id == 'ID':
            s_tag_id = t_id
        size = len(s_value)
        msg = pack(f">BBHHQ{size}s", 1, s_cmd, s_tag_id, size, s_time_us,
                   s_value)
        writer.write(msg)
        for reply in test['recv']:
            try:
                async with asyncio.timeout(0.1):
                    data += await reader.read(1000)
            except TimeoutError:
                pass
            if reply is None:
                if data == b'':
                    assert True
                    continue
                assert False, test['desc']
            elif reply is not None and data == b'':
                assert False, test['desc']
            r_cmd, r_tag_id, r_time_us, r_value = reply
            _v, cmd, tag_id, size, time_us = unpack_from(
                '>BBHHQ', data, offset=0)
            data = data[14:]
            if cmd == pc.CMD_ID:
                t_id = tag_id
            if r_tag_id == 'ID':
                r_tag_id = t_id
            value = unpack_from(f'>{size}s', data, offset=0)[0]
            data = data[size:]
            assert r_cmd == cmd, test['desc']
            assert r_tag_id is None or r_tag_id == tag_id, test['desc']
            assert r_time_us is None or r_time_us == time_us, test['desc']
            assert r_value is None or value.startswith(r_value), test['desc']


@pytest.mark.asyncio
async def test_client_speed(capsys, bus_server):
    """Connect to the server and test the protocol."""
    global server_port
    TEST_COUNT = 1000  # shorter troublesome in windows
    client = BusClient(port=server_port)
    await client.connect()
    tag_13 = Tag('tag_13', int)
    tag_14 = Tag('tag_14', str)
    await asyncio.sleep(0.1)
    assert tag_13.id is not None, 'Bus should have assigned ID'
    assert tag_14.id is not None, 'Bus should have assigned ID'
    assert tag_13.id != tag_14.id, 'Bus tags should have different IDs'
    queue = asyncio.Queue()

    def cb_int(tag: Tag, _from_bus):
        nonlocal queue
        queue.put_nowait(tag.value)

    def cb_str(tag: Tag, _from_bus):
        nonlocal queue
        queue.put_nowait(tag.value)

    tag_13.add_callback(cb_int)
    tag_14.add_callback(cb_str)
    _, writer = await asyncio.open_connection('127.0.0.1', server_port)
    t0 = process_time_ns()
    for test_value in range(TEST_COUNT):
        msg = pack('>BBHHQBq', 1, pc.CMD_SET, tag_13.id, 9, 1234, pc.TYPE_INT,
                   test_value)
        writer.write(msg)
        response = await queue.get()
        assert test_value == response
    t1 = process_time_ns()
    ms_per_cycle = (t1 - t0) / 1000000 / TEST_COUNT
    with capsys.disabled():
        print(f'\n{TEST_COUNT} writes, round trip {ms_per_cycle}ms/write')
    assert ms_per_cycle < 10  # less than 10ms per count
    await client.shutdown()


@pytest.mark.asyncio
async def test_client_big(capsys, bus_server):
    """Connect to the server and test the protocol."""
    global server_port
    TEST_LENGTH = 1000000  # 1MB is 0s, 10MB is 0.2s, 100MB is 22s
    client = BusClient(port=server_port)
    await client.connect()
    tag_14 = Tag('tag_14', str)
    await asyncio.sleep(0.1)
    queue = asyncio.Queue()

    def cb_str(tag: Tag, _from_bus):
        nonlocal queue
        queue.put_nowait(tag.value)

    tag_14.add_callback(cb_str)
    _, writer = await asyncio.open_connection('127.0.0.1', server_port)
    value = b'\x03' + b'x' * TEST_LENGTH
    t0 = process_time_ns()
    for i in range(0, len(value) + 1, pc.MAX_LEN):
        snip = value[i:i+pc.MAX_LEN]
        size = len(snip)
        msg = pack(f'>BBHHQ{size}s', 1, pc.CMD_SET, tag_14.id, size, 5678,
                   snip)
        await writer.drain()
        writer.write(msg)
    writer.close()
    await writer.wait_closed()
    response = await queue.get()
    t1 = process_time_ns()
    ns_per_byte = (t1 - t0) / 1000000
    with capsys.disabled():
        print(f'\n{TEST_LENGTH} write, time {ns_per_byte}ms')
    assert len(response) == TEST_LENGTH
    await client.shutdown()
