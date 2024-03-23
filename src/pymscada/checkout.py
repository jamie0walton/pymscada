"""Create base config folder and check out demo files."""
import difflib
from pathlib import Path
import sys
from pymscada.config import get_demo_files, get_pdf_files


PATH = {
    '__PYTHON__': Path(f'{sys.exec_prefix}/bin/python').absolute(),
    '__PYMSCADA__': Path(sys.argv[0]).absolute(),
    '__DIR__': Path('.').absolute()
}
if sys.platform == "win32":
    PATH = {
        '__PYTHON__': Path(f'{sys.exec_prefix}/python.exe').absolute(),
        '__PYMSCADA__': Path(sys.argv[0]).absolute(),
        '__DIR__': Path('.').absolute()
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
        print('making pdf dir')
        pdf_dir.mkdir()
    for pdf_file in get_pdf_files():
        target = pdf_dir.joinpath(pdf_file.name)
        target.write_bytes(pdf_file.read_bytes())


def make_config(overwrite: bool):
    """Make the config folder, if missing, and copy files in."""
    config_dir = PATH['__DIR__'].joinpath('config')
    if not config_dir.exists():
        print('making config dir')
        config_dir.mkdir()
    for config_file in get_demo_files():
        target = config_dir.joinpath(config_file.name)
        rt = 'Creating '
        if target.exists():
            if overwrite:
                rt = 'Replacing '
                target.unlink()
            else:
                continue
        print(f'{rt} {target}')
        if str(target).endswith('service'):
            rd_bytes = config_file.read_bytes()
            for k, v in PATH.items():
                rd_bytes = rd_bytes.replace(k.encode(),
                                            str(v.absolute()).encode())
            target.write_bytes(rd_bytes)
        else:
            target.write_bytes(config_file.read_bytes())


def read_with_subst(file: Path):
    """Read the file and replace DIR markers."""
    rd = file.read_bytes().decode()
    if str(file).endswith('service'):
        for k, v in PATH.items():
            rd = rd.replace(k, str(v.absolute()))
    lines = rd.splitlines()
    return lines


def compare_config():
    """Compare old and new config."""
    config_dir = PATH['__DIR__'].joinpath('config')
    if not config_dir.exists():
        print('No config dir, are you in the right directory')
        return
    for config_file in get_demo_files():
        target = config_dir.joinpath(config_file.name)
        if target.exists():
            new_lines = read_with_subst(config_file)
            old_lines = read_with_subst(target)
            diff = list(difflib.unified_diff(old_lines, new_lines,
                        fromfile=str(target), tofile=str(config_file)))
            if len(diff):
                print('\n'.join(diff), '\n')
        else:
            print(f'\n--- MISSING FILE\n\n+++ {config_file}')


def checkout(overwrite=False, diff=False):
    """Do it."""
    for name in PATH:
        if not PATH[name].exists():
            raise SystemExit(f'{PATH[name]} is missing')
    if diff:
        compare_config()
    else:
        make_history()
        make_pdf()
        make_config(overwrite)
