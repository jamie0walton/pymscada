"""
Check the bus client.

Note, having a BusClient in another test that has not been properly closed
will cause these tests to fail.
"""
import pytest
import pytest_asyncio
import asyncio
import struct
import json
import time
from pymscada.bus_client import BusClient
from pymscada.bus_client_tag import TagInt, TagDict
from pymscada.bus_server import BusServer, BusTag
import pymscada.protocol_constants as pc

SERVER_BUS_ID = 901
CLIENT_BUS_ID = 902
server_port = None
server_queue = asyncio.Queue()


@pytest_asyncio.fixture(scope='module')
async def bus_server():
    """Run a live server on an unused port."""
    global server_port
    global SERVER_ID
    busserver = BusServer(port=0)
    server = await busserver.start()
    server_port = server.sockets[0].getsockname()[1]
    int_tag = BusTag(b'test_int')
    rta_tag = BusTag(b'rta_test')

    def cb_int(tag: BusTag, bus_id):
        global server_queue
        tagname = tag.name.decode()
        if tag.value is None:
            data = None
        else:
            data = struct.unpack_from('!q', tag.value, offset=1)[0]
        server_queue.put_nowait(f'{tagname} {data}')

    def cb_rta(tag: BusTag, bus_id):
        global server_queue
        tagname = tag.name.decode()
        if tag.value is None:
            data = None
        else:
            data = json.loads(struct.unpack_from(f'!{len(tag.value) - 1}s',
                                                 tag.value, offset=1
                                                 )[0].decode())
        server_queue.put_nowait(f'{tagname} {data}')

    int_tag.add_callback(cb_int, SERVER_BUS_ID)
    rta_tag.add_callback(cb_rta, SERVER_BUS_ID)


@pytest.mark.asyncio(loop_scope='module')
async def test_write_data_none(bus_server):
    """Test write() method with data=None."""
    global server_port
    global server_queue
    client = BusClient(port=server_port)
    await client.start()
    client_tag = TagInt('test_int')
    client_tag.value = 5
    result = await server_queue.get()
    assert result == 'test_int 5'
    await client.shutdown()


@pytest.mark.asyncio(loop_scope='module')
async def test_bus_client_rta(bus_server):
    """test RTA messaging."""
    global server_port
    global server_queue
    rta_queue = asyncio.Queue()
    client = BusClient(port=server_port)
    await client.start()
    author_tag = TagDict('rta_test')
    author_tag.value = {'test': 'data'}
    result = await server_queue.get()

    def rta_handler(request):
        rta_queue.put_nowait(request)

    client.add_callback_rta('rta_test', rta_handler)
    request = {'action': 'test', 'value': 42}
    jsonstr = json.dumps(request).encode()
    size = len(jsonstr)
    rta_data = struct.pack(f'!B{size}s', pc.TYPE.JSON, jsonstr)
    time_us = int(time.time() * 1e6)
    client.process(pc.COMMAND.RTA, author_tag.id, time_us, rta_data)
    result = await asyncio.wait_for(rta_queue.get(), timeout=1.0)
    assert result == request
