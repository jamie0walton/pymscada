# Index
#### [Up](../README.md) [Next](./windows_demo.md)
## Security
_busserver_ listens on a port for the bus module. At very least
a denial of service attack will work. This should listen on 127.0.0.1
and nothing else.

_wwwserver_ relies on software designed for secure connection to
a network to provide security. You should __not__ expose any process
control to Internet.

_modbusserver_ should be (as for any PLC) isolated both from Internet
and you corporate IT in its own dedicated OT network. ```pymscada```
should be in the same space with appropriate security between IT and OT.

See [apache](./apache.md) for a reasonably secure way to provide
intranet access to users already permitted on your network.

## Index

- Install and getting the demo to run in [Windows](./windows_demo.md)
- ... and in [Debian 12](./debian_demo.md)
- Additional [Modules](./module_list.md)
- The [Tag](./tags.md) class
- A description of the [Modbus PLC](./modbus_plc_demo.md) emulation demo
- Setting up a [development environment](./debian_dev.md) on Debian
- Using [Apache](./apache.md) as a front end.
- [Road map](./road_map.md)

Older (and likely not current) information includes:
- [Initial build](./initial_build.md) description
