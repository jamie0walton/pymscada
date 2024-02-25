# Running on Windows
#### [Previous](./weather.md) [Up](./README.md) [Next](./debian_demo.md)
## Prerequisites
I have run this on both Windows 11 and Windows 10 at varying times with python
versions from 3.9 to 3.11. When the ```--config``` argument is not used
```pymscada``` uses the internal copy of the files written out when you run
```pymscada checkout```. This is a convenience function. When you check the
config files out samples are written and appropriate ```systemd``` config files
are generated.

You may be able to make these run in the background in windows with
[daemonize](https://github.com/thesharp/daemonize), however ```pymscada``` is
really intended to run as services on a linux system.

## Installing

```shell
pip install pymscada
```

## Run the Demo

Open five command shell windows. In each command shell:
```shell
mkdir My Dir
cd MyDir
pymscada checkout
python .\config\modbus_plc.py --verbose
```
```shell
cd MyDir
pymscada bus --verbose
```
```shell
cd MyDir
pymscada wwwserver --verbose
```
```shell
cd MyDir
pymscada modbusclient --verbose
```
```shell
cd MyDir
pymscada history --verbose
```
