# Environment

Assumes a Debian 12 host without direct internet access.
Cursor or VS Code as the IDE.

On my system there are three running instances
- /home/mscada/config/bus.yaml port 1324
- /home/ecogas/config/bus.yaml port 1326
- /home/jamie/config/bus.yaml port 1325

mscada and ecogas are production
jamie is development

Each instance of MobileSCADA has a bus, on the named port and a set
of client processes.

On the dev instance each client process can be stopped and run in the IDE
with the debugger with live data. The web client can be passed an argument
so that the pages are served from a different path than the data, so that
a test web client can run in debug against a dev server (or real in a pinch).

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
