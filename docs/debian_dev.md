# Development Environment - Debian
#### [Previous](./modbus_plc_demo.md) [Up](./README.md) [Next](./apache.md)

## Prerequisites
You will need a linux install with support for ```systemd```, you should
select Apache and ssh, I normally don't install any form of x windows as
the idea is to never need to log on to the SCADA server as a desktop
computer.Difficult to secure a desktop, a server style install with minimal
attack surface is best. The attack surface I aim for is https and wss
through Apache and ssh.

The following fairly standard set of changes taken from my console history are:

```bash
vi /etc/hosts                  # Comment out IPV6 (localhost)
vi /etc/network/interfaces     # No X so static IPV4 config
adduser mscada
```



## Setup
Debian 12, once ipv4 is working. Set up to run headless (no x-windows), with ssh
and apache. Remote development with VS code over ssh, and with Apache for web
facing services. Then:

```bash
su -
apt install build-essential git git-doc curl python3-pdm
adduser mscada
su mscada
git config --global credential.helper cache
git clone https://github.com/jamie0walton/angmscada.git
git clone https://github.com/jamie0walton/pymscada.git
cd pymscada
pdm install
```

You should be able to run pymscada ...
```bash
(.venv) mscada@deb12dev:~/pymscada$ pymscada
usage: pymscada [-h] [--config file] [--tags file] [--verbose] [--path folder] action [component]
pymscada: error: the following arguments are required: action
(.venv) mscada@deb12dev:~/pymscada$ 
```

# Notes

VSCode extensions typically auto-detect and prompt for install if you open a python
file. For my system these include python, flake8, vscode noticing the .venv folder
and probably some other things as well.

Avoid using pip. pdm avoids it, and as of Debian 12, the OS version of python
doesn't like it either (see PEP 668).

The simplest dev setup is to use VS Code to ssh to a Debian install, have the services
you are not editing run by systemd, and run the service you are debugging with the
python debugger in VS code. Best to set all the services up to run, and stop the one
you are going to run in debug.

```bash
cd /home/mscada
pymscada checkout
```

Before installing the services, have a look at the ```.service``` files in ```config```. If you want
to edit ```.yaml``` files, change out the comment lines. ```pymscada checkout``` copies the files
out with directory name replacement so they are essentially identical.

Once you have finalised your ```.service``` files:

```bash
su -
cd /home/mscada
for f in config/*.service
do
cp $f /lib/systemd/system/
systemctl enable `basename $f`
systemctl start `basename $f`
done
```

## Checking its Running

All going well all the services will be running.

```bash
systemctl status pymscada-*
```

Or checking on each individually:

```bash
systemctl status pymscada-bus.service
journalctl -fu pymscada-bus.service
```

Of course browsing to <host ip>:8324 is also good.

## Useful bits

Handy to run modbusclient against port 502 with Schneider's
[test program](https://www.se.com/nz/en/faqs/FA180037/)
that only connects to port 502.
```bash
setcap CAP_NET_BIND_SERVICE=+eip /usr/bin/python3.11
```

Running the demo PLC code.
```bash
nohup .venv/bin/python3.11 src/pymscada/demo/modbus_plc.py &
```

# Windows

Mostly works the same, just install the latest CPython, ```pip install pdm``` then
checkout the repos and run ```pdm install``` as for Debian.

There is no systemd equivalent, although there are various approaches people have
managed to make work for Windows daemons / services.
