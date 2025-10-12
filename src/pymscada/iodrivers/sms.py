"""SMS to RUT241"""
import asyncio
from aiohttp import web, ClientSession
import logging
import socket
from typing import Callable

from pymscada.bus_client import BusClient
from pymscada.misc import find_nodes
from pymscada.periodic import Periodic
from pymscada.tag import Tag


class RUT241:
    """RUT241 SMS modem."""
    # disable RMS settings
    # just use admin for api call, too damned obscure to configure
    # need to configure SMS to http gateway for incoming SMS
    # point to this server, use aiohttp to serve, awkward but
    # by exception so fast and light
    # set the http forward to use sms_number and sms_message
    # If keeping it simple (i.e. limit to SMS and LAN)
    # Network WAN - turn all off, LAN - static, Wireless - turn off
    
    
    def __init__(self, ip: str = None, username: str = None,
                 password: str = None, port: int = 8080,
                 recv_cb: Callable = None, info: dict = {}):
        if ip is None:
            raise ValueError('ip is required')
        if username is None:
            raise ValueError('username is required')
        if password is None:
            raise ValueError('password is required')

        self.ip = ip
        self.username = username
        self.password = password
        self.port = port
        self.recv_cb = recv_cb
        self.tags = {}
        for info, tagname in info.items():
            self.tags[info] = Tag(tagname, str)
        self.token = None
        self.modem = None
        self.carrier = None
        self.webapp = None

    async def login(self):
        url = f'https://{self.ip}/api/login'
        json = {'username': self.username,
                'password': self.password}
        headers = {'Content-Type': 'application/json'}
        async with ClientSession() as session:
            async with session.post(url, json=json, headers=headers,
                    ssl=False) as response:
                if response.status == 200:
                    resp = await response.json()
                    self.token = resp['data']['token']
                    logging.info(f'RUT241 login token {self.token}')
                else:
                    logging.error(f'RUT241 login error {response.status} '
                                  f'{response.text}')

    async def get_modem_info(self):
        if self.token is None:
            await self.login()
        if self.token is None:
            return
        url = f'https://{self.ip}/api/modems/apns/status'
        headers = {'Authorization': f'Bearer {self.token}'}
        async with ClientSession() as session:
            async with session.get(url, headers=headers, ssl=False) as response:
                if response.status == 200:
                    resp = await response.json()
                    self.modem = next(find_nodes('modem', resp))['modem']
                    self.carrier = next(find_nodes('carrier', resp))['carrier']
                    logging.info(f'RUT241 {self.modem} on {self.carrier}')
                else:
                    self.token = None
                    logging.error(f'RUT241 lost token {response.status} '
                                  f'{response.text}')

    async def send_sms(self, phone: str, message: str):
        url = f'https://{self.ip}/api/messages/actions/send'
        headers = {'Authorization': f'Bearer {self.token}',
                   'Content-Type': 'application/json'}
        json = {'data': {
                    'number': phone,
                    'message': message,
                    'modem': self.modem
                }}
        logging.info(f'RUT241 {json}')
        async with ClientSession() as session:
            async with session.post(url, headers=headers, json=json, ssl=False) as response:
                if response.status == 200:
                    resp = await response.json()
                    logging.info(f'RUT241 {resp}')
                else:
                    logging.error(f'RUT241 {response.status} {response.text}')

    async def listen_sms(self):
        webserver = web.Application()
        
        async def post_handler(request):
            data = await request.post()
            if data['sms_message'][:2].upper() == 'IN':
                tag = self.tags['__default__']
                if tag.value is None:
                    message = '__default__'
                else:
                    message = tag.value
                asyncio.create_task(self.send_sms(data['sms_number'], message))
                return web.Response(text='OK', status=200)
            if self.recv_cb is not None:
                self.recv_cb(dict(data))
            return web.Response(text='OK', status=200)
        
        webserver.router.add_post('/', post_handler)
        self.webapp = web.AppRunner(webserver)
        await self.webapp.setup()
        site = web.TCPSite(self.webapp, '0.0.0.0', self.port)
        await site.start()

    async def stop_listening(self):
        if self.webapp is not None:
            await self.webapp.cleanup()


class SMS:
    """Connect to SMS modem."""

    def __init__(
        self,
        bus_ip: str | None = '127.0.0.1',
        bus_port: int | None = 1324,
        sms_send_tag: str = '__sms_send__',
        sms_recv_tag: str = '__sms_recv__',
        modem: str = 'rut241',
        modem_ip: str | None = None,
        username: str | None = None,
        password: str | None = None,
        listen_port: int | None = 8080,
        info: dict = {}
    ) -> None:
        """
        Connect to SMS, only RUT240 at the moment.
        For testing bus_ip can be None to skip connection.
        ip must be valid and reachable, check.
        """
        if bus_ip is None:
            logging.warning('Callout has bus_ip=None, only use for testing')
        else:
            try:
                socket.gethostbyname(bus_ip)
            except socket.gaierror as e:
                raise ValueError(f'Cannot resolve IP/hostname: {e}')
            if not isinstance(bus_port, int):
                raise TypeError('bus_port must be an integer')
            if not 1024 <= bus_port <= 65535:
                raise ValueError('bus_port must be between 1024 and 65535')
        if not isinstance(sms_send_tag, str) or not sms_send_tag:
            raise ValueError('sms_send_tag must be a non-empty string')
        if not isinstance(sms_recv_tag, str) or not sms_recv_tag:
            raise ValueError('sms_recv_tag must be a non-empty string')
        if modem == 'rut241':
            self.modem = RUT241(ip=modem_ip, username=username,
                                password=password, port=listen_port,
                                recv_cb=self.sms_recv_cb, info=info)
        else:
            raise ValueError(f'Unknown modem type: {type}')

        logging.warning(f'SMS {bus_ip} {bus_port} {sms_send_tag} '
                        f'{sms_recv_tag}')
        self.sms_send = Tag(sms_send_tag, dict)
        self.sms_send.add_callback(self.sms_send_cb)
        self.sms_recv = Tag(sms_recv_tag, dict)
        self.tags = {}
        for info, tagname in info.items():
            self.tags[info] = Tag(tagname, str)
        self.busclient = None
        if bus_ip is not None:
            self.busclient = BusClient(bus_ip, bus_port, module='SMS')
        self.periodic = Periodic(self.periodic_cb, 60.0)

    def sms_send_cb(self, tag: Tag):
        """Handle SMS messages from the modem."""
        if tag.value is None:
            return
        number = tag.value['number']
        message = tag.value['message']
        logging.info(f'Sending SMS to {number}: {message}')
        asyncio.create_task(self.modem.send_sms(number, message))

    def sms_recv_cb(self, value: dict):
        """Handle SMS messages from the modem."""
        self.sms_recv.value = {
            'number': value['sms_number'],
            'message': value['sms_message']
        }

    async def periodic_cb(self):
        """Periodic callback to check alarms and send callouts."""
        await self.modem.get_modem_info()

    async def start(self):
        """Async startup."""
        if self.busclient is not None:
            await self.busclient.start()
        await self.modem.get_modem_info()
        await self.modem.listen_sms()
        await self.periodic.start()
