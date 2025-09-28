"""Test the config reading."""
import pytest
from textwrap import dedent
from pathlib import Path
from pymscada.config import Config, get_demo_file, get_demo_files, \
    get_pdf_files


def test_Config():
    """Read config back as dictionary."""
    cfg = Config('bus.yaml')  # fails over to demo
    assert cfg['ip'] == '127.0.0.1'
    assert cfg['port'] == 1324
    with pytest.raises(SystemExit):
        Config('no such config')


def test_variables():
    """Check variable interpolation."""
    s = dedent("""
        __vars__:
        - &BEN2201_color darkblue
        - &SPOT_color lime
        ip: '192.168.1.100'
        port: 8080
        BEN: *BEN2201_color
        SPOT: *SPOT_color
    """)
    fn = Path('tests/test_assets/config_temp.yaml')
    with open(fn, 'w') as fh:
        fh.write(s)
    cfg = Config(fn)
    assert '__vars__' not in cfg
    assert cfg['ip'] == '192.168.1.100'
    assert cfg['port'] == 8080
    assert cfg['BEN'] == 'darkblue'
    assert cfg['SPOT'] == 'lime'
    fn.unlink()


def test_demo():
    """Read demo files."""
    get_demo_file('tags.yaml')
    with pytest.raises(FileNotFoundError):
        get_demo_file('not here')
    for fh in get_demo_files():
        pass


def test_pdf():
    """Read pdf files."""
    for fh in get_pdf_files():
        assert fh.suffix == '.pdf'
