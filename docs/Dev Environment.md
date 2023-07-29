# Development Environment

This project initially started in Debian, when I started the open source version
I did the initial work up to this point in Windows. At a certain point the lack
of systemd become a compelling factor and I switched back.

# Debian
## Setup

In development PC, assuming Debian, and once you have the network roughly right. I normally
install headless (no x-windows), with ssh and apache the only options I really add. Then:

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

I use VSCode and remote ssh development. Many of the extensions self-detect
and prompt for install if you open a python file. For my system these include
python, flake8, vscode noticing the .venv folder and probably some other
things as well.

Avoid using pip. pdm avoids it, and as of Debian 12, the OS version of python
doesn't like it either (see PEP 668).

You should be able to run pymscada ...
```bash
(.venv) mscada@deb12dev:~/pymscada$ pymscada
usage: pymscada [-h] [--config file] [--tags file] [--verbose] [--path folder] action [component]
pymscada: error: the following arguments are required: action
(.venv) mscada@deb12dev:~/pymscada$ 
```

## Running the Example

You can just ```pymscada run bus``` as above for windows, however use ```systemd```.

```bash
su -
cp /home/mscada/pymscada/docs/examples/pymscada-*.service /lib/systemd/system/
for f in pymscada-bus.service pymscada-wwwserver.service pymscada-simulate.service pymscada-files.service pymscada-history.service
do
echo "Processing $f"
systemctl enable $f
systemctl start $f
done
```

To monitor the status, one of these.
```bash
systemctl status pymscada-bus.service
journalctl -fu pymscada-bus.service
```

Repeat for:
 - pymscada-wwwserver.service
 - pymscada-simulate.service
 - pymscada-files.service
 - pymscada-history.service

```bash
su -
cp /home/mscada/pymscada/docs/examples/pymscada-*.service /lib/systemd/system/

```

# Windows

Mostly works the same, just install the latest CPython, ```pip install pdm``` then
checkout the repos and run ```pdm install``` as for Debian.

What does not work is ```systemd``` so instead just open as many terminals as you
need and manually run the services. 

```shell
pymscada run bus --verbose
pymscada run wwwserver --config .\docs\examples\wwwserver.yaml --tags .\docs\examples\tags.yaml
pymscada run simulate --config .\docs\examples\simulate.yaml --tags .\docs\examples\tags.yaml
pymscada run files --config .\docs\examples\files.yaml
pymscada run history --config .\docs\examples\history.yaml --tags .\docs\examples\tags.yaml
http://localhost:8324
```
