# Debian Quickstart
#### [Previous](../README.md) [Up](../README.md) [Next](../README.md)

## Installing pymscada
Assuming your control system code is in an OT network with perimeter security and
you can ```ssh``` into your system, you will need to tunnel a proxy. ```squid``` is
good (see another guide for this).

As root
```bash
vi /etc/apt/apt.conf.d/40proxy
```

```ini
Acquire::http::Proxy "http://127.0.0.1:3128";
```

As root
```bash
apt install python3.11-venv
vi /etc/ssh/sshd_config
```

Edit to change
```ini
AllowAgentForwarding yes
AllowTcpForwarding yes
GatewayPorts yes
#GatewayPorts no
```

Now you can ```ssh``` with a tunnelled port as ```R3128 your.proxy.server:3128```. A
dedicated Debian VM running ```squid``` works for this.

For the final setup steps as a standard user
```bash
cd ~
python -m venv .venv
```

For ease of use create a ```.bash_aliases``` file for adding proxies and
setting the python virtual environment. If you are also using this for development
<span style="background-color:darkred">do NOT use this venv</span>.
```bash
function proxy_set() {
    export {http,https}_proxy='http://proxy-serv:8080'
}

function proxy_unset() {
    unset {http,https}_proxy
}

function activate() {
    source ~/.venv/bin/activate
}
```

As a standard user, logging in with a fresh terminal session.
```sh
proxy_set
source_activate
# your prompt should change to show the .venv status.
pip install pymscada
```

## Apache 2

As root
```bash
apt install apache2
a2enmod rewrite
a2enmod proxy
a2enmod proxy_http
a2enmod proxy_wstunnel
pushd /etc/apache2/sites-available
cp default-ssl.conf pymscada.conf
vi pymscada.conf
```

Depending on your setup, edit to add the following
```ini
    RewriteEngine on
    RewriteCond %{HTTP:Upgrade} websocket [NC]
    RewriteCond %{HTTP:Connection} upgrade [NC]
    RewriteRule ^/pymscada/?(.*) "ws://127.0.0.1:8324/ws" [P,L]
    ProxyPass /pymscada/ http://127.0.0.1:8324/
    ProxyPassReverse /pymscada/ http://127.0.0.1:8324/
    <Location /pymscada>
        Authtype Basic
        Authname "Password Required - pymscada Authorised Users Only"
        AuthUserFile /etc/apache2/pymscada.htpasswd
        Require all granted
    </Location>
```

Continue as root
```bash
popd
cp /etc/apache2
systemctl restart apache2
```

## Running pymscada

At this stage you should be able to run ```pymscada -h``` and see a useful help message.

```bash
cd ~   # your preferred directory to do this may differ
pymscada checkout
```

```pymscada checkout``` populates the files with some default path names that <u>match the
directory you checkout to</u> so moving the service files later requires editing the files.

At this stage it makes sense to start the bus and webserver.

As root
```bash
cd /lib/systemd/system
ln -s /home/{$username}/config/pymscada-bus.service
ln -s /home/{$username}/config/pymscada-wwwserver.service
systemctl enable pymscada-bus
systemctl enable pymscada-wwwserver
systemctl start pymscada-bus
systemctl start pymscada-wwwserver
```

You should now be able to connect as [https://your-apache-server/pymscada/]().

Useful debugging tools at this stage are:
- ```systemctl status pymscada-bus``` which should show the bus running and wwwserver
  having connected.
- Similarly ```systemctl status pymscada-wwwserver``` and, to follow this running,
  ```journalctl -fu pymscada-bus```.

## pymscada console

With ```pymscada console``` you can interogate the bus valve. On the web page set a new
value for the integer setpoint. In the console ```g IntSet``` should show the current value
and ```s IntSet``` will subscribe to changes.

```set IntSet 123``` will set the value so you can see the change in the webclient. ```h``` gives a list of available commands.

I suggest you open multiple web page clients, line them up so you can see them all, and
experiment with setting the Integer Setpoint. This gives a good illustration of the speed
and open connectivity to setpoints.

## Security

```pymscada``` is designed to make it easy to access control systems, exactly what you
__don't__ want any random person to access. These systems tend to be fundamentally insecure,
depending on perimeter security and access control. This package works with apache and,
https and wss, it is up to <span style='background-color:red'>&nbsp;__you__&nbsp;</span>
to secure it.