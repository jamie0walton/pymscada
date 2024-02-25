"""Main server entry point."""
import argparse
import asyncio
from importlib.metadata import version
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
from pymscada.www_server import WwwServer
from pymscada.validate import validate


async def bus(options):
    """Return bus module."""
    config = Config(options.config)
    return BusServer(**config)


async def wwwserver(options):
    """Return wwwserver module."""
    config = Config(options.config)
    tag_info = dict(Config(options.tags))
    return WwwServer(tag_info=tag_info, **config)


async def history(options):
    """Return history module."""
    config = Config(options.config)
    tag_info = dict(Config(options.tags))
    return History(tag_info=tag_info, **config)


async def files(options):
    """TODO Return files module."""
    config = Config(options.config)
    return Files(**config)


async def console(_options):
    """TODO Return console module."""
    return Console()


async def _checkout(options):
    """Checkout files in current working directory."""
    checkout(overwrite=options.overwrite)
    return


async def _validate(options):
    """Validate config files."""
    r, e, p = validate(options.path)
    if r:
        print(f'Config files in {p} valid.')
    else:
        print(e)
    return


async def modbusserver(options):
    """Return modbusserver module."""
    config = Config(options.config)
    return ModbusServer(**config)


async def modbusclient(options):
    """Return modbusclient module."""
    config = Config(options.config)
    return ModbusClient(**config)


async def logixclient(options):
    """Return logixclient module."""
    config = Config(options.config)
    return LogixClient(**config)


async def snmpclient(options):
    """Return snmpclient module."""
    config = Config(options.config)
    return SnmpClient(**config)


def add_subparser_defaults(
        parser: argparse._SubParsersAction,
        name: str, call, help: str):
    """Add arguments common to all subparsers."""
    s = parser.add_parser(name, help=help)
    s.set_defaults(get_module=call, module=name)
    s.add_argument('--config', metavar='file', default=None,
                   help=f'Config file, default is "{name}.yaml".')
    s.add_argument('--tags', metavar='file', default=None,
                   help='Tags file, default is "tags.yaml".')
    s.add_argument('--verbose', action='store_true',
                   help="Set level to logging.INFO.")
    return s


def args(_version: str):
    """Read commandline arguments."""
    parser = argparse.ArgumentParser(
        prog='pymscada',
        description='Connect IO, logic, applications, and webpage UI',
        epilog=f'Python Mobile SCADA {_version}'
    )
    subparsers = parser.add_subparsers(title='module')
    for module, func, help in [
        ['bus', bus, 'run the message bus'],
        ['wwwserver', wwwserver, 'serve web pages'],
        ['history', history, 'collect and serve history'],
        ['files', files, 'receive and send files'],
        ['console', console, 'interactive bus console'],
        ['checkout', _checkout, 'create example config files'],
        ['validate', _validate, 'validate config files'],
        ['modbusserver', modbusserver, 'receive modbus messages'],
        ['modbusclient', modbusclient, 'poll/write to modbus devices'],
        ['logixclient', logixclient, 'poll/write to logix devices'],
        ['snmpclient', snmpclient, 'poll snmp oids'],
    ]:
        modparser = add_subparser_defaults(subparsers, module, func, help)
        if module == 'checkout':
            modparser.add_argument(
                '--overwrite', action='store_true', default=False,
                help='checkout may overwrite files, CARE!')
        elif module == 'validate':
            modparser.add_argument(
                '--path', metavar='file',
                help='default is current working directory')
    return parser.parse_args()


async def run():
    """Run bus and wwwserver."""
    _version = version("pymscada")
    logging.warning(f'pymscada {_version} starting')
    options = args(_version)
    if options.verbose:
        logging.basicConfig(level=logging.INFO)
    if options.config is None:
        options.config = f'{options.module}.yaml'
    if options.tags is None:
        options.tags = 'tags.yaml'
    module = await options.get_module(options)
    if module is None:
        return
    await module.start()
    await asyncio.get_event_loop().create_future()
