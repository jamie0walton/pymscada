"""Test the config reading."""
import pytest
import tempfile
from textwrap import dedent
from pymscada.config import Config, get_demo_files


def test_Config():
    """Read config back as dictionary."""
    cfg = Config('src/pymscada/demo/yaml/bus.yaml')
    assert cfg['ip'] == '__ADDRESS__'  # demo file values
    assert cfg['port'] == '__PORT__'
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
    with tempfile.NamedTemporaryFile('w', suffix='.yaml') as fh:
        fh.write(s)
        fh.flush()
        cfg = Config(fh.name)
    assert '__vars__' not in cfg
    assert cfg['ip'] == '192.168.1.100'
    assert cfg['port'] == 8080
    assert cfg['BEN'] == 'darkblue'
    assert cfg['SPOT'] == 'lime'