"""Main server entry point."""
import asyncio
import argparse
import logging
from .config import Config
from .www_server import WwwServer
from .console import Console
from .history import History
from .bus_server import BusServer


def args():
    """Read commandline arguments."""
    parser = argparse.ArgumentParser(
        prog='pymscada',
        description='Connect IO, logic, applications and webpage UI.',
        epilog='Python MobileSCADA.'
    )
    commands = ['run']
    components = ['bus', 'console', 'wwwserver', 'history']
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


def run():
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
        if options.component != 'bus':
            tag_info = dict(Config(options.tags))
    except FileNotFoundError:
        logging.warning('Tag file not found, only OK for bus.')
    action = (options.action, options.component)
    if action == ('run', 'bus'):
        busserver = BusServer(**config)
        asyncio.run(busserver.run_forever())
    elif action == ('run', 'console'):
        console = Console()
        asyncio.run(console.run_forever())
    elif action == ('run', 'wwwserver'):
        wwwserver = WwwServer(tag_info=tag_info, **config)
        asyncio.run(wwwserver.run_forever())
    elif action == ('run', 'history'):
        history = History(tag_info=tag_info, **config)
        asyncio.run(history.run_forever())
    else:
        logging.warning(f'no action {action}')
