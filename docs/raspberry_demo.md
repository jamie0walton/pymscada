#  Running on a Raspberry Pi
#### [Previous](./debian_demo.md) [Up](./README.md) [Next](./module_list.md)
## Prerequisites
My test system for writing this description was Raspbian 11 on a Raspberry
Pi 3B+. This has python 3.9 and is a little simpler to install.

## Installing
Installing is slightly simpler than on Debian 12 where pep668 applies.

```bash
sudo su -
apt update
apt upgrade
exit
pip install pymscada
# log out, and log in again for ~/.local/bin to pick up
mkdir MyDir
cd MyDir
pymscada checkout
# prints help
```

The ```.service``` files in the ```MyDir/config``` directory are updated
for your path and virtual environment as they are written out, so these
should be good to go in the current directory.

## Fast way
You can copy this across the fast way however as this package is new there
are things that break so I suggest the slow way.
```bash
# Check defaults with your preferred text editor :D
vi config/*.service 
for f in config/*.service
    do cp $f /lib/systemd/system/
    systemctl enable `basename $f`
    systemctl start `basename $f`
    done
# Browse to http://xx.xx.xx.xx:8324/
```

If something is wrong start with ```journalctl status pymscada-bus```,
followed by ```wwwserver```.

## Slow way
Best to do these one at a time and check they are running properly.

The bus process won't do much until another process connects to it.
```bash
su -
cd /home/mscada/MyDir
cp ./config/pymscada-bus.service /etc/systemd/system/mnulti-user.target.wants/
systemctl enable pymscada-bus
systemctl status pymscada-bus
```

The web server process will connect to the bus and let you browse with the
web client, typically http://<addr>:8324/ up until you have Apache configured.
```bash
su -
cd /home/mscada/MyDir
cp ./config/pymscada-wwwserver.service /etc/systemd/system/mnulti-user.target.wants/
systemctl enable pymscada-wwwserver
systemctl status pymscada-wwwserver
```

Now for the simulated Modbus PLC. This requires running as root because it
binds to port 502. You can change the port for testing.
```bash
su -
cd /home/mscada/MyDir
cp ./config/pymscada-demo-modbus_plc.service /etc/systemd/system/mnulti-user.target.wants/
systemctl enable pymscada-demo-modbus_plc
systemctl status pymscada-demo-modbus_plc
```

The Modbus client can now run and connect to the demo PLC.
```bash
su -
cd /home/mscada/MyDir
cp ./config/pymscada-modbusclient.service /etc/systemd/system/mnulti-user.target.wants/
systemctl enable pymscada-modbusclient
systemctl status pymscada-modbusclient
```
