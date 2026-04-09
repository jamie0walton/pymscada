import argparse
import asyncio
import time
from pymscada.bus_client import BusClient
from pymscada.bus_client_tag import TagSetNone


async def run(tagname: str, host: str, port: int) -> None:
    bc = BusClient(host, port, module='set_tag_none')
    await bc.start()
    t = TagSetNone(tagname)
    while t.id is None:
        await asyncio.sleep(0.02)
    t.set_value(None, int(time.time() * 1e6), 0)
    await asyncio.sleep(0.05)
    await bc.shutdown()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('tagname')
    ap.add_argument('-H', '--host', default='127.0.0.1')
    ap.add_argument('-p', '--port', type=int, default=1324)
    args = ap.parse_args()
    asyncio.run(run(args.tagname, args.host, args.port))


if __name__ == '__main__':
    main()
