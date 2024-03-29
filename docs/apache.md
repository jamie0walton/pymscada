# Apache
#### [Previous](./debian_dev.md) [Up](./README.md) [Next](./road_map.md)
## Fresh OS install
Assuming that ```https:\\<yourhost>``` is not working and as root:

```bash
cd /etc/apache2/sites-available
cp  default-ssl.conf  mscada.conf
a2dissite 000-default
a2dissite detault-ssl
a2enmod ssl
```

```http://``` and ```https://``` should both work on your server,
probably just showing the default apache page.

## Add the pymscada proxy

Add the following into ```mscada.conf```
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
        Require all granted  # Apache 2.4, same as when omitted in 2.2
    </Location>
```

```bash
a2ensite mscada
htpasswd -c /etc/apache2/pymscada.htpasswd pymscada
# give the user a password
a2enmod rewrite
a2enmod proxy
a2enmod proxy_http
a2enmod proxy_wstunnel
apache2ctl configtest
# Syntax OK
systemctl reload apache2
```

```https://<address>/pymscada/``` should now work in the same way that
```http://<address>:8324/``` does. Once you have this working it is good
to change pymscada ```.yaml``` files such that the bus and other server
packages listen on 127.0.0.1 and not 0.0.0.0.
