"""Main server entry point."""
import asyncio
import argparse
import logging
from .bus_server import BusServer


def args():
    """Read commandline arguments."""
    parser = argparse.ArgumentParser(
        prog='pymscada',
        description='Connect IO, logic, applications and webpage UI.',
        epilog='Python MobileSCADA.'
    )
    commands = ['run']
    components = ['bus', 'wwwserver']
    parser.add_argument('action', type=str, choices=commands, metavar='action',
                        help=f'select one of: {", ".join(commands)}')
    parser.add_argument('component', type=str, nargs='?', choices=components,
                        metavar='component',
                        help='all if empty, otherwise: '
                        f'{", ".join(components)}')
    parser.add_argument('-c', '--config', metavar='file',
                        help='yaml file.')
    parser.add_argument('-v', '--verbose', action='store_true',
                        help="Set level to logging.INFO.")
    return parser.parse_args()


def run():
    """Run bus and wwwserver."""
    opts = args()
    if opts.verbose:
        logging.basicConfig(level=logging.INFO)
    action = (opts.action, opts.component)
    if action == ('run', 'bus'):
        busserver = BusServer()
        asyncio.run(busserver.run_forever())
    else:
        logging.warning(f'no action {action}')
