"""Main server entry point."""
import argparse
import asyncio
from importlib.metadata import version
import logging
import sys
from pymscada.bus_server import BusServer
from pymscada.checkout import checkout
from pymscada.config import Config
from pymscada.console import Console
from pymscada.files import Files
from pymscada.history import History
from pymscada.iodrivers.logix_client import LogixClient
from pymscada.iodrivers.modbus_client import ModbusClient
from pymscada.iodrivers.modbus_server import ModbusServer
from pymscada.iodrivers.ping_client import PingClient
from pymscada.iodrivers.snmp_client import SnmpClient
from pymscada.www_server import WwwServer
from pymscada.validate import validate


MODULES = {}


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
    checkout(overwrite=options.overwrite, diff=options.diff)
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


async def ping(options):
    """Return logixclient module."""
    if sys.platform.startswith("win"):
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    config = Config(options.config)
    return PingClient(**config)


async def snmpclient(options):
    """Return snmpclient module."""
    config = Config(options.config)
    return SnmpClient(**config)


def add_subparser_defaults(
        parser: argparse._SubParsersAction,
        name: str, call, help: str, epilog: str):
    """Add arguments common to all subparsers."""
    s = parser.add_parser(name, help=help, epilog=epilog)
    s.set_defaults(get_module=call, module=name)
    s.add_argument('--config', metavar='file', default=None,
                   help=f"Config file, default is '{name}.yaml'")
    s.add_argument('--tags', metavar='file', default=None,
                   help="Tags file, default is 'tags.yaml'")
    s.add_argument('--verbose', action='store_true',
                   help="Set level to logging.INFO")
    return s


def args(_version: str):
    """Read commandline arguments."""
    parser = argparse.ArgumentParser(
        prog='pymscada',
        description='Connect IO, logic, applications, and webpage UI',
        epilog=f'Python Mobile SCADA {_version}'
    )
    subparsers = parser.add_subparsers(title='module')
    for module, func, help, epilog in [
        ['bus', bus, 'run the message bus', None],
        ['wwwserver', wwwserver, 'serve web pages', None],
        ['history', history, 'collect and serve history', None],
        ['files', files, 'receive and send files', None],
        ['console', console, 'interactive bus console', None],
        ['checkout', _checkout, 'create example config files', """
            To add to systemd `f="pymscada-bus" && cp config/$f.service
            /lib/systemd/system && systemctl enable $f && systemctl start
            $f`"""],
        ['validate', _validate, 'validate config files', None],
        ['modbusserver', modbusserver, 'receive modbus messages', """
            Needs `setcap CAP_NET_BIND_SERVICE=+eip /usr/bin/python3.nn` to
            bind to port 502"""],
        ['modbusclient', modbusclient, 'poll/write to modbus devices', None],
        ['ping', ping, 'ping a list of addresses, return time', """
            Needs `setcap CAP_NET_RAW+ep /usr/bin/python3.nn` to open SOCK_RAW
            """],
        ['logixclient', logixclient, 'poll/write to logix devices', None],
        ['snmpclient', snmpclient, 'poll snmp oids', None],
    ]:
        modparser = add_subparser_defaults(subparsers, module, func, help,
                                           epilog)
        if module == 'checkout':
            modparser.add_argument(
                '--overwrite', action='store_true', default=False,
                help='checkout may overwrite files, CARE!')
            modparser.add_argument(
                '--diff', action='store_true', default=False,
                help='compare default with existing')
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
