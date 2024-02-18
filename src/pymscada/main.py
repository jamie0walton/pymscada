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


def args():
    """Read commandline arguments."""
    parser = argparse.ArgumentParser(
        prog='pymscada',
        description='Connect IO, logic, applications, and webpage UI',
        epilog='Python Mobile SCADA'
    )
    parser.add_argument('--config', metavar='file',
                        help='Config file, default is "[module].yaml".')
    parser.add_argument('--tags', metavar='file',
                        help='Tags file, default is "tags.yaml".')
    parser.add_argument('--verbose', action='store_true',
                        help="Set level to logging.INFO.")
    sp = parser.add_subparsers(title='module')
    # Add individual module options, most use --config and --tags
    s = sp.add_parser('bus', help='run the message bus')
    s.set_defaults(get_module=bus)
    s = sp.add_parser('wwwserver', help='serve web pages')
    s.set_defaults(get_module=wwwserver)
    s = sp.add_parser('history', help='collect and serve history')
    s.set_defaults(get_module=history)
    s = sp.add_parser('files', help='receive and send files')
    s.set_defaults(get_module=files)
    s = sp.add_parser('console', help='interactive bus console')
    s.set_defaults(get_module=console)
    s = sp.add_parser('checkout', help='create example config files')
    s.set_defaults(get_module=_checkout)
    s.add_argument('--overwrite', action='store_true', default=False,
                   help='checkout may overwrite files, CARE!')
    s = sp.add_parser('validate', help='validate config files')
    s.set_defaults(get_module=_validate)
    s.add_argument('--path', metavar='file',
                   help='default is current working directory')
    s = sp.add_parser('modbusserver', help='receive modbus commands')
    s.set_defaults(get_module=modbusserver)
    s = sp.add_parser('modbusclient', help='poll/write to modbus devices')
    s.set_defaults(get_module=modbusclient)
    s = sp.add_parser('logixclient', help='poll/write to logix devices')
    s.set_defaults(get_module=logixclient)
    s = sp.add_parser('snmpclient', help='poll to snmp oids')
    s.set_defaults(get_module=snmpclient)
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
    module = await options.get_module(options)
    if module is None:
        return
    await module.start()
    await asyncio.get_event_loop().create_future()
