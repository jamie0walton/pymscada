"""Just test connections to a real PLC."""
import asyncio
import pytest
from time import time
from pymscada import Tag, LogixClient

CLIENT = {
    'bus_ip': None,
    'bus_port': None,
    'rtus': [
        {
            'name': 'Ani',
            'ip': '172.26.7.196',
            'rate': '0.2',
            'read': [
                {'addr': 'Fout', 'type': 'REAL[]', 'start': 0, 'end': 99},
                {'addr': 'Iout', 'type': 'DINT[]', 'start': 0, 'end': 99},
                {'addr': 'OutVar', 'type': 'REAL'}
            ],
            'writeok': [
                {'addr': 'Fin', 'type': 'REAL[]', 'start': 0, 'end': 99},
                {'addr': 'Iin', 'type': 'DINT[]', 'start': 0, 'end': 99},
                {'addr': 'InVar', 'type': 'REAL'}
            ]
        }
    ],
    'tags': {
        'Ani_Fin_20': {'type': 'float32', 'addr': 'Ani:Fin[20]'},
        'Ani_Fout_20': {'type': 'float32', 'addr': 'Ani:Fout[20]'},
        'Ani_Iin_20': {'type': 'int32', 'addr': 'Ani:Iin[20]'},
        'Ani_Iout_20': {'type': 'int32', 'addr': 'Ani:Iout[20]'},
        'InVar': {'type': 'float32', 'addr': 'Ani:InVar'},
        'OutVar': {'type': 'float32', 'addr': 'Ani:OutVar'},
        'Ani_Iin_21_0': {'type': 'bool', 'addr': 'Ani:Iin[21].0'},
        'Ani_Iout_21_0': {'type': 'bool', 'addr': 'Ani:Iout[21].0'},
        'Ani_Iin_21_1': {'type': 'bool', 'addr': 'Ani:Iin[21].1'},
        'Ani_Iout_21_1': {'type': 'bool', 'addr': 'Ani:Iout[21].1'},
    }
}
queue = asyncio.Queue()


def tag_callback(tag: Tag):
    """Pipe all async messages through here."""
    global queue
    queue.put_nowait(tag)


LOGIX_TEST = [
    (float, '', '', 123.456, -987.654)
]


@pytest.mark.asyncio
async def test_connect():
    """Test Logix."""
    global queue
    lc = LogixClient(**CLIENT)
    # PLC code maps 'in' tags to 'out' tags to close the loop
    # requires a real PLC with Controller scoped tags
    intags: list[Tag] = [
        Tag('Ani_Fin_20', float),
        Tag('Ani_Iin_20', int),
        Tag('InVar', float),
        Tag('Ani_Iin_21_0', int),
        Tag('Ani_Iin_21_1', int)
    ]
    outtags: list[Tag] = [
        Tag('Ani_Fout_20', float),
        Tag('Ani_Iout_20', int),
        Tag('OutVar', float),
        Tag('Ani_Iout_21_0', int),
        Tag('Ani_Iout_21_1', int)
    ]
    start = time()
    for i in range(5):
        outtags[i].add_callback(tag_callback)
    intags[0].value = 1e20
    intags[1].value = 1000000
    intags[2].value = -1e10
    intags[3].value = 0
    intags[4].value = 1
    await lc._poll()
    assert outtags[0].value == pytest.approx(1e20)
    assert outtags[1].value == 1000000
    assert outtags[2].value == pytest.approx(-1e10)
    assert outtags[3].value == 0
    assert outtags[4].value == 1
    # second set
    intags[0].value = -10.5
    intags[1].value = 1
    intags[2].value = 100.1
    intags[3].value = 1
    intags[4].value = 0
    await lc._poll()
    assert outtags[0].value == pytest.approx(-10.5)
    assert outtags[1].value == 1
    assert outtags[2].value == pytest.approx(100.1)
    assert outtags[3].value == 1
    assert outtags[4].value == 0
    # do another fifty
    for i in range(50):
        for j in range(3):
            intags[j].value += 1
        await lc._poll()
    assert outtags[0].value == pytest.approx(39.5)
    assert outtags[1].value == 51
    assert outtags[2].value == pytest.approx(150.1)
    assert queue.qsize() == 160
    duration = time() - start
    assert duration < 1
