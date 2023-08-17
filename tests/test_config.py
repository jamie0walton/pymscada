"""Test the config reading."""
from pymscada.config import get_file, Config


def test_file():
    """Read bus config."""
    fn = get_file('robots.txt')
    with open(fn, 'r') as fh:
        assert fh.readline().strip() == 'User-agent: *'
        assert fh.readline().strip() == 'Disallow: /'


def test_Config():
    """Read config back as dictionary."""
    cfg = Config('docs/examples/bus.yaml')
    assert cfg['bus_ip'] == '127.0.0.1'
    assert cfg['bus_port'] == 1324
