import sys
from importlib.metadata import version
import logging
# from pymscada_milp import matrix


def run():
    """Run a MILP solve."""
    _version = version('pymscada-milp')
    logging.warning(f'pymscada-milp {_version} starting')
    print(f'hi {sys.argv}')
