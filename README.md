# pymscada
## Python Mobile SCADA
You will need to install ```pymscada```, this requires ```PyYAML``` and ```aiohttp```.

```bash
pip install pymscada
```

## Run the Demo
pymscada is a collection of modulees that run individually, you will need a terminal
for each one. It's set up to work well in Debian with systemd but does run in Windows.

```shell
pymscada run bus                # always run this first
pymscada run wwwserver
pymscada run files
pymscada run history
pymscada run modbusclient
python modbus_device.py         # for the demo only
# Browse to https://localhost:8324/
```
![Display and Setpoint Components](ex001.png)
![uPlot based Trend Display](ex002.png)

## Create Your Own
Demo configs are in the pymscada package, you can check these out into your directory
and start editing from here. These _are_ the demo config files.

```shell
mkdir MyProject
cd MyProject
pymscada checkout               # creates files and folder in .
pymscada run bus
pymscada run wwwserver --config config\wwwserver.yaml --tags config\tags.yaml
pymscada run simulate --config config\simulate.yaml --tags config\tags.yaml
pymscada run files --config config\files.yaml
pymscada run history --config config\history.yaml --tags config\tags.yaml
# Browse to http://localhost:8324
```

## Still Here?
Dev environment setup is in the [docs](https://github.com/jamie0walton/pymscada/tree/main/docs).
