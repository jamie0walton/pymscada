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


class TDSConnector():
    def __init__(self, private_key: str, issuer: str, site: str, endpoint: str,
                 host: str, alt_host: str, get: str, put: str, corr_id: str, mw_set_tag: str, mvar_set_tag: str, error_code_tag: str, state_tag: str):
        with open(private_key, "r") as f:
            self.private_key = f.read()
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
        self.sequence_number = None
        self.dispatch = None
        self.periodic = Periodic(self.poll, 20.0)
        self.mw_set_tag = TagFloat(mw_set_tag)
        self.mvar_set_tag = TagFloat(mvar_set_tag)
        self.error_code_tag = TagInt(error_code_tag)
        self.state_tag = TagInt(state_tag)

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

    async def get_dispatch(self):
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
                    self.data = await response.json()
                else:
                    self.data = None
                    self.error_code_tag.value = response.status
                    if self.failed_time is None:
                        self.failed_time = time.time()
        except Exception as e:
            self.data = None
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
        if self.data is None:
            return
        try:
            self.dispatch = None
            dispatch = self.data[0]
            seq_no = dispatch['sequenceNumber']
            if seq_no == self.sequence_number:
                return
            self.sequence_number = seq_no
            endpoint = dispatch['dispatchEndpointName']
            if endpoint != self.endpoint:
                logging.warning(f"Endpoint {endpoint} is not {self.endpoint}")
                return
            corr_id = dispatch['correlationId']
            energy_dispatch = dispatch['energyDispatch']
            volts_dispatch = dispatch['voltageDispatch']
            if energy_dispatch is not None:
                node = energy_dispatch['nodes'][0]
            elif volts_dispatch is not None:
                node = volts_dispatch['nodes'][0]
            else:
                logging.warning('heartbeat')
                return
            if node['name'] != self.site:
                logging.warning(f"Invalid site {node['name']}")
                return
            dispatch_type = node['primaryValues'][0]['dispatchType']
            dispatch_value = node['primaryValues'][0]['dispatchValue']
            dispatch_time = node['primaryValues'][0]['dispatchTime']
            utc_seconds = int(datetime.fromisoformat(dispatch_time
                              ).astimezone(timezone.utc).timestamp())
            self.dispatch = {
                'dispatch_type': dispatch_type,
                'dispatch_value': dispatch_value,
                'dispatch_time': dispatch_time,
                'dispatch_time_utc': utc_seconds,
                'correlation_id': corr_id,
                'sequence_number': seq_no,
            }
            logging.warning(f"Dispatch: {self.dispatch}")
        except Exception as e:
            logging.warning(f"Exception {e} parsing {self.data}")

    def set_tag_values(self):
        if self.dispatch is None:
            return
        time_s = int(time.time())
        if time_s - self.dispatch['dispatch_time_utc'] > 1800:
            logging.warning(f"Dispatch > 30 minutes old, ignore dispatch")
            return
        if self.dispatch['dispatch_type'] == 'MW':
            self.mw_set_tag.value = self.dispatch['dispatch_value']
        elif self.dispatch['dispatch_type'] == 'MVAR':
            self.mvar_set_tag.value = self.dispatch['dispatch_value']
        else:
            logging.warning(f"Unknown dispatch type {self.dispatch['dispatch_type']}")
            return

    async def poll(self):
        if self.state_tag.value == RESET:
            await self.close_session()
            self.state_tag.value = TRY_HOST
        await self.get_dispatch()
        self.process_dispatch()
        self.set_tag_values()

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
