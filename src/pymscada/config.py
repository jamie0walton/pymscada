"""Read config, either from command line argument or from resources."""
import importlib.resources
from importlib.abc import Traversable
import logging
from pathlib import Path
from yaml import safe_load_all, YAMLError
from pymscada import demo, pdf


def get_demo_file(filename: str) -> Traversable:
    """Provide file resources to package."""
    fn = importlib.resources.files(demo).joinpath(filename)
    if fn.is_file():
        return fn
    else:
        raise FileNotFoundError(filename)


def get_demo_files():
    """Provide an iterable of the demo files."""
    return importlib.resources.files(demo).iterdir()


def get_pdf_files():
    """Provide an iterable of the demo files."""
    return importlib.resources.files(pdf).iterdir()


class Config(dict):
    """Read config from yaml file."""

    def __init__(self, filename: str):
        """Open."""
        fp = Path(filename)
        if fp.exists():
            logging.info(f'using config file {fp}')
        else:
            try:
                fp = get_demo_file(filename)
                logging.warning(f'using demo config file {fp}')
            except FileNotFoundError:
                raise SystemExit(f'config {filename} missing')
        with open(fp, 'r') as fh:
            try:
                for data in safe_load_all(fh):
                    for x in data:
                        self[x] = data[x]
            except YAMLError as e:
                raise SystemExit(f'failed to load {filename} {e}')
