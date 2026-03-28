"""WITS market offer upload client."""
import time
import requests
from requests_toolbelt import MultipartEncoder
from ms import Log, bid_period, bid_time
from datetime import datetime
import json

LOG = Log(__name__)


class WITSClient():
    """WITS market offer upload client."""

    def __init__(self, config: dict):
        """WITS market offer upload client."""
        LOG.info('WITSClient.__init__')
        self._dst_transition_dates = []
        self.config = config
        self.wits = config['wits']
        self.offer = config['offer']
        self.dryrun = config.get('dryrun', False)
        self.currentTagDict = {}
        self.futureTagDict = {}
        self.session = None

    def current_tag_update(self, tags: dict, utcSeconds=None):
        """Update the tagDict which are going to be sent."""
        LOG.info('WITSClient.current_tag_update')
        if utcSeconds is None:
            utcSeconds = int(time.time())
        startPeriod = bid_period(utcSeconds + 3660)
        bidStartTime_UTC = bid_time(utcSeconds+3660, startPeriod)
        currentTagDic = {}
        for service in self.offer['services']:
            for bidTime_utc in range(
                bidStartTime_UTC,
                bidStartTime_UTC + self.offer['horizon'] * 30 * 60,
                1800
            ):
                tradingDate_utc = datetime.fromtimestamp(bidTime_utc).\
                                  strftime("%d/%m/%Y")
                tagPeriod = bid_period(bidTime_utc)
                if tradingDate_utc not in currentTagDic:
                    currentTagDic[tradingDate_utc] = {}
                if tagPeriod in tags['MW_plan'].value['period']:
                    idx = tags['MW_plan'].value['period'].index(tagPeriod)
                elif tagPeriod in [47, 48]:
                    idx = tags['MW_plan'].value['period'].index(46)
                elif tagPeriod in [49, 50]:
                    idx = tags['MW_plan'].value['period'].index(48)
                currentTagDic[tradingDate_utc][tagPeriod] = \
                    tags['MW_plan'].value['setpoint'][idx]
        self.currentTagDict = currentTagDic

    def build_offer(self, tradingDict: dict):
        """Create offer string from updated tagDict."""
        LOG.info('WITSClient.build_offer')
        offerStringList = []

        bus = self.offer['bus']
        site = self.offer['site']
        maxOutput = self.offer['maxOutput']
        maxRampUpRate = self.offer['maxRampUpRate']
        maxRampDownRate = self.offer['maxRampDownRate']
        clientCode = self.offer['clientCode']
        freeText = ''
        complianceReason = ''

        for key in tradingDict:
            for sub_key in tradingDict[key]:
                if tradingDict[key][sub_key] is None:
                    tradingDict[key][sub_key] = 11
                offer_row = f"{bus},{site},0,{key},{sub_key},{maxOutput},"\
                    f"{maxRampUpRate},{maxRampDownRate},0,"\
                    f"{float(tradingDict[key][sub_key]):.3f},0,0,0,0,0,0,0,0,"\
                    f"{clientCode},{freeText},{complianceReason}"
                offerStringList.append(offer_row)
        return '\n'.join(offerStringList)

    def send_request(self, offerString: str, tags: dict):
        """Send offer to wits, returns sent offer as 'date_period_value'[]."""
        LOG.info('WITSClient.send_request')
        m = MultipartEncoder(
            fields={'filename': (
                'orders.csv', offerString, 'multipart/form-data; charset=UTF-8'
            ), 'order-type': (None, 'OFFER', 'text/plain')}
        )
        headers = {'X-API-Username': self.wits['user'],
                   'X-API-Token': self.wits['password'],
                   'Content-Type': m.content_type}
        # Prepared request headers, Host header is mandatory,
        # Accept-Encoding header is auto set as identity
        if self.session is None:
            time.sleep(15.0)
            self.session = requests.Session()
        req = requests.Request('POST', self.wits['host'], data=m,
                               headers=headers)
        prepped = self.session.prepare_request(req)
        LOG.info(f"{self.wits['host']} {self.wits['user']} "
                 f"{self.wits['password']} {headers}")
        try:
            resp = self.session.send(prepped)
            if (resp.status_code == 200):
                tags['_wits_status'].value = 'Connection_Success'
                # handling response info from with server
                resp_data = json.loads(resp.text)
                tags['_wits_upload_id'].value = resp_data['upload_id']
                tags['_wits_status_code'].value = resp.status_code
                tags['_wits_errors'].value = len(resp_data['upload_errors'])
                for error in resp_data['upload_errors']:
                    LOG.info('error in line: ' + str(error['line_no']))
            else:
                tags['_wits_status'].value = 'Communication_Fail'
                tags['_wits_status_code'].value = resp.status_code
        except requests.exceptions.ConnectionError as e:
            LOG.warn('Connection Error: ' + str(e))
            tags['_wits_status_code'].value = 1001
            self.session = None
        except requests.exceptions.HTTPError as e:
            LOG.warn('HTTPError: ' + str(e))
            tags['_wits_status_code'].value = 1002
            self.session = None
        except requests.exceptions.RequestException as e:
            LOG.warn('Oops: Something Else' + str(e))
            tags['_wits_status_code'].value = 1003
            self.session = None
        except Exception as err:
            LOG.warn(f"Error:{err}")

        offer_sent_wits = []
        for offer in offerString.split('\n'):
            offer_items = offer.split(',')
            offer_sent_wits.append(f"{offer_items[3]}_{offer_items[4]}"
                                   f"_{offer_items[9]}")
        return ','.join(offer_sent_wits)

    def send(self, tags: dict):
        """Send the offer to WITS."""
        LOG.info('WITSClient.send')
        offer_string = self.build_offer(self.currentTagDict)
        if not self.futureTagDict:
            LOG.info('sleeping, why?')
            time.sleep(1)  # TODO this is awfully optimistic, fix
        else:
            if self.dryrun:
                LOG.info('Dry run - not sending offer')
                tags['_wits_sent'].value = offer_string
            else:
                LOG.info('send offer')
                tags['_wits_sent'].value = self.send_request(offer_string,
                                                             tags)
                time.sleep(1)
            # log the first two trading period
            LOG.info(f'offer sent finished: {tags["_wits_sent"].value[:44]}')

        future_tag_dict = {}
        temp_sub_dict = {}
        for key in self.currentTagDict:
            for sub_key in self.currentTagDict[key]:
                temp_sub_dict[sub_key] = self.currentTagDict[key][sub_key]
            future_tag_dict[key] = temp_sub_dict
            temp_sub_dict = {}
        self.futureTagDict = future_tag_dict
