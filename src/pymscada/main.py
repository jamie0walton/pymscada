"""Main server entry point."""
import argparse
import asyncio
import logging
import sys
from importlib.metadata import version
from pymscada.module_config import ModuleFactory


def args():
    """Read commandline arguments."""
    parser = argparse.ArgumentParser(
        prog='pymscada',
        description='Connect IO, logic, applications, and webpage UI',
        epilog=f'Python Mobile SCADA {version("pymscada")}'
    )
    factory = ModuleFactory()
    subparsers = parser.add_subparsers(title='module', dest='module_name')
    for _, module_def in factory.modules.items():
        factory.add_module_parser(subparsers, module_def)
    return parser.parse_args()


async def run():
    """Run the selected module."""
    options = args()
    if not options.module_name:
        print("Error: Please specify a module to run")
        sys.exit(1)
    root_logger = logging.getLogger()
    handler = logging.StreamHandler()
    formatter = logging.Formatter('%(levelname)s:pymscada: %(message)s')
    handler.setFormatter(formatter)
    root_logger.handlers.clear()  # Remove any existing handlers
    root_logger.addHandler(handler)
    root_logger.setLevel(logging.INFO)
    logging.info(f'Python Mobile SCADA {version("pymscada")} starting '
                 f'{options.module_name}')
    if not options.verbose:
        root_logger.setLevel(logging.WARNING)
    factory = ModuleFactory()
    module = factory.create_module(options.module_name, options)
    if module is not None:
        if hasattr(module, 'start'):
            await module.start()
        if options.module_name in factory.modules:
            module_def = factory.modules[options.module_name]
            if module_def.await_future:
                await asyncio.get_event_loop().create_future()


def main():
    """Entry point."""
    asyncio.run(run())

if __name__ == '__main__':
    main()
