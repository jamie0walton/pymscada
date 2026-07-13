# this is a snip from older working code.

class SMSModem():
    """Communicate with SMS Modem."""

    def __init__(self, smsqueue: asyncio.Queue, almqueue: asyncio.Queue,
                 sendurl: str, recvport: int, username: str, password: str):
        """SMS web client and server."""
        self.dryrun = False
        self.smsqueue = smsqueue
        self.almqueue = almqueue
        self.sendurl = sendurl
        self.recvport = recvport
        self.username = username
        self.password = password
        self.phone = set()
        self.names = {}
        self.modemip = '192.168.1.1'
        self.port = 1089
        self.info = 'info not configured'

    def add_phone(self, phone: str, name: str):
        """Add phone number."""
        self.phone.add(phone)
        self.names[phone] = name

    async def post_handler(self, request):
        """Handle SMS POST messages."""
        data = await request.post()
        message = {
            'sender': '',
            'text': ''
        }
        if 'Sender' in data:
            message['sender'] = data['Sender']
        if 'Text' in data:
            message['text'] = b64decode(data['Text']).decode()
        LOG.warn(f"got {message}")
        if message['text'].lower().startswith('ack') or \
                message['text'].lower().startswith('ok') or \
                message['text'].lower().startswith('got') or \
                message['text'].lower().startswith('thank') or \
                message['text'].lower().startswith('done'):
            if message['sender'] in self.phone:
                name = f"{message['sender']} {self.names[message['sender']]}"
                self.almqueue.put_nowait(
                    {'action': 'ACK', 'sender': name}
                )
            else:
                LOG.warn("not an operator, cannot ACK")
        elif message['text'].lower().startswith('info'):
            self.smsqueue.put_nowait({
                'to': message['sender'],
                'header': 'INFO',
                'message': self.info
            })
        return web.Response(text="OK\n")

    async def send_message(self):
        """
        Send SMS picked from smsqueue.
        Add message to queue as a dict with 'to', 'header' and
        'message' keys, all: str.
        """
        async with ClientSession() as session:
            while True:
                tosend = await self.smsqueue.get()
                to: str = tosend['to']
                if to.startswith('+64'):
                    to = '0' + to[3:]
                if len(tosend['message']):
                    msg = tosend['header'] + '\n' + tosend['message']
                else:
                    msg = tosend['header']
                LOG.warn(f"SMSModem sending {tosend}")
                if not self.dryrun:
                    async with session.post(
                        self.sendurl,
                        data={
                            'username': self.username,
                            'password': self.password,
                            'number': to,
                            'text': msg
                        }
                    ) as resp:
                        if resp.status != 200:
                            LOG.warn(f"SMSModem send error {resp.status}")

    async def start(self):
        """Start web server for SMS POST messages."""
        self.ws = web.Application()
        self.ws.add_routes([
            web.post('/', self.post_handler)
        ])
        self.runner = web.AppRunner(self.ws, access_log=None)
        await self.runner.setup()
        self.site = web.TCPSite(self.runner, '0.0.0.0', self.port)
        await self.site.start()
        asyncio.create_task(self.send_message())

