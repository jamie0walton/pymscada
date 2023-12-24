"""Test periodic functions."""
import pytest
import asyncio
from pymscada.periodic import Periodic

flag = 0


async def do_period():
    """Fast periodic counter function."""
    global flag
    flag += 1
    if flag == 2:
        # causes count to slip one
        await asyncio.sleep(0.1)


def resetflag():
    """Reset counter."""
    global flag
    flag = 0


@pytest.mark.asyncio()
async def test_periodic():
    """Periodic should run three times in 0.21 seconds."""
    resetflag()
    periodic = Periodic(do_period, 0.05)
    await periodic.start()
    await asyncio.sleep(0.21)
    await periodic.stop()
    assert flag == 4


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
