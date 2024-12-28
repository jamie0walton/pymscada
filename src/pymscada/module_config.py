"""Module configuration and factory system."""
from typing import Any, Optional, Type
import argparse
from textwrap import dedent
from importlib.metadata import version
import logging
from pymscada.config import Config
from pymscada.console import Console

class ModuleArgument:
    def __init__(self, args: tuple[str, ...], kwargs: dict[str, Any]):
        self.args = args
        self.kwargs = kwargs

class ModuleDefinition:
    """Defines a module's configuration and behavior."""
    def __init__(self, name: str, help: str, module_class: Type[Any], *,
                 config: bool = True, tags: bool = True,
                 epilog: Optional[str] = None,
                 extra_args: list[ModuleArgument] = None,
                 await_future: bool = True):
        self.name = name
        self.help = help
        self.module_class = module_class
        self.config = config
        self.tags = tags
        self.epilog = epilog
        self.extra_args = extra_args
        self.await_future = await_future

def create_module_registry():
    """Create the central module registry with lazy imports."""
    return [
        ModuleDefinition(
            name='bus',
            help='run the message bus',
            module_class='pymscada.bus_server:BusServer',
            tags=False
        ),
        ModuleDefinition(
            name='wwwserver',
            help='serve web pages',
            module_class='pymscada.www_server:WwwServer'
        ),
        ModuleDefinition(
            name='history',
            help='save tag changes to database',
            module_class='pymscada.history:History'
        ),
        ModuleDefinition(
            name='files',
            help='serve files',
            module_class='pymscada.files:Files',
            tags=False
        ),
        ModuleDefinition(
            name='opnotes',
            help='operator notes',
            module_class='pymscada.opnotes:OpNotes',
            tags=False
        ),
        ModuleDefinition(
            name='validate',
            help='validate config files',
            module_class='pymscada.validate:validate',
            config=False,
            tags=False,
            extra_args=[
                ModuleArgument(
                    ('--path',),
                    {'metavar': 'file', 'help': 'default is current working directory'}
                )
            ]
        ),
        ModuleDefinition(
            name='checkout',
            help='create example config files',
            module_class='pymscada.checkout:Checkout',
            config=False,
            tags=False,
            await_future=False,
            epilog=dedent("""
                To add to systemd:
                  su -
                  cd /lib/systemd/system
                  cp config/pymscada-bus.service .
                  systemctl enable pymscada-bus
                  systemctl start pymscada-bus"""),
            extra_args=[
                ModuleArgument(
                    ('--overwrite',),
                    {'action': 'store_true', 'default': False,
                     'help': 'checkout may overwrite files, CARE!'}
                ),
                ModuleArgument(
                    ('--diff',),
                    {'action': 'store_true', 'default': False,
                     'help': 'compare default with existing'}
                )
            ]
        ),
        ModuleDefinition(
            name='accuweatherclient',
            help='poll weather information',
            module_class='pymscada.iodrivers.accuweather:AccuWeatherClient',
            tags=False
        ),
        ModuleDefinition(
            name='logixclient',
            help='poll/write to logix devices',
            module_class='pymscada.iodrivers.logix_client:LogixClient',
            tags=False
        ),
        ModuleDefinition(
            name='modbusclient',
            help='poll/write modbus devices',
            module_class='pymscada.iodrivers.modbus_client:ModbusClient',
            tags=False
        ),
        ModuleDefinition(
            name='modbusserver',
            help='serve modbus devices',
            module_class='pymscada.iodrivers.modbus_server:ModbusServer',
            tags=False
        ),
        ModuleDefinition(
            name='openweatherclient',
            help='poll OpenWeather current and forecast data',
            module_class='pymscada.iodrivers.openweather:OpenWeatherClient',
            tags=False,
            epilog=dedent("""
                OPENWEATHERMAP_API_KEY can be set in the openweathermap.yaml
                or as an environment variable:
                  vi ~/.bashrc
                  export OPENWEATHERMAP_API_KEY='1234567890'""")
        ),
        ModuleDefinition(
            name='pingclient',
            help='ping network devices',
            module_class='pymscada.iodrivers.ping_client:PingClient',
            tags=False
        ),
        ModuleDefinition(
            name='snmpclient',
            help='poll SNMP devices',
            module_class='pymscada.iodrivers.snmp_client:SnmpClient',
            tags=False
        ),
        ModuleDefinition(
            name='console',
            help='interactive bus console',
            module_class='pymscada.console:Console',
            config=False,
            await_future=False,
            epilog=dedent("""
                --tags tag.yaml is not strictly necessary, unless you'd
                like to see correctly typed values and set values."""),
            extra_args=[
                ModuleArgument(
                    ('-p', '--bus-port'),
                    {'action': 'store', 'type': int, 'default': 1324,
                     'help': 'connect to port (default: 1324)'}
                ),
                ModuleArgument(
                    ('-i', '--bus-ip'),
                    {'action': 'store', 'default': 'localhost',
                     'help': 'connect to ip address (default: localhost)'}
                )
            ]
        ),
    ]

class ModuleFactory:
    """Creates and manages module instances."""
    
    def __init__(self):
        self.modules = {m.name: m for m in create_module_registry()}
        
    def add_module_parser(self, subparser: argparse._SubParsersAction, 
                         module_def: ModuleDefinition) -> argparse.ArgumentParser:
        """Add a parser for a module with its arguments."""
        parser = subparser.add_parser(
            module_def.name,
            help=module_def.help,
            epilog=module_def.epilog,
            formatter_class=argparse.RawDescriptionHelpFormatter
        )
        if module_def.config:
            parser.add_argument(
                '--config',
                metavar='file',
                default=f'{module_def.name}.yaml',
                help=f"Config file, default is '{module_def.name}.yaml'"
            )
        if module_def.tags:
            parser.add_argument(
                '--tags',
                metavar='file',
                default='tags.yaml',
                help="Tags file, default is 'tags.yaml'"
            )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help="Set level to logging.INFO"
        )
        if module_def.extra_args:
            for arg in module_def.extra_args:
                parser.add_argument(*arg.args, **arg.kwargs)
        return parser

    def create_module(self, options: argparse.Namespace):
        """Create a module instance based on configuration and options."""
        if options.module_name not in self.modules:
            raise ValueError(f'{options.module_name} does not exist')
        module_def = self.modules[options.module_name]
        logging.info(f'Python Mobile SCADA {version("pymscada")} '
                     f'starting {module_def.name}')
        # Import the module class only when needed
        if isinstance(module_def.module_class, str):
            module_path, class_name = module_def.module_class.split(':')
            module = __import__(module_path, fromlist=[class_name])
            actual_class = getattr(module, class_name)
        else:
            actual_class = module_def.module_class
        kwargs = {}
        if module_def.config:
            kwargs.update(Config(options.config))
        if module_def.tags:
            kwargs['tag_info'] = dict(Config(options.tags))
        if module_def.extra_args:
            for arg in module_def.extra_args:
                arg_name = arg.args[-1].lstrip('-').replace('-', '_')
                if hasattr(options, arg_name):
                    kwargs[arg_name] = getattr(options, arg_name)
        return actual_class(**kwargs)
