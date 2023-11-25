"""Create base config folder and check out demo files."""
from pathlib import Path
import sys
from pymscada.config import get_demo_files, get_pdf_files


PATH = {
    '__DIR__': Path('.'),
    '__EXE__': Path(f'{sys.exec_prefix}/bin/pymscada'),
    '__PYTHON__': Path(f'{sys.exec_prefix}/bin/python')
}
if sys.platform == "win32":
    PATH = {
        '__DIR__': Path('.'),
        '__EXE__': Path(f'{sys.exec_prefix}/Scripts/pymscada'),
        '__PYTHON__': Path(f'{sys.exec_prefix}/Scripts/python')
    }


def make_history():
    """Make the history folder if missing."""
    history_dir = PATH['__DIR__'].joinpath('history')
    if not history_dir.exists():
        print("making 'history' folder")
        history_dir.mkdir()


def make_pdf():
    """Make the pdf folder if missing."""
    pdf_dir = PATH['__DIR__'].joinpath('pdf')
    if not pdf_dir.exists():
        print('making pdf')
        pdf_dir.mkdir()
    for pdf_file in get_pdf_files():
        target = pdf_dir.joinpath(pdf_file.name)
        target.write_bytes(pdf_file.read_bytes())


def make_config(overwrite):
    """Make the config folder, if missing, and copy files in."""
    config_dir = PATH['__DIR__'].joinpath('config')
    if not config_dir.exists():
        print('making config')
        config_dir.mkdir()
    for config_file in get_demo_files():
        target = config_dir.joinpath(config_file.name)
        if target.exists():
            if overwrite:
                print(f'removing old {target}')
                target.unlink()
            else:
                # print(f'keeping current {target}')
                continue
        if str(target).endswith('service'):
            rd_bytes = config_file.read_bytes()
            for k, v in PATH.items():
                rd_bytes = rd_bytes.replace(k.encode(),
                                            str(v.absolute()).encode())
            print(f"creating new {target}")
            target.write_bytes(rd_bytes)
        else:
            print(f"creating new {target}")
            target.write_bytes(config_file.read_bytes())


def checkout(overwrite=False):
    """Do it."""
    for name in PATH:
        if not PATH[name].exists():
            raise SystemExit(f'{PATH[name]} is missing')
    make_history()
    make_pdf()
    make_config(overwrite)
