# Running Windows Demo
#### [Previous](./README.md) [Up](./README.md) [Next](./debian_demo.md)
## Prerequisites
I tried this on both Windows 11 and Windows 10 at varying times, although my
home computer is Windows 11 so this is the least impacted by IT security
policy. I used python from [here](https://www.python.org/downloads/).
Versions varied between 3.9 and 3.11.

## Installing

```shell
pip install pymscada
```

## Run the Demo

Open five command shell windows. In all change directory to a temp directory
where you can create the files. For all of these, be in the same directory.
Not all of this is absolutely necessary, however Windows performance has
not been my focus.
```shell
pymscada bus --verbose
```
```shell
pymscada wwwserver --verbose
```
```shell
pymscada checkout
python .\config\modbus_plc.py
```
```shell
pymscada modbusclient --verbose
```
```shell
pymscada history --verbose
```
