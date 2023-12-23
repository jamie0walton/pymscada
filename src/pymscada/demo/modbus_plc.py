"""Demo PLC simulation."""
import asyncio
import pymscada.samplers as ps
from pymscada import Config, ramp, ModbusServer, Periodic, Tag


class PLC_Logic():
    """PLC Logic."""

    def __init__(self):
        """Create tags."""
        self.i = 0
        self.sim_IntSet = Tag('sim_IntSet', int)
        self.sim_IntSet.value = 0
        self.sim_IntVal = Tag('sim_IntVal', int)
        self.sim_FloatSet = Tag('sim_FloatSet', float)
        self.sim_FloatSet.value = 0
        self.sim_FloatVal = Tag('sim_FloatVal', float)
        self.sim_MultiSet = Tag('sim_MultiSet', int)
        self.sim_MultiSet.value = 0
        self.sim_MultiVal = Tag('sim_MultiVal', int)
        self.sim_TimeSet = Tag('sim_TimeSet', int)
        self.sim_TimeSet.value = 0
        self.sim_TimeVal = Tag('sim_TimeVal', int)
        self.sim_DateSet = Tag('sim_DateSet', int)
        self.sim_DateSet.value = 0
        self.sim_DateVal = Tag('sim_DateVal', int)
        self.sim_DateTimeSet = Tag('sim_DateTimeSet', int)
        self.sim_DateTimeSet.value = 0
        self.sim_DateTimeVal = Tag('sim_DateTimeVal', int)
        self.avg_temp = ps.Average(Tag('cpu_temp', float))
        self.cpu_load = Tag('cpu_load', float)
        self.disk_use = Tag('disk_use', float)

    async def periodic(self):
        """Emulate some PLC logic."""
        self.sim_IntVal.value = ramp(self.sim_IntVal.value,
                                     self.sim_IntSet.value, 1)
        self.sim_FloatVal.value = ramp(self.sim_FloatVal.value,
                                       self.sim_FloatSet.value, 0.5)
        self.sim_MultiVal.value = self.sim_MultiSet.value
        self.sim_TimeVal.value = self.sim_TimeSet.value
        self.sim_DateVal.value = self.sim_DateSet.value
        self.sim_DateTimeVal.value = self.sim_DateTimeSet.value
        self.avg_temp.step(ps.get_cpu_temp())
        self.i += 1
        if self.i % 60 == 0:
            self.cpu_load.value = ps.get_cpu_load()
            self.disk_use.value = ps.get_disk_use()


async def main():
    """Emulate a PLC supporting Modbus/TCP (registers only)."""
    config = Config('modbusserver.yaml')
    mbserver = ModbusServer(**config)
    await mbserver.start()
    plc = PLC_Logic()
    periodic = Periodic(plc.periodic, 1.0)
    await periodic.start()
    await asyncio.get_event_loop().create_future()


if __name__ == '__main__':
    asyncio.run(main())
