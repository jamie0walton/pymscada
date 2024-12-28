"""Create base config folder and check out demo files."""
import difflib
import getpass
from pathlib import Path
import sys
from pymscada.config import get_demo_files, get_pdf_files


class Checkout:
    """Create and manage configuration files."""
    
    def __init__(self, **kwargs):
        """Initialize paths and settings."""
        self.path = {
            '__PYTHON__': Path(f'{sys.exec_prefix}/bin/python').absolute(),
            '__PYMSCADA__': Path(sys.argv[0]).absolute(),
            '__DIR__': Path('.').absolute(),
            '__HOME__': Path.home().absolute(),
            '__USER__': getpass.getuser()
        }
        if sys.platform == "win32":
            self.path['__PYTHON__'] = Path(f'{sys.exec_prefix}/python.exe').absolute()
        
        self.overwrite = kwargs.get('overwrite', False)
        self.diff = kwargs.get('diff', False)

    def make_history(self):
        """Make the history folder if missing."""
        history_dir = self.path['__DIR__'].joinpath('history')
        if not history_dir.exists():
            print("making 'history' folder")
            history_dir.mkdir()

    def make_pdf(self):
        """Make the pdf folder if missing."""
        pdf_dir = self.path['__DIR__'].joinpath('pdf')
        if not pdf_dir.exists():
            print('making pdf dir')
            pdf_dir.mkdir()
        for pdf_file in get_pdf_files():
            target = pdf_dir.joinpath(pdf_file.name)
            target.write_bytes(pdf_file.read_bytes())

    def make_config(self):
        """Make the config folder, if missing, and copy files in."""
        config_dir = self.path['__DIR__'].joinpath('config')
        if not config_dir.exists():
            print('making config dir')
            config_dir.mkdir()
        for config_file in get_demo_files():
            target = config_dir.joinpath(config_file.name)
            rt = 'Creating '
            if target.exists():
                if self.overwrite:
                    rt = 'Replacing '
                    target.unlink()
                else:
                    continue
            print(f'{rt} {target}')
            rd_bytes = config_file.read_bytes()
            if target.name.lower() != 'readme.md':
                for k, v in self.path.items():
                    rd_bytes = rd_bytes.replace(k.encode(), str(v).encode())
            target.write_bytes(rd_bytes)

    def read_with_subst(self, file: Path):
        """Read the file and replace DIR markers."""
        rd = file.read_bytes().decode()
        for k, v in self.path.items():
            rd = rd.replace(k, str(v))
        lines = rd.splitlines()
        return lines

    def compare_config(self):
        """Compare old and new config."""
        config_dir = self.path['__DIR__'].joinpath('config')
        if not config_dir.exists():
            print('No config dir, are you in the right directory')
            return
        for config_file in get_demo_files():
            target = config_dir.joinpath(config_file.name)
            if target.exists():
                new_lines = self.read_with_subst(config_file)
                old_lines = self.read_with_subst(target)
                diff = list(difflib.unified_diff(old_lines, new_lines,
                            fromfile=str(target), tofile=str(config_file)))
                if len(diff):
                    print('\n'.join(diff), '\n')
            else:
                print(f'\n--- MISSING FILE\n\n+++ {config_file}')

    async def start(self):
        """Execute checkout process."""
        for name in ['__PYTHON__', '__PYMSCADA__', '__DIR__', '__HOME__']:
            if not self.path[name].exists():
                raise SystemExit(f'{self.path[name]} is missing')
        
        if self.diff:
            self.compare_config()
        else:
            self.make_history()
            self.make_pdf()
            self.make_config()
