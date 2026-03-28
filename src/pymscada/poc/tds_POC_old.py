"""From a prior version of pymscada. Many bus and tag elements have changed. The interface to transpower, however, worked."""
HOST = "https://dispatch-sim.transpower.co.nz/api/v1/dispatch/endpoints/BOP/"
# HOST = "https://dispatch-north.transpower.co.nz/api/v1/dispatch/endpoints/BOP/"
PRIVATE_KEY = "/home/jamie/private_key.pem"
# PRIVATE_KEY = "/home/jamie/ani_prod_private_key.pem"
ISSUER = "anidispatch@pioneerenergy.co.nz"
GET = "instructions/latest"
PUT = "acknowledgements"
SITE = "MAT1101 ANI0"
NAME = "PERL"  # used in the correlation IO when not defined by dispatch

"""Transpower Dispatch Service client class."""
import asyncio
import time
import requests
import jwt
import logging
import time


logging.basicConfig(level=logging.DEBUG)
logging.getLogger("urllib3").setLevel(logging.DEBUG)
logging.getLogger("requests.packages.urllib3").setLevel(logging.DEBUG)


ACK_AS = "A"  # A or Q

READ_ONLY = 0
ACKA_MANUAL = 1
ACKQ_QUERY = 2
AUTOMATIC = 3

class BearerAuth(requests.auth.AuthBase):
    """Subclassed for Transpower web services authentication."""

    def __init__(self, issuer, private_key):
        """Only requires the token."""
        print(f"Issuer: {issuer}")
        self.issuer = issuer
        self.private_key = private_key

    def __call__(self, request):
        """Return the auth header Transpower is looking for."""
        print('BearerAuth create token')
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
        print("Authorization header set:", request.headers['Authorization'])
        return request


class TDSClient():
    """TDS dispatch client."""

    def __init__(self):
        """TDS dispatch client."""
        with open(PRIVATE_KEY) as f:
            self.private_key = f.read()
        self.issuer = ISSUER
        self.bearerauth = BearerAuth(self.issuer, self.private_key)
        self.session = None
        self.site = SITE
        self.get_url = HOST + GET
        self.ack_url = HOST + PUT

    def ensure_session(self):
        """TODO ensure that a session is available."""
        print("ensure_session")
        if self.session is None:
            self.session = requests.Session()
            self.session.trust_env = False
            self.session.headers.clear()  # Prune extraneous default headers

    def get_dispatch(self):
        """Blocking. Get dispatch from Transpower and issue ACK."""
        print("get_dispatch")
        if self.session is None:
            print("Session is None")
            return
        try:
            current_time = int(time.time())
            correlation_id = f"_{NAME}_{current_time}_"
            response = self.session.get(
                self.get_url,
                timeout=6.0,
                auth=self.bearerauth,
                headers={'Correlation-Id': correlation_id}
            )
            print(f"Correlation ID: {correlation_id}")
            print(f"get_dispatch Status code:{response.status_code}")
            print(response.text)
        except Exception as e:
            print(f"Exception {e}")


def main():
    print(time.localtime())
    print(HOST)
    print(PRIVATE_KEY)
    print(ISSUER)
    tds = TDSClient()
    tds.ensure_session()
    time.sleep(0.5)
    tds.get_dispatch()


if __name__ == "__main__":
    main()
