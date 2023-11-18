"""Test periodic functions."""
import pytest
import asyncio
import time
from pymscada.periodic import Heartbeat, Periodic, RunEvery

flag = 0


async def do_period():
    """Fast periodic counter function."""
    global flag
    flag += 1


def fastcount():
    """Fast periodic counter function."""
    global flag
    flag += 1


def resetflag():
    """Reset counter."""
    global flag
    flag = 0


@pytest.mark.asyncio()
async def test_periodic():
    """Periodic should run three times in 0.21 seconds."""
    resetflag()
    periodic = Periodic(do_period, 0.1)
    await periodic.start()
    await asyncio.sleep(0.21)
    await periodic.stop()
    assert flag == 3


@pytest.mark.asyncio()
async def test_timechange():
    """Periodic should run four times in 0.41 seconds."""
    resetflag()
    periodic = Periodic(do_period, 0.1)
    await periodic.start()
    await asyncio.sleep(0.21)
    periodic.period = 0.3
    await asyncio.sleep(0.2)
    await periodic.stop()
    assert flag == 4


@pytest.mark.asyncio()
async def test_runevery():
    """Run every should ... ."""
    resetflag()
    RunEvery(fastcount, 0.1)
    await asyncio.sleep(0.21)
    assert flag == 3


def error():
    """Error causing function."""
    raise UserWarning('ta da')


@pytest.mark.asyncio()
async def test_runevery_error():
    """Run every should ... ."""
    try:
        RunEvery(error, 0.01)
        await asyncio.gather(*asyncio.all_tasks() - {asyncio.current_task()})
    except BaseException as e:
        raised_error = e
    assert raised_error.args[0] == 'RunEvery re-raising'


def countbeat():
    """Fast periodic counter function."""
    global beats
    beats.append(time.time())


@pytest.mark.asyncio()
async def test_heartbeat():
    """Run every should ... ."""
    global beats
    beats = []
    Heartbeat(countbeat, 0.1)
    await asyncio.sleep(0.25)
    assert len(beats) in [2, 3]

    def near(v):
        rv = round(v, 1)
        return abs(rv - v)

    time_error = sum([near(x) for x in beats[:2]])
    assert time_error < 0.003  # ~0.001 in dev
