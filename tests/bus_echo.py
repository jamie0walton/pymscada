"""Connect to the test bus server and echo values."""
import asyncio
from functools import partial
import sys
from pymscada.bus_client import BusClient
from pymscada.tag import Tag


def callback(a: Tag, b: Tag):
    """Map values from tag to tag."""
    a.value = b.value


def rta_handler(tag: Tag):
    """__bus_echo__."""

    def rta(data: dict):
        """Process request set."""
        nonlocal tag
        if data == 'ping':
            tag.value = 'pong'

    return rta


async def main(port):
    """Set up maps."""
    tag = Tag('__bus_echo__', str)
    tag.value = 'started'
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
    client = BusClient(port=port)
    client.add_callback_rta(tag.name, rta_handler(tag))
    await client.start()
    await asyncio.get_event_loop().create_future()

if __name__ == '__main__':
    asyncio.run(main(int(sys.argv[1])))
