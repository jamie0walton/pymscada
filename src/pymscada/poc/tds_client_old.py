"""Transpower Dispatch Service client class."""
import asyncio
import time
import requests
import jwt
from ms.log import Log
from ms.app_v2 import BusApp

LOG = Log(__name__)

CONNECT = 0
DISCONNECT = 1

READ_ONLY = 0
ACKA_MANUAL = 1
ACKQ_QUERY = 2
AUTOMATIC = 3


class BearerAuth(requests.auth.AuthBase):
    """Subclassed for Transpower web services authentication."""

    def __init__(self, issuer, private_key):
        """Only requires the token."""
        self.issuer = issuer
        self.private_key = private_key

    def __call__(self, request):
        """Return the auth header Transpower is looking for."""
        LOG.debug('BearerAuth create token')
        current_time = int(time.time())
        payload = {
            'nbf': current_time - 90,
            'exp': current_time + 90,
            'iss': self.issuer
        }
        self.token = jwt.encode(
            payload, self.private_key, algorithm='RS256'
        ).decode('utf-8')
        request.headers['Authorization'] = 'Bearer ' + self.token
        return request


class TDSClient():
    """TDS dispatch client."""

    def __init__(self, app: BusApp):
        """TDS dispatch client."""
        LOG.info("__init__")
        self.app = app
        self.config = app.config
        with open(app.config['private_key']) as f:
            self.private_key = f.read()
        self.issuer = app.config['issuer']
        self.bearerauth = BearerAuth(self.issuer, self.private_key)
        self.dryrun = app.config.get('dryrun', False)
        self.session = None
        self.sleepy = 1.0
        self.site = app.config['site']
        self.get_url = app.config['host'] + app.config['get']
        self.ack_url = app.config['host'] + app.config['put']
        self.mw_sendack = False
        self.mw_newNo = None
        self.mw_No = None
        self.mw_ID = None
        self.mw_MW = None
        self.mw_RESS = None
        self.mw_RESF = None
        self.mvar_sendack = False
        self.mvar_newNo = None
        self.mvar_No = None
        self.mvar_ID = None
        self.mvar_MVAR = None
        self.mvar_VOLT = None

    def connected(self):
        """Timeout and refresh session."""
        LOG.info("connected")
        if self.app.ctag('connect').value == DISCONNECT:
            LOG.info('request_handler Session set to None')
            self.session = None
            return False
        return True

    async def ensure_session(self):
        """TODO ensure that a session is available."""
        LOG.info("ensure_session")
        if self.session is None:
            await asyncio.sleep(self.sleepy)
            self.sleepy = 60.0
            self.session = requests.Session()

    def send_ack(self, ack_type: str, group: str):
        """Blocking. Put all acknowledge handling in a single place."""
        LOG.debug('send_ack')
        if group == 'energyMW':
            gn = 'energy'
            sequence = self.mw_No
            correlation = self.mw_ID
        elif group == 'voltageMVAR':
            gn = 'voltage'
            sequence = self.mvar_No
            correlation = self.mvar_ID
        else:
            LOG.error(f"send_ack {group} invalid")
            return
        try:
            response = self.session.put(
                self.ack_url,
                timeout=6.0,
                auth=self.bearerauth,
                headers={'Correlation-Id': correlation},
                json={'ackType': ack_type,
                      'dispatchGroupName': gn,
                      'sequenceNumber': sequence}
            )
            LOG.warn(f"send_ack {group} {ack_type} {sequence} {correlation}"
                     f" {response.content}")
            if ack_type == 'ACK':
                self.app.ctag('acktime').value = int(time.time())
            elif ack_type == 'ACKA':
                self.app.ctag('ackatime').value = int(time.time())
            elif ack_type == 'ACKQ':
                self.app.ctag('ackqtime').value = int(time.time())
        except (
            requests.HTTPError, requests.ConnectionError, requests.Timeout
        ) as err:
            LOG.info(f"send_ack http error: {err}")
        except Exception as err:
            LOG.warn(f"send_ack Error:{err}")

    def parse_json(self, tp_json):
        """Extract MW and MVAR setpoints from Transpower dispatch."""
        LOG.info("parse_json")
        try:
            for a in tp_json:
                LOG.info(f"parse_json {a}")
                if a['dispatchGroupName'] == 'energy':
                    self.mw_newNo = a['sequenceNumber']
                    self.mw_ID = a['correlationId']
                    for b in a['energyDispatch']['nodes']:
                        if b['name'] != self.site:
                            continue
                        else:
                            for c in b['primaryValues']:
                                if c['dispatchType'] == 'MW':
                                    self.mw_MW = c['dispatchValue']
                                    LOG.warn(f"parse_json {self.mw_MW} MW")
                                elif c['dispatchType'] == 'RESS':
                                    self.mw_RESS = c['dispatchValue']
                                    LOG.warn(f"parse_json {self.mw_RESS} RESS")
                                elif c['dispatchType'] == 'RESF':
                                    self.mw_RESF = c['dispatchValue']
                                    LOG.warn(f"parse_json {self.mw_RESF} RESF")
                elif a['dispatchGroupName'] == 'voltage':
                    self.mvar_newNo = a['sequenceNumber']
                    self.mvar_ID = a['correlationId']
                    for b in a['voltageDispatch']['nodes']:
                        if b['name'] != self.site:
                            continue
                        else:
                            for c in b['primaryValues']:
                                if c['dispatchType'] == 'MVAR':
                                    self.mvar_MVAR = c['dispatchValue']
                                    LOG.warn(
                                        f"parse_json {self.mvar_MVAR} MVAR"
                                    )
                                elif c['dispatchType'] == 'VOLT':
                                    self.mvar_VOLT = c['dispatchValue']
                                    LOG.warn(
                                        f"parse_json {self.mvar_VOLT} VOLT"
                                    )
        except KeyError:
            LOG.error('parse_json Transpower structure unexpected')

    def get_dispatch(self):
        """Blocking. Get dispatch from Transpower and issue ACK."""
        LOG.info("get_dispatch")
        try:
            response = self.session.get(
                self.get_url,
                timeout=9006.0,
                auth=self.bearerauth,
                headers={'Correlation-Id': '_null_correlation_id_'}
            )
            self.app.ctag('errorcode').value = response.status_code
            LOG.debug(f"get_dispatch Status code:{response.status_code}")
            if response.status_code in [200, 202]:
                self.parse_json(response.json())  # updates tds
                self.mw_sendack = False
                self.mvar_sendack = False
                if self.mw_No != self.mw_newNo:
                    self.mw_No = self.mw_newNo
                    LOG.info(f"get_dispatch energy dispatch {self.mw_No} "
                             f"{self.mw_ID} {self.mw_MW}")
                    # follow TP software, conflict with doc...
                    self.mw_sendack = True
                    self.app.ctag('mw_dispatch').value = self.mw_MW
                    self.send_ack('ACK', 'energyMW')
                    if self.app.ctag('mw_control').value == ACKA_MANUAL:
                        self.send_ack('ACKA', 'energyMW')
                    elif self.app.ctag('mw_control').value == ACKQ_QUERY:
                        self.send_ack('ACKQ', 'energyMW')
                if self.mvar_No != self.mvar_newNo:
                    self.mvar_No = self.mvar_newNo
                    LOG.info(f"get_dispatch voltage dispatch {self.mvar_No} "
                             f"{self.mvar_ID} {self.mvar_MVAR}")
                    self.mvar_sendack = True
                    self.app.ctag('mvar_dispatch').value = self.mvar_MVAR
                    self.send_ack('ACK', 'voltageMVAR')
                    if self.app.ctag('mvar_control').value == ACKA_MANUAL:
                        self.send_ack('ACKA', 'voltageMVAR')
                    elif self.app.ctag('mvar_control').value == ACKQ_QUERY:
                        self.send_ack('ACKQ', 'voltageMVAR')
            else:
                self.session = None
        except (requests.HTTPError, requests.ConnectionError,
                requests.Timeout) as err:
            LOG.error(f"get_dispatch http error: {err}")
            self.session = None
            self.app.ctag('errorcode').value = 1001
        except Exception as err:
            LOG.error(f"get_dispatch Error: {err}")

    def post_request_ack(self, group):
        """Blocking. Send ACKA or ACKQ for energy or voltage dispatch."""
        LOG.debug('post_request_ack')
        if self.mw_sendack and group == 'energyMW':
            self.mw_sendack = False
            if self.app.ctag('mw_control').value == ACKA_MANUAL:
                self.send_ack('ACKA', group)
            elif self.app.ctag('mw_control').value == ACKQ_QUERY:
                self.send_ack('ACKQ', group)
            elif self.app.ctag('mw_control').value == AUTOMATIC:
                dispatch = self.app.ctag('mw_dispatch').value
                feedback = self.app.ctag('mw_feedback').value
                if abs(dispatch - feedback) < 0.95:
                    self.send_ack('ACKA', group)
                else:
                    self.send_ack('ACKQ', group)
        elif self.mvar_sendack and group == 'voltageMVAR':
            self.mvar_sendack = False
            if self.app.ctag('mvar_control').value == ACKA_MANUAL:
                self.send_ack('ACKA', group)
            elif self.app.ctag('mvar_control').value == ACKQ_QUERY:
                self.send_ack('ACKQ', group)
            elif self.app.ctag('mvar_control').value == AUTOMATIC:
                dispatch = self.app.ctag('mvar_dispatch').value
                feedback = self.app.ctag('mvar_feedback').value
                if abs(dispatch - feedback) < 0.5:
                    self.send_ack('ACKA', group)
                else:
                    self.send_ack('ACKQ', group)