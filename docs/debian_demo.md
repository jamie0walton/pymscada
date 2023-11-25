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
pymscada run bus                # always run this first
pymscada run wwwserver
pymscada run files
pymscada run history
pymscada run modbusclient
python modbus_device.py         # for the demo only
# Browse to https://localhost:8324/
```

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
