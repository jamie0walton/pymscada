import asyncio
import ssl
import time
import aiohttp
import jwt


HOST = "https://dispatch-sim.transpower.co.nz/api/v1/dispatch/endpoints/BOP/"
# HOST = "https://dispatch-north.transpower.co.nz/api/v1/dispatch/endpoints/BOP/"
PRIVATE_KEY = "/home/jamie/private_key.pem"
# PRIVATE_KEY = "/home/jamie/ani_prod_private_key.pem"
ISSUER = "anidispatch@pioneerenergy.co.nz"
GET = "instructions/latest"
PUT = "acknowledgements"
SITE = "MAT1101 ANI0"


class TDSClient():
    def __init__(self):
        with open(PRIVATE_KEY, "r") as f:
            self.private_key = f.read()
        self.issuer = ISSUER
        self.site = SITE
        self.get_url = HOST + GET
        self.ack_url = HOST + PUT
        self.ssl_ctx = ssl.create_default_context()
        self.timeout = aiohttp.ClientTimeout(total=90)
        self.session = None
        self.auth = None
        self.correlation_id = None

    def make_token(self):
        self.now = int(time.time())
        payload = {
            "iss": self.issuer,
            "nbf": self.now - 90,
            "exp": self.now + 90,  # Transpower JWT validation includes nbf/exp with 300s max expiry [1](https://static.transpower.co.nz/public/bulk-upload/documents/GL-SD-1045%20Market%20Dispatch%20Integration%20-%20ICCP%20and%20Web%20Services%20Guideline.pdf?VersionId=1TseCSWjUG_8vZgQy2GzNSIPUNK5IsWB)
        }
        self.token = jwt.encode(payload, self.private_key, algorithm="RS256", headers=None)
        if isinstance(self.token, bytes):
            self.token = self.token.decode("utf-8")

    def ensure_session(self):        
        if self.session is None:
            self.session = aiohttp.ClientSession(timeout=self.timeout)

    async def get_dispatch(self):
        self.ensure_session()
        self.make_token()
        # if self.correlation_id is None:
        self.correlation_id = f"_initial_{self.now}_"
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Correlation-Id": self.correlation_id,
        }
        async with self.session.get(self.get_url, headers=headers) as response:
            if response.status == 200:
                return await response.json()
            else:
                print(f"GET failed: {response.status}")


async def main():
    tds = TDSClient()
    response = await tds.get_dispatch()
    print(response)


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
