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
from pymscada.opnotes import OpNotes
from pymscada.www_server import WwwServer
from pymscada.iodrivers.logix_client import LogixClient
from pymscada.iodrivers.modbus_client import ModbusClient
from pymscada.iodrivers.modbus_server import ModbusServer
from pymscada.iodrivers.ping_client import PingClient
from pymscada.iodrivers.snmp_client import SnmpClient
from pymscada.validate import validate


class Module():
    """Default Module."""

    name = None
    help = None
    epilog = None
    module = None
    config = True
    tags = True
    sub = None
    await_future = True

    def __init__(self, subparser: argparse._SubParsersAction):
        """Add arguments common to all subparsers."""
        self.sub = subparser.add_parser(
            self.name, help=self.help, epilog=self.epilog)
        self.sub.set_defaults(app=self)
        if self.config:
            self.sub.add_argument(
                '--config', metavar='file', default=f'{self.name}.yaml',
                help=f"Config file, default is '{self.name}.yaml'")
        if self.tags:
            self.sub.add_argument(
                '--tags', metavar='file', default='tags.yaml',
                help="Tags file, default is 'tags.yaml'")
        self.sub.add_argument('--verbose', action='store_true',
                              help="Set level to logging.INFO")


class _Bus(Module):
    """Bus Server."""

    name = 'bus'
    help = 'run the message bus'
    tags = False

    def run_once(self, options):
        """Create the module."""
        config = Config(options.config)
        self.module = BusServer(**config)


class _WwwServer(Module):
    """WWW Server Module."""

    name = 'wwwserver'
    help = 'serve web pages'

    def run_once(self, options):
        """Create the module."""
        config = Config(options.config)
        tag_info = dict(Config(options.tags))
        self.module = WwwServer(tag_info=tag_info, **config)


class _History(Module):
    """History Module."""

    name = 'history'
    help = 'collect and serve history'

    def run_once(self, options):
        """Create the module."""
        config = Config(options.config)
        tag_info = dict(Config(options.tags))
        self.module = History(tag_info=tag_info, **config)


class _Files(Module):
    """Files Module."""

    name = 'files'
    help = 'receive and send files'
    tags = False

    def run_once(self, options):
        """Create the module."""
        config = Config(options.config)
        self.module = Files(**config)


class _OpNotes(Module):
    """Operator Notes Module."""

    name = 'opnotes'
    help = 'present and manage operator notes'
    tags = False

    def run_once(self, options):
        """Create the module."""
        config = Config(options.config)
        self.module = OpNotes(**config)


class _Console(Module):
    """Bus Module."""

    name = 'console'
    help = 'interactive bus console'
    config = False
    await_future = False

    def __init__(self, subparser: argparse._SubParsersAction):
        super().__init__(subparser)
        self.sub.add_argument(
            '-p', '--port', action='store', type=int, default=1324,
            help='connect to port (default: 1324)')
        self.sub.add_argument(
            '-i', '--ip', action='store', default='localhost',
            help='connect to ip address (default: locahost)')

    def run_once(self, options):
        """Create the module."""
        tag_info = dict(Config(options.tags))
        self.module = Console(options.ip, options.port, tag_info)


class _checkout(Module):
    """Bus Module."""

    name = 'checkout'
    help = 'create example config files'
    epilog = """
        To add to systemd `f="pymscada-bus" && cp config/$f.service
        /lib/systemd/system && systemctl enable $f && systemctl start
        $f`"""
    config = False
    tags = False

    def __init__(self, subparser: argparse._SubParsersAction):
        super().__init__(subparser)
        self.sub.add_argument(
            '--overwrite', action='store_true', default=False,
            help='checkout may overwrite files, CARE!')
        self.sub.add_argument(
            '--diff', action='store_true', default=False,
            help='compare default with existing')

    def run_once(self, options):
        """Create the module."""
        checkout(overwrite=options.overwrite, diff=options.diff)


class _validate(Module):
    """Bus Module."""

    name = 'validate'
    help = 'validate config files'
    config = False
    tags = False

    def __init__(self, subparser: argparse._SubParsersAction):
        super().__init__(subparser)
        self.sub.add_argument(
            '--path', metavar='file',
            help='default is current working directory')

    def run_once(self, options):
        """Create the module."""
        r, e, p = validate(options.path)
        if r:
            print(f'Config files in {p} valid.')
        else:
            print(e)


class _LogixClient(Module):
    """Bus Module."""

    name = 'logixclient'
    help = 'poll/write to logix devices'

    def run_once(self, options):
        """Create the module."""
        config = Config(options.config)
        self.module = LogixClient(**config)


class _ModbusServer(Module):
    """Bus Module."""

    name = 'modbusserver'
    help = 'receive modbus messages'
    epilog = """
        Needs `setcap CAP_NET_BIND_SERVICE=+eip /usr/bin/python3.nn` to
        bind to port 502."""
    tags = False

    def run_once(self, options):
        """Create the module."""
        config = Config(options.config)
        self.module = ModbusServer(**config)


class _ModbusClient(Module):
    """Bus Module."""

    name = 'modbusclient'
    help = 'poll/write to modbus devices'
    tags = False

    def run_once(self, options):
        """Create the module."""
        config = Config(options.config)
        self.module = ModbusClient(**config)


class _PingClient(Module):
    """Bus Module."""

    name = 'ping'
    help = 'ping a list of addresses, return time'
    epilog = """
        Needs `setcap CAP_NET_RAW+ep /usr/bin/python3.nn` to open SOCK_RAW
    """
    tags = False

    def run_once(self, options):
        """Create the module."""
        if sys.platform.startswith("win"):
            asyncio.set_event_loop_policy(
                asyncio.WindowsSelectorEventLoopPolicy())
        config = Config(options.config)
        self.module = PingClient(**config)


class _SnmpClient(Module):
    """Bus Module."""

    name = 'snmpclient'
    help = 'poll snmp oids'
    tags = False

    def run_once(self, options):
        """Create the module."""
        config = Config(options.config)
        self.module = SnmpClient(**config)


def args(_version: str):
    """Read commandline arguments."""
    parser = argparse.ArgumentParser(
        prog='pymscada',
        description='Connect IO, logic, applications, and webpage UI',
        epilog=f'Python Mobile SCADA {_version}'
    )
    s = parser.add_subparsers(title='module')
    _Bus(s)
    _WwwServer(s)
    _History(s)
    _Files(s)
    _OpNotes(s)
    _Console(s)
    _checkout(s)
    _validate(s)
    _LogixClient(s)
    _ModbusServer(s)
    _ModbusClient(s)
    _PingClient(s)
    _SnmpClient(s)
    return parser.parse_args()


async def run():
    """Run bus and wwwserver."""
    _version = version("pymscada")
    logging.warning(f'pymscada {_version} starting')
    options = args(_version)
    if options.verbose:
        logging.getLogger().setLevel(logging.INFO)
    options.app.run_once(options)
    if options.app.module is not None:
        await options.app.module.start()
        if options.app.await_future:
            await asyncio.get_event_loop().create_future()
