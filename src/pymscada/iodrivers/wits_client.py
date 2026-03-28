import asyncio
import aiohttp
import copy
import json
import logging
import time
from datetime import datetime
from pymscada import bid_period, bid_time, BusClient, TagDict, TagInt, TagStr

RESET = 0
TRY_HOST = 1
HOST_OK = 2
TRY_ALT_HOST = 3
ALT_HOST_OK = 4
DISABLE = 5


def url_join(base: str, path: str) -> str:
    return f"{base.rstrip('/')}/{path.lstrip('/')}"


class WITSConnector:
    def __init__(self, host: str, alt_host: str, put: str, user: str, password: str,
                 window: int, horizon: int, timeZone: str, bus: str, site: str,
                 startPeriod: int, maxOutput: float, maxRampUpRate: float,
                 maxRampDownRate: float, clientCode: str,
                 bid_tag: str, state_tag: str, sent_tag: str, upload_id_tag: str,
                 upload_time_tag: str, status_code_tag: str, service_type: str = 'MW'):
        self.host = host
        self.alt_host = alt_host
        self.put = put
        self.user = user
        self.password = password
        self.window = window
        self.horizon = horizon
        self.timeZone = timeZone
        self.bus = bus
        self.site = site
        self.startPeriod = startPeriod
        self.maxOutput = maxOutput
        self.maxRampUpRate = maxRampUpRate
        self.maxRampDownRate = maxRampDownRate
        self.clientCode = clientCode
        self.service_type = service_type
        self.timeout = aiohttp.ClientTimeout(total=90)
        self.session = None
        self.failed_time = None
        self.currentTagDict = {}
        self.futureTagDict = {}
        self.bid_tag = TagDict(bid_tag)
        self.state_tag = TagInt(state_tag)
        self.sent_tag = TagStr(sent_tag)
        self.upload_id_tag = TagStr(upload_id_tag)
        self.upload_time_tag = TagInt(upload_time_tag)
        self.status_code_tag = TagInt(status_code_tag)

    async def close_session(self):
        if self.session is not None:
            await self.session.close()
            self.session = None

    def on_change(self, tag):
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return
        loop.create_task(self.evaluate())

    def current_tag_update(self, utc_seconds=None):
        if utc_seconds is None:
            utc_seconds = int(time.time())
        plan = self.bid_tag.value
        start_p = bid_period(utc_seconds + self.window)
        bid_start = bid_time(utc_seconds + self.window, start_p)
        current = {}
        for bid_t in range(
                bid_start,
                bid_start + self.horizon * 30 * 60,
                1800):
            td = datetime.fromtimestamp(bid_t).strftime("%d/%m/%Y")
            tag_p = bid_period(bid_t)
            if td not in current:
                current[td] = {}
            periods = plan['period']
            if tag_p in periods:
                idx = periods.index(tag_p)
            elif tag_p in (47, 48):
                idx = periods.index(46)
            elif tag_p in (49, 50):
                idx = periods.index(48)
            else:
                continue
            current[td][tag_p] = plan['setpoint'][idx]
        self.currentTagDict = current

    def build_offer(self, trading_dict: dict) -> str:
        td = copy.deepcopy(trading_dict)
        rows = []
        free_text = ''
        compliance = ''
        for key in td:
            for sk in td[key]:
                if td[key][sk] is None:
                    td[key][sk] = 11
                row = (
                    f"{self.bus},{self.site},0,{key},{sk},"
                    f"{self.maxOutput},{self.maxRampUpRate},"
                    f"{self.maxRampDownRate},0,"
                    f"{float(td[key][sk]):.3f},0,0,0,0,0,0,0,0,"
                    f"{self.clientCode},{free_text},{compliance}")
                rows.append(row)
        return '\n'.join(rows)

    def dicts_equal(self) -> bool:
        return self.currentTagDict == self.futureTagDict

    def apply_host_state_transitions(self):
        st = self.state_tag.value
        if st == DISABLE:
            return
        if st == TRY_HOST:
            if self.failed_time is None:
                self.state_tag.value = HOST_OK
            elif time.time() - self.failed_time > 60:
                self.state_tag.value = TRY_ALT_HOST
                self.failed_time = None
        elif st == HOST_OK:
            if self.failed_time is not None:
                self.state_tag.value = TRY_HOST
        elif st == TRY_ALT_HOST:
            if self.failed_time is None:
                self.state_tag.value = ALT_HOST_OK
            elif time.time() - self.failed_time > 60:
                self.state_tag.value = TRY_HOST
                self.failed_time = None
        elif st == ALT_HOST_OK:
            if self.failed_time is not None:
                self.state_tag.value = TRY_ALT_HOST

    def post_base(self) -> str:
        st = self.state_tag.value
        if st in (TRY_HOST, HOST_OK):
            return self.host
        return self.alt_host

    async def do_post(self, offer_string: str) -> bool:
        if self.session is None:
            self.session = aiohttp.ClientSession(timeout=self.timeout)
        url = url_join(self.post_base(), self.put)
        form = aiohttp.FormData()
        form.add_field(
            'filename',
            offer_string,
            filename='orders.csv',
            content_type='multipart/form-data; charset=UTF-8')
        form.add_field('order-type', 'OFFER', content_type='text/plain')
        headers = {
            'X-API-Username': self.user,
            'X-API-Token': self.password,
        }
        ok = False
        try:
            async with self.session.post(
                    url, data=form, headers=headers) as resp:
                text = await resp.text()
                self.status_code_tag.value = resp.status
                if resp.status == 200:
                    self.failed_time = None
                    data = json.loads(text)
                    self.upload_id_tag.value = str(data['upload_id'])
                    self.upload_time_tag.value = int(time.time())
                    self.status_code_tag.value = resp.status
                    for err in data.get('upload_errors', []):
                        logging.info('error in line: %s', err.get('line_no'))
                    summary = self.offer_sent_summary(offer_string)
                    self.sent_tag.value = summary
                    logging.info('offer sent finished: %s', summary[:44])
                    ok = True
                else:
                    if self.failed_time is None:
                        self.failed_time = time.time()
                    logging.warning('POST failed: %s', resp.status)
        except aiohttp.ClientError as e:
            self.status_code_tag.value = 1001
            if self.failed_time is None:
                self.failed_time = time.time()
            logging.warning('POST failed: %s', e)
            await self.close_session()
        except json.JSONDecodeError as e:
            self.status_code_tag.value = 1002
            if self.failed_time is None:
                self.failed_time = time.time()
            logging.warning('POST JSON failed: %s', e)
        except Exception as e:
            self.status_code_tag.value = 1003
            if self.failed_time is None:
                self.failed_time = time.time()
            logging.warning('POST failed: %s', e)
            await self.close_session()
        self.apply_host_state_transitions()
        if ok:
            self.futureTagDict = copy.deepcopy(self.currentTagDict)
        return ok

    def offer_sent_summary(self, offer_string: str) -> str:
        parts = []
        for line in offer_string.split('\n'):
            if not line.strip():
                continue
            items = line.split(',')
            if len(items) > 10:
                parts.append(f"{items[3]}_{items[4]}_{items[9]}")
        return ','.join(parts)

    async def evaluate(self):
        async with self.eval_lock:
            st = self.state_tag.value
            if st == DISABLE:
                return
            force = False
            if st == RESET:
                await self.close_session()
                self.state_tag.value = TRY_HOST
                force = True
            if self.bid_tag.is_none:
                return
            try:
                self.current_tag_update()
            except (KeyError, TypeError, ValueError) as e:
                logging.warning('current_tag_update: %s', e)
                return
            if not force and self.futureTagDict and self.dicts_equal():
                return
            offer = self.build_offer(self.currentTagDict)
            if not offer.strip():
                return
            await self.do_post(offer)

    async def start(self):
        self.eval_lock = asyncio.Lock()
        self.bid_tag.add_callback(self.on_change, 0)
        self.state_tag.add_callback(self.on_change, 0)
        self.state_tag.value = RESET
        await self.evaluate()


class WITSClient:
    """Connect to bus, upload WITS market offers from MW_plan."""

    def __init__(self, bus_ip: str = '127.0.0.1', bus_port: int = 1324,
                 **kwargs) -> None:
        self.tag_names = kwargs.pop('tags')
        bus_ip = kwargs.pop('bus_ip', bus_ip)
        bus_port = kwargs.pop('bus_port', bus_port)
        self.connector_kwargs = kwargs
        self.busclient = None
        if bus_ip is not None:
            self.busclient = BusClient(bus_ip, bus_port, module='WITS Client')
        self.connection = None

    async def start(self):
        if self.busclient is not None:
            await self.busclient.start()
        self.connection = WITSConnector(self.tag_names, **self.connector_kwargs)
        await self.connection.start()
