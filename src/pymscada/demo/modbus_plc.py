"""Demo PLC simulation."""
import asyncio
from pymscada.config import Config
from pymscada.modbus_server import ModbusServer
from pymscada.periodic import RunEvery
from pymscada.tag import Tag


sim_IntSet = Tag('sim_IntSet', int)
sim_IntSet.value = 0
sim_IntVal = Tag('sim_IntVal', int)
sim_FloatSet = Tag('sim_FloatSet', float)
sim_FloatSet.value = 0
sim_FloatVal = Tag('sim_FloatVal', float)
sim_MultiSet = Tag('sim_MultiSet', int)
sim_MultiSet.value = 0
sim_MultiVal = Tag('sim_MultiVal', int)
sim_TimeSet = Tag('sim_TimeSet', int)
sim_TimeSet.value = 0
sim_TimeVal = Tag('sim_TimeVal', int)
sim_DateSet = Tag('sim_DateSet', int)
sim_DateSet.value = 0
sim_DateVal = Tag('sim_DateVal', int)
sim_DateTimeSet = Tag('sim_DateTimeSet', int)
sim_DateTimeSet.value = 0
sim_DateTimeVal = Tag('sim_DateTimeVal', int)


def ramp(current, target, step):
    """Ramp the current value to the target no faster than step."""
    if target is None:
        return current
    if current is None:
        return target
    if target > current:
        current += step
        if target < current:
            current = target
    elif target < current:
        current -= step
        if target > current:
            current = target
    return current


def run_every_second():
    """Simulate a simple PLC."""
    # print(f'Float val is {sim_FloatVal.value} '
    #       f'Float set is {sim_FloatSet.value}')
    sim_IntVal.value = ramp(sim_IntVal.value, sim_IntSet.value, 1)
    sim_FloatVal.value = ramp(sim_FloatVal.value, sim_FloatSet.value, 0.5)
    sim_MultiVal.value = sim_MultiSet.value
    sim_TimeVal.value = sim_TimeSet.value
    sim_DateVal.value = sim_DateSet.value
    sim_DateTimeVal.value = sim_DateTimeSet.value


async def main():
    """Run the Modbus server."""
    config = Config('modbusserver.yaml')
    mbserver = ModbusServer(**config)
    await mbserver.start()
    RunEvery(run_every_second, 1.0)
    await asyncio.get_event_loop().create_future()


if __name__ == '__main__':
    asyncio.run(main())
