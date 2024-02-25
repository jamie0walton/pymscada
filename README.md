# pymscada
#### [Docs](https://github.com/jamie0walton/pymscada/blob/main/docs/README.md)

#### [@Github](https://github.com/jamie0walton/pymscada/blob/main/README.md)

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

# Use
Checkout the example files.
```bash
mscada@raspberrypi:~/test $ pymscada checkout
making 'history' folder
making pdf dir
making config dir
Creating  /home/mscada/test/config/modbusclient.yaml
Creating  /home/mscada/test/config/pymscada-history.service
Creating  /home/mscada/test/config/wwwserver.yaml
Creating  /home/mscada/test/config/pymscada-demo-modbus_plc.service
Creating  /home/mscada/test/config/files.yaml
Creating  /home/mscada/test/config/pymscada-modbusserver.service
Creating  /home/mscada/test/config/pymscada-wwwserver.service
Creating  /home/mscada/test/config/simulate.yaml
Creating  /home/mscada/test/config/tags.yaml
Creating  /home/mscada/test/config/history.yaml
Creating  /home/mscada/test/config/pymscada-files.service
Creating  /home/mscada/test/config/bus.yaml
Creating  /home/mscada/test/config/modbusserver.yaml
Creating  /home/mscada/test/config/modbus_plc.py
Creating  /home/mscada/test/config/pymscada-modbusclient.service
Creating  /home/mscada/test/config/pymscada-bus.service
Creating  /home/mscada/test/config/README.md
mscada@raspberrypi:~/test $ pymscada validate
WARNING:root:pymscada 0.1.0 starting
Config files in ./ valid.
``` 

Runs on a Raspberry Pi and includes preconfigured systemd files to
automate running the services. Mostly works on Windows, works better
on linux.

Modules can be run from the command line, although you need
a terminal for each running module (better with systemd).
```bash
pymscada bus --config bus.yaml
pymscada wwwserver --config wwwserver.yaml --tags tags.yaml
pymscada history --config history.yaml --tags tags.yaml
python weather.py
```
