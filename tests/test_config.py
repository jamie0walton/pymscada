"""Test the config reading."""
from pymscada.config import get_html_file, Config


def test_html_file():
    """Read bus config."""
    fn = get_html_file('robots.txt')
    with open(fn, 'r') as fh:
        assert fh.readline().strip() == 'User-agent: *'
        assert fh.readline().strip() == 'Disallow: /'


def test_Config():
    """Read config back as dictionary."""
    cfg = Config('bus.yaml')
    assert cfg['ip'] == '127.0.0.1'
    assert cfg['port'] == 1324
