#  Running on Debian
#### [Previous](./windows_demo.md) [Up](./README.md) [Next](./raspberry_demo.md)
## Prerequisites
My test system for writing this description was Debian 12 which changed
to follow [pep 668](https://peps.python.org/pep-0668/) with respect to
externally managed python. Short version, ```pip install``` no longer
works globally.

## Installing

You will need '''.venv'''.
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install pymscada
```

## Run the Demo
pymscada is a collection of modulees that run individually, you will need a terminal
for each one. It's set up to work well in Debian with systemd but does run in Windows.

```shell
mkdir MyDir
cd MyDir
pmscada checkout  # required to get modbus_plc.py
nohup pymscada bus --config config/wwwserver.yaml --tags config/tags.yaml &
nohup pymscada wwwserver --config config/simulate.yaml --tags config/tags.yaml &
nohup pymscada history --config config/files.yaml &
nohup .venv/bin/python ./config/modbus_plc.py &
nohup pymscada modbusclient --config config/history.yaml --tags config/tags.yaml  &
# Browse to https://localhost:8324/
```

See the Raspberry Pi description for using ```systemd```.
