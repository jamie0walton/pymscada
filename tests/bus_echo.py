"""Connect to the test bus server and echo values."""
import asyncio
from functools import partial
import sys
from pymscada.bus_client import BusClient
from pymscada.tag import Tag


def callback(a: Tag, b: Tag):
    """Map values from tag to tag."""
    a.value = b.value


def rqs_handler(tag: Tag):
    """__bus_echo__."""

    def rqs(tagname: str, data: dict):
        """Process request set."""
        nonlocal tag
        if data['type'] == 'ping':
            tag.value = 'pong'

    return rqs


async def main(port):
    """Set up maps."""
    tag = Tag('__bus_echo__', str)
    tag.value = 'started'
    tag.add_rqs(rqs_handler(tag))
    tag1 = Tag('one', str)
    tag2 = Tag('two', str)
    tag1.add_callback(partial(callback, tag2))
    tag3 = Tag('three', int)
    tag4 = Tag('four', int)
    tag3.add_callback(partial(callback, tag4))
    tagpo = Tag('pipeout', int)
    tagpi = Tag('pipein', int)
    tagpo.add_callback(partial(callback, tagpi))
    tagspo = Tag('spipeout', str)
    tagspi = Tag('spipein', str)
    tagspo.add_callback(partial(callback, tagspi))
    busclient = BusClient(port=port)
    await busclient.run_forever()


if __name__ == '__main__':
    asyncio.run(main(int(sys.argv[1])))
