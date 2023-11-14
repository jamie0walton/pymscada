"""Create base config folder and check out demo files."""
import logging
from pathlib import Path
import sys
from pymscada.config import get_demo_files, get_pdf_files


def make_history(path):
    """Make the history folder if missing."""
    history_dir = path.joinpath('history')
    if not history_dir.exists():
        logging.info('making history folder')
        history_dir.mkdir()


def make_pdf(path):
    """Make the pdf folder if missing."""
    pdf_dir = path.joinpath('pdf')
    if not pdf_dir.exists():
        logging.info('making pdf folder')
        pdf_dir.mkdir()
    for pdf_file in get_pdf_files():
        target = pdf_dir.joinpath(pdf_file.name)
        target.write_bytes(pdf_file.read_bytes())


def make_config(path, overwrite):
    """Make the config folder, if missing, and copy files in."""
    config_dir = path.joinpath('config')
    if not config_dir.exists():
        logging.info('making config folder')
        config_dir.mkdir()
    for config_file in get_demo_files():
        target = config_dir.joinpath(config_file.name)
        if target.exists():
            if overwrite:
                logging.warn(f'overwriting {target}')
            else:
                logging.info(f'not overwriting {target}')
                continue
        if str(target).endswith('service'):
            target.write_bytes(
                config_file.read_bytes().replace(
                    b'__DIR__', bytes(path.absolute())).replace(
                    b'__EXE__', bytes(exec.absolute())))
        else:
            target.write_bytes(config_file.read_bytes())


def checkout(overwrite=False):
    """Do it."""
    exec = Path(f'{sys.exec_prefix}/bin/pymscada')
    if not exec.is_file():
        raise SystemExit(f'cannot find executable {exec}')
    path = Path()
    make_history(path)
    make_pdf(path)
    make_config(path, overwrite)
