# Modbus PLC Demo
#### [Previous](./tags.md) [Up](./README.md) [Next](./debian_dev.md)

## Function
The Modbus PLC demo provides both a completely functional demo system
you can run on your system and an example of how you can write your
own function to connect to the pymscada bus and add custom logic.

Mobile SCADA was created to allow custom logic to be connected to
a hydro generation scheme to provide dispatch control. pymscada is
the parts of Mobile SCADA used to make the connection, and provide
a flexible display.

## Config

The following snip shows everything up to the first tag. In this case
the bus_ip and port are left empty. This is a special case that tells
the ```BusClient``` not to connect to the bus, otherwise the simulation
tags would be directly available on the bus. Not a problem if the names
don't clash.

The single _sim_IntSet_ tag shown is linked with the Modbus holding
register address 40001. Any modbus write to this address will result
in the tag value changing and any tag callback being called, although
no callbacks are shown in this example.

```yaml
bus_ip:
bus_port:
rtus:
- name: RTU
  ip: 0.0.0.0
  port: 502
  tcp_udp: tcp
  serve:
  - {unit: 1, file: 4x, start: 1, end: 100}
tags:
  sim_IntSet:
    type: int16
    addr: RTU:1:4x:1
```

Configuration file checking (a work in progress) can be carried out as:
```bash
pymscada validate --path path/to/config_dir
```

The complete python code that uses this confir file starts with a
minimal set of imports.
```python
import asyncio
from pymscada import Config, ramp, ModbusServer, Periodic, Tag
```

In this example the tag values are declared globally. For this simple
example the context is provided by the fact that this program is
already a self-contained module.

This section is whatever you need it to be.
```python
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
```

The main periodic function is a co-routine. For functions like those
in this example that return immediately this is not required. However
this does allow the potential for the periodic function to poll some
web API where the response may need to be await'd.

This section is also whatever your application requires.
```python
async def main_periodic():
    """Emulate some PLC logic."""
    sim_IntVal.value = ramp(sim_IntVal.value, sim_IntSet.value, 1)
    sim_FloatVal.value = ramp(sim_FloatVal.value, sim_FloatSet.value, 0.5)
    sim_MultiVal.value = sim_MultiSet.value
    sim_TimeVal.value = sim_TimeSet.value
    sim_DateVal.value = sim_DateSet.value
    sim_DateTimeVal.value = sim_DateTimeSet.value
```

The main routine must load the config yaml file. The config yaml file
is passed as **kwargs so the yaml file structure is constrained to match
valid arguments of ```ModbusServer```. Tags are required in this example
as ```BusClient``` maps tag values used in the program with the Modbus
tables.

In this section you need to start something pymscada related to use the
```BusClient``` including calling it directly. Any functions should be
started as co-routines or callbacks to tag updates.
```python
async def main():
    """Emulate a PLC supporting Modbus/TCP (registers only)."""
    config = Config('modbusserver.yaml')
    mbserver = ModbusServer(**config)
    await mbserver.start()
    periodic = Periodic(main_periodic, 1.0)
    await periodic.start()
    await asyncio.get_event_loop().create_future()  # Run forever


if __name__ == '__main__':
    asyncio.run(main())
```