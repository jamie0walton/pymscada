# pymscada Modules
#### [Previous](./raspberry_demo.md) [Up](./README.md) [Next](./tags.md)
## Bus Server

[Tag](./tags.md) message exchange. This serves tag values to subscribers
and also passes tag RQS messages (ReQuest Set) to the tag author to
provide database update commands through a tag.

_busserver_ must never stop, as any connected applications depend on
tag values, once set, being set forever.

## Bus Client

BusClient is a class used by all modules, it is not a module itself.
The bus client manages the upstream traffic of tag values in a way
that is invisible to the client application.

## WWW Server

_wwwserver_ uses ```aiohttp``` to provide http and ws services to
connected web clients. It serves the Angular single page application
and then provides subscribed tag values, and tag value set commands
through to the bus.

## Modbus Client

_modbusclient_ connects to a real (or simulated) PLC, reads register
values and provides for register writes. It converts integer and real
values in both directions in INT and UINT, 16, 32 and 64 bit formats
and REAL in 32 and 64 bit.

Modbus client doesn't (but will) handle bit unpacking to Tag values
Unlikely I'll ever do the reverse. The
[pymodbus](https://github.com/pymodbus-dev/pymodbus) library is
likely a better bet if you'd like this.

This version has very little protection against overloading a PLC,
I wrote it with the deliberate intent to stress test communications
channels and as such it can continuously send more data than a PLC
is likely to be able to handle.

## Modbus Server

_modbusserver_ listens as a mailbox for Modbus data written to
```pymscada``` by other devices. This is also useful for in-package
testing of the Modbus client.

## Logix Client

_logixclient_ uses the [pycomm3](https://github.com/ottowayi/pycomm3)
module to read and write to ControlLogix PLCs.

## SnmpClient

_snmpclient_ uses the [pysnmplib](https://github.com/pysnmp/pysnmp)
to read MIBs from network devices.

## History

The _history_ module creates binary event driven historical log files
in a python binary array format. This data is directly copied to the
RQS tag when requested by the web client in order to minimize the
amount of handling required to deliver history.

## Console

Not implemented.

Early versions of ```pymscada``` wrapped in to ```Mobile SCADA``` used
a text network protocol. This made it possible to telnet directly to
the bus, subscribe to tag values directly and watch traffic. _console_
will replicate this function (when I get around to it).

## Not Included
### Optimal Dispatch & Observer
I've implemented a model predictive control for hydraulic systems, gates
and hydro generators that uses a MILP solver to optimise generation
dispatch. This is a commercial product that uses many of the functions
I have migrated into ```pymscada```. Over time I hope to change the
split between functions, improving the supportability and back-end
code along the way.
