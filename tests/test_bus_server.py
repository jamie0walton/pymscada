"""Test the bus server."""
import pytest
import pytest_asyncio
from time import process_time_ns
import asyncio
import subprocess
import sys
import gc
import weakref
from struct import pack, unpack_from
from pymscada.protocol_constants import COMMAND, TYPE
from pymscada.bus_server import BusTags, BusTag, BusServer
from pymscada.tag import Tag
from pymscada.bus_client import BusClient

server_port = None
queue = asyncio.Queue()
qhist = []


@pytest.mark.asyncio
async def test_bustag():
    """Basic BusTags and BusTag checks."""
    tag_0 = BusTag(b'tag_0')
    tag_1 = BusTag(b'tag_1')
    tag_2 = BusTag(b'tag_0')
    assert tag_0.id == 1  # 0th tag_id is invalid
    assert tag_1.id == 2
    assert tag_2.id == 1
    assert BusTags._tag_by_id[2].name == b'tag_1'
    assert BusTags._tag_by_name[b'tag_1'].id == 2
    cb0 = None

    def cb(tag: BusTag, bus_id):
        nonlocal cb0
        cb0 = tag.name + b' ' + str(tag.id).encode() + b' ' + tag.value

    tag_0.add_callback(cb, None)
    tag_0.update(b'new', 1000, 55)
    assert cb0 == b'tag_0 1 new'
    tag_2.update(b'newer', 0, 22)
    assert cb0 == b'tag_0 1 newer'
    """TODO the following is wrong."""
    tag_2.del_callback(cb, None)  # deletes callback on tag_0 as same tag
    tag_0.update(b'new again', 1000, 55)
    assert cb0 == b'tag_0 1 newer'
    tag_0.del_callback(cb, None)


@pytest_asyncio.fixture(scope='module')
async def bus_server():
    """Run a live server on an unused port."""
    global server_port
    busserver = BusServer(port=0)
    server = await busserver.start()
    server_port = server.sockets[0].getsockname()[1]


@pytest.mark.asyncio
@pytest_asyncio.fixture(scope='module')
async def bus_echo(bus_server):
    """Run an echo client for testing."""
    proc = subprocess.Popen([sys.executable, "tests/bus_echo.py",
                             str(server_port)])
    yield
    proc.terminate()
    proc.wait()


PROTOCOL_TESTS = [
    {'desc': 'create a new bus tag with ID request',
     'send': (COMMAND.ID, 170, 18_446_744_073_709_551_615, b't_0'),
     'recv': [(COMMAND.ERR, None, None, b"ID b't_0' undefined"),
              (COMMAND.ID, 'ID', None, b'')]},
    {'desc': 'SET the value of an existing tag',
     'send': (COMMAND.SET, 'ID', 6_744_073_709_551_615, b'VAL'),
     'recv': [None]},
    {'desc': 'GET the value just SET',
     'send': (COMMAND.GET, 'ID', 0, b''),
     'recv': [(COMMAND.SET, 'ID', 6_744_073_709_551_615, b'VAL')]},
    {'desc': 'SUB to the created tag',
     'send': (COMMAND.SUB, 'ID', 0, b''),
     'recv': [(COMMAND.SET, 'ID', 6_744_073_709_551_615, b'VAL')]},
    {'desc': 'SET the subscribed tag',
     'send': (COMMAND.SET, 'ID', 615, b'New value'),
     'recv': [None]},  # SUB does not return as this is sending bus
    {'desc': 'LIST bus tags',
     'send': (COMMAND.LIST, 0, 0, b'^t_0'),
     'recv': [(COMMAND.LIST, 0, None, b't_0')]},
]


@pytest.mark.asyncio(scope='module')
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
        msg = pack(f'!BBHHQ{size}s', 1, s_cmd, s_tag_id, size, s_time_us,
                   s_value)
        writer.write(msg)
        for reply in test['recv']:
            # Accumulate responses, can be zero or more
            try:
                async with asyncio.timeout(0.1):
                    data += await reader.read(1000)
            except TimeoutError:
                pass
            # confirm there no data when no reply is wanted
            if reply is None:
                if data == b'':
                    assert True
                    continue
                assert False, test['desc']
            # A reply is wanted and not received
            elif reply is not None and data == b'':
                assert False, test['desc']
            r_cmd, r_tag_id, r_time_us, r_value = reply
            _v, cmd, tag_id, size, time_us = unpack_from(
                '!BBHHQ', data, offset=0)
            data = data[14:]
            if cmd == COMMAND.ID:
                t_id = tag_id
            if r_tag_id == 'ID':
                r_tag_id = t_id
            value = unpack_from(f'!{size}s', data, offset=0)[0]
            data = data[size:]
            assert r_cmd == cmd, test['desc']
            assert r_tag_id is None or r_tag_id == tag_id, test['desc']
            assert r_time_us is None or r_time_us == time_us, test['desc']
            assert r_value is None or value.startswith(r_value), test['desc']
    writer.close()
    await writer.wait_closed()


"""
Group all responses from the bus through a queue as every message should be
expected and in a pre-determined sequence. This is nearly independent of the
test order, the exception being the first creation of the tag in the bus
where the ID is assigned.
"""


def tag_callback(tag: Tag):
    """Pipe all tag updates through here."""
    global queue
    global qhist
    qhist.append((tag.name, tag.value))
    queue.put_nowait(tag)


def msg_callback(msg: str):
    """Pipe all tag updates through here."""
    global queue
    global qhist
    qhist.append(msg)
    queue.put_nowait(msg)


@pytest.mark.asyncio(scope='module')
async def test_client_init(bus_server):
    """Check a busclient cleans up on deletion."""
    global server_port
    global queue
    # Hack the tag value straight into the bus
    mybustag = BusTag(b'myinit')
    mybustag.value = pack('!B4s', TYPE.STR, b'init')
    # standard bus client tag setup
    mytag = Tag('myinit', str)
    # callback to see when the tag updates
    mytag.add_callback(tag_callback)  # earliest sign mytag has a value
    # create the client, that's all that's needed.
    client = BusClient(port=server_port)
    await client.start()
    # make sure the busclient cleans up afterwards
    weakref.finalize(client, msg_callback, 'finalized')
    # we should see the tag value arrive without any effort at all.
    assert mytag == await queue.get()
    # it should have the value hacked into the bus tag
    assert mytag.value == 'init'
    # now clean up, shutdown to clean up the varying connections
    # then delete the client and then do a manual gc.collect.
    await client.shutdown()  # normally necessary and sufficient
    del client
    gc.collect()  # required for the finalizer to be called
    # ... and we should see client tidied up.
    assert await queue.get() == 'finalized'
    # For all that, normally, one client should be open for the life of the
    # program.
    # Remove the tag from callback otherwise other clients will notice.
    mytag.del_callback(tag_callback)


@pytest.mark.asyncio(scope='module')
async def test_tag_info(bus_server):
    """Check tag info init works."""
    global server_port
    global queue
    tag_info = {
        'ftag1': {'init': 123.456},
        'dtag1': {'init': {'look': 'here'}},
    }
    ftag1 = Tag('ftag1', float)
    dtag1 = Tag('dtag1', dict)
    client = BusClient(port=server_port, tag_info=tag_info)
    await client.start()
    # must get None from bus before initialising
    await asyncio.sleep(0.1)
    assert ftag1.value == 123.456
    assert dtag1.value == {'look': 'here'}
    # cleanup, normally don't bother with this, but tests check more
    # internals that ever done in an application
    await client.shutdown()
    del client
    gc.collect()


@pytest.mark.asyncio(scope='module')
async def test_client_speed(capsys, bus_echo):
    """Test for round-trip speed of small packets."""
    global server_port
    global queue
    TEST_COUNT = 1000  # shorter troublesome in windows
    client = BusClient(port=server_port)
    await client.start()
    tagpi = Tag('pipein', int)
    tagpo = Tag('pipeout', int)
    tagpi.add_callback(tag_callback)
    await asyncio.sleep(0.1)
    assert tagpi.id is not None, 'Bus should have assigned ID'
    assert tagpo.id is not None, 'Bus should have assigned ID'
    assert tagpi.id != tagpo.id, 'Bus tags should have different IDs'
    t0 = process_time_ns()
    for test_value in range(TEST_COUNT):
        tagpo.value = test_value
        response = await queue.get()
        assert test_value == response.value
    t1 = process_time_ns()
    await client.shutdown()
    ms_per_cycle = (t1 - t0) / 1000000 / TEST_COUNT
    with capsys.disabled():
        print(f'\n{TEST_COUNT} writes, round trip {ms_per_cycle}ms/write')
    assert ms_per_cycle < 10  # less than 10ms per count
    tagpi.del_callback(tag_callback)


@pytest.mark.asyncio(scope='module')
async def test_client_big(capsys, bus_echo):
    """Test a message that needs multiple packets."""
    global server_port
    global queue
    TEST_LENGTH = 100000  # 1MB is 0s, 10MB is 0.2s, 100MB is 22s
    tagspi = Tag('spipein', str)
    tagspo = Tag('spipeout', str)
    tagspi.add_callback(tag_callback)
    client = BusClient(port=server_port)
    await client.start()
    value = '0123456789' * TEST_LENGTH
    t0 = process_time_ns()
    tagspo.value = value
    response = await queue.get()
    assert value == response.value
    t1 = process_time_ns()
    await client.shutdown()
    ns_per_byte = (t1 - t0) / 10 / TEST_LENGTH
    with capsys.disabled():
        print(f'\n{10 * TEST_LENGTH} write, time {ns_per_byte}ms/byte')
    assert len(response.value) == 10 * TEST_LENGTH
    tagspi.del_callback(tag_callback)


@pytest.mark.asyncio(scope='module')
async def test_client_echo(capsys, bus_echo):
    """Test echo from a separate process."""
    global server_port
    global queue
    client = BusClient(port=server_port)
    await client.start()
    tag_send_str = Tag('one', str)
    tag_send_int = Tag('three', int)
    tag_recv_str = Tag('two', str)
    tag_recv_int = Tag('four', int)
    tag_recv_int.add_callback(tag_callback)
    for i in range(100):
        tag_send_str.value = f'count {i}'
        tag_send_int.value = i
        ready = await queue.get()
        assert ready.value == i
        assert tag_recv_str.value == tag_send_str.value
        assert tag_recv_int.value == tag_send_int.value
    await client.shutdown()
    tag_recv_int.del_callback(tag_callback)


@pytest.mark.asyncio(scope='module')
async def test_client_rta(bus_echo):
    """Test request to author (RTA) with __bus_echo__."""
    global server_port
    global queue
    client = BusClient(port=server_port)
    await client.start()
    be = Tag('__bus_echo__', str)
    be.add_callback(tag_callback)
    r = await queue.get()
    assert r.value == 'started'
    for _ in range(10):
        client.rta(be.name, 'ping')
        r = await queue.get()
        assert r.value == 'pong'
