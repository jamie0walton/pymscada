"""Read config, either from command line argument or from resources."""
import importlib.resources
from importlib.abc import Traversable
from yaml import safe_load_all, YAMLError
import logging
from pymscada import assets


def get_file(filename: str) -> Traversable:
    """Provide file resources to package."""
    fn = importlib.resources.files(assets).joinpath(filename)
    if fn.is_file():
        return fn
    else:
        raise FileNotFoundError(filename)


class Config(dict):
    """Read config from yaml file."""

    def __init__(self, filename: str):
        """Open."""
        with open(filename, 'r') as fh:
            try:
                for data in safe_load_all(fh):
                    for x in data:
                        self[x] = data[x]
            except YAMLError as e:
                logging.error(f'failed to load {filename} {e}')
