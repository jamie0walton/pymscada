"""Main server entry point."""
import argparse
import asyncio
import logging
from pymscada.bus_server import BusServer
from pymscada.config import Config
from pymscada.console import Console
from pymscada.files import Files
from pymscada.history import History
from pymscada.simulate import Simulate
from pymscada.www_server import WwwServer


def args():
    """Read commandline arguments."""
    parser = argparse.ArgumentParser(
        prog='pymscada',
        description='Connect IO, logic, applications and webpage UI.',
        epilog='Python MobileSCADA.'
    )
    commands = ['run']
    components = ['bus', 'console', 'wwwserver', 'history', 'files',
                  'simulate']
    parser.add_argument('action', type=str, choices=commands, metavar='action',
                        help=f'select one of: {", ".join(commands)}')
    parser.add_argument('component', type=str, nargs='?', choices=components,
                        metavar='component', help='all if empty, otherwise: '
                        f'{", ".join(components)}')
    parser.add_argument('--config', metavar='file',
                        help='Config file, default is "[component].yaml".')
    parser.add_argument('--tags', metavar='file',
                        help='Tags file, default is "tags.yaml".')
    parser.add_argument('--verbose', action='store_true',
                        help="Set level to logging.INFO.")
    parser.add_argument('--path', metavar='folder',
                        help="Working folder, used for history.")
    return parser.parse_args()


async def run():
    """Run bus and wwwserver."""
    options = args()
    if options.verbose:
        logging.basicConfig(level=logging.INFO)
    config = {}
    if options.config is None:
        options.config = f'{options.component}.yaml'
    if options.tags is None:
        options.tags = 'tags.yaml'
    try:
        config = Config(options.config)
    except FileNotFoundError:
        logging.warning('Config file not found, using defaults.')
    try:
        if options.component not in ['bus', 'files']:
            tag_info = dict(Config(options.tags))
    except FileNotFoundError:
        logging.warning('Tag file not found, OK for bus and files.')
    if options.action == 'run':
        if options.component == 'bus':
            bus = BusServer(**config)
            await bus.start()
        elif options.component == 'console':
            console = Console()
            await console.start()
        elif options.component == 'wwwserver':
            www = WwwServer(tag_info=tag_info, **config)
            await www.start()
        elif options.component == 'history':
            history = History(tag_info=tag_info, **config)
            await history.start()
        elif options.component == 'files':
            files = Files(**config)
            await files.start()
        elif options.component == 'simulate':
            sim = Simulate(tag_info=tag_info, **config)
            await sim.start()
        else:
            logging.warning(f'no run {options.component}')
    else:
        logging.warning(f'no {options.action}')
    await asyncio.get_event_loop().create_future()
