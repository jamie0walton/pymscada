#  Running Linux Demo
#### [Previous](./windows_demo.md) [Up](./README.md) [Next](./module_list.md)
## Prerequisites
My test system for writing this description was Debian 12 which changed
to follow [pep 668](https://peps.python.org/pep-0668/) with respect to
externally managed python. Short version, ```pip install``` no longer
works globally.

However, I've recently installed on a Raspberry Pi 3B+ with Python 3.9 and ```pip install``` works perfectly fine.


## Installing

You will need '''.venv''' as [pep 668](https://peps.python.org/pep-0668/) distro's do not support installing modules, even in
your local directory.
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install pymscada
```

## Run the Demo
pymscada is a collection of modulees that run individually, you will need a terminal
for each one. It's set up to work well in Debian with systemd but does run in Windows.

```shell
nohup pymscada bus --verbose &
nohup pymscada wwwserver --verbose &
nohup pymscada history --verbose  &
pmscada checkout  # required to get modbus_plc.py
nohup .venv/bin/python ./config/modbus_plc.py &
nohup pymscada modbusclient --verbose  &
# Browse to https://localhost:8324/
```

## Create Your Own
The files created in the prior step in order to create ```modbus_plc.py``` also
creates a directory of config files. You can edit and use these as follows,
wrapping in ```nohup ... &``` or setting as service (see the dev description).

```shell
pymscada run bus
pymscada run wwwserver --config config/wwwserver.yaml --tags config/tags.yaml
pymscada run simulate --config config/simulate.yaml --tags config/tags.yaml
pymscada run files --config config/files.yaml
pymscada run history --config config/history.yaml --tags config/tags.yaml
# Browse to http://localhost:8324
```
