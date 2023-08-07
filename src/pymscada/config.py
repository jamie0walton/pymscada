"""Read config, either from command line argument or from resources."""
import importlib.resources
from importlib.abc import Traversable
from yaml import safe_load_all, YAMLError
import logging
from . import assets


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
        self._writeable = True
        with open(filename, 'r') as fh:
            try:
                for data in safe_load_all(fh):
                    for x in data:
                        self[x] = data[x]
            except YAMLError as e:
                logging.error(f'failed to load {filename} {e}')
        self._writeable = False

    def __setitem__(self, k, v) -> None:
        """Allow the dictionary to be frozen."""
        if self._writeable:
            return super().__setitem__(k, v)
        else:
            raise RuntimeError(f"Writing Config['{k}'] not permitted")
