"""Read config, either from command line argument or from resources."""
import importlib.resources
import logging
import os
import re
from pathlib import Path
from yaml import safe_load_all, YAMLError
from pymscada import demo


def get_demo_files():
    """Provide an iterable of the config files."""

    def walk(resource):
        for child in resource.iterdir():
            if child.is_dir() and child.name != '__pycache__':
                yield from walk(child)
            elif child.is_file() and child.name != '__init__.py':
                yield child

    yield from walk(importlib.resources.files(demo))


def _expand_env_vars(value):
    """Recursively expand environment variables in config values."""
    if isinstance(value, str):
        pattern = re.compile(r'\$\{([^}]+)\}')
        def replace_env(match):
            env_var = match.group(1)
            return os.environ.get(env_var, match.group(0))
        return pattern.sub(replace_env, value)
    elif isinstance(value, dict):
        return {k: _expand_env_vars(v) for k, v in value.items()}
    elif isinstance(value, list):
        return [_expand_env_vars(item) for item in value]
    return value


class Config(dict):
    """Read config from yaml file."""

    def __init__(self, filename: str):
        """Open."""
        fp = Path(filename)
        if fp.exists():
            logging.info(f'using config file {fp}')
        else:
            raise SystemExit(f'file not found: {fp}')
        with fp.open(encoding='utf-8') as fh:
            try:
                for data in safe_load_all(fh):
                    if '__vars__' in data:
                        del data['__vars__']
                    for x in data:
                        self[x] = _expand_env_vars(data[x])
            except YAMLError as e:
                raise SystemExit(f'failed to load {filename} {e}')
