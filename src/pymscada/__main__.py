"""Provides `python -m pymscada` and `pymscada.exe`."""
import asyncio
from pymscada.main import run


def cmd_line():
    """Run from commandline."""
    asyncio.run(run())


if __name__ == '__main__':
    """Starts with creating an event loop."""
    asyncio.run(run())
