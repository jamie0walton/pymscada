# Index
#### [Up](../README.md) [Next](./windows_demo.md)

## Python Mobile SCADA

This is a small SCADA package that will run on Linux (preferably) or
Windows. The server runs as several modules on the host, sharing
information through a message bus. A __subset__ of modules is:

- Bus server - shares tag values with by exception updates
- Modbus client - reads and writes to a PLC using Modbus/TCP
- History - saves data changes, serves history to web pages
- Web server - serves web pages which connect with a web socket
- Web pages - an Angular single page web application

Web pages are responsive and defined procedurally from the
```wwwserver.yaml``` config file.

![Display and Setpoint Components](ex001.png)

Trends use [uPlot](https://github.com/leeoniya/uPlot).

![uPlot based Trend Display](ex002.png)

## Objectives

Traditional SCADA has a fixed 19:6, 1920x1080 or some equivalent layout.
It's great on a big screen but not good on a phone. Hence __Mobile__
SCADA with a responsive layout. I wrote Mobile SCADA to provide a GUI for
an optimal dispatch package, adding enough to make it useful on its own.

Uptimes should be good. An earlier version has been running continuously
for over 5 years for about half of the script modules. This version is a
complete rewrite, however the aim is the same.

All tag value updates are by exception. So an update from you setting a
value to seeing the feedback should be __FAST__.

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

# Licence

```pymscada``` is distributed under the GPLv3 [license](./LICENSE).
