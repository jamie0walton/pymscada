import aiohttp
from datetime import datetime, timezone
import jwt
import logging
import time
from pymscada import BusClient, Periodic, TagFloat, TagInt


RESET = 0
TRY_HOST = 1
HOST_OK = 2
TRY_ALT_HOST = 3
ALT_HOST_OK = 4
DISABLE = 5


def utc_seconds(ds: str) -> int:
    return int(datetime.fromisoformat(ds).astimezone(timezone.utc).timestamp())


class TDSConnector():
    def __init__(self, private_key: str, issuer: str, site: str, endpoint: str,
                 host: str, alt_host: str, get: str, put: str, corr_id: str, instructions: list[dict], error_code_tag: str,
                 state_tag: str):
        with open(private_key, "r") as f:
            self.private_key = f.read()
        self.recv = None
        self.corr_id = corr_id
        self.issuer = issuer
        self.site = site
        self.endpoint = endpoint
        self.host = host
        self.alt_host = alt_host
        self.failed_time = None
        self.get = get
        self.put = put
        self.auth = "ACKA"
        self.timeout = aiohttp.ClientTimeout(total=90)
        self.session = None
        self.dispatches = []
        self.acka_corr_id = ''
        self.periodic = Periodic(self.poll, 10.0)
        self.error_code_tag = TagInt(error_code_tag)
        self.state_tag = TagInt(state_tag)
        self.instructions = instructions
        for d in self.instructions:
            d['tag'] = TagFloat(d['tag'])
            d['sequenceNumber'] = 0

    async def close_session(self):
        if self.session is not None:
            await self.session.close()
            self.session = None

    def make_token(self):
        self.now = int(time.time())
        payload = {
            "iss": self.issuer,
            "nbf": self.now - 90,
            "exp": self.now + 90
        }
        self.token = jwt.encode(payload, self.private_key, algorithm="RS256", headers=None)
        if isinstance(self.token, bytes):
            self.token = self.token.decode("utf-8")

    async def get_dispatches(self):
        """Get from Host or Alt Host, switching if necessary."""
        if self.session is None:
            self.session = aiohttp.ClientSession(timeout=self.timeout)
            logging.info('TDS session created')
        self.make_token()
        if self.state_tag.value in [TRY_HOST, HOST_OK]:
            host = self.host
        else:
            host = self.alt_host
        self.get_url = f"{host}{self.endpoint}/{self.get}"
        corr_id = f"_{self.corr_id}_{self.now}_"
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Correlation-Id": corr_id,
        }
        try:
            async with self.session.get(self.get_url, headers=headers) as response:
                logging.info(f"GET corr_id: {corr_id} status: {response.status}")
                if response.status == 200:
                    self.error_code_tag.value = 200
                    self.failed_time = None
                    self.recv = await response.json()
                    logging.debug(f"GET {corr_id} {self.recv}")
                else:
                    self.recv = None
                    self.error_code_tag.value = response.status
                    if self.failed_time is None:
                        self.failed_time = time.time()
                    logging.debug(f"GET error {corr_id} {response.status}")
        except Exception as e:
            self.recv = None
            self.error_code_tag.value = 0
            if self.failed_time is None:
                self.failed_time = time.time()
            logging.warning(f"GET corr_id: {corr_id} error: {e}")
        state = self.state_tag.value
        if state == TRY_HOST:
            if self.failed_time is None:
                logging.info('success TRY_HOST to HOST_OK')
                self.state_tag.value = HOST_OK
            elif time.time() - self.failed_time > 60:
                logging.info('failed TRY_HOST to TRY_ALT_HOST')
                self.state_tag.value = TRY_ALT_HOST
                self.failed_time = None
        elif state == HOST_OK:
            if self.failed_time is not None:
                logging.info('failed HOST_OK to TRY_HOST')
                self.state_tag.value = TRY_HOST
        elif state == TRY_ALT_HOST:
            if self.failed_time is None:
                logging.info('success TRY_ALT_HOST to ALT_HOST_OK')
                self.state_tag.value = ALT_HOST_OK
            elif time.time() - self.failed_time > 60:
                logging.info('failed TRY_ALT_HOST to TRY_HOST')
                self.state_tag.value = TRY_HOST
                self.failed_time = None
        elif state == ALT_HOST_OK:
            if self.failed_time is not None:
                logging.info('failed ALT_HOST_OK to TRY_ALT_HOST')
                self.state_tag.value = TRY_ALT_HOST

    def process_dispatch(self):
        """Handle a single dispatch for a single dispatch type."""
        if self.recv is None:
            return
        self.dispatches = []
        time_s = int(time.time())
        for dispatch in self.recv:
            endpoint = dispatch['dispatchEndpointName']
            if endpoint != self.endpoint:
                logging.warning(f"Ignore endpoint {endpoint}")
                continue
            dispatch_group = dispatch['dispatchGroupName']
            corr_id = dispatch['correlationId']
            for i in self.instructions:
                if dispatch_group != i['group']:
                    continue
                if dispatch[i['class']] is None:
                    continue
                nodes = dispatch[i['class']]['nodes']
                for node in nodes:
                    if node['name'] != self.site:
                        logging.warning(f"Ignore node {node['name']}")
                        continue
                    for pv in node['primaryValues']:
                        dt = pv['dispatchType']
                        dv = pv['dispatchValue']
                        seq_no = dispatch['sequenceNumber']
                        dtime = pv['dispatchTime']
                        ds = utc_seconds(dtime)
                        if dt != i['type']:
                            logging.warning(f"Ignoring {dt} {dv:.2f} {dtime}")
                            continue
                        if time_s - ds > 300:
                            logging.warning(f"> 5m old {dt} {dv:.2f} {dtime}")
                            continue
                        if seq_no <= i['sequenceNumber']:
                            logging.warning(f"Ignore sequence {seq_no}")
                            continue
                        i['tag'].value = dv
                        i['sequenceNumber'] = seq_no
                        self.dispatches.append({
                            'correlationId': corr_id,
                            'dispatchGroupName': dispatch_group,
                            'sequenceNumber': seq_no,
                            'dispatchType': dt,
                            'dispatchValue': dv,
                            'dispatchTime': dtime
                        })
        if len(self.dispatches):
            logging.info(f"Dispatches: {self.dispatches}")

    async def acka_dispatches(self, dispatch: dict):
        corr_id = dispatch['correlationId']
        if corr_id == self.acka_corr_id or self.session is None:
            return
        self.make_token()
        if self.state_tag.value in [TRY_HOST, HOST_OK]:
            host = self.host
        else:
            host = self.alt_host
        put_url = f"{host}{self.endpoint}/{self.put}"
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Correlation-Id": corr_id,
        }
        try:
#             ack_body = {
#                 "ackType": "ACK",
#                 "dispatchGroupName": dispatch['dispatch_group'],
#                 "sequenceNumber": dispatch['sequence_number'],
#             }
#             logging.info(f"ACK body: {ack_body}")
#             async with self.session.put(put_url, headers=headers,
#                                         json=ack_body) as response:
#                 status = response.status
#                 txt = await response.text()
#                 logging.info(f"ACK corr_id: {corr_id} status: {status} text: {txt}")
# #                if status != 200:
# #                    return
            acka_body = {
                "ackType": self.auth,
                "dispatchGroupName": dispatch['dispatchGroupName'],
                "sequenceNumber": dispatch['sequenceNumber']
            }
            logging.info(f"ACKA body: {acka_body}")
            async with self.session.put(put_url, headers=headers,
                                        json=acka_body) as response:
                status = response.status
                txt = await response.text()
                logging.info(f"ACKA corr_id: {corr_id} status: {status} text: {txt}")
                if status == 200:
                    self.acka_corr_id = corr_id
        except Exception as e:
            logging.warning(f"PUT ACKA corr_id: {corr_id} error: {e}")

    async def poll(self):
        if self.state_tag.value == DISABLE:
            await self.close_session()
            return
        if self.state_tag.value == RESET:
            await self.close_session()
            self.state_tag.value = TRY_HOST
        await self.get_dispatches()
        try:
            self.process_dispatch()
        except Exception as e:
            logging.warning(f"Error processing dispatch: {e}")
        if len(self.dispatches):
            for dispatch in self.dispatches:
                await self.acka_dispatches(dispatch)

    async def start(self):
        """Start polling."""
        self.state_tag.value = RESET
        await self.periodic.start()


class TDSClient:
    """Connect to bus on bus_ip:bus_port, read Transpower Dispatch Service."""

    def __init__(self, bus_ip: str = '127.0.0.1', bus_port: int = 1324,
                 **kwargs) -> None:
        """
        Connect to bus on bus_ip:bus_port.

        Makes connections to Modbus PLCs to read and write data.
        Event loop must be running.
        """
        self.config = kwargs
        self.busclient = None
        if bus_ip is not None:
            self.busclient = BusClient(bus_ip, bus_port,
                                       module='TDS Client')

    async def start(self):
        """Provide a TDS client."""
        if self.busclient is not None:
            await self.busclient.start()
        self.connection = TDSConnector(**self.config)
        await self.connection.start()
