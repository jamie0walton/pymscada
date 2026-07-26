"""Create base config folder and check out demo files."""
import difflib
import getpass
from pathlib import Path
import sys
from pymscada.config import get_demo_files


class Checkout:
    """Create and manage configuration files."""
    
    def __init__(self, **kwargs):
        """Initialize paths and settings."""
        exe = '/bin/python' if sys.platform != "win32" else '/python.exe'
        self.path = {
            '__PYTHON__': Path(f"{sys.exec_prefix}{exe}").absolute(),
            '__PYMSCADA__': Path(sys.argv[0]).absolute(),
            '__DIR__': Path('.').absolute(),
            '__PREFIX__': kwargs.get('prefix', 'ms'),
            '__SITE__': kwargs.get('site', ''),
            '__USER__': getpass.getuser(),
            '__ADDRESS__': kwargs.get('address', '127.0.0.1'),
            '__PORT__': kwargs.get('port', '1324')
        }
        if self.path['__SITE__']:
            self.path['__SITE__'] = f" - {self.path['__SITE__']}"
        self.overwrite = kwargs.get('overwrite', False)
        self.diff = kwargs.get('diff', None)
        self.paths = kwargs.get('paths', False)

    def make_history(self):
        """Make the history folder if missing."""
        history_dir = self.path['__DIR__'].joinpath('history')
        if not history_dir.exists():
            print(f"make dir {history_dir}")
            history_dir.mkdir()

    def make_log(self):
        """Make the log folder if missing."""
        log_dir = self.path['__DIR__'].joinpath('log')
        if not log_dir.exists():
            print(f"make dir {log_dir}")
            log_dir.mkdir()

    def read_with_subst(self, file: Path):
        """Read the file and replace DIR markers."""
        rd = file.read_bytes().decode()
        for k, v in self.path.items():
            rd = rd.replace(k, str(v))
        lines = rd.splitlines()
        return lines

    def make_config(self):
        """Make the config folder, if missing, and copy files in."""
        config_dir = self.path['__DIR__']
        for file in get_demo_files():
            demo_idx = file.parts.index('demo')
            dir_under_demo = Path(*file.parts[demo_idx + 1:-1])
            target_dir = config_dir / dir_under_demo
            target = target_dir / file.name
            if not target_dir.exists():
                print(f"make dir {target_dir}")
                target_dir.mkdir()
            delete = False
            if target.exists():
                if self.overwrite:
                    delete = True
                    target.unlink()
                else:
                    print(f"skip {target}")
                    continue
            new_lines = self.read_with_subst(file)
            if delete:
                print(f"replace {target}")
            else:
                print(f"new {target}")
            with target.open('w', encoding='utf-8') as fh:
                fh.write('\n'.join(new_lines))

    def compare_config(self):
        """Compare old and new config."""
        config_dir = self.path['__DIR__']
        for file in get_demo_files():
            if self.diff and self.diff not in str(file):
                continue
            demo_idx = file.parts.index('demo')
            dir_under_demo = Path(*file.parts[demo_idx + 1:-1])
            target_dir = config_dir / dir_under_demo
            target = target_dir / file.name
            if target.exists():
                new_lines = self.read_with_subst(file)
                old_lines = self.read_with_subst(target)
                diff = list(difflib.unified_diff(old_lines, new_lines,
                            fromfile=str(target), tofile=str(file)))
                if len(diff):
                    print('\n', '\n'.join(diff))
            else:
                print(f"\n+++ MISSING FILE {target}")

    async def start(self):
        """Execute checkout process."""
        for name in ['__PYTHON__', '__PYMSCADA__', '__DIR__']:
            if not self.path[name].exists():
                raise SystemExit(f'{self.path[name]} is missing')
        config_marker = self.path['__DIR__'].joinpath('pymscada.md')
        if not config_marker.exists():
            raise SystemExit(f"No {config_marker} aborting")
        if self.diff is not None:
            self.compare_config()
        elif self.paths:
            print('\n'.join([f'{k} = {v}' for k, v in self.path.items()]))
        else:
            self.make_history()
            self.make_log()
            self.make_config()
