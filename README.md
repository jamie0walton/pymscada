# pymscada
#### [Docs](https://github.com/jamie0walton/pymscada/blob/main/docs/README.md)

#### [@Github](https://github.com/jamie0walton/pymscada/blob/main/README.md)

<span style='color:aqua'>WIP: Presently updating documentation and deployment.</span>

## Python Mobile SCADA

```pymscada``` read / write to Modbus and Logix PLCs. Read SNMP OIDs.
Collect history values and provide the ability to set values and trends
and issue commands.

User interface is via a web client embedded in this package. Examples included
for securing with Apache as a proxy.

Configuration with text yaml files, including the web page which are
procedurally built.

# See also

- The angular project [angmscada](https://github.com/jamie0walton/angmscada)
- Python container for the compiled angular pages [pymscada-html](https://github.com/jamie0walton/pymscada-html)

# Licence

```pymscada``` is distributed under the GPLv3 [license](./LICENSE).

# Running

While many parts of ```pymscada``` will run in windows, this is not intentional.

Running a useful subset requires quite a lot of steps, you have to choose the services
you want and providing meaningful configuation. ```pymscada checkout``` will create
templates of all of these for you that allows
[Debian Quickstart](./docs/debian_quickstart.md) to get you to a working web page,
however to connect to a PLC, trend data, read data and write setpoints, requires
knowledge of typical SCADA and PLC functionality.
