# Debian
#### [Previous](./modbus_plc_demo.md) [Up](./README.md) [Next](./apache.md)

## System Build

Installing as a headless VM gives the most flexibility. Has very low resource requirements unless you are using the MILP functionality where the external solver package benefits from a lot more RAM and CPU. I use:

- 20 GB Hard Disk
- 8 GB RAM
- 8 CPU cores
- Debian, latest network ISO
- Graphical install
- Location, language and keyboard to suit
- name and domain to suit, empty is fine for domain
- root password, add mscada user and password
- Clock to suit
- Guided, entire disk, all in one partition, finish and write to disk (wipes your disk)
- No extra media, your country, archive mirror and proxy (if required)
- Deselect Debian desktop environment and GNOME
- Select web server, SSH server, standard system utilities
  - There is nothing to stop you using a desktop environment, it's not required
- GRUB, pick a device, the install will proceed, reboot

If you have run this up as a VM its easiest to bridge the network. Log in to the system and run ```ip a s``` to see the IP address. Use Putty to connect.

## System Setup

Initially DHCP is fine, however later fix the network address.

```
vi /etc/network/interfaces
#allow-hotplug ens192
#iface ensp1s0 inet dhcp
auto ens192
iface ens192 inet static
    address 192.168.178.33
    netmask 255.255.255.0
    gateway 192.168.178.254
:wq
systemctl restart networking
ip a s
```

Turn off IPV6, ng serve for angular binds to ipv6 (last I checked).

```
vi /etc/sysctl.conf
 --- Add the following at the bottom of the file:
net.ipv6.conf.all.disable_ipv6 = 1
net.ipv6.conf.default.disable_ipv6 = 1
net.ipv6.conf.lo.disable_ipv6 = 1
net.ipv6.conf.tun0.disable_ipv6 = 1
```





## Notes

With the venv prefix as ```(.venv)``` its not obvious which venv is running :(.
```bash
python -c "import sys; print(sys.prefix)"
git clone https://github.com/jamie0walton/pymscada.git
cd pymscada
python3 -m venv .venv   # TODO this later proved to be a problem and I deleted it
source .venv/bin/activate
pip install pdm
pdm install
```

In VS code over a remote ssh session, open a python file. With any luck VS code will
notice and prompt for the correct venv.

Best for the debian user to be dedicated to the development. That way the directory
structure can be consistent. Go with:
```ini
/home/username/
            # run - pymscada checkout
            # run - git clone pymscada
            # run - git glone angmscada
    config/
            # systemd and yaml config files are here
            # edit as needed
    history/
            # history files are created if the logger is run
    pdf/
            # convenience for serving pdf files
    pymscada/
            # dev folder for python, uses a DIFFERENT .venv
    angmscada/
            # dev folder for angular
        dist/angmscada/
            # dev web pages are created here
```

## Prerequisites

Start with the description in [Quickstart](./debian_quickstart.md). I'm uncertain
what impact having the right version of [PDM](https://pdm-project.org/en/latest/) is so
I don't install it in the OS. Rather:

```bash
cd ~
git clone https
```

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
cd /lib/systemd/system
ln -s /home/mscada/config/pymscada-io-sms.service
systemctl enable pymscada-io-sms
systemctl start pymscada-io-sms
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

NOTE that the .env file is not included in indexing but does contain data
that must be updated for environment variables to work for IDE test extension.
Should be something like the following:
```.env
ENV_VAR=12345
```

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

# Putty

Using Putty with a port rule ```R3128 192.168.1.1:3128``` and a local internet
connected squid proxy on 192.168.1.1 allows things like ```pip install pymscada```
to work. VS Code / Cursor have a nasty habit of trying to do this automatically
with varying degrees of success. YMMV.

```bash
jamie@debianv12:~$ cat .bash_aliases
function px_set() {
    export {http,https,ftp}_proxy='http://127.0.0.1:3128'
}

function activate() {
    source ~/pymscada/.venv/bin/activate
}
```
