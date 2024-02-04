"""Main server entry point."""
import argparse
import asyncio
import logging
from pymscada.bus_server import BusServer
from pymscada.checkout import checkout
from pymscada.config import Config
from pymscada.console import Console
from pymscada.files import Files
from pymscada.history import History
from pymscada.iodrivers.logix_client import LogixClient
from pymscada.iodrivers.modbus_client import ModbusClient
from pymscada.iodrivers.modbus_server import ModbusServer
from pymscada.iodrivers.snmp_client import SnmpClient
from pymscada.simulate import Simulate
from pymscada.www_server import WwwServer
from pymscada.validate import validate


def args():
    """Read commandline arguments."""
    parser = argparse.ArgumentParser(
        prog='pymscada',
        description='Connect IO, logic, applications and webpage UI.',
        epilog='Python MobileSCADA.'
    )
    commands = ['bus', 'console', 'wwwserver', 'history', 'files',
                'logixclient',
                'modbusserver', 'modbusclient',
                'snmpclient',
                'simulate', 'checkout',
                'validate']
    parser.add_argument('module', type=str, choices=commands, metavar='action',
                        help=f'select one of: {", ".join(commands)}')
    parser.add_argument('--config', metavar='file',
                        help='Config file, default is "[module].yaml".')
    parser.add_argument('--tags', metavar='file',
                        help='Tags file, default is "tags.yaml".')
    parser.add_argument('--verbose', action='store_true',
                        help="Set level to logging.INFO.")
    parser.add_argument('--path', metavar='folder',
                        help="Working folder, used for history and validate.")
    parser.add_argument('--overwrite', action='store_true', default=False,
                        help='checkout may overwrite files, CARE!')
    return parser.parse_args()


async def run():
    """Run bus and wwwserver."""
    options = args()
    if options.verbose:
        logging.basicConfig(level=logging.INFO)
    if options.config is None:
        options.config = f'{options.module}.yaml'
    if options.tags is None:
        options.tags = 'tags.yaml'
    if options.module == 'bus':
        config = Config(options.config)
        module = BusServer(**config)
    elif options.module == 'console':
        module = Console()
    elif options.module == 'wwwserver':
        config = Config(options.config)
        tag_info = dict(Config(options.tags))
        module = WwwServer(tag_info=tag_info, **config)
    elif options.module == 'history':
        config = Config(options.config)
        tag_info = dict(Config(options.tags))
        module = History(tag_info=tag_info, **config)
    elif options.module == 'files':
        config = Config(options.config)
        module = Files(**config)
    elif options.module == 'logixclient':
        config = Config(options.config)
        module = LogixClient(**config)
    elif options.module == 'modbusclient':
        config = Config(options.config)
        module = ModbusClient(**config)
    elif options.module == 'modbusserver':
        config = Config(options.config)
        module = ModbusServer(**config)
    elif options.module == 'snmpclient':
        config = Config(options.config)
        module = SnmpClient(**config)
    elif options.module == 'simulate':
        config = Config(options.config)
        tag_info = dict(Config(options.tags))
        module = Simulate(tag_info=tag_info, **config)
    elif options.module == 'checkout':
        checkout(overwrite=options.overwrite)
        return
    elif options.module == 'validate':
        r, e = validate(options.path)
        if r == True:
            print(f'Config files in {options.path} valid.')
        else:
            print(e)
        return
    else:
        logging.warning(f'no {options.module}')
    await module.start()
    await asyncio.get_event_loop().create_future()
