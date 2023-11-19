"""Demo PLC simulation."""
import asyncio
from pymscada import Config, ramp, ModbusServer, Periodic, Tag


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


async def main_periodic():
    """Emulate some PLC logic."""
    sim_IntVal.value = ramp(sim_IntVal.value, sim_IntSet.value, 1)
    sim_FloatVal.value = ramp(sim_FloatVal.value, sim_FloatSet.value, 0.5)
    sim_MultiVal.value = sim_MultiSet.value
    sim_TimeVal.value = sim_TimeSet.value
    sim_DateVal.value = sim_DateSet.value
    sim_DateTimeVal.value = sim_DateTimeSet.value


async def main():
    """Emulate a PLC supporting Modbus/TCP (registers only)."""
    config = Config('modbusserver.yaml')
    mbserver = ModbusServer(**config)
    await mbserver.start()
    periodic = Periodic(main_periodic, 1.0)
    await periodic.start()
    await asyncio.get_event_loop().create_future()


if __name__ == '__main__':
    asyncio.run(main())
